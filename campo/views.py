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
from .models import FieldService, FieldServiceDailyExpense


BONO_LIDER = Decimal("90000")
BONO_APOYO = Decimal("75000")


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
        .filter(fecha__range=[fecha_inicio, fecha_fin])
        .order_by("fecha", "servicio__paw__numero_paw", "dia_numero")
    )

    detalle = []
    total = Decimal("0")
    dias_lider = 0
    dias_apoyo = 0

    for gasto in gastos:
        servicio = gasto.servicio
        paw = servicio.paw

        if servicio.especialista_lider == tecnico:
            detalle.append({
                "fecha": gasto.fecha,
                "dia": gasto.dia_numero,
                "paw": paw.numero_paw,
                "nombre": paw.nombre_paw,
                "campo": paw.campo,
                "rol": "Especialista líder",
                "valor": BONO_LIDER,
            })
            total += BONO_LIDER
            dias_lider += 1

        if servicio.especialista_apoyo == tecnico:
            detalle.append({
                "fecha": gasto.fecha,
                "dia": gasto.dia_numero,
                "paw": paw.numero_paw,
                "nombre": paw.nombre_paw,
                "campo": paw.campo,
                "rol": "Especialista apoyo",
                "valor": BONO_APOYO,
            })
            total += BONO_APOYO
            dias_apoyo += 1

    return render(request, "campo/reporte_bonos_empleado.html", {
        "tecnico": tecnico,
        "detalle": detalle,
        "total": total,
        "dias_lider": dias_lider,
        "dias_apoyo": dias_apoyo,
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
        .prefetch_related("gastos"),
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
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.servicio = servicio
            gasto.registrado_por = request.user

            # Mantiene consecutivo seguro aunque manipulen el HTML.
            if not gasto.dia_numero:
                gasto.dia_numero = _siguiente_dia(servicio)

            gasto.save()
            messages.success(request, "Registro diario guardado correctamente.")
            return redirect("campo:detalle_servicio", servicio_id=servicio.id)
    else:
        form = FieldServiceDailyExpenseForm(initial={
            "dia_numero": _siguiente_dia(servicio),
            "fecha": timezone.localdate(),
        })

    return render(request, "campo/gasto_form.html", {
        "form": form,
        "servicio": servicio,
        "modo": "crear",
    })


@login_required
def editar_gasto_diario(request, gasto_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes permiso para editar gastos de campo.")
        return redirect("/")

    gasto = get_object_or_404(
        FieldServiceDailyExpense.objects.select_related("servicio", "servicio__paw"),
        id=gasto_id,
    )
    servicio = gasto.servicio

    if servicio.estado == FieldService.Estado.FINALIZADO:
        messages.error(request, "No puedes editar registros de un servicio finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    if request.method == "POST":
        form = FieldServiceDailyExpenseForm(request.POST, instance=gasto)
        if form.is_valid():
            form.save()
            messages.success(request, "Registro diario actualizado correctamente.")
            return redirect("campo:detalle_servicio", servicio_id=servicio.id)
    else:
        form = FieldServiceDailyExpenseForm(instance=gasto)

    return render(request, "campo/gasto_form.html", {
        "form": form,
        "servicio": servicio,
        "gasto": gasto,
        "modo": "editar",
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
        .prefetch_related("gastos"),
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
        .prefetch_related("gastos"),
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

    Regla:
    - Corte estándar del 28 al 27.
    - Líder: 90.000 por día registrado.
    - Apoyo: 75.000 por día registrado.
    - Cada día se toma desde FieldServiceDailyExpense.
    - Cada técnico se toma desde FieldService.especialista_lider / especialista_apoyo.
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
        .filter(fecha__range=[fecha_inicio, fecha_fin])
        .order_by("fecha", "servicio__paw__numero_paw", "dia_numero")
    )

    resumen = defaultdict(lambda: {
        "dias_lider": 0,
        "dias_apoyo": 0,
        "total": Decimal("0"),
        "detalle": [],
    })

    total_general = Decimal("0")
    total_dias_lider = 0
    total_dias_apoyo = 0

    for gasto in gastos:
        servicio = gasto.servicio
        paw = servicio.paw

        if servicio.especialista_lider:
            tecnico = servicio.especialista_lider
            resumen[tecnico]["dias_lider"] += 1
            resumen[tecnico]["total"] += BONO_LIDER
            resumen[tecnico]["detalle"].append({
                "fecha": gasto.fecha,
                "dia": gasto.dia_numero,
                "paw": paw.numero_paw,
                "nombre": paw.nombre_paw,
                "campo": paw.campo,
                "rol": "Especialista líder",
                "valor": BONO_LIDER,
            })

            total_general += BONO_LIDER
            total_dias_lider += 1

        if servicio.especialista_apoyo:
            tecnico = servicio.especialista_apoyo
            resumen[tecnico]["dias_apoyo"] += 1
            resumen[tecnico]["total"] += BONO_APOYO
            resumen[tecnico]["detalle"].append({
                "fecha": gasto.fecha,
                "dia": gasto.dia_numero,
                "paw": paw.numero_paw,
                "nombre": paw.nombre_paw,
                "campo": paw.campo,
                "rol": "Especialista apoyo",
                "valor": BONO_APOYO,
            })

            total_general += BONO_APOYO
            total_dias_apoyo += 1

    resumen_ordenado = dict(sorted(resumen.items(), key=lambda item: item[0]))

    return render(request, "campo/reporte_bonos.html", {
        "resumen": resumen_ordenado,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "total_general": total_general,
        "total_dias_lider": total_dias_lider,
        "total_dias_apoyo": total_dias_apoyo,
        "bono_lider": BONO_LIDER,
        "bono_apoyo": BONO_APOYO,
    })
