from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from .forms import AsignarTecnicosForm, FieldServiceDailyExpenseForm
from .models import FieldService, FieldServiceDailyExpense


def _puede_campo(user):
    return tiene_rol(user, ["CAMPO", "INGENIERIA", "GERENTE", "ADMIN"])


def _puede_ver_gastos(user):
    return tiene_rol(user, ["FINANZAS", "GERENTE", "ADMIN"])


def _siguiente_dia(servicio):
    ultimo = servicio.gastos.order_by("-dia_numero", "-id").first()
    return (ultimo.dia_numero + 1) if ultimo else 1


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
        FieldService.objects.select_related("paw", "responsable").prefetch_related("gastos"),
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

    gasto = get_object_or_404(FieldServiceDailyExpense.objects.select_related("servicio", "servicio__paw"), id=gasto_id)
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
        FieldService.objects.select_related("paw", "responsable").prefetch_related("gastos"),
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
        FieldService.objects.select_related("paw", "responsable").prefetch_related("gastos"),
        id=servicio_id,
    )

    return render(request, "campo/reporte_gastos.html", {
        "servicio": servicio,
        "gastos": servicio.gastos.all(),
    })
