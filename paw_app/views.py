from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Q

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
def cerrar_paw_antiguo(request, paw_id):
    if not tiene_rol(request.user, ["ADMIN"]):
        messages.error(request, "No tienes permiso para cerrar PAW antiguos.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":
        from workorders.models import WorkOrder

        with transaction.atomic():
            # Cierre administrativo del PAW legado.
            # No crea BOM, compras, entregas, ensambles ni servicios faltantes.
            paw.estado_operativo = "FACTURADO"
            paw.save(update_fields=["estado_operativo", "actualizado_en"])

            # Toda OT asociada queda cerrada administrativamente para que no siga
            # apareciendo como pendiente en módulos operativos.
            ots_cerradas = paw.ots.exclude(
                estado__in=[
                    WorkOrder.Status.TERMINADA,
                    WorkOrder.Status.CERRADA,
                ]
            ).update(
                estado=WorkOrder.Status.CERRADA,
            )

        messages.success(
            request,
            (
                f"PAW {paw.numero_paw} cerrado y enviado al historial. "
                f"Se cerraron administrativamente {ots_cerradas} OT pendientes; "
                "los pasos omitidos no fueron creados ni marcados como ejecutados."
            ),
        )
        return redirect("paw_historial")

    return redirect("paw_detail", paw_id=paw.id)

@login_required
def paw_historial(request):
    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    criticidad = request.GET.get("criticidad", "").strip()
    gestion = request.GET.get("gestion", "").strip()

    estados_historial = [
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    ]

    # Historial: PAW que ya salieron del tablero operativo.
    # También se incluyen los que tienen factura asociada, aunque el estado no se haya sincronizado.
    paws = (
        Paw.objects
        .select_related("cotizacion", "creado_por")
        .filter(Q(estado_operativo__in=estados_historial) | Q(factura__isnull=False))
    )

    if query:
        paws = paws.filter(
            Q(numero_paw__icontains=query) |
            Q(nombre_paw__icontains=query) |
            Q(cliente__icontains=query) |
            Q(campo__icontains=query) |
            Q(cotizacion__numero_cotizacion__icontains=query) |
            Q(cotizacion__nombre_cotizacion__icontains=query)
        )

    if estado:
        paws = paws.filter(estado_operativo=estado)

    if criticidad:
        paws = paws.filter(criticidad=criticidad)

    if gestion:
        paws = paws.filter(estado_gestion=gestion)

    paws = paws.order_by("-actualizado_en")

    return render(request, "paw_app/paw_historial.html", {
        "paws": paws,
        "query": query,
        "estado": estado,
        "criticidad": criticidad,
        "gestion": gestion,
        "estados_historial": estados_historial,
        "criticidades": Criticidad.choices,
        "estados_gestion": EstadoGestion.choices,
    })

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
def actualizar_alcance_paw(request, paw_id):
    if not tiene_rol(request.user, ["ADMIN", "GERENTE", "INGENIERIA"]):
        messages.error(request, "No tienes permiso para cambiar el alcance del PAW.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":

        paw.requiere_taller = "requiere_taller" in request.POST
        paw.requiere_campo = "requiere_campo" in request.POST
        paw.requiere_compras = "requiere_compras" in request.POST

        if not paw.requiere_taller and not paw.requiere_campo and not paw.requiere_compras:
            messages.error(
                request,
                "Debe seleccionar al menos un alcance para el PAW.",
            )
            return redirect("paw_detail", paw_id=paw.id)

        # IMPORTANTE:
        # Todavía NO modificamos tipo_operacion.
        # Se conserva para proteger el funcionamiento de los PAW existentes.

        paw.save(
            update_fields=[
                "requiere_taller",
                "requiere_campo",
                "requiere_compras",
                "actualizado_en",
            ]
        )

        messages.success(
            request,
            f"Alcance del PAW {paw.numero_paw} actualizado correctamente."
        )

    return redirect("paw_detail", paw_id=paw.id)

@login_required
def paw_list(request):
    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    criticidad = request.GET.get("criticidad", "").strip()
    gestion = request.GET.get("gestion", "").strip()

    estados_historial = [
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    ]

    paws = Paw.objects.select_related("cotizacion", "creado_por")

    # Dashboard limpio: no mostrar PAW ya enviados a facturación, radicados o facturados.
    # También se excluyen los que ya tengan factura asociada.
    paws = paws.exclude(
        Q(estado_operativo__in=estados_historial) | Q(factura__isnull=False)
    )

    # Filtro tipo cotizaciones: busca por PAW, nombre, cliente, campo y cotización.
    if query:
        paws = paws.filter(
            Q(numero_paw__icontains=query) |
            Q(nombre_paw__icontains=query) |
            Q(cliente__icontains=query) |
            Q(campo__icontains=query) |
            Q(cotizacion__numero_cotizacion__icontains=query) |
            Q(cotizacion__nombre_cotizacion__icontains=query)
        )

    if estado:
        paws = paws.filter(estado_operativo=estado)

    if criticidad:
        paws = paws.filter(criticidad=criticidad)

    if gestion:
        paws = paws.filter(estado_gestion=gestion)

    paws = paws.order_by("criticidad", "estado_gestion", "-creado_en")

    return render(request, "paw_app/paw_list.html", {
        "paws": paws,
        "query": query,
        "estado": estado,
        "criticidad": criticidad,
        "gestion": gestion,
        "criticidades": Criticidad.choices,
        "estados_gestion": EstadoGestion.choices,
    })

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
def activar_seguimiento_publico(request, paw_id):
    if not tiene_rol(
        request.user,
        ["ADMIN", "GERENTE", "INGENIERIA", "TALLER"]
    ):
        messages.error(
            request,
            "No tienes permiso para administrar el seguimiento público."
        )
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":
        from datetime import timedelta

        paw.seguimiento_publico_activo = True

        # Mientras el PAW esté abierto dejamos el enlace sin vencimiento.
        paw.seguimiento_publico_vence = None

        paw.save(
            update_fields=[
                "seguimiento_publico_activo",
                "seguimiento_publico_vence",
                "actualizado_en",
            ]
        )

        messages.success(
            request,
            f"Seguimiento público del PAW {paw.numero_paw} activado."
        )

    return redirect("paw_detail", paw_id=paw.id)


@login_required
def desactivar_seguimiento_publico(request, paw_id):
    if not tiene_rol(
        request.user,
        ["ADMIN", "GERENTE", "INGENIERIA", "TALLER"]
    ):
        messages.error(
            request,
            "No tienes permiso para administrar el seguimiento público."
        )
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if request.method == "POST":
        paw.seguimiento_publico_activo = False

        paw.save(
            update_fields=[
                "seguimiento_publico_activo",
                "actualizado_en",
            ]
        )

        messages.success(
            request,
            f"Seguimiento público del PAW {paw.numero_paw} desactivado."
        )

    return redirect("paw_detail", paw_id=paw.id)

def seguimiento_publico(request, token):

    paw = get_object_or_404(
        Paw.objects.select_related(
            "cotizacion",
            "creado_por",
        ).prefetch_related("ots"),
        public_token=token,
    )

    if not paw.seguimiento_publico_activo:
        return render(
            request,
            "paw_app/seguimiento_publico.html",
            {
                "seguimiento_inactivo": True,
            },
            status=404,
        )

    seguimiento_vencido = False

    if paw.seguimiento_publico_vence:
        if timezone.now() > paw.seguimiento_publico_vence:
            seguimiento_vencido = True

    if seguimiento_vencido:
        return render(
            request,
            "paw_app/seguimiento_publico.html",
            {
                "paw": paw,
                "seguimiento_vencido": True,
            },
        )

    ot = paw.ots.first()

    tiene_ot = bool(ot)

    tiene_bom = bool(
        ot and getattr(ot, "bom", None)
    )

    estado = paw.estado_operativo

    paso_recibido = True
    paso_inspeccion = tiene_ot
    paso_diagnostico = tiene_bom

    estados_repuestos = {
        "EN_COMPRAS",
        "EN_FINANZAS",
        "EN_APROBACION",
        "PAGO_OK",
        "MATERIAL_RECIBIDO",
        "ENTREGADO_TALLER",
        "PRODUCTO_OK",
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    }

    paso_repuestos = (
        not paw.aplica_compras
        or estado in estados_repuestos
    )

    estados_reparacion = {
        "ENTREGADO_TALLER",
        "PRODUCTO_OK",
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    }

    paso_reparacion = (
        not paw.aplica_taller
        or estado in estados_reparacion
    )

    estados_pruebas = {
        "PRODUCTO_OK",
        "EN_FACTURACION",
        "FACTURADO",
        "RADICADO",
    }

    paso_pruebas = (
        not paw.aplica_taller
        or estado in estados_pruebas
    )

    paso_finalizado = (
        paw.listo_para_facturar
        or estado in {
            "EN_FACTURACION",
            "FACTURADO",
            "RADICADO",
        }
    )

    if paso_finalizado:
        etapa_actual = 7
        estado_publico = "Servicio finalizado"
        titulo_actual = "Servicio finalizado"
        descripcion_actual = (
            "El proceso técnico asociado a este equipo "
            "ha sido completado."
        )

    elif paso_pruebas:
        etapa_actual = 6
        estado_publico = "Pruebas finales"
        titulo_actual = "Pruebas y validación"
        descripcion_actual = (
            "El equipo se encuentra en proceso de pruebas "
            "y validación final."
        )

    elif paso_reparacion:
        etapa_actual = 5
        estado_publico = "Reparación en proceso"
        titulo_actual = "Reparación / Ensamble"
        descripcion_actual = (
            "Nuestro equipo técnico se encuentra ejecutando "
            "el proceso de reparación y ensamble."
        )

    elif paso_repuestos:
        etapa_actual = 4
        estado_publico = "Gestión de repuestos"
        titulo_actual = "Gestión de repuestos"
        descripcion_actual = (
            "Los componentes necesarios para continuar "
            "el proceso se encuentran en gestión."
        )

    elif paso_diagnostico:
        etapa_actual = 3
        estado_publico = "Diagnóstico técnico"
        titulo_actual = "Diagnóstico"
        descripcion_actual = (
            "Se está evaluando técnicamente el equipo y "
            "definiendo el alcance de la intervención."
        )

    elif paso_inspeccion:
        etapa_actual = 2
        estado_publico = "Inspección"
        titulo_actual = "Inspección inicial"
        descripcion_actual = (
            "El equipo se encuentra en proceso de inspección "
            "y evaluación inicial."
        )

    else:
        etapa_actual = 1
        estado_publico = "Equipo recibido"
        titulo_actual = "Recepción"
        descripcion_actual = (
            "El equipo ha sido registrado y recibido "
            "para iniciar el proceso técnico."
        )

    etapas = [
        {"numero": 1, "nombre": "Recibido", "completo": paso_recibido},
        {"numero": 2, "nombre": "Inspección", "completo": paso_inspeccion},
        {"numero": 3, "nombre": "Diagnóstico", "completo": paso_diagnostico},
        {"numero": 4, "nombre": "Repuestos", "completo": paso_repuestos},
        {"numero": 5, "nombre": "Reparación", "completo": paso_reparacion},
        {"numero": 6, "nombre": "Pruebas", "completo": paso_pruebas},
        {"numero": 7, "nombre": "Finalizado", "completo": paso_finalizado},
    ]

    contexto = {
        "paw": paw,
        "etapas": etapas,
        "etapa_actual": etapa_actual,
        "estado_publico": estado_publico,
        "titulo_actual": titulo_actual,
        "descripcion_actual": descripcion_actual,
    }

    return render(
        request,
        "paw_app/seguimiento_publico.html",
        contexto,
    )


@login_required
def paw_detail(request, paw_id):
    paw = get_object_or_404(
        Paw.objects.select_related("cotizacion", "creado_por"),
        id=paw_id,
    )

    if tiene_rol(request.user, ["CAMPO"]) and not request.user.is_superuser:
        if not paw.aplica_campo:
            messages.error(
                request,
                "No tienes acceso a este PAW porque no incluye servicio en campo."
            )
            return redirect("campo:dashboard")

    return render(
        request,
        "paw_app/paw_detail.html",
        {"paw": paw}
    )
@login_required
def paw_detail(request, paw_id):
    paw = get_object_or_404(
        Paw.objects.select_related("cotizacion", "creado_por"),
        id=paw_id,
    )

    if tiene_rol(request.user, ["CAMPO"]) and not request.user.is_superuser:
        if not paw.aplica_campo:
            messages.error(request, "No tienes acceso a este PAW porque no incluye servicio en campo.")
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
        requiere_taller = "requiere_taller" in request.POST
        requiere_campo = "requiere_campo" in request.POST
        requiere_compras = "requiere_compras" in request.POST

        # El PAW debe tener al menos un alcance seleccionado.
        if not requiere_taller and not requiere_campo and not requiere_compras:
            messages.error(
                request,
                "Debe seleccionar al menos un alcance para crear el PAW.",
            )
            return render(request, "paw_app/crear_paw.html", {
                "cotizacion": cotizacion,
            })

        # Compatibilidad con la lógica histórica.
        # Solo campo conserva SERVICIO_CAMPO. Cualquier alcance con Taller,
        # o solo Compras, conserva ENSAMBLE mientras terminamos la migración.
        if requiere_campo and not requiere_taller:
            tipo_operacion = Paw.TipoOperacion.SERVICIO_CAMPO
        else:
            tipo_operacion = Paw.TipoOperacion.ENSAMBLE

        try:
            with transaction.atomic():
                numero_paw = obtener_siguiente_numero_paw()

                paw = Paw.objects.create(
                    numero_paw=numero_paw,
                    cotizacion=cotizacion,
                    creado_por=request.user,
                    tipo_operacion=tipo_operacion,
                    requiere_taller=requiere_taller,
                    requiere_campo=requiere_campo,
                    requiere_compras=requiere_compras,
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
    })


@login_required
def iniciar_servicio_campo(request, paw_id):
    if not tiene_rol(request.user, ["CAMPO", "INGENIERIA", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para iniciar servicios de campo.")
        return redirect("paw_detail", paw_id=paw_id)

    from campo.models import FieldService

    paw = get_object_or_404(Paw, id=paw_id)

    if not paw.aplica_campo:
        messages.error(
            request,
            "Este PAW no tiene habilitado el alcance de instalación / servicio en campo.",
        )
        return redirect("paw_detail", paw_id=paw.id)

    if paw.aplica_taller and not paw.taller_finalizado:
        messages.error(
            request,
            "Primero debe finalizar el trabajo de Taller antes de iniciar el servicio en campo.",
        )
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

    if not paw.aplica_taller:
        messages.error(
            request,
            "Este PAW no tiene habilitado el alcance de Taller / reparación.",
        )
        return redirect("paw_detail", paw_id=paw.id)

    if paw.estado_operativo != "ENTREGADO_TALLER":
        messages.error(request, "No puede marcar producto OK hasta registrar ensamble.")
        return redirect("paw_detail", paw_id=paw.id)

    paw.estado_operativo = "PRODUCTO_OK"
    paw.save(update_fields=["estado_operativo"])

    if paw.listo_para_facturar:
        messages.success(
            request,
            "Trabajo de Taller finalizado. El PAW quedó listo para facturación.",
        )
    elif paw.aplica_campo:
        messages.success(
            request,
            "Trabajo de Taller finalizado. El PAW queda pendiente de instalación / servicio en campo.",
        )
    else:
        messages.success(request, "Producto marcado como OK.")

    return redirect("paw_detail", paw_id=paw.id)


@login_required
def registrar_ensamble(request, paw_id):
    if not tiene_rol(request.user, ["TALLER", "INGENIERIA", "GERENTE", "ADMIN"]):
        messages.error(request, "No tienes permiso para registrar ensamble.")
        return redirect("paw_detail", paw_id=paw_id)

    paw = get_object_or_404(Paw, id=paw_id)

    if not paw.aplica_taller:
        messages.error(
            request,
            "Este PAW no tiene habilitado el alcance de Taller / reparación.",
        )
        return redirect("paw_detail", paw_id=paw.id)

    if paw.aplica_compras and paw.estado_operativo != "MATERIAL_RECIBIDO":
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