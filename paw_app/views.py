from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Max

from core.roles import tiene_rol
from .models import Paw, Criticidad, EstadoGestion
from quotes.models import Quotation


def obtener_siguiente_numero_paw():
    numeros = Paw.objects.exclude(
        numero_paw__isnull=True
    ).exclude(
        numero_paw=""
    ).values_list("numero_paw", flat=True)

    mayor = 0

    for numero in numeros:
        try:
            numero_int = int(str(numero).strip())
            if numero_int > mayor:
                mayor = numero_int
        except (TypeError, ValueError):
            continue

    siguiente = mayor + 1

    while Paw.objects.filter(numero_paw=str(siguiente)).exists():
        siguiente += 1

    return str(siguiente)


@login_required
def cambiar_tipo_operacion(request, paw_id):
    if not tiene_rol(request.user, ["ADMIN", "GERENTE", "INGENIERIA"]):
        messages.error(request, "No tienes permiso para cambiar el tipo de operación.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":
        tipo_operacion = request.POST.get("tipo_operacion")

        if tipo_operacion not in [
            Paw.TipoOperacion.ENSAMBLE,
            Paw.TipoOperacion.SERVICIO_CAMPO,
        ]:
            messages.error(request, "Tipo de operación no válido.")
            return redirect("paw_detail", paw_id=paw.id)

        paw.tipo_operacion = tipo_operacion
        paw.save(update_fields=["tipo_operacion", "actualizado_en"])

        messages.success(request, "Tipo de operación actualizado correctamente.")
        return redirect("paw_detail", paw_id=paw.id)

    return redirect("paw_detail", paw_id=paw.id)


@login_required
def paw_list(request):
    paws = Paw.objects.select_related("cotizacion", "creado_por").order_by("-creado_en")

    if tiene_rol(request.user, ["CAMPO"]) and not request.user.is_superuser:
        paws = paws.filter(tipo_operacion=Paw.TipoOperacion.SERVICIO_CAMPO)

    return render(request, "paw_app/paw_list.html", {"paws": paws})

@login_required
def actualizar_gestion_paw(request, paw_id):
    if not tiene_rol(request.user, ["ADMIN", "GERENTE", "INGENIERIA", "TALLER"]):
        messages.error(request, "No tienes permiso para actualizar la gestión del PAW.")
        return redirect("paw_list")

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":
        criticidad = request.POST.get("criticidad")
        estado_gestion = request.POST.get("estado_gestion")

        criticidades_validas = [choice[0] for choice in Criticidad.choices]
        estados_validos = [choice[0] for choice in EstadoGestion.choices]

        if criticidad in criticidades_validas:
            paw.criticidad = criticidad

        if estado_gestion in estados_validos:
            paw.estado_gestion = estado_gestion

        paw.save(update_fields=["criticidad", "estado_gestion", "actualizado_en"])
        messages.success(request, f"PAW {paw.numero_paw} actualizado correctamente.")

    return redirect("paw_list")

@login_required
def paw_detail(request, paw_id):
    paw = get_object_or_404(
        Paw.objects.select_related("cotizacion", "creado_por"),
        id=paw_id,
    )

    if tiene_rol(request.user, ["CAMPO"]) and not request.user.is_superuser:
        if paw.tipo_operacion != Paw.TipoOperacion.SERVICIO_CAMPO:
            messages.error(request, "No tienes acceso a este PAW.")
            return redirect("campo:dashboard")

    return render(request, "paw_app/paw_detail.html", {"paw": paw})


@login_required
def crear_paw(request, cotizacion_id):
    if not tiene_rol(request.user, ["COMERCIAL", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para crear PAW.")
        return redirect("/paw/")

    cotizacion = get_object_or_404(Quotation, id=cotizacion_id)

    paw_existente = Paw.objects.filter(cotizacion=cotizacion).first()
    if paw_existente:
        messages.warning(request, "Esta cotización ya tiene un PAW generado.")
        return redirect("paw_detail", paw_id=paw_existente.id)

    if request.method == "POST":
        tipo_operacion = request.POST.get("tipo_operacion") or Paw.TipoOperacion.ENSAMBLE

        tipos_validos = [choice[0] for choice in Paw.TipoOperacion.choices]
        if tipo_operacion not in tipos_validos:
            tipo_operacion = Paw.TipoOperacion.ENSAMBLE

        try:
            with transaction.atomic():
                numero_paw = obtener_siguiente_numero_paw()

                paw = Paw.objects.create(
                    numero_paw=numero_paw,
                    cotizacion=cotizacion,
                    creado_por=request.user,
                    tipo_operacion=tipo_operacion,
                )

        except IntegrityError:
            messages.error(
                request,
                "No se pudo generar el PAW porque el consecutivo ya existía. Intente nuevamente.",
            )
            return redirect("crear_paw", cotizacion_id=cotizacion.id)

        messages.success(request, f"PAW {paw.numero_paw} creado correctamente.")
        return redirect("paw_detail", paw_id=paw.id)

    return render(request, "paw_app/crear_paw.html", {
        "cotizacion": cotizacion,
        "tipos_operacion": Paw.TipoOperacion.choices,
    })


@login_required
def iniciar_servicio_campo(request, paw_id):
    if not tiene_rol(request.user, ["CAMPO", "INGENIERIA", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para iniciar servicios de campo.")
        return redirect("paw_detail", paw_id=paw_id)

    from campo.models import FieldService

    paw = get_object_or_404(Paw, id=paw_id)

    if paw.tipo_operacion != Paw.TipoOperacion.SERVICIO_CAMPO:
        messages.error(request, "Este PAW no está marcado como servicio técnico en campo.")
        return redirect("paw_detail", paw_id=paw.id)

    servicio, created = FieldService.objects.get_or_create(
        paw=paw,
        defaults={
            "responsable": request.user,
            "estado": FieldService.Estado.EN_CURSO,
        },
    )

    if created:
        messages.success(request, "Servicio de campo iniciado correctamente.")
    else:
        messages.info(request, "Este PAW ya tiene un servicio de campo iniciado.")

    return redirect("campo:detalle_servicio", servicio_id=servicio.id)


@login_required
def marcar_producto_ok(request, paw_id):
    if not tiene_rol(request.user, ["TALLER", "INGENIERIA", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para marcar producto OK.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if paw.tipo_operacion == Paw.TipoOperacion.SERVICIO_CAMPO:
        messages.error(
            request,
            "Este PAW es de servicio de campo. Debes finalizar el servicio desde el módulo Campo.",
        )
        return redirect("paw_detail", paw_id=paw.id)

    if paw.estado_operativo != "ENTREGADO_TALLER":
        messages.error(request, "No puede marcar producto OK hasta registrar ensamble.")
        return redirect("paw_detail", paw_id=paw.id)

    paw.estado_operativo = "PRODUCTO_OK"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Producto marcado como OK.")
    return redirect("paw_detail", paw_id=paw.id)


@login_required
def registrar_ensamble(request, paw_id):
    if not tiene_rol(request.user, ["TALLER", "INGENIERIA", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para registrar ensamble.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if paw.tipo_operacion == Paw.TipoOperacion.SERVICIO_CAMPO:
        messages.error(
            request,
            "Este PAW es de servicio de campo. Usa la opción Iniciar instalación.",
        )
        return redirect("paw_detail", paw_id=paw.id)

    if paw.estado_operativo != "MATERIAL_RECIBIDO":
        messages.error(request, "No puede registrar ensamble hasta que el material esté recibido.")
        return redirect("paw_detail", paw_id=paw.id)

    paw.estado_operativo = "ENTREGADO_TALLER"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Ensamble registrado correctamente.")
    return redirect("paw_detail", paw_id=paw.id)

@login_required
def eliminar_paw(request, paw_id):
    if not tiene_rol(request.user, ["ADMIN"]):
        messages.error(request, "No tienes permisos para eliminar PAW.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":
        numero = paw.numero_paw
        paw.delete()

        messages.success(request, f"PAW {numero} eliminado correctamente.")
        return redirect("paw_list")

    return render(request, "paw_app/eliminar_paw.html", {
        "paw": paw
    })