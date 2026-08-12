from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from .models import PurchaseApproval, PurchaseApprovalLine


def _puede_aprobar(user):
    return tiene_rol(user, ["GERENTE", "ADMIN"])


@login_required
def dashboard(request):
    if not _puede_aprobar(request.user):
        messages.error(request, "No tienes permiso para gestionar aprobaciones de Gerencia.")
        return redirect("/")

    aprobaciones = (
        PurchaseApproval.objects
        .select_related("purchase_request", "enviado_por")
        .prefetch_related(
            "lineas",
            "lineas__purchase_line",
            "lineas__decidido_por",
        )
        .order_by("-actualizado_en")
    )

    pendientes = []
    historial = []

    for aprobacion in aprobaciones:
        lineas_credito = [
            ln for ln in aprobacion.lineas.all()
            if (ln.tipo_pago or "").upper() == "CREDITO"
        ]

        if not lineas_credito:
            continue

        aprobacion.lineas_credito = lineas_credito
        aprobacion.total_credito = len(lineas_credito)
        aprobacion.total_pendientes = sum(
            1 for ln in lineas_credito
            if ln.estado_aprobacion == PurchaseApprovalLine.EstadoAprobacion.PENDIENTE
        )
        aprobacion.total_aprobadas = sum(
            1 for ln in lineas_credito
            if ln.estado_aprobacion == PurchaseApprovalLine.EstadoAprobacion.APROBADO
        )
        aprobacion.total_rechazadas = sum(
            1 for ln in lineas_credito
            if ln.estado_aprobacion == PurchaseApprovalLine.EstadoAprobacion.RECHAZADO
        )

        if aprobacion.total_pendientes:
            pendientes.append(aprobacion)
        else:
            historial.append(aprobacion)

    return render(request, "aprobacion/dashboard.html", {
        "pendientes": pendientes,
        "historial": historial,
        "total_pendientes": sum(a.total_pendientes for a in pendientes),
    })


@require_POST
@login_required
def aprobar_linea(request, linea_id):
    if not _puede_aprobar(request.user):
        messages.error(request, "No tienes permiso para aprobar compras.")
        return redirect("/")

    linea = get_object_or_404(
        PurchaseApprovalLine.objects.select_related(
            "approval",
            "approval__purchase_request",
            "purchase_line",
        ),
        id=linea_id,
    )

    if (linea.tipo_pago or "").upper() != "CREDITO":
        messages.error(request, "Esta línea no corresponde a una compra a crédito.")
        return redirect("aprobacion:dashboard")

    linea.estado_aprobacion = PurchaseApprovalLine.EstadoAprobacion.APROBADO
    linea.observacion_finanzas = request.POST.get("observacion", "").strip()
    linea.touch_decision_audit(request.user)
    linea.save(update_fields=[
        "estado_aprobacion",
        "observacion_finanzas",
        "decidido_por",
        "decidido_en",
        "actualizado_en",
    ])

    aprobacion = linea.approval
    aprobacion.recalcular_estado()
    aprobacion.save(update_fields=["estado", "actualizado_en"])

    messages.success(
        request,
        f"Ítem {linea.codigo or linea.id} aprobado por Gerencia."
    )
    return redirect("aprobacion:dashboard")


@require_POST
@login_required
def rechazar_linea(request, linea_id):
    if not _puede_aprobar(request.user):
        messages.error(request, "No tienes permiso para rechazar compras.")
        return redirect("/")

    linea = get_object_or_404(
        PurchaseApprovalLine.objects.select_related(
            "approval",
            "approval__purchase_request",
            "purchase_line",
        ),
        id=linea_id,
    )

    if (linea.tipo_pago or "").upper() != "CREDITO":
        messages.error(request, "Esta línea no corresponde a una compra a crédito.")
        return redirect("aprobacion:dashboard")

    observacion = request.POST.get("observacion", "").strip()
    if not observacion:
        messages.error(request, "Debe registrar una observación para rechazar el ítem.")
        return redirect("aprobacion:dashboard")

    linea.estado_aprobacion = PurchaseApprovalLine.EstadoAprobacion.RECHAZADO
    linea.observacion_finanzas = observacion
    linea.touch_decision_audit(request.user)
    linea.save(update_fields=[
        "estado_aprobacion",
        "observacion_finanzas",
        "decidido_por",
        "decidido_en",
        "actualizado_en",
    ])

    aprobacion = linea.approval
    aprobacion.recalcular_estado()
    aprobacion.save(update_fields=["estado", "actualizado_en"])

    messages.success(
        request,
        f"Ítem {linea.codigo or linea.id} rechazado por Gerencia."
    )
    return redirect("aprobacion:dashboard")