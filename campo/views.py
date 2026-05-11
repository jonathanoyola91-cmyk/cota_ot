from collections import defaultdict
from decimal import Decimal
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from .forms import AsignarTecnicosForm, FieldServiceDailyExpenseForm
from .models import (
    BONO_APOYO,
    BONO_LIDER,
    BONO_MOVILIZACION_PERSONA,
    FieldService,
    FieldServiceDailyExpense,
    FieldServicePersonExpense,
)


def _puede_campo(user):
    return tiene_rol(user, ["CAMPO", "INGENIERIA", "GERENTE", "ADMIN"])


def _puede_ver_gastos(user):
    return tiene_rol(user, ["FINANZAS", "GERENTE", "ADMIN"])


def _siguiente_dia(servicio):
    ultimo = servicio.gastos.order_by("-dia_numero", "-id").first()
    return (ultimo.dia_numero + 1) if ultimo else 1


def _periodo_corte_27(fecha_base):
    """
    Calcula el periodo de corte:
    - Si hoy es <= 27: desde el 28 del mes anterior hasta el 27 del mes actual.
    - Si hoy es > 27: desde el 28 del mes actual hasta el 27 del mes siguiente.
    """
    if fecha_base.day <= 27:
        if fecha_base.month == 1:
            fecha_inicio = date(fecha_base.year - 1, 12, 28)
        else:
            fecha_inicio = date(fecha_base.year, fecha_base.month - 1, 28)

        fecha_fin = date(fecha_base.year, fecha_base.month, 27)

    else:
        fecha_inicio = date(fecha_base.year, fecha_base.month, 28)

        if fecha_base.month == 12:
            fecha_fin = date(fecha_base.year + 1, 1, 27)
        else:
            fecha_fin = date(fecha_base.year, fecha_base.month + 1, 27)

    return fecha_inicio, fecha_fin


def _parse_fecha(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _to_decimal(value):
    if value in [None, ""]:
        return Decimal("0.00")

    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return Decimal("0.00")


def _to_bool(value):
    return str(value).lower() in ["1", "true", "on", "yes", "si", "sí"]


def _tecnicos_base(servicio, cantidad=None):
    tecnicos = []

    if servicio.especialista_lider:
        tecnicos.append(servicio.especialista_lider)

    if servicio.especialista_apoyo and servicio.especialista_apoyo not in tecnicos:
        tecnicos.append(servicio.especialista_apoyo)

    cantidad = int(cantidad or len(tecnicos) or 1)

    while len(tecnicos) < cantidad:
        tecnicos.append("")

    return tecnicos[:cantidad]


def _clasificacion_desde_flags(dia_trabajado, salida_tarde, regreso_tarde, solo_viaje):
    if solo_viaje:
        return FieldServicePersonExpense.Clasificacion.SOLO_VIAJE_TRASLADO
    if dia_trabajado and regreso_tarde:
        return FieldServicePersonExpense.Clasificacion.REGRESO_DESPUES_6PM
    if dia_trabajado:
        return FieldServicePersonExpense.Clasificacion.DIA_TRABAJADO_CAMPO
    if regreso_tarde:
        return FieldServicePersonExpense.Clasificacion.REGRESO_DESPUES_6PM
    if salida_tarde:
        return FieldServicePersonExpense.Clasificacion.SALIDA_DESPUES_MEDIODIA
    return FieldServicePersonExpense.Clasificacion.DIA_TRABAJADO_CAMPO


def _clasificacion_texto_item(item):
    etiquetas = []
    if item.get("dia_trabajado_campo"):
        etiquetas.append("Día trabajado en campo")
    if item.get("salida_despues_mediodia"):
        etiquetas.append("Salida después del mediodía")
    if item.get("regreso_despues_6pm"):
        etiquetas.append("Regreso después de las 6:00 pm")
    if item.get("solo_viaje_traslado"):
        etiquetas.append("Solo viaje / traslado")
    return " + ".join(etiquetas) if etiquetas else "Sin clasificación"


def _detalle_personas_inicial(servicio, cantidad=None):
    detalle = []

    for tecnico in _tecnicos_base(servicio, cantidad):
        detalle.append({
            "persona": tecnico,
            "clasificacion": FieldServicePersonExpense.Clasificacion.DIA_TRABAJADO_CAMPO,
            "dia_trabajado_campo": True,
            "salida_despues_mediodia": False,
            "regreso_despues_6pm": False,
            "solo_viaje_traslado": False,
            "alojamiento": Decimal("0.00"),
            "alimentacion": Decimal("0.00"),
            "lavanderia": Decimal("0.00"),
            "transporte_personal": Decimal("0.00"),
            "vuelo_ida_aplica": False,
            "vuelo_ida_valor": Decimal("0.00"),
            "vuelo_regreso_aplica": False,
            "vuelo_regreso_valor": Decimal("0.00"),
            "observaciones": "",
        })

    return detalle


def _detalle_personas_existente(gasto):
    detalle = []

    for linea in gasto.detalle_personas.all():
        detalle.append({
            "persona": linea.persona,
            "clasificacion": linea.clasificacion,
            "dia_trabajado_campo": linea.dia_trabajado_campo,
            "salida_despues_mediodia": linea.salida_despues_mediodia,
            "regreso_despues_6pm": linea.regreso_despues_6pm,
            "solo_viaje_traslado": linea.solo_viaje_traslado,
            "alojamiento": linea.alojamiento,
            "alimentacion": linea.alimentacion,
            "lavanderia": linea.lavanderia,
            "transporte_personal": linea.transporte_personal,
            "vuelo_ida_aplica": linea.vuelo_ida_aplica,
            "vuelo_ida_valor": linea.vuelo_ida_valor,
            "vuelo_regreso_aplica": linea.vuelo_regreso_aplica,
            "vuelo_regreso_valor": linea.vuelo_regreso_valor,
            "observaciones": linea.observaciones,
        })

    if not detalle:
        detalle = _detalle_personas_inicial(gasto.servicio, gasto.personas)

    return detalle


def _leer_detalle_personas_post(request):
    personas = request.POST.getlist("persona[]")
    alojamientos = request.POST.getlist("alojamiento_persona[]")
    alimentaciones = request.POST.getlist("alimentacion_persona[]")
    lavanderias = request.POST.getlist("lavanderia_persona[]")
    transportes_personales = request.POST.getlist("transporte_personal[]")
    vuelos_ida_aplica = request.POST.getlist("vuelo_ida_aplica[]")
    vuelos_ida_valor = request.POST.getlist("vuelo_ida_valor[]")
    vuelos_regreso_aplica = request.POST.getlist("vuelo_regreso_aplica[]")
    vuelos_regreso_valor = request.POST.getlist("vuelo_regreso_valor[]")
    observaciones = request.POST.getlist("observacion_persona[]")

    total = max(
        len(personas),
        len(alojamientos),
        len(alimentaciones),
        len(lavanderias),
        len(transportes_personales),
        len(vuelos_ida_valor),
        len(vuelos_regreso_valor),
        0,
    )

    detalle = []

    for index in range(total):
        persona = personas[index].strip() if index < len(personas) else ""

        if not persona:
            continue

        dia_trabajado = _to_bool(request.POST.get(f"dia_trabajado_campo_{index}", False))
        salida_tarde = _to_bool(request.POST.get(f"salida_despues_mediodia_{index}", False))
        regreso_tarde = _to_bool(request.POST.get(f"regreso_despues_6pm_{index}", False))
        solo_viaje = _to_bool(request.POST.get(f"solo_viaje_traslado_{index}", False))

        if solo_viaje:
            dia_trabajado = False
            regreso_tarde = False
            salida_tarde = False

        clasificacion = _clasificacion_desde_flags(
            dia_trabajado,
            salida_tarde,
            regreso_tarde,
            solo_viaje,
        )

        detalle.append({
            "persona": persona,
            "clasificacion": clasificacion,
            "dia_trabajado_campo": dia_trabajado,
            "salida_despues_mediodia": salida_tarde,
            "regreso_despues_6pm": regreso_tarde,
            "solo_viaje_traslado": solo_viaje,
            "alojamiento": _to_decimal(alojamientos[index] if index < len(alojamientos) else 0),
            "alimentacion": _to_decimal(alimentaciones[index] if index < len(alimentaciones) else 0),
            "lavanderia": _to_decimal(lavanderias[index] if index < len(lavanderias) else 0),
            "transporte_personal": _to_decimal(transportes_personales[index] if index < len(transportes_personales) else 0),
            "vuelo_ida_aplica": _to_bool(vuelos_ida_aplica[index] if index < len(vuelos_ida_aplica) else False),
            "vuelo_ida_valor": _to_decimal(vuelos_ida_valor[index] if index < len(vuelos_ida_valor) else 0),
            "vuelo_regreso_aplica": _to_bool(vuelos_regreso_aplica[index] if index < len(vuelos_regreso_aplica) else False),
            "vuelo_regreso_valor": _to_decimal(vuelos_regreso_valor[index] if index < len(vuelos_regreso_valor) else 0),
            "observaciones": observaciones[index].strip() if index < len(observaciones) else "",
        })

    return detalle


def _guardar_detalle_personas(gasto, detalle):
    gasto.detalle_personas.all().delete()

    for item in detalle:
        FieldServicePersonExpense.objects.create(
            gasto_diario=gasto,
            persona=item["persona"],
            clasificacion=item["clasificacion"],
            dia_trabajado_campo=item["dia_trabajado_campo"],
            salida_despues_mediodia=item["salida_despues_mediodia"],
            regreso_despues_6pm=item["regreso_despues_6pm"],
            solo_viaje_traslado=item["solo_viaje_traslado"],
            alojamiento=item["alojamiento"],
            alimentacion=item["alimentacion"],
            lavanderia=item["lavanderia"],
            transporte_personal=item["transporte_personal"],
            vuelo_ida_aplica=item["vuelo_ida_aplica"],
            vuelo_ida_valor=item["vuelo_ida_valor"],
            vuelo_regreso_aplica=item["vuelo_regreso_aplica"],
            vuelo_regreso_valor=item["vuelo_regreso_valor"],
            observaciones=item["observaciones"],
        )


def _sincronizar_campos_legados_bonos(gasto, detalle):
    """
    Mantiene los campos anteriores sincronizados para no romper pantallas/reportes
    que todavía miren los booleanos del gasto diario.
    """
    gasto.dia_trabajado_campo = any(item["dia_trabajado_campo"] for item in detalle)
    gasto.salida_despues_mediodia = any(item["salida_despues_mediodia"] for item in detalle)
    gasto.regreso_despues_6pm = any(item["regreso_despues_6pm"] for item in detalle)
    gasto.solo_viaje_traslado = bool(
        detalle
        and all(item["solo_viaje_traslado"] for item in detalle)
        and not gasto.dia_trabajado_campo
        and not gasto.regreso_despues_6pm
    )

    gasto.personas = max(len(detalle), 1)

    gasto.save(update_fields=[
        "dia_trabajado_campo",
        "salida_despues_mediodia",
        "regreso_despues_6pm",
        "solo_viaje_traslado",
        "personas",
        "actualizado_en",
    ])


def _bono_campo_persona(servicio, persona, dia_trabajado_campo):
    if not dia_trabajado_campo:
        return Decimal("0.00")

    if persona == servicio.especialista_lider:
        return BONO_LIDER

    if persona == servicio.especialista_apoyo:
        return BONO_APOYO

    return Decimal("0.00")


def _bono_movilizacion_persona(salida_despues_mediodia, regreso_despues_6pm, solo_viaje_traslado):
    if salida_despues_mediodia or regreso_despues_6pm or solo_viaje_traslado:
        return BONO_MOVILIZACION_PERSONA

    return Decimal("0.00")


@login_required
def reporte_bonos_empleado(request):
    if not _puede_ver_gastos(request.user):
        messages.error(request, "No tienes acceso al reporte de bonos.")
        return redirect("/")

    tecnico = request.GET.get("tecnico")
    fecha_inicio = _parse_fecha(request.GET.get("fecha_inicio"))
    fecha_fin = _parse_fecha(request.GET.get("fecha_fin"))

    if not tecnico or not fecha_inicio or not fecha_fin:
        messages.error(request, "Faltan datos para generar el reporte.")
        return redirect("campo:reporte_bonos")

    gastos = (
        FieldServiceDailyExpense.objects
        .select_related("servicio", "servicio__paw")
        .prefetch_related("detalle_personas")
        .filter(fecha__range=[fecha_inicio, fecha_fin])
        .order_by("fecha", "servicio__paw__numero_paw", "dia_numero")
    )

    detalle = []
    total = Decimal("0")
    dias_lider = 0
    dias_apoyo = 0
    dias_movilizacion = 0

    for gasto in gastos:
        servicio = gasto.servicio
        paw = servicio.paw

        lineas = list(gasto.detalle_personas.all())

        if lineas:
            for linea in lineas:
                if linea.persona != tecnico:
                    continue

                es_lider = servicio.especialista_lider == tecnico
                es_apoyo = servicio.especialista_apoyo == tecnico

                rol = "Técnico"
                if es_lider:
                    rol = "Especialista líder"
                elif es_apoyo:
                    rol = "Especialista apoyo"

                bono_campo = _bono_campo_persona(servicio, tecnico, linea.dia_trabajado_campo)
                bono_movilizacion = _bono_movilizacion_persona(linea.salida_despues_mediodia, linea.regreso_despues_6pm, linea.solo_viaje_traslado)

                if bono_campo > 0:
                    if es_lider:
                        dias_lider += 1
                    elif es_apoyo:
                        dias_apoyo += 1

                if bono_movilizacion > 0:
                    dias_movilizacion += 1

                total_dia = bono_campo + bono_movilizacion

                if total_dia <= 0:
                    continue

                detalle.append({
                    "fecha": gasto.fecha,
                    "dia": gasto.dia_numero,
                    "paw": paw.numero_paw,
                    "nombre": paw.nombre_paw,
                    "campo": paw.campo,
                    "rol": rol,
                    "clasificacion": linea.clasificacion_texto,
                    "bono_campo": bono_campo,
                    "bono_movilizacion": bono_movilizacion,
                    "total_dia": total_dia,
                })

                total += total_dia

            continue

        es_lider = servicio.especialista_lider == tecnico
        es_apoyo = servicio.especialista_apoyo == tecnico

        if not es_lider and not es_apoyo:
            continue

        rol = "Especialista líder" if es_lider else "Especialista apoyo"
        bono_campo = Decimal("0")
        bono_movilizacion = Decimal("0")

        if es_lider and gasto.bono_lider > 0:
            bono_campo = Decimal(gasto.bono_lider or 0)
            dias_lider += 1

        if es_apoyo and gasto.bono_apoyo > 0:
            bono_campo = Decimal(gasto.bono_apoyo or 0)
            dias_apoyo += 1

        if gasto.aplica_bono_movilizacion:
            bono_movilizacion = BONO_MOVILIZACION_PERSONA
            dias_movilizacion += 1

        total_dia = bono_campo + bono_movilizacion

        # Si el técnico está asignado, pero ese día no tiene bono de campo ni movilización, no se lista.
        if total_dia <= 0:
            continue

        detalle.append({
            "fecha": gasto.fecha,
            "dia": gasto.dia_numero,
            "paw": paw.numero_paw,
            "nombre": paw.nombre_paw,
            "campo": paw.campo,
            "rol": rol,
            "clasificacion": "Registro anterior",
            "bono_campo": bono_campo,
            "bono_movilizacion": bono_movilizacion,
            "total_dia": total_dia,
        })

        total += total_dia

    return render(request, "campo/reporte_bonos_empleado.html", {
        "tecnico": tecnico,
        "detalle": detalle,
        "total": total,
        "dias_lider": dias_lider,
        "dias_apoyo": dias_apoyo,
        "dias_movilizacion": dias_movilizacion,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
    })


@login_required
def dashboard_campo(request):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes acceso al módulo Campo.")
        return redirect("/")

    servicios = (
        FieldService.objects
        .select_related("paw", "responsable")
        .prefetch_related("gastos")
        .order_by("-actualizado_en")
    )

    return render(request, "campo/dashboard.html", {
        "servicios": servicios,
    })


@login_required
def detalle_servicio(request, servicio_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes acceso al módulo Campo.")
        return redirect("/")

    servicio = get_object_or_404(
        FieldService.objects
        .select_related("paw", "responsable")
        .prefetch_related("gastos", "gastos__detalle_personas"),
        id=servicio_id,
    )

    return render(request, "campo/detalle_servicio.html", {
        "servicio": servicio,
        "gastos": servicio.gastos.all(),
        "puede_ver_gastos": _puede_ver_gastos(request.user),
    })


@login_required
def asignar_tecnicos(request, servicio_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes permiso para asignar técnicos de campo.")
        return redirect("/")

    servicio = get_object_or_404(
        FieldService.objects.select_related("paw", "responsable"),
        id=servicio_id,
    )

    if servicio.estado == FieldService.Estado.FINALIZADO:
        messages.error(request, "No puedes cambiar técnicos de un servicio finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    if request.method == "POST":
        form = AsignarTecnicosForm(request.POST, instance=servicio)
        if form.is_valid():
            form.save()
            messages.success(request, "Técnicos asignados correctamente.")
            return redirect("campo:detalle_servicio", servicio_id=servicio.id)
    else:
        form = AsignarTecnicosForm(instance=servicio)

    return render(request, "campo/asignar_tecnicos.html", {
        "servicio": servicio,
        "form": form,
    })


@login_required
def crear_gasto_diario(request, servicio_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes permiso para registrar gastos de campo.")
        return redirect("/")

    servicio = get_object_or_404(FieldService, id=servicio_id)

    if servicio.estado == FieldService.Estado.FINALIZADO:
        messages.error(request, "No puedes agregar gastos a un servicio finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    if request.method == "POST":
        form = FieldServiceDailyExpenseForm(request.POST)
        detalle_personas = _leer_detalle_personas_post(request)

        if not detalle_personas:
            form.add_error(None, "Debes registrar al menos una persona en el detalle individual.")

        if form.is_valid() and detalle_personas:
            gasto = form.save(commit=False)
            gasto.servicio = servicio
            gasto.registrado_por = request.user

            # Mantiene consecutivo seguro aunque manipulen el HTML.
            if not gasto.dia_numero:
                gasto.dia_numero = _siguiente_dia(servicio)

            gasto.personas = len(detalle_personas)
            gasto.save()

            _guardar_detalle_personas(gasto, detalle_personas)
            _sincronizar_campos_legados_bonos(gasto, detalle_personas)

            messages.success(request, "Registro diario guardado correctamente.")
            return redirect("campo:detalle_servicio", servicio_id=servicio.id)
    else:
        cantidad_inicial = servicio.cantidad_tecnicos_asignados or 1
        form = FieldServiceDailyExpenseForm(initial={
            "dia_numero": _siguiente_dia(servicio),
            "fecha": timezone.localdate(),
            "personas": cantidad_inicial,
        })
        detalle_personas = _detalle_personas_inicial(servicio, cantidad_inicial)

    return render(request, "campo/gasto_form.html", {
        "form": form,
        "servicio": servicio,
        "modo": "crear",
        "detalle_personas": detalle_personas,
    })


@login_required
def editar_gasto_diario(request, gasto_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes permiso para editar gastos de campo.")
        return redirect("/")

    gasto = get_object_or_404(
        FieldServiceDailyExpense.objects
        .select_related("servicio", "servicio__paw")
        .prefetch_related("detalle_personas"),
        id=gasto_id,
    )
    servicio = gasto.servicio

    if servicio.estado == FieldService.Estado.FINALIZADO:
        messages.error(request, "No puedes editar registros de un servicio finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    if request.method == "POST":
        form = FieldServiceDailyExpenseForm(request.POST, instance=gasto)
        detalle_personas = _leer_detalle_personas_post(request)

        if not detalle_personas:
            form.add_error(None, "Debes registrar al menos una persona en el detalle individual.")

        if form.is_valid() and detalle_personas:
            gasto = form.save(commit=False)
            gasto.personas = len(detalle_personas)
            gasto.save()

            _guardar_detalle_personas(gasto, detalle_personas)
            _sincronizar_campos_legados_bonos(gasto, detalle_personas)

            messages.success(request, "Registro diario actualizado correctamente.")
            return redirect("campo:detalle_servicio", servicio_id=servicio.id)
    else:
        form = FieldServiceDailyExpenseForm(instance=gasto)
        detalle_personas = _detalle_personas_existente(gasto)

    return render(request, "campo/gasto_form.html", {
        "form": form,
        "servicio": servicio,
        "gasto": gasto,
        "modo": "editar",
        "detalle_personas": detalle_personas,
    })


@require_POST
@login_required
def finalizar_servicio(request, servicio_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes permiso para finalizar servicios de campo.")
        return redirect("/")

    servicio = get_object_or_404(FieldService.objects.select_related("paw"), id=servicio_id)

    if servicio.estado == FieldService.Estado.FINALIZADO:
        messages.info(request, "Este servicio ya estaba finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    if not servicio.gastos.exists():
        messages.error(request, "No puedes finalizar el servicio sin registrar al menos un día de actividades.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    servicio.estado = FieldService.Estado.FINALIZADO
    servicio.fecha_fin = timezone.localdate()
    servicio.save(update_fields=["estado", "fecha_fin", "actualizado_en"])

    paw = servicio.paw
    paw.estado_operativo = "PRODUCTO_OK"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Servicio finalizado. El PAW quedó listo para facturación.")
    return redirect("paw_detail", paw_id=paw.id)


@login_required
def reporte_actividades(request, servicio_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes acceso al reporte de actividades.")
        return redirect("/")

    servicio = get_object_or_404(
        FieldService.objects
        .select_related("paw", "responsable")
        .prefetch_related("gastos", "gastos__detalle_personas"),
        id=servicio_id,
    )

    return render(request, "campo/reporte_actividades.html", {
        "servicio": servicio,
        "gastos": servicio.gastos.all(),
    })


@login_required
def reporte_gastos(request, servicio_id):
    if not _puede_ver_gastos(request.user):
        messages.error(request, "No tienes acceso al reporte de gastos.")
        return redirect("campo:detalle_servicio", servicio_id=servicio_id)

    servicio = get_object_or_404(
        FieldService.objects
        .select_related("paw", "responsable")
        .prefetch_related("gastos", "gastos__detalle_personas"),
        id=servicio_id,
    )

    return render(request, "campo/reporte_gastos.html", {
        "servicio": servicio,
        "gastos": servicio.gastos.all(),
    })


@login_required
def reporte_bonos(request):
    """
    Reporte interno de bonos de técnicos por corte.

    Reglas:
    - Corte estándar del 28 al 27.
    - Si el gasto diario tiene detalle por persona, liquida por cada técnico.
    - Si el gasto diario es antiguo y no tiene detalle, conserva la lógica anterior.
    - Los costos operativos como transporte comunidad, vuelos y gastos adicionales quedan separados.
    """
    if not _puede_ver_gastos(request.user):
        messages.error(request, "No tienes acceso al reporte de bonos.")
        return redirect("/")

    hoy = timezone.localdate()
    fecha_inicio_default, fecha_fin_default = _periodo_corte_27(hoy)

    fecha_inicio = _parse_fecha(request.GET.get("fecha_inicio")) or fecha_inicio_default
    fecha_fin = _parse_fecha(request.GET.get("fecha_fin")) or fecha_fin_default

    if fecha_inicio > fecha_fin:
        messages.error(request, "La fecha inicial no puede ser mayor que la fecha final.")
        fecha_inicio, fecha_fin = fecha_inicio_default, fecha_fin_default

    gastos = (
        FieldServiceDailyExpense.objects
        .select_related("servicio", "servicio__paw")
        .prefetch_related("detalle_personas")
        .filter(fecha__range=[fecha_inicio, fecha_fin])
        .order_by("fecha", "servicio__paw__numero_paw", "dia_numero")
    )

    resumen = defaultdict(lambda: {
        "dias_lider": 0,
        "dias_apoyo": 0,
        "dias_movilizacion": 0,
        "total": Decimal("0"),
        "detalle": [],
    })

    total_general = Decimal("0")
    total_dias_lider = 0
    total_dias_apoyo = 0
    total_dias_movilizacion = 0

    for gasto in gastos:
        servicio = gasto.servicio
        paw = servicio.paw
        lineas = list(gasto.detalle_personas.all())

        if lineas:
            for linea in lineas:
                tecnico = linea.persona

                if not tecnico:
                    continue

                bono_campo = _bono_campo_persona(servicio, tecnico, linea.dia_trabajado_campo)
                bono_movilizacion = _bono_movilizacion_persona(linea.salida_despues_mediodia, linea.regreso_despues_6pm, linea.solo_viaje_traslado)

                if bono_campo <= 0 and bono_movilizacion <= 0:
                    continue

                rol = "Técnico"
                concepto = linea.clasificacion_texto

                if tecnico == servicio.especialista_lider:
                    rol = "Especialista líder"
                    if bono_campo > 0:
                        resumen[tecnico]["dias_lider"] += 1
                        total_dias_lider += 1

                elif tecnico == servicio.especialista_apoyo:
                    rol = "Especialista apoyo"
                    if bono_campo > 0:
                        resumen[tecnico]["dias_apoyo"] += 1
                        total_dias_apoyo += 1

                if bono_movilizacion > 0:
                    resumen[tecnico]["dias_movilizacion"] += 1
                    total_dias_movilizacion += 1

                if bono_campo > 0:
                    resumen[tecnico]["total"] += bono_campo
                    resumen[tecnico]["detalle"].append({
                        "fecha": gasto.fecha,
                        "dia": gasto.dia_numero,
                        "paw": paw.numero_paw,
                        "nombre": paw.nombre_paw,
                        "campo": paw.campo,
                        "rol": rol,
                        "concepto": f"Bono campo - {concepto}",
                        "valor": bono_campo,
                    })
                    total_general += bono_campo

                if bono_movilizacion > 0:
                    resumen[tecnico]["total"] += bono_movilizacion
                    resumen[tecnico]["detalle"].append({
                        "fecha": gasto.fecha,
                        "dia": gasto.dia_numero,
                        "paw": paw.numero_paw,
                        "nombre": paw.nombre_paw,
                        "campo": paw.campo,
                        "rol": "Movilización",
                        "concepto": f"Bono movilización - {concepto}",
                        "valor": bono_movilizacion,
                    })
                    total_general += bono_movilizacion

            continue

        # Lógica anterior para registros que no tengan detalle individual.
        if servicio.especialista_lider and gasto.bono_lider > 0:
            tecnico = servicio.especialista_lider
            resumen[tecnico]["dias_lider"] += 1
            resumen[tecnico]["total"] += gasto.bono_lider
            resumen[tecnico]["detalle"].append({
                "fecha": gasto.fecha,
                "dia": gasto.dia_numero,
                "paw": paw.numero_paw,
                "nombre": paw.nombre_paw,
                "campo": paw.campo,
                "rol": "Especialista líder",
                "concepto": "Bono campo líder",
                "valor": gasto.bono_lider,
            })

            total_general += gasto.bono_lider
            total_dias_lider += 1

        if servicio.especialista_apoyo and gasto.bono_apoyo > 0:
            tecnico = servicio.especialista_apoyo
            resumen[tecnico]["dias_apoyo"] += 1
            resumen[tecnico]["total"] += gasto.bono_apoyo
            resumen[tecnico]["detalle"].append({
                "fecha": gasto.fecha,
                "dia": gasto.dia_numero,
                "paw": paw.numero_paw,
                "nombre": paw.nombre_paw,
                "campo": paw.campo,
                "rol": "Especialista apoyo",
                "concepto": "Bono campo apoyo",
                "valor": gasto.bono_apoyo,
            })

            total_general += gasto.bono_apoyo
            total_dias_apoyo += 1

        if gasto.aplica_bono_movilizacion:
            for tecnico in [servicio.especialista_lider, servicio.especialista_apoyo]:
                if not tecnico:
                    continue

                resumen[tecnico]["dias_movilizacion"] += 1
                resumen[tecnico]["total"] += BONO_MOVILIZACION_PERSONA
                resumen[tecnico]["detalle"].append({
                    "fecha": gasto.fecha,
                    "dia": gasto.dia_numero,
                    "paw": paw.numero_paw,
                    "nombre": paw.nombre_paw,
                    "campo": paw.campo,
                    "rol": "Movilización",
                    "concepto": "Bono movilización",
                    "valor": BONO_MOVILIZACION_PERSONA,
                })

                total_general += BONO_MOVILIZACION_PERSONA
                total_dias_movilizacion += 1

    resumen_ordenado = dict(sorted(resumen.items(), key=lambda item: item[0]))

    return render(request, "campo/reporte_bonos.html", {
        "resumen": resumen_ordenado,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_general": total_general,
        "total_dias_lider": total_dias_lider,
        "total_dias_apoyo": total_dias_apoyo,
        "total_dias_movilizacion": total_dias_movilizacion,
        "bono_lider": BONO_LIDER,
        "bono_apoyo": BONO_APOYO,
        "bono_movilizacion": BONO_MOVILIZACION_PERSONA,
    })
