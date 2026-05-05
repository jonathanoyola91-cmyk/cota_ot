from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from .forms import FieldServiceDailyExpenseForm
from .models import FieldService, FieldServiceDailyExpense


def _puede_campo(user):
    return tiene_rol(user, ["CAMPO", "INGENIERIA", "GERENTE", "ADMIN"])


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
    })


def _siguiente_dia(servicio):
    ultimo = servicio.gastos.order_by("-dia_numero").first()
    return (ultimo.dia_numero + 1) if ultimo else 1


@login_required
def crear_gasto_diario(request, servicio_id):
    if not _puede_campo(request.user):
        messages.error(request, "No tienes permiso para registrar gastos de campo.")
        return redirect("/")

    servicio = get_object_or_404(FieldService, id=servicio_id)

    if servicio.estado == FieldService.Estado.FINALIZADO:
        messages.error(request, "No puedes agregar gastos a un servicio finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    siguiente_dia = _siguiente_dia(servicio)

    if request.method == "POST":
        form = FieldServiceDailyExpenseForm(request.POST, siguiente_dia=siguiente_dia)
        if form.is_valid():
            gasto = form.save(commit=False)
            gasto.servicio = servicio
            gasto.dia_numero = siguiente_dia
            gasto.registrado_por = request.user
            gasto.save()
            messages.success(request, f"Gasto diario día {gasto.dia_numero} registrado correctamente.")
            return redirect("campo:detalle_servicio", servicio_id=servicio.id)
    else:
        form = FieldServiceDailyExpenseForm(siguiente_dia=siguiente_dia)

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
        messages.error(request, "No puedes editar gastos de un servicio finalizado.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    if request.method == "POST":
        form = FieldServiceDailyExpenseForm(request.POST, instance=gasto)
        if form.is_valid():
            gasto = form.save(commit=False)
            # Se mantiene el día original para evitar saltos o duplicados por edición.
            gasto.dia_numero = gasto.dia_numero
            gasto.save()
            messages.success(request, "Gasto diario actualizado correctamente.")
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
        messages.error(request, "No puedes finalizar el servicio sin registrar al menos un gasto diario.")
        return redirect("campo:detalle_servicio", servicio_id=servicio.id)

    servicio.estado = FieldService.Estado.FINALIZADO
    servicio.fecha_fin = timezone.localdate()
    servicio.save(update_fields=["estado", "fecha_fin", "actualizado_en"])

    paw = servicio.paw
    paw.estado_operativo = "PRODUCTO_OK"
    paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Servicio finalizado. El PAW quedó listo para facturación.")
    return redirect("paw_detail", paw_id=paw.id)
