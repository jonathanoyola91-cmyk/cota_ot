from collections import defaultdict
from datetime import date, datetime, timedelta, time
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from workorders.models import WorkOrder
from compras_oil.models import PurchaseRequest
from inventario.models import WorkshopDelivery
from paw_app.models import Paw
from .forms_horas import AsignarTecnicosTallerForm, IniciarEnsambleForm, JornadaTallerForm
from .models import CamaraTaller, EnsambleTaller, JornadaTaller, OrdenMecanizadoEje


def optimizar_foto_metrologia(archivo, max_lado=1920, calidad=82):
    """Reduce fotografías de evidencia antes de almacenarlas.

    Corrige la orientación EXIF, limita el lado mayor y convierte a JPEG
    optimizado. Si Pillow no puede procesar el archivo, lanza ValueError para
    que la vista informe al usuario sin perder las mediciones ya diligenciadas.
    """
    try:
        archivo.seek(0)
        with Image.open(archivo) as img:
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "L"):
                # Las evidencias son fotografías; un fondo blanco evita fondos
                # negros si excepcionalmente llega una imagen con transparencia.
                if "A" in img.getbands():
                    fondo = Image.new("RGB", img.size, "white")
                    alpha = img.getchannel("A")
                    fondo.paste(img.convert("RGB"), mask=alpha)
                    img = fondo
                else:
                    img = img.convert("RGB")
            elif img.mode == "L":
                img = img.convert("RGB")

            img.thumbnail((max_lado, max_lado), Image.Resampling.LANCZOS)

            salida = BytesIO()
            img.save(
                salida,
                format="JPEG",
                quality=calidad,
                optimize=True,
                progressive=True,
            )
    except Exception as exc:
        raise ValueError("No fue posible procesar la fotografía seleccionada.") from exc

    nombre_base = Path(getattr(archivo, "name", "evidencia")).stem
    nombre = f"{nombre_base[:80] or 'evidencia'}.jpg"
    return ContentFile(salida.getvalue(), name=nombre)


def obtener_bom_seguro(ot):
    try:
        return ot.bom
    except Exception:
        return None


def puede_editar_taller(user):
    return tiene_rol(user, ["TALLER", "ADMIN"])


def calcular_progreso_entrega(entrega):
    """Calcula el avance con la cantidad neta que todavía exige el PAW.

    La cantidad original deja de ser la referencia cuando Inventario libera a
    bodega o cancela justificadamente un saldo. Usar la cantidad neta evita que
    Taller vea entregas completas como si todavía estuvieran parciales.
    """
    total_requerido = Decimal("0")
    total_entregado = Decimal("0")
    total_lineas = 0
    lineas_entregadas = 0

    for linea in entrega.lineas.all():
        requerido = Decimal(linea.cantidad_requerida_neta or 0)
        entregado = Decimal(linea.cantidad_entregada or 0)

        if requerido <= 0:
            continue

        total_requerido += requerido
        total_entregado += min(entregado, requerido)
        total_lineas += 1

        if entregado >= requerido:
            lineas_entregadas += 1

    porcentaje = 0
    if total_requerido > 0:
        porcentaje = min(round((total_entregado / total_requerido) * 100), 100)

    return {
        "total_requerido": total_requerido,
        "total_entregado": total_entregado,
        "total_lineas": total_lineas,
        "lineas_entregadas": lineas_entregadas,
        "porcentaje": porcentaje,
        "completa": total_requerido > 0 and total_entregado >= total_requerido,
    }


@login_required
def dashboard(request):
    estados_paw_fuera_operacion = [
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    ]

    # Una OT cuyo PAW ya salió de operación no debe seguir apareciendo
    # como "Pendiente BOM", "Esperando material", "Material parcial", etc.
    # También excluimos OTs cerradas/terminadas.
    ots = (
        WorkOrder.objects
        .select_related("paw")
        .filter(
            Q(paw__isnull=True)
            | Q(paw__requiere_taller=True)
            | Q(paw__requiere_taller__isnull=True, paw__tipo_operacion="ENSAMBLE")
        )
        .exclude(
            Q(paw__estado_operativo__in=estados_paw_fuera_operacion)
            | Q(estado__in=[
                WorkOrder.Status.TERMINADA,
                WorkOrder.Status.CERRADA,
            ])
        )
        .order_by("-numero")
    )

    pendientes_bom = []
    bom_borrador = []
    esperando_material = []
    material_parcial = []
    material_entregado = []

    for ot in ots:
        bom = obtener_bom_seguro(ot)

        if not bom:
            pendientes_bom.append(ot)
            continue

        compra = PurchaseRequest.objects.filter(bom=bom).first()

        entrega = None
        if compra:
            entrega = (
                WorkshopDelivery.objects
                .filter(purchase_request=compra, destino="TALLER")
                .prefetch_related("lineas")
                .first()
            )

        progreso = calcular_progreso_entrega(entrega) if entrega else {
            "total_lineas": 0,
            "lineas_entregadas": 0,
            "porcentaje": 0,
            "completa": False,
        }

        item = {
            "ot": ot,
            "bom": bom,
            "compra": compra,
            "entrega": entrega,
            "total_lineas": progreso["total_lineas"],
            "entregadas": progreso["lineas_entregadas"],
            "porcentaje_entrega": progreso["porcentaje"],
        }

        estado_bom = getattr(bom, "estado", "")

        if estado_bom == "BORRADOR":
            bom_borrador.append(item)
        elif entrega and progreso["completa"]:
            if not ot.ensamble_ok:
                material_entregado.append(item)
        elif entrega and progreso["porcentaje"] > 0:
            material_parcial.append(item)
        else:
            esperando_material.append(item)

    historial_ensamble = (
        WorkOrder.objects
        .select_related("paw", "ensamble_confirmado_por")
        .filter(ensamble_ok=True)
        .order_by("-fecha_ensamble_ok", "-actualizado_en")
    )

    return render(request, "taller/dashboard.html", {
        "pendientes_bom": pendientes_bom,
        "bom_borrador": bom_borrador,
        "esperando_material": esperando_material,
        "material_parcial": material_parcial,
        "material_entregado": material_entregado,
        "historial_ensamble": historial_ensamble,

        "total_pendientes_bom": len(pendientes_bom),
        "total_bom_borrador": len(bom_borrador),
        "total_esperando_material": len(esperando_material),
        "total_material_parcial": len(material_parcial),
        "total_material_entregado": len(material_entregado),
        "total_historial_ensamble": historial_ensamble.count(),

        "puede_editar_taller": puede_editar_taller(request.user),
        "puede_configurar_metrologia": (request.user.is_superuser or request.user.is_staff or tiene_rol(request.user, ["ADMIN"])),
    })


@login_required
def detalle_material(request, entrega_id):
    """Detalle de solo lectura para que Taller no dependa de Inventario/PAW."""
    entrega = get_object_or_404(
        WorkshopDelivery.objects
        .select_related("purchase_request__bom__workorder__paw")
        .prefetch_related("lineas"),
        pk=entrega_id,
        destino="TALLER",
    )

    progreso = calcular_progreso_entrega(entrega)
    lineas = []
    for linea in entrega.lineas.all():
        requerido = Decimal(linea.cantidad_requerida_neta or 0)
        entregado = min(Decimal(linea.cantidad_entregada or 0), requerido)
        pendiente = max(requerido - entregado, Decimal("0"))
        lineas.append({
            "objeto": linea,
            "requerido": requerido,
            "entregado": entregado,
            "pendiente": pendiente,
            "completa": requerido <= 0 or pendiente <= 0,
        })

    return render(request, "taller/detalle_material.html", {
        "entrega": entrega,
        "ot": entrega.purchase_request.bom.workorder,
        "lineas_material": lineas,
        "progreso": progreso,
        "puede_editar_taller": puede_editar_taller(request.user),
    })


@require_POST
@login_required
def confirmar_ensamble_ok(request, ot_id):
    if not puede_editar_taller(request.user):
        messages.error(request, "No tienes permiso para modificar Taller.")
        return redirect("taller:dashboard")

    ot = get_object_or_404(
        WorkOrder.objects.select_related("paw"),
        numero=ot_id
    )

    if ot.ensamble_ok:
        messages.info(request, "Este ensamble ya fue confirmado.")
        return redirect("taller:dashboard")

    bom = obtener_bom_seguro(ot)

    if not bom:
        messages.error(request, "No se puede cerrar: la OT no tiene BOM.")
        return redirect("taller:dashboard")

    compra = PurchaseRequest.objects.filter(bom=bom).first()

    if not compra:
        messages.error(request, "No hay solicitud de compra.")
        return redirect("taller:dashboard")

    entrega = (
        WorkshopDelivery.objects
        .filter(purchase_request=compra, destino="TALLER")
        .prefetch_related("lineas")
        .first()
    )

    if not entrega:
        messages.error(request, "No hay entrega a taller.")
        return redirect("taller:dashboard")

    progreso = calcular_progreso_entrega(entrega)

    if progreso["total_requerido"] <= 0:
        messages.error(request, "No se puede confirmar: no hay cantidades requeridas válidas.")
        return redirect("taller:dashboard")

    if not progreso["completa"]:
        messages.error(request, "Aún hay material pendiente.")
        return redirect("taller:dashboard")

    ot.ensamble_ok = True
    ot.fecha_ensamble_ok = timezone.now()
    ot.ensamble_confirmado_por = request.user
    ot.etapa_taller = WorkOrder.EtapaTaller.TERMINADO
    ot.estado = WorkOrder.Status.TERMINADA
    ot.terminado_en = timezone.now()
    ot.save(update_fields=[
        "ensamble_ok",
        "fecha_ensamble_ok",
        "ensamble_confirmado_por",
        "etapa_taller",
        "estado",
        "terminado_en",
        "actualizado_en",
    ])

    if ot.paw:
        ot.paw.estado_operativo = "PRODUCTO_OK"
        ot.paw.save(update_fields=["estado_operativo"])

        if ot.paw.listo_para_facturar:
            messages.success(
                request,
                "Ensamble confirmado. El PAW quedó listo para facturación.",
            )
        elif ot.paw.aplica_campo:
            messages.success(
                request,
                "Ensamble confirmado. Taller finalizó y el PAW queda pendiente de Campo.",
            )
        else:
            messages.success(request, "Ensamble confirmado correctamente.")
    else:
        messages.success(request, "Ensamble confirmado correctamente.")

    return redirect("taller:dashboard")

@login_required
def camaras_taller(request):

    # La ubicación física de la cámara depende del estado ENTREGADA,
    # no de si ya tiene PAW. Una cámara con PAW puede seguir en Taller.
    activas = (
        CamaraTaller.objects
        .exclude(estado=CamaraTaller.Estado.ENTREGADA)
        .select_related("paw")
        .order_by("fecha_ingreso", "id")
    )

    # Historial: únicamente cámaras que ya salieron físicamente de Taller.
    historial = (
        CamaraTaller.objects
        .filter(estado=CamaraTaller.Estado.ENTREGADA)
        .select_related("paw")
        .order_by("-actualizado_en")
    )

    return render(request, "taller/camaras_taller.html", {
        "activas": activas,
        "historial": historial,
        "total_activas": activas.count(),
    })


@login_required
def camara_nueva(request):

    if request.method == "POST":

        cliente = request.POST.get("cliente", "").strip()
        marca = request.POST.get("marca", "").strip()
        serial = request.POST.get("serial", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        fecha_ingreso = request.POST.get("fecha_ingreso")
        fecha_tear_down = request.POST.get("fecha_tear_down") or None
        observaciones = request.POST.get("observaciones", "").strip()

        if not cliente or not serial or not fecha_ingreso:
            messages.error(
                request,
                "Cliente, serial y fecha de ingreso son obligatorios."
            )
            return redirect("taller:camara_nueva")

        CamaraTaller.objects.create(
            cliente=cliente,
            marca=marca,
            serial=serial,
            modelo=modelo,
            fecha_ingreso=fecha_ingreso,
            fecha_tear_down=fecha_tear_down,
            estado=CamaraTaller.Estado.RECIBIDA,
            observaciones=observaciones,
        )

        messages.success(
            request,
            f"Cámara serial {serial} registrada en Taller."
        )

        return redirect("taller:camaras_taller")

    return render(request, "taller/camara_nueva.html")

@login_required
def camara_editar(request, camara_id):

    camara = get_object_or_404(
        CamaraTaller,
        id=camara_id
    )

    if request.method == "POST":

        cliente = request.POST.get("cliente", "").strip()
        marca = request.POST.get("marca", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        serial = request.POST.get("serial", "").strip()
        fecha_ingreso = request.POST.get("fecha_ingreso")
        fecha_tear_down = request.POST.get("fecha_tear_down") or None
        estado = request.POST.get("estado")
        observaciones = request.POST.get("observaciones", "").strip()

        if not cliente or not serial or not fecha_ingreso:
            messages.error(
                request,
                "Cliente, serial y fecha de ingreso son obligatorios."
            )
            return redirect(
                "taller:camara_editar",
                camara_id=camara.id
            )

        estados_validos = [
            valor for valor, texto in CamaraTaller.Estado.choices
        ]

        if estado not in estados_validos:
            messages.error(
                request,
                "El estado seleccionado no es válido."
            )
            return redirect(
                "taller:camara_editar",
                camara_id=camara.id
            )

        camara.cliente = cliente
        camara.marca = marca
        camara.modelo = modelo
        camara.serial = serial
        camara.fecha_ingreso = fecha_ingreso
        camara.fecha_tear_down = fecha_tear_down
        camara.estado = estado
        camara.observaciones = observaciones

        camara.save()

        if camara.estado == CamaraTaller.Estado.ENTREGADA:
            messages.success(
                request,
                f"Cámara serial {camara.serial} marcada como entregada y trasladada al historial."
            )
        else:
            messages.success(
                request,
                f"Cámara serial {camara.serial} actualizada correctamente."
            )

        return redirect("taller:camaras_taller")

    return render(
        request,
        "taller/camara_editar.html",
        {
            "camara": camara,
            "estados": CamaraTaller.Estado.choices,
        }
    )

# ============================================================
# CONTROL DE HORAS DE ENSAMBLE - TALLER
# ============================================================

def _puede_taller(user):
    return tiene_rol(user, ["TALLER", "INGENIERIA", "GERENTE", "ADMIN"])


def _puede_ver_reporte_horas(user):
    return tiene_rol(user, ["FINANZAS", "GERENTE", "ADMIN"])


def _parse_fecha(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@login_required
def dashboard_horas_taller(request):
    if not _puede_taller(request.user) and not _puede_ver_reporte_horas(request.user):
        messages.error(request, "No tienes acceso al control de horas de Taller.")
        return redirect("/")

    # Todo PAW creado como ENSAMBLE aparece en Taller sin depender de OT
    # ni de que CamaraTaller tenga el PAW relacionado.
    estados_fuera_operacion = ["EN_FACTURACION", "FACTURADO", "RADICADO"]

    paws_disponibles = (
        Paw.objects
        .select_related("cotizacion")
        .filter(
            Q(requiere_taller=True)
            | Q(
                requiere_taller__isnull=True,
                tipo_operacion=Paw.TipoOperacion.ENSAMBLE,
            )
        )
        .exclude(estado_operativo__in=estados_fuera_operacion)
        .filter(ensamble_horas_taller__isnull=True)
        .order_by("-creado_en")
    )

    ensambles_base = (
        EnsambleTaller.objects
        .select_related("paw", "paw__cotizacion", "responsable")
        .prefetch_related("tecnicos", "jornadas")
        .filter(paw__isnull=False)
    )

    # Controles que todavía pueden recibir jornadas o ajustes.
    ensambles_abiertos = (
        ensambles_base
        .exclude(estado=EnsambleTaller.Estado.FINALIZADO)
        .order_by("-actualizado_en")
    )

    # Histórico de controles de horas ya cerrados.
    ensambles_finalizados = (
        ensambles_base
        .filter(estado=EnsambleTaller.Estado.FINALIZADO)
        .order_by("-fecha_fin", "-actualizado_en")
    )

    return render(request, "taller_horas/dashboard.html", {
        "paws_disponibles": paws_disponibles,
        "ensambles": ensambles_base,
        "ensambles_abiertos": ensambles_abiertos,
        "ensambles_finalizados": ensambles_finalizados,
        "total_controles": ensambles_base.count(),
        "total_abiertos": ensambles_abiertos.count(),
        "total_finalizados": ensambles_finalizados.count(),
        "total_pendientes_iniciar": paws_disponibles.count(),
        "puede_operar": _puede_taller(request.user),
        "puede_reporte": _puede_ver_reporte_horas(request.user),
    })


@login_required
def iniciar_ensamble(request, paw_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para iniciar controles de horas de Taller.")
        return redirect("/")

    paw = get_object_or_404(
        Paw.objects.select_related("cotizacion"),
        id=paw_id,
    )

    if not paw.aplica_taller:
        messages.error(request, "Este PAW no tiene habilitado el alcance de Taller / reparación.")
        return redirect("taller:horas_dashboard")

    existente = EnsambleTaller.objects.filter(paw=paw).first()
    if existente:
        return redirect("taller:horas_detalle", ensamble_id=existente.id)

    if request.method == "POST":
        form = IniciarEnsambleForm(request.POST)
        if form.is_valid():
            ensamble = form.save(commit=False)
            ensamble.paw = paw
            ensamble.responsable = request.user
            ensamble.save()
            messages.success(
                request,
                f"Control de horas iniciado para el PAW {paw.numero_paw}."
            )
            return redirect("taller:horas_asignar_tecnicos", ensamble_id=ensamble.id)
    else:
        form = IniciarEnsambleForm(initial={"fecha_inicio": timezone.localdate()})

    return render(request, "taller_horas/iniciar_ensamble.html", {
        "paw": paw,
        "form": form,
    })


@login_required
def detalle_ensamble(request, ensamble_id):
    if not _puede_taller(request.user) and not _puede_ver_reporte_horas(request.user):
        messages.error(request, "No tienes acceso a este control de horas.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw", "paw__cotizacion", "responsable")
        .prefetch_related("tecnicos", "jornadas", "jornadas__tecnico"),
        id=ensamble_id,
    )

    camara_relacionada = None
    if ensamble.paw_id:
        camara_relacionada = (
            CamaraTaller.objects
            .filter(paw=ensamble.paw)
            .order_by("-actualizado_en")
            .first()
        )

    return render(request, "taller_horas/detalle.html", {
        "ensamble": ensamble,
        "jornadas": ensamble.jornadas.all(),
        "camara_relacionada": camara_relacionada,
        "puede_operar": _puede_taller(request.user),
        "puede_reporte": _puede_ver_reporte_horas(request.user),
    })


@login_required
def asignar_tecnicos(request, ensamble_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para asignar técnicos.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw")
        .prefetch_related("tecnicos"),
        id=ensamble_id,
    )

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.error(request, "No puedes modificar técnicos de un control finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if request.method == "POST":
        form = AsignarTecnicosTallerForm(request.POST, ensamble=ensamble)
        if form.is_valid():
            form.save()
            messages.success(request, "Técnicos de Taller actualizados.")
            return redirect("taller:horas_detalle", ensamble_id=ensamble.id)
    else:
        form = AsignarTecnicosTallerForm(ensamble=ensamble)

    return render(request, "taller_horas/asignar_tecnicos.html", {
        "ensamble": ensamble,
        "form": form,
    })


@login_required
def crear_jornada(request, ensamble_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para registrar jornadas de Taller.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw")
        .prefetch_related("tecnicos"),
        id=ensamble_id,
    )

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.error(request, "No puedes registrar horas en un control finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if not ensamble.tecnicos.exists():
        messages.error(request, "Primero debes asignar los técnicos involucrados.")
        return redirect("taller:horas_asignar_tecnicos", ensamble_id=ensamble.id)

    if request.method == "POST":
        form = JornadaTallerForm(request.POST, ensamble=ensamble)

        # La instancia debe conocer el ensamble ANTES de form.is_valid().
        # Así las validaciones del modelo (incluido solapamiento de horarios)
        # aparecen como errores del formulario y no generan ValidationError 500.
        form.instance.ensamble = ensamble

        if form.is_valid():
            jornada = form.save(commit=False)
            jornada.ensamble = ensamble
            jornada.registrado_por = request.user
            jornada.save()
            messages.success(request, "Actividad registrada y horas calculadas automáticamente.")
            return redirect("taller:horas_detalle", ensamble_id=ensamble.id)
    else:
        ahora = timezone.localtime()
        form = JornadaTallerForm(
            ensamble=ensamble,
            initial={
                "fecha": timezone.localdate(),
                "hora_entrada": ahora.strftime("%H:%M"),
            },
        )

    return render(request, "taller_horas/jornada_form.html", {
        "ensamble": ensamble,
        "form": form,
        "modo": "crear",
    })


@login_required
def editar_jornada(request, jornada_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para editar jornadas de Taller.")
        return redirect("/")

    jornada = get_object_or_404(
        JornadaTaller.objects
        .select_related("ensamble", "ensamble__paw", "tecnico"),
        id=jornada_id,
    )
    ensamble = jornada.ensamble

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.error(request, "No puedes editar jornadas de un control finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if request.method == "POST":
        form = JornadaTallerForm(request.POST, instance=jornada, ensamble=ensamble)
        if form.is_valid():
            form.save()
            messages.success(request, "Jornada actualizada.")
            return redirect("taller:horas_detalle", ensamble_id=ensamble.id)
    else:
        form = JornadaTallerForm(instance=jornada, ensamble=ensamble)

    return render(request, "taller_horas/jornada_form.html", {
        "ensamble": ensamble,
        "jornada": jornada,
        "form": form,
        "modo": "editar",
    })


@require_POST
@login_required
def finalizar_ensamble(request, ensamble_id):
    if not _puede_taller(request.user):
        messages.error(request, "No tienes permiso para finalizar controles de horas de Taller.")
        return redirect("/")

    ensamble = get_object_or_404(
        EnsambleTaller.objects
        .select_related("paw")
        .prefetch_related("jornadas"),
        id=ensamble_id,
    )

    if ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
        messages.info(request, "Este control de horas ya estaba finalizado.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    if not ensamble.jornadas.exists():
        messages.error(request, "No puedes finalizar sin registrar al menos una jornada.")
        return redirect("taller:horas_detalle", ensamble_id=ensamble.id)

    # CIERRE EXCLUSIVAMENTE INTERNO.
    # No cambia paw.estado_operativo, tipo_operacion ni el estado de CamaraTaller.
    ensamble.estado = EnsambleTaller.Estado.FINALIZADO
    ensamble.fecha_fin = timezone.localdate()
    ensamble.save(update_fields=["estado", "fecha_fin", "actualizado_en"])

    messages.success(
        request,
        "Control de horas finalizado internamente. El flujo principal del PAW no fue modificado."
    )
    return redirect("taller:horas_detalle", ensamble_id=ensamble.id)



def _merge_intervalos(intervalos):
    """
    Une intervalos que se tocan o se superponen.
    Devuelve una lista de pares (inicio, fin) sin doble conteo.
    """
    if not intervalos:
        return []

    ordenados = sorted(intervalos, key=lambda x: x[0])
    resultado = [list(ordenados[0])]

    for inicio, fin in ordenados[1:]:
        ultimo = resultado[-1]
        if inicio <= ultimo[1]:
            if fin > ultimo[1]:
                ultimo[1] = fin
        else:
            resultado.append([inicio, fin])

    return [(i, f) for i, f in resultado]


def _clasificar_intervalos_dia(intervalos):
    """
    Consolida todos los PAW trabajados por un técnico en un mismo día y
    clasifica el tiempo efectivo sin duplicar intervalos.
    """
    if not intervalos:
        cero = Decimal("0.00")
        return cero, cero, cero, cero

    intervalos_unidos = _merge_intervalos(intervalos)

    ordinarias = Decimal("0.00")
    extra_diurna = Decimal("0.00")
    extra_nocturna = Decimal("0.00")

    for inicio, fin in intervalos_unidos:
        cursor = inicio.date()
        fin_dia = fin.date()

        while cursor <= fin_dia:
            dia_sig = cursor + timedelta(days=1)

            tramos_ordinarios = [
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=7)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=12)),
                ),
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=13)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=16)),
                ),
            ]

            tramos_extra_diurna = [
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=6)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=7)),
                ),
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=16)),
                    datetime.combine(cursor, datetime.min.time().replace(hour=19)),
                ),
            ]

            tramos_extra_nocturna = [
                (
                    datetime.combine(cursor, datetime.min.time()),
                    datetime.combine(cursor, datetime.min.time().replace(hour=6)),
                ),
                (
                    datetime.combine(cursor, datetime.min.time().replace(hour=19)),
                    datetime.combine(dia_sig, datetime.min.time()),
                ),
            ]

            for desde, hasta in tramos_ordinarios:
                ordinarias += JornadaTaller._horas_interseccion(inicio, fin, desde, hasta)

            for desde, hasta in tramos_extra_diurna:
                extra_diurna += JornadaTaller._horas_interseccion(inicio, fin, desde, hasta)

            for desde, hasta in tramos_extra_nocturna:
                extra_nocturna += JornadaTaller._horas_interseccion(inicio, fin, desde, hasta)

            cursor = dia_sig

    total = ordinarias + extra_diurna + extra_nocturna
    return ordinarias, extra_diurna, extra_nocturna, total


@login_required
def reporte_horas(request):
    if not _puede_ver_reporte_horas(request.user):
        messages.error(request, "No tienes acceso al reporte contable de horas de Taller.")
        return redirect("/")

    hoy = timezone.localdate()
    fecha_inicio = _parse_fecha(request.GET.get("fecha_inicio")) or hoy.replace(day=1)
    fecha_fin = _parse_fecha(request.GET.get("fecha_fin")) or hoy

    jornadas = (
        JornadaTaller.objects
        .filter(fecha__range=[fecha_inicio, fecha_fin])
        .select_related("tecnico", "ensamble", "ensamble__paw")
        .order_by("tecnico__tecnico", "fecha", "hora_entrada")
    )

    # Agrupamos por técnico y fecha para consolidar todos los PAW del día.
    por_tecnico_fecha = defaultdict(lambda: {
        "intervalos": [],
        "detalle": [],
    })

    for j in jornadas:
        clave = (j.tecnico.tecnico, j.fecha)
        inicio, fin = j._intervalo_real()
        por_tecnico_fecha[clave]["intervalos"].append((inicio, fin))
        por_tecnico_fecha[clave]["detalle"].append(j)

    resumen = defaultdict(lambda: {
        "ordinarias": Decimal("0.00"),
        "extra_diurna": Decimal("0.00"),
        "extra_nocturna": Decimal("0.00"),
        "total": Decimal("0.00"),
        "detalle": [],
        "dias": [],
    })

    total_ord = Decimal("0.00")
    total_ed = Decimal("0.00")
    total_en = Decimal("0.00")
    total_general = Decimal("0.00")

    for (nombre, fecha), info in sorted(por_tecnico_fecha.items(), key=lambda x: (x[0][0], x[0][1])):
        ord_dia, ed_dia, en_dia, total_dia = _clasificar_intervalos_dia(info["intervalos"])

        data = resumen[nombre]
        data["ordinarias"] += ord_dia
        data["extra_diurna"] += ed_dia
        data["extra_nocturna"] += en_dia
        data["total"] += total_dia
        data["detalle"].extend(info["detalle"])
        data["dias"].append({
            "fecha": fecha,
            "ordinarias": ord_dia,
            "extra_diurna": ed_dia,
            "extra_nocturna": en_dia,
            "total": total_dia,
            "detalle": info["detalle"],
        })

        total_ord += ord_dia
        total_ed += ed_dia
        total_en += en_dia
        total_general += total_dia

    return render(request, "taller_horas/reporte_horas.html", {
        "resumen": dict(resumen),
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_ordinarias": total_ord,
        "total_extra_diurna": total_ed,
        "total_extra_nocturna": total_en,
        "total_general": total_general,
    })


@login_required
def reporte_horas_empleado(request):
    if not _puede_ver_reporte_horas(request.user):
        messages.error(
            request,
            "No tienes acceso al reporte individual de horas extra de Taller."
        )
        return redirect("/")

    tecnico = request.GET.get("tecnico", "").strip()

    if not tecnico:
        messages.error(request, "Debes indicar el técnico.")
        return redirect("taller:horas_reporte")

    hoy = timezone.localdate()
    corte_inicio, corte_fin = _periodo_corte_27(hoy)

    fecha_inicio = (
        _parse_fecha(request.GET.get("fecha_inicio"))
        or corte_inicio
    )

    fecha_fin = (
        _parse_fecha(request.GET.get("fecha_fin"))
        or corte_fin
    )

    jornadas = (
        JornadaTaller.objects
        .filter(
            tecnico__tecnico=tecnico,
            fecha__range=[fecha_inicio, fecha_fin],
            ensamble__estado=EnsambleTaller.Estado.FINALIZADO,
        )
        .select_related(
            "tecnico",
            "ensamble",
            "ensamble__paw",
        )
        .order_by("fecha", "hora_entrada")
    )

    # Consolidar por fecha todos los PAW del empleado para evitar doble conteo.
    por_fecha = defaultdict(list)
    for jornada in jornadas:
        por_fecha[jornada.fecha].append(jornada._intervalo_real())

    total_ordinarias = Decimal("0.00")
    total_extra_diurna = Decimal("0.00")
    total_extra_nocturna = Decimal("0.00")
    total_general = Decimal("0.00")

    for intervalos in por_fecha.values():
        ord_dia, ed_dia, en_dia, total_dia = _clasificar_intervalos_dia(intervalos)
        total_ordinarias += ord_dia
        total_extra_diurna += ed_dia
        total_extra_nocturna += en_dia
        total_general += total_dia

    return render(
        request,
        "taller_horas/reporte_horas_empleado.html",
        {
            "tecnico": tecnico,
            "jornadas": jornadas,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "total_ordinarias": total_ordinarias,
            "total_extra_diurna": total_extra_diurna,
            "total_extra_nocturna": total_extra_nocturna,
            "total_general": total_general,
        }
    )

def _periodo_corte_27(fecha_base):
    if fecha_base.day <= 27:

        if fecha_base.month == 1:
            fecha_inicio = date(
                fecha_base.year - 1,
                12,
                28
            )
        else:
            fecha_inicio = date(
                fecha_base.year,
                fecha_base.month - 1,
                28
            )

        fecha_fin = date(
            fecha_base.year,
            fecha_base.month,
            27
        )

    else:

        fecha_inicio = date(
            fecha_base.year,
            fecha_base.month,
            28
        )

        if fecha_base.month == 12:
            fecha_fin = date(
                fecha_base.year + 1,
                1,
                27
            )
        else:
            fecha_fin = date(
                fecha_base.year,
                fecha_base.month + 1,
                27
            )

    return fecha_inicio, fecha_fin


# =========================
# METROLOGIA / INSPECCION DE EJES
# =========================
from django.db import transaction
from .forms_metrologia import NuevaInspeccionEjeForm, DictamenInspeccionEjeForm
from .models import InspeccionEje, MedicionEje, InstrumentoMetrologico, CalibracionInstrumento, PlantillaEje, PuntoMedicionEje, TipoPiezaMetrologia



@login_required
@transaction.atomic
def metrologia_plantilla_configurar(request, plantilla_id):
    # La configuración dimensional queda restringida a administración.
    if not _puede_gestionar_metrologia(request.user):
        messages.error(request, "No tiene permisos para configurar plantillas metrológicas.")
        return redirect("taller:metrologia_ejes")

    plantilla = get_object_or_404(PlantillaEje, pk=plantilla_id)
    puntos = list(plantilla.puntos.all())

    if request.method == "POST":
        accion = request.POST.get("accion", "guardar")
        if accion == "nuevo":
            codigo = request.POST.get("codigo", "").strip().upper()
            descripcion = request.POST.get("descripcion", "").strip()
            if not codigo or not descripcion:
                messages.error(request, "Indique código y característica para el nuevo punto.")
            elif plantilla.puntos.filter(codigo=codigo).exists():
                messages.error(request, f"El punto {codigo} ya existe en esta plantilla.")
            else:
                def dec(name):
                    v = (request.POST.get(name) or "").strip().replace(",", ".")
                    if not v:
                        return None
                    try:
                        return Decimal(v)
                    except (InvalidOperation, ValueError, TypeError):
                        raise ValueError(f"El campo {name} debe contener solo un número (ej. 0,003 o 0.003).")
                try:
                    nominal_nuevo = dec("nominal")
                    minimo_nuevo = dec("minimo")
                    maximo_nuevo = dec("maximo")
                    minimo_reutilizable_nuevo = dec("minimo_reutilizable")
                    x_nuevo = dec("posicion_x") or Decimal("50")
                    y_nuevo = dec("posicion_y") or Decimal("50")
                except ValueError as exc:
                    messages.error(request, str(exc))
                    return redirect("taller:metrologia_plantilla_configurar", plantilla_id=plantilla.id)
                PuntoMedicionEje.objects.create(
                    plantilla=plantilla, codigo=codigo, descripcion=descripcion,
                    tipo=request.POST.get("tipo") or PuntoMedicionEje.Tipo.DIAMETRO,
                    nominal=nominal_nuevo, minimo=minimo_nuevo, maximo=maximo_nuevo,
                    minimo_reutilizable=minimo_reutilizable_nuevo, permite_mecanizado=bool(request.POST.get("permite_mecanizado")),
                    unidad=request.POST.get("unidad", "mm").strip() or "mm",
                    instrumento_sugerido=request.POST.get("instrumento_sugerido", "").strip(),
                    critico=bool(request.POST.get("critico")), obligatorio=bool(request.POST.get("obligatorio")),
                    orden=(plantilla.puntos.order_by("-orden").values_list("orden", flat=True).first() or 0)+1,
                    posicion_x=x_nuevo, posicion_y=y_nuevo,
                )
                messages.success(request, f"Punto {codigo} creado.")
            return redirect("taller:metrologia_plantilla_configurar", plantilla_id=plantilla.id)

        for punto in puntos:
            pref=f"p_{punto.id}_"
            if request.POST.get(pref+"delete"):
                punto.delete()
                continue
            def decp(name, actual=None):
                v = (request.POST.get(pref+name) or "").strip().replace(",", ".")
                if not v:
                    return None
                try:
                    return Decimal(v)
                except (InvalidOperation, ValueError, TypeError):
                    raise ValueError(f"El campo {name} del punto {punto.codigo} debe contener solo un número (ej. 0,003 o 0.003).")
            punto.descripcion=request.POST.get(pref+"descripcion", punto.descripcion).strip()
            try:
                punto.nominal=decp("nominal")
                punto.minimo=decp("minimo")
                punto.maximo=decp("maximo")
                punto.minimo_reutilizable=decp("minimo_reutilizable")
                punto.posicion_x=decp("x") or Decimal("50")
                punto.posicion_y=decp("y") or Decimal("50")
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect("taller:metrologia_plantilla_configurar", plantilla_id=plantilla.id)
            punto.unidad=request.POST.get(pref+"unidad", punto.unidad).strip() or "mm"
            punto.instrumento_sugerido=request.POST.get(pref+"instrumento", punto.instrumento_sugerido).strip()
            punto.critico=bool(request.POST.get(pref+"critico"))
            punto.obligatorio=bool(request.POST.get(pref+"obligatorio"))
            punto.permite_mecanizado=bool(request.POST.get(pref+"permite_mecanizado"))
            punto.save()
        messages.success(request, "Configuración de puntos guardada.")
        return redirect("taller:metrologia_plantilla_configurar", plantilla_id=plantilla.id)

    return render(request, "taller/metrologia_plantilla_configurar.html", {
        "plantilla": plantilla, "puntos": puntos, "tipos": PuntoMedicionEje.Tipo.choices,
    })


def _puede_gestionar_metrologia(user):
    """Plantillas metrológicas: solo quien tenga el permiso específico de configuración."""
    return user.is_superuser or user.has_perm("taller.gestionar_plantillas_metrologicas")


def _puede_gestionar_instrumentos(user):
    """Instrumentos/calibraciones: usa los permisos estándar asignados en Django Admin."""
    return (
        user.is_superuser
        or user.has_perm("taller.add_instrumentometrologico")
        or user.has_perm("taller.change_instrumentometrologico")
        or user.has_perm("taller.add_calibracioninstrumento")
        or user.has_perm("taller.change_calibracioninstrumento")
    )


def _fecha_post(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
def metrologia_instrumentos(request):
    instrumentos = list(InstrumentoMetrologico.objects.all().order_by("nombre", "codigo"))
    resumen = {"total": len(instrumentos), "vigentes": 0, "proximos": 0, "vencidos": 0, "sin_calibracion": 0, "fuera_servicio": 0}
    for i in instrumentos:
        estado = i.estado_calibracion
        if estado == "VIGENTE": resumen["vigentes"] += 1
        elif estado == "PROXIMO": resumen["proximos"] += 1
        elif estado == "VENCIDO": resumen["vencidos"] += 1
        elif estado == "SIN_CALIBRACION": resumen["sin_calibracion"] += 1
        else: resumen["fuera_servicio"] += 1
    return render(request, "taller/metrologia_instrumentos.html", {
        "instrumentos": instrumentos, "resumen": resumen,
        "puede_gestionar": _puede_gestionar_instrumentos(request.user),
    })


@login_required
@transaction.atomic
def metrologia_instrumento_form(request, instrumento_id=None):
    permiso_requerido = (
        "taller.change_instrumentometrologico"
        if instrumento_id
        else "taller.add_instrumentometrologico"
    )
    if not (request.user.is_superuser or request.user.has_perm(permiso_requerido)):
        messages.error(request, "No tiene permisos para administrar instrumentos de metrología.")
        return redirect("taller:metrologia_instrumentos")
    instrumento = get_object_or_404(InstrumentoMetrologico, pk=instrumento_id) if instrumento_id else InstrumentoMetrologico()
    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip()
        nombre = request.POST.get("nombre", "").strip()
        if not codigo or not nombre:
            messages.error(request, "Código interno y tipo de instrumento son obligatorios.")
        elif InstrumentoMetrologico.objects.exclude(pk=instrumento.pk).filter(codigo__iexact=codigo).exists():
            messages.error(request, "Ya existe un instrumento con ese código interno.")
        else:
            instrumento.codigo = codigo
            instrumento.nombre = nombre
            for campo in ["marca", "modelo", "serial", "rango", "resolucion", "unidad", "ubicacion", "responsable", "observaciones"]:
                setattr(instrumento, campo, request.POST.get(campo, "").strip())
            instrumento.estado = request.POST.get("estado") or InstrumentoMetrologico.Estado.ACTIVO
            instrumento.activo = instrumento.estado == InstrumentoMetrologico.Estado.ACTIVO
            instrumento.save()
            messages.success(request, "Instrumento guardado. Ahora registre su calibración vigente.")
            return redirect("taller:metrologia_instrumento_detalle", instrumento_id=instrumento.id)
    return render(request, "taller/metrologia_instrumento_form.html", {"instrumento": instrumento, "estados": InstrumentoMetrologico.Estado.choices})


@login_required
@transaction.atomic
def metrologia_instrumento_detalle(request, instrumento_id):
    instrumento = get_object_or_404(InstrumentoMetrologico, pk=instrumento_id)
    historial = instrumento.historial_calibraciones.all()
    if request.method == "POST":
        if not (
            request.user.is_superuser
            or request.user.has_perm("taller.add_calibracioninstrumento")
        ):
            messages.error(request, "No tiene permisos para registrar calibraciones.")
            return redirect("taller:metrologia_instrumento_detalle", instrumento_id=instrumento.id)
        fecha_cal = _fecha_post(request.POST.get("fecha_calibracion"))
        fecha_ven = _fecha_post(request.POST.get("fecha_vencimiento"))
        if not fecha_cal or not fecha_ven:
            messages.error(request, "Fecha de calibración y fecha de vencimiento son obligatorias.")
        elif fecha_ven < fecha_cal:
            messages.error(request, "La fecha de vencimiento no puede ser anterior a la calibración.")
        else:
            certificado = request.FILES.get("certificado")
            cal = CalibracionInstrumento.objects.create(
                instrumento=instrumento, fecha_calibracion=fecha_cal, fecha_vencimiento=fecha_ven,
                laboratorio=request.POST.get("laboratorio", "").strip(),
                numero_certificado=request.POST.get("numero_certificado", "").strip(),
                certificado=certificado,
                observaciones=request.POST.get("observaciones", "").strip(), registrado_por=request.user,
            )
            instrumento.fecha_calibracion = cal.fecha_calibracion
            instrumento.fecha_vencimiento = cal.fecha_vencimiento
            instrumento.laboratorio = cal.laboratorio
            instrumento.numero_certificado = cal.numero_certificado
            if cal.certificado:
                instrumento.certificado = cal.certificado
            instrumento.save(update_fields=["fecha_calibracion", "fecha_vencimiento", "laboratorio", "numero_certificado", "certificado"])
            messages.success(request, "Calibración registrada y vigencia del instrumento actualizada.")
            return redirect("taller:metrologia_instrumento_detalle", instrumento_id=instrumento.id)
    return render(request, "taller/metrologia_instrumento_detalle.html", {
        "instrumento": instrumento, "historial": historial,
        "puede_gestionar": _puede_gestionar_instrumentos(request.user),
    })



@login_required
@transaction.atomic
def metrologia_tipos_pieza(request):
    if not _puede_gestionar_metrologia(request.user):
        messages.error(request, "No tiene permisos para administrar tipos de pieza.")
        return redirect("taller:metrologia_ejes")
    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        if not nombre:
            messages.error(request, "Indique el nombre del tipo de pieza.")
        elif TipoPiezaMetrologia.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ese tipo de pieza ya existe.")
        else:
            TipoPiezaMetrologia.objects.create(nombre=nombre)
            messages.success(request, f"Tipo de pieza {nombre} creado.")
        return redirect("taller:metrologia_tipos_pieza")
    return render(request, "taller/metrologia_tipos_pieza.html", {"tipos": TipoPiezaMetrologia.objects.all()})


@login_required
def metrologia_plantillas(request):
    if not _puede_gestionar_metrologia(request.user):
        messages.error(request, "No tiene permisos para gestionar plantillas metrológicas.")
        return redirect("taller:metrologia_ejes")
    q = (request.GET.get("q") or "").strip()
    plantillas = PlantillaEje.objects.all().prefetch_related("puntos").order_by("tipo_pieza", "nombre", "revision")
    if q:
        plantillas = plantillas.filter(Q(nombre__icontains=q) | Q(codigo_plano__icontains=q) | Q(material__icontains=q))
    return render(request, "taller/metrologia_plantillas.html", {"plantillas": plantillas, "q": q})


@login_required
@transaction.atomic
def metrologia_plantilla_form(request, plantilla_id=None):
    if not _puede_gestionar_metrologia(request.user):
        messages.error(request, "No tiene permisos para gestionar plantillas metrológicas.")
        return redirect("taller:metrologia_ejes")
    plantilla = get_object_or_404(PlantillaEje, pk=plantilla_id) if plantilla_id else None
    if request.method == "POST":
        nombre = (request.POST.get("nombre") or "").strip()
        if not nombre:
            messages.error(request, "El nombre/modelo de la plantilla es obligatorio.")
        elif PlantillaEje.objects.exclude(pk=getattr(plantilla, "pk", None)).filter(nombre__iexact=nombre).exists():
            messages.error(request, "Ya existe una plantilla con ese nombre.")
        else:
            obj = plantilla or PlantillaEje()
            obj.nombre = nombre
            tipo_id = request.POST.get("tipo_pieza_ref")
            obj.tipo_pieza_ref = TipoPiezaMetrologia.objects.filter(pk=tipo_id, activo=True).first() if tipo_id else None
            obj.tipo_pieza = PlantillaEje.TipoPieza.OTRO if obj.tipo_pieza_ref else (request.POST.get("tipo_pieza") or PlantillaEje.TipoPieza.EJE)
            obj.codigo_plano = (request.POST.get("codigo_plano") or "").strip()
            obj.revision = (request.POST.get("revision") or "").strip()
            obj.material = (request.POST.get("material") or "").strip()
            obj.observaciones = (request.POST.get("observaciones") or "").strip()
            obj.activo = bool(request.POST.get("activo"))
            if request.FILES.get("imagen_archivo"):
                obj.imagen_archivo = request.FILES["imagen_archivo"]
            obj.save()
            messages.success(request, "Plantilla guardada. Ahora puede ubicar y configurar sus puntos metrológicos.")
            return redirect("taller:metrologia_plantilla_configurar", plantilla_id=obj.id)
    return render(request, "taller/metrologia_plantilla_form.html", {"plantilla": plantilla, "tipos_pieza": TipoPiezaMetrologia.objects.filter(activo=True)})


@login_required
def metrologia_paw_detalle(request, paw_id):
    paw = get_object_or_404(Paw, pk=paw_id)
    inspecciones = list(InspeccionEje.objects.filter(paw=paw).select_related("plantilla", "inspeccion_origen").order_by("serial_eje", "plantilla__nombre", "numero_inspeccion", "creado_en"))
    grupos = {}
    for i in inspecciones:
        raiz = i.inspeccion_origen_id or i.id
        clave = (i.plantilla_id, i.serial_eje or "SIN-SERIAL", raiz)
        g = grupos.setdefault(clave, {"plantilla": i.plantilla, "serial": i.serial_eje or "—", "inspecciones": [], "ultima": i})
        g["inspecciones"].append(i)
        g["ultima"] = i
    return render(request, "taller/metrologia_paw_detalle.html", {"paw": paw, "grupos": list(grupos.values())})


@login_required
def metrologia_ejes(request):
    inspecciones = list(
        InspeccionEje.objects.select_related("paw", "plantilla", "realizado_por", "revisado_por").all()
    )
    por_paw = {}
    for i in inspecciones:
        g = por_paw.setdefault(i.paw_id, {"paw": i.paw, "tipo_trabajo": i.get_tipo_trabajo_display(), "inspecciones": 0, "piezas": set(), "reinspecciones": 0, "estado": "Pendiente"})
        g["inspecciones"] += 1
        raiz = i.inspeccion_origen_id or i.id
        g["piezas"].add((i.plantilla_id, i.serial_eje or "SIN-SERIAL", raiz))
        if i.inspeccion_origen_id:
            g["reinspecciones"] += 1
        if i.dictamen == InspeccionEje.Dictamen.MECANIZADO:
            g["estado"] = "Requiere mecanizado"
        elif i.resultado_dimensional == InspeccionEje.Resultado.NO_CONFORME and g["estado"] == "Pendiente":
            g["estado"] = "No conforme"
        elif i.dictamen == InspeccionEje.Dictamen.APROBADO and g["estado"] == "Pendiente":
            g["estado"] = "Con inspecciones aprobadas"
    grupos_paw = []
    for g in por_paw.values():
        g["cantidad_piezas"] = len(g.pop("piezas"))
        grupos_paw.append(g)
    grupos_paw.sort(key=lambda x: max([i.creado_en for i in inspecciones if i.paw_id == x["paw"].id], default=timezone.now()), reverse=True)
    puede_configurar = _puede_gestionar_metrologia(request.user)
    return render(request, "taller/metrologia_ejes.html", {"grupos_paw": grupos_paw, "puede_configurar_metrologia": puede_configurar})


@login_required
@transaction.atomic
def metrologia_eje_nueva(request):
    if request.method == "POST":
        form = NuevaInspeccionEjeForm(request.POST)
        if form.is_valid():
            inspeccion = form.save(commit=False)
            inspeccion.realizado_por = request.user
            inspeccion.save()
            puntos = inspeccion.plantilla.puntos.all()
            MedicionEje.objects.bulk_create([
                MedicionEje(inspeccion=inspeccion, punto=punto) for punto in puntos
            ])
            messages.success(request, "Inspección creada. Ya puede registrar las medidas del eje.")
            return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    else:
        initial = {}
        paw_id = request.GET.get("paw")
        if paw_id:
            initial["paw"] = paw_id
            anterior = InspeccionEje.objects.filter(paw_id=paw_id).exclude(serial_equipo="").order_by("creado_en").first()
            if anterior:
                initial["serial_equipo"] = anterior.serial_equipo
                initial["tipo_trabajo"] = anterior.tipo_trabajo
        form = NuevaInspeccionEjeForm(initial=initial)
    return render(request, "taller/metrologia_eje_nueva.html", {"form": form})


@login_required
@transaction.atomic
def metrologia_eje_detalle(request, inspeccion_id):
    inspeccion = get_object_or_404(
        InspeccionEje.objects.select_related("paw", "plantilla", "camara", "realizado_por", "revisado_por"),
        pk=inspeccion_id,
    )
    mediciones = list(inspeccion.mediciones.select_related("punto", "instrumento").all())
    instrumentos = [i for i in InstrumentoMetrologico.objects.filter(activo=True, estado=InstrumentoMetrologico.Estado.ACTIVO).order_by("nombre", "codigo") if i.calibracion_vigente]

    if request.method == "POST" and inspeccion.estado == InspeccionEje.Estado.BORRADOR:
        hubo_error = False
        for medicion in mediciones:
            pref = f"m_{medicion.id}_"

            # Guardado incremental: un campo vacío o ausente NO borra una
            # medición que ya estaba almacenada. También aceptamos coma decimal.
            clave_valor = pref + "valor"
            if clave_valor in request.POST:
                valor_raw = request.POST.get(clave_valor, "").strip()
                if valor_raw:
                    valor_normalizado = valor_raw.replace(",", ".")
                    try:
                        medicion.valor = Decimal(valor_normalizado)
                    except (InvalidOperation, ValueError, TypeError):
                        messages.error(
                            request,
                            f"El valor del punto {medicion.punto.codigo} no es válido. "
                            "Use solo números, por ejemplo 0,003 o 0.003.",
                        )
                        hubo_error = True
                        continue

            clave_instrumento = pref + "instrumento"
            if clave_instrumento in request.POST:
                instrumento_id = request.POST.get(clave_instrumento, "").strip()
                if instrumento_id:
                    instrumento = InstrumentoMetrologico.objects.filter(pk=instrumento_id).first()
                    if not instrumento or not instrumento.disponible_para_medicion:
                        messages.error(request, f"El instrumento seleccionado para el punto {medicion.punto.codigo} no está disponible o tiene la calibración vencida.")
                        hubo_error = True
                        continue
                    medicion.instrumento = instrumento

            clave_instrumento_texto = pref + "instrumento_texto"
            if clave_instrumento_texto in request.POST:
                instrumento_texto = request.POST.get(clave_instrumento_texto, "").strip()
                if instrumento_texto:
                    medicion.instrumento_texto = instrumento_texto

            clave_observacion = pref + "observacion"
            if clave_observacion in request.POST:
                observacion = request.POST.get(clave_observacion, "").strip()
                if observacion:
                    medicion.observacion = observacion

            archivo = request.FILES.get(pref + "evidencia")
            if archivo:
                # El técnico puede tomar la foto directamente con el celular.
                # Guardamos una copia optimizada para no llenar el almacenamiento
                # con fotografías de varios MB y mantener buena lectura en PDF.
                if archivo.size > 20 * 1024 * 1024:
                    messages.error(
                        request,
                        f"La foto del punto {medicion.punto.codigo} supera 20 MB. "
                        "Seleccione una imagen más liviana.",
                    )
                    hubo_error = True
                else:
                    try:
                        medicion.evidencia = optimizar_foto_metrologia(archivo)
                    except ValueError:
                        messages.error(
                            request,
                            f"No fue posible procesar la foto del punto {medicion.punto.codigo}. "
                            "Use una imagen JPG, PNG o una foto tomada desde el navegador.",
                        )
                        hubo_error = True
            medicion.save()

        if hubo_error:
            # Conservamos lo válido que sí se alcanzó a guardar y regresamos al
            # formulario sin permitir que una revisión cierre datos incompletos.
            inspeccion.recalcular_resultado()
            return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

        inspeccion.recalcular_resultado()
        if "revisar" in request.POST:
            faltantes = [m for m in inspeccion.mediciones.select_related("punto") if m.punto.obligatorio and m.valor is None]
            if faltantes:
                messages.error(request, "Faltan mediciones obligatorias. Complete los puntos antes de revisar.")
            else:
                inspeccion.estado = InspeccionEje.Estado.REVISADA
                inspeccion.revisado_por = request.user
                inspeccion.fecha_revision = timezone.now()
                inspeccion.save(update_fields=["estado", "revisado_por", "fecha_revision", "actualizado_en"])
                messages.success(request, "Mediciones revisadas. Ya puede emitir el dictamen de Calidad.")
        else:
            messages.success(request, "Mediciones guardadas.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

    orden_mecanizado = OrdenMecanizadoEje.objects.filter(inspeccion_origen=inspeccion).first()
    return render(request, "taller/metrologia_eje_detalle.html", {
        "inspeccion": inspeccion,
        "mediciones": mediciones,
        "instrumentos": instrumentos,
        "orden_mecanizado": orden_mecanizado,
        "reinspecciones": inspeccion.reinspecciones.order_by("numero_inspeccion"),
    })


@login_required
@transaction.atomic
def metrologia_eje_dictamen(request, inspeccion_id):
    inspeccion = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    if inspeccion.estado == InspeccionEje.Estado.BORRADOR:
        messages.error(request, "Primero debe revisar las mediciones.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

    # Un dictamen cerrado puede corregirse mientras no haya iniciado el flujo
    # de mecanizado/reinspección. Después se conserva bloqueado como evidencia.
    if inspeccion.estado == InspeccionEje.Estado.CERRADA:
        tiene_orden = OrdenMecanizadoEje.objects.filter(inspeccion_origen=inspeccion).exists()
        tiene_reinspeccion = inspeccion.reinspecciones.exists()
        if tiene_orden or tiene_reinspeccion:
            messages.error(request, "El dictamen ya no puede cambiarse porque existe una orden de mecanizado o una reinspección asociada.")
            return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)

    if request.method == "POST":
        form = DictamenInspeccionEjeForm(request.POST, instance=inspeccion)
        if form.is_valid() and form.cleaned_data["dictamen"] != InspeccionEje.Dictamen.PENDIENTE:
            obj = form.save(commit=False)
            obj.estado = InspeccionEje.Estado.CERRADA
            obj.revisado_por = request.user
            obj.fecha_revision = timezone.now()
            obj.save()
            messages.success(request, "Dictamen de Calidad actualizado.")
            if obj.dictamen == InspeccionEje.Dictamen.MECANIZADO:
                messages.info(request, "La pieza requiere mecanizado. Ya puede crear la orden de mecanizado.")
                return redirect("taller:metrologia_eje_detalle", inspeccion_id=obj.id)
            return redirect("taller:metrologia_eje_reporte", inspeccion_id=obj.id)
    else:
        form = DictamenInspeccionEjeForm(instance=inspeccion)
    return render(request, "taller/metrologia_eje_dictamen.html", {"form": form, "inspeccion": inspeccion})


@login_required
def metrologia_eje_reporte(request, inspeccion_id):
    inspeccion = get_object_or_404(
        InspeccionEje.objects.select_related("paw", "plantilla", "realizado_por", "revisado_por"),
        pk=inspeccion_id,
    )
    mediciones = list(inspeccion.mediciones.select_related("punto", "instrumento").all())
    hay_evidencias = any(bool(m.evidencia) for m in mediciones)
    # Resumen único de los equipos físicos utilizados para trazabilidad metrológica.
    instrumentos_usados = []
    vistos = set()
    for m in mediciones:
        if m.instrumento_id and m.instrumento_id not in vistos:
            vistos.add(m.instrumento_id)
            instrumentos_usados.append(m.instrumento)
    return render(request, "taller/metrologia_eje_reporte.html", {
        "inspeccion": inspeccion,
        "mediciones": mediciones,
        "hay_evidencias": hay_evidencias,
        "instrumentos_usados": instrumentos_usados,
    })

@login_required
@require_POST
@transaction.atomic
def metrologia_mecanizado_crear(request, inspeccion_id):
    inspeccion = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    if inspeccion.estado != InspeccionEje.Estado.CERRADA or inspeccion.dictamen != InspeccionEje.Dictamen.MECANIZADO:
        messages.error(request, "La orden de mecanizado solo puede crearse desde una inspección cerrada con dictamen Requiere mecanizado.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    if hasattr(inspeccion, "orden_mecanizado"):
        messages.info(request, "Esta inspección ya tiene una orden de mecanizado.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    trabajo = request.POST.get("trabajo_requerido", "").strip()
    if not trabajo:
        messages.error(request, "Describa el trabajo de mecanizado requerido.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)
    OrdenMecanizadoEje.objects.create(
        inspeccion_origen=inspeccion,
        trabajo_requerido=trabajo,
        medida_objetivo=request.POST.get("medida_objetivo", "").strip(),
        responsable=request.user,
        creado_por=request.user,
    )
    messages.success(request, "Orden de mecanizado creada. La inspección original permanece bloqueada como evidencia.")
    return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)


@login_required
@require_POST
@transaction.atomic
def metrologia_mecanizado_terminar(request, inspeccion_id):
    inspeccion = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    orden = get_object_or_404(OrdenMecanizadoEje, inspeccion_origen=inspeccion)
    orden.observaciones_taller = request.POST.get("observaciones_taller", "").strip()
    orden.estado = OrdenMecanizadoEje.Estado.TERMINADO
    orden.terminado_en = timezone.now()
    orden.save(update_fields=["observaciones_taller", "estado", "terminado_en"])
    messages.success(request, "Mecanizado marcado como terminado. Ya puede crear la reinspección.")
    return redirect("taller:metrologia_eje_detalle", inspeccion_id=inspeccion.id)


@login_required
@require_POST
@transaction.atomic
def metrologia_reinspeccion_crear(request, inspeccion_id):
    origen = get_object_or_404(InspeccionEje, pk=inspeccion_id)
    orden = get_object_or_404(OrdenMecanizadoEje, inspeccion_origen=origen)
    if orden.estado != OrdenMecanizadoEje.Estado.TERMINADO:
        messages.error(request, "Primero marque el mecanizado como terminado.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=origen.id)
    existente = origen.reinspecciones.order_by("-numero_inspeccion").first()
    if existente:
        messages.info(request, "Ya existe una reinspección creada para esta inspección.")
        return redirect("taller:metrologia_eje_detalle", inspeccion_id=existente.id)
    nueva = InspeccionEje.objects.create(
        paw=origen.paw, plantilla=origen.plantilla, camara=origen.camara,
        serial_equipo=origen.serial_equipo, serial_eje=origen.serial_eje, realizado_por=request.user,
        inspeccion_origen=origen, numero_inspeccion=origen.numero_inspeccion + 1,
    )
    for punto in origen.plantilla.puntos.all():
        MedicionEje.objects.create(inspeccion=nueva, punto=punto)
    orden.estado = OrdenMecanizadoEje.Estado.REINSPECCIONADO
    orden.save(update_fields=["estado"])
    messages.success(request, "Reinspección creada. Las mediciones originales se conservaron sin cambios.")
    return redirect("taller:metrologia_eje_detalle", inspeccion_id=nueva.id)
