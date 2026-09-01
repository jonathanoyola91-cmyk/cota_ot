import mimetypes
from pathlib import Path

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AdjuntoMensaje, Conversacion, Mensaje


MAX_ADJUNTO_BYTES = 15 * 1024 * 1024  # 15 MB

EXTENSIONES_PERMITIDAS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
}


def _nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.username


def _descripcion_ultimo_mensaje(mensaje):
    if not mensaje:
        return "Sin mensajes todavía"

    if mensaje.texto:
        return mensaje.texto

    adjunto = mensaje.adjuntos.first()
    if adjunto:
        return f"📎 {adjunto.nombre_original}"

    return "Mensaje"



def _lista_conversaciones_usuario(usuario):
    """
    Construye la lista lateral reutilizable para bandeja y conversación.
    Mantiene privados, grupos, PAW y OT en un solo lugar.
    """
    conversaciones = (
        Conversacion.objects
        .filter(
            participantes=usuario,
            activa=True,
        )
        .prefetch_related(
            "participantes",
            "mensajes__autor",
            "mensajes__lecturas",
            "mensajes__adjuntos",
        )
        .distinct()
        .order_by("-actualizado_en")
    )

    lista = []

    for conv in conversaciones:
        ultimo_mensaje = (
            conv.mensajes
            .filter(eliminado=False)
            .order_by("-creado_en")
            .first()
        )

        no_leidos = (
            conv.mensajes
            .filter(eliminado=False)
            .exclude(autor=usuario)
            .exclude(lecturas__usuario=usuario)
            .distinct()
            .count()
        )

        participantes = list(conv.participantes.all())

        if conv.tipo == "PRIVADA":
            otro_usuario = next(
                (
                    item
                    for item in participantes
                    if item.id != usuario.id
                ),
                None,
            )

            if not otro_usuario:
                continue

            nombre = _nombre_usuario(otro_usuario)
            avatar = otro_usuario.username[:1].upper() or "U"
            subtitulo = f"@{otro_usuario.username}"
            buscar = f"{nombre} {otro_usuario.username}".lower()

        else:
            otro_usuario = None

            if conv.tipo == "PAW":
                nombre = conv.nombre.strip() or f"Chat PAW {conv.id}"
                avatar = "📋"
            elif conv.tipo == "OT":
                nombre = conv.nombre.strip() or f"Chat OT {conv.id}"
                avatar = "🛠️"
            else:
                nombre = conv.nombre.strip() or f"Grupo {conv.id}"
                avatar = "👥"

            cantidad = len(participantes)
            subtitulo = (
                f"{conv.get_tipo_display()} · "
                f"{cantidad} participante{'s' if cantidad != 1 else ''}"
            )
            buscar = (
                nombre
                + " "
                + " ".join(
                    _nombre_usuario(item)
                    for item in participantes
                )
            ).lower()

        lista.append({
            "conversacion": conv,
            "usuario": otro_usuario,
            "nombre": nombre,
            "avatar": avatar,
            "subtitulo": subtitulo,
            "buscar": buscar,
            "es_grupo": conv.tipo == "GRUPO",
            "es_paw": conv.tipo == "PAW",
            "es_ot": conv.tipo == "OT",
            "es_multipersonal": conv.tipo != "PRIVADA",
            "ultimo_mensaje": ultimo_mensaje,
            "ultimo_texto": _descripcion_ultimo_mensaje(ultimo_mensaje),
            "no_leidos": no_leidos,
        })

    return lista


@login_required
def bandeja(request):
    usuarios = (
        User.objects
        .exclude(id=request.user.id)
        .filter(is_active=True)
        .order_by("first_name", "last_name", "username")
    )

    return render(
        request,
        "internal_chat/bandeja.html",
        {
            "usuarios": usuarios,
            "lista_conversaciones": _lista_conversaciones_usuario(request.user),
        }
    )


@login_required
def abrir_chat_privado(request, user_id):
    otro_usuario = get_object_or_404(
        User,
        id=user_id,
        is_active=True,
    )

    if otro_usuario.id == request.user.id:
        return redirect("internal_chat:bandeja")

    conversaciones = (
        Conversacion.objects
        .filter(
            tipo="PRIVADA",
            participantes=request.user,
            activa=True,
        )
        .filter(participantes=otro_usuario)
        .distinct()
    )

    conversacion = None

    for candidata in conversaciones:
        if candidata.participantes.count() == 2:
            conversacion = candidata
            break

    if conversacion is None:
        conversacion = Conversacion.objects.create(
            tipo="PRIVADA"
        )
        conversacion.participantes.add(
            request.user,
            otro_usuario,
        )

    return redirect(
        "internal_chat:conversacion",
        conversacion_id=conversacion.id,
    )


@login_required
@require_POST
def crear_grupo(request):
    nombre = (request.POST.get("nombre_grupo") or "").strip()
    participantes_ids = request.POST.getlist("participantes")

    if not nombre:
        messages.error(
            request,
            "Escribe un nombre para el grupo."
        )
        return redirect("internal_chat:bandeja")

    if len(nombre) > 200:
        messages.error(
            request,
            "El nombre del grupo no puede superar 200 caracteres."
        )
        return redirect("internal_chat:bandeja")

    ids_limpios = set()

    for valor in participantes_ids:
        try:
            usuario_id = int(valor)
        except (TypeError, ValueError):
            continue

        if usuario_id != request.user.id:
            ids_limpios.add(usuario_id)

    participantes = list(
        User.objects.filter(
            id__in=ids_limpios,
            is_active=True,
        )
    )

    # Grupo = creador + mínimo 2 personas adicionales.
    if len(participantes) < 2:
        messages.error(
            request,
            "Selecciona al menos 2 usuarios para crear un grupo."
        )
        return redirect("internal_chat:bandeja")

    with transaction.atomic():
        conversacion = Conversacion.objects.create(
            tipo="GRUPO",
            nombre=nombre,
        )

        conversacion.participantes.add(
            request.user,
            *participantes,
        )

    messages.success(
        request,
        f"Grupo «{nombre}» creado correctamente."
    )

    return redirect(
        "internal_chat:conversacion",
        conversacion_id=conversacion.id,
    )


@login_required
def conversacion(request, conversacion_id):
    conversacion = get_object_or_404(
        Conversacion.objects.prefetch_related("participantes"),
        id=conversacion_id,
        activa=True,
        participantes=request.user,
    )

    mensajes_chat = (
        conversacion.mensajes
        .filter(eliminado=False)
        .select_related("autor")
        .prefetch_related(
            "lecturas",
            "adjuntos",
        )
        .order_by("creado_en")
    )

    otros = conversacion.participantes.exclude(
        id=request.user.id
    )

    total_participantes = conversacion.participantes.count()
    total_destinatarios = max(total_participantes - 1, 1)

    contexto = {
        "conversacion": conversacion,
        "mensajes": mensajes_chat,
        "otros": otros,
        "total_participantes": total_participantes,
        "total_destinatarios": total_destinatarios,
        "es_grupo": conversacion.tipo == "GRUPO",
        "es_paw": conversacion.tipo == "PAW",
        "es_multipersonal": conversacion.tipo != "PRIVADA",
        "lista_conversaciones": _lista_conversaciones_usuario(request.user),
    }

    if request.GET.get("partial") == "1":
        return render(
            request,
            "internal_chat/conversacion_panel.html",
            contexto,
        )

    return render(
        request,
        "internal_chat/conversacion.html",
        contexto,
    )


def _total_no_leidos(usuario_id):
    return (
        Mensaje.objects
        .filter(
            conversacion__participantes__id=usuario_id,
            conversacion__activa=True,
            eliminado=False,
        )
        .exclude(autor_id=usuario_id)
        .exclude(lecturas__usuario_id=usuario_id)
        .distinct()
        .count()
    )


@login_required
@require_POST
def subir_adjunto(request, conversacion_id):
    conversacion = get_object_or_404(
        Conversacion,
        id=conversacion_id,
        activa=True,
        participantes=request.user,
    )

    archivo = request.FILES.get("archivo")

    if not archivo:
        return JsonResponse(
            {
                "ok": False,
                "error": "No se recibió ningún archivo.",
            },
            status=400,
        )

    if archivo.size <= 0:
        return JsonResponse(
            {
                "ok": False,
                "error": "El archivo está vacío.",
            },
            status=400,
        )

    if archivo.size > MAX_ADJUNTO_BYTES:
        return JsonResponse(
            {
                "ok": False,
                "error": "El archivo supera el límite de 15 MB.",
            },
            status=400,
        )

    extension = Path(archivo.name).suffix.lower()

    if extension not in EXTENSIONES_PERMITIDAS:
        return JsonResponse(
            {
                "ok": False,
                "error": (
                    "Tipo de archivo no permitido. "
                    "Puedes enviar imágenes, PDF, Word, Excel, CSV o TXT."
                ),
            },
            status=400,
        )

    tipo_mime = (
        getattr(archivo, "content_type", "")
        or mimetypes.guess_type(archivo.name)[0]
        or "application/octet-stream"
    )

    try:
        with transaction.atomic():
            mensaje = Mensaje.objects.create(
                conversacion=conversacion,
                autor=request.user,
                texto="",
            )

            adjunto = AdjuntoMensaje.objects.create(
                mensaje=mensaje,
                archivo=archivo,
                nombre_original=archivo.name[:255],
                tipo_mime=tipo_mime[:150],
                tamano=archivo.size,
            )

            conversacion.save(
                update_fields=["actualizado_en"]
            )

    except Exception:
        return JsonResponse(
            {
                "ok": False,
                "error": "No fue posible guardar el archivo.",
            },
            status=500,
        )

    nombre_autor = _nombre_usuario(request.user)

    url_segura = reverse(
        "internal_chat:ver_adjunto",
        args=[adjunto.id],
    )

    total_destinatarios = max(
        conversacion.participantes.count() - 1,
        1,
    )

    payload = {
        "mensaje_id": mensaje.id,
        "autor": nombre_autor,
        "autor_id": request.user.id,
        "creado_en": timezone.localtime(
            mensaje.creado_en
        ).strftime("%H:%M"),
        "adjunto_id": adjunto.id,
        "nombre": adjunto.nombre_original,
        "tipo_mime": adjunto.tipo_mime,
        "tamano": adjunto.tamano,
        "es_imagen": adjunto.es_imagen,
        "url": url_segura,
        "tipo_conversacion": conversacion.tipo,
        "leidos": 0,
        "total_destinatarios": total_destinatarios,
    }

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f"chat_{conversacion.id}",
        {
            "type": "chat_attachment",
            **payload,
        }
    )

    destinatarios = list(
        conversacion.participantes
        .exclude(id=request.user.id)
        .values_list("id", flat=True)
    )

    for destinatario_id in destinatarios:
        async_to_sync(channel_layer.group_send)(
            f"user_{destinatario_id}",
            {
                "type": "new_message_notification",
                "conversation_id": conversacion.id,
                "message_id": mensaje.id,
                "sender": nombre_autor,
                "message": f"📎 {adjunto.nombre_original}",
                "count": _total_no_leidos(destinatario_id),
            }
        )

    return JsonResponse(
        {
            "ok": True,
            **payload,
        }
    )


@login_required
def ver_adjunto(request, adjunto_id):
    adjunto = get_object_or_404(
        AdjuntoMensaje.objects.select_related(
            "mensaje__conversacion"
        ),
        id=adjunto_id,
        mensaje__eliminado=False,
        mensaje__conversacion__activa=True,
        mensaje__conversacion__participantes=request.user,
    )

    # R2 es privado. django-storages genera una URL firmada temporal.
    return redirect(adjunto.archivo.url)
