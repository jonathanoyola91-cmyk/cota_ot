from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from core.roles import tiene_rol
from .models import FinanceApproval, FinanceApprovalLine


@login_required
def aprobacion_pagos(request):
    if not tiene_rol(request.user, ["GERENTE", "ADMIN"]):
        messages.error(request, "Solo gerencia puede aprobar pagos.")
        return redirect("/")

    lineas = FinanceApprovalLine.objects.select_related(
        "approval",
        "approval__purchase_request",
        "purchase_line",
        "purchase_line__proveedor",
    ).filter(
        pagado=False
    ).order_by("decision", "scheduled_date", "-creado_en")

    return render(request, "finanzas/aprobacion_pagos.html", {
        "lineas": lineas,
    })


@login_required
def aprobar_linea_pago(request, linea_id):
    if not tiene_rol(request.user, ["GERENTE", "ADMIN"]):
        messages.error(request, "Solo gerencia puede aprobar pagos.")
        return redirect("/")

    linea = get_object_or_404(FinanceApprovalLine, id=linea_id)

    if request.method == "POST":
        decision = request.POST.get("decision")
        scheduled_date = request.POST.get("scheduled_date") or None
        nota_admin = request.POST.get("nota_admin", "")

        if decision not in ["PENDIENTE", "APROBADO", "PROGRAMADO", "EN_ESPERA", "RECHAZADO"]:
            messages.error(request, "Decisión no válida.")
            return redirect("finanzas:aprobacion_pagos")

        linea.decision = decision
        linea.scheduled_date = scheduled_date
        linea.nota_admin = nota_admin
        linea.decidido_por = request.user
        linea.decidido_en = timezone.now()
        linea.save()

        messages.success(request, "Decisión financiera actualizada correctamente.")

    return redirect("finanzas:aprobacion_pagos")

@login_required
def dashboard_finanzas(request):
    items = FinanceApproval.objects.select_related(
        "purchase_request"
    ).order_by("-actualizado_en")

    return render(request, "finanzas/dashboard.html", {
        "items": items
    })


@login_required
def detalle_finanzas(request, pk):
    fin = get_object_or_404(
        FinanceApproval.objects.select_related("purchase_request"),
        pk=pk
    )

    lineas = fin.lineas.select_related(
        "purchase_line",
        "purchase_line__proveedor"
    ).all()

    return render(request, "finanzas/detalle.html", {
        "fin": fin,
        "lineas": lineas
    })


@login_required
def marcar_pagado(request, linea_id):
    if not tiene_rol(request.user, ["FINANZAS", "ADMIN"]):
        messages.error(request, "Solo finanzas puede ejecutar pagos.")
        return redirect("/")

    linea = get_object_or_404(FinanceApprovalLine, id=linea_id)

    try:
        linea.mark_paid(request.user)

        paw = linea.approval.purchase_request.bom.workorder.paw
        if paw:
            paw.estado_operativo = "PAGO_OK"
            paw.save(update_fields=["estado_operativo"])

        messages.success(request, "Pago registrado correctamente.")

    except Exception as e:
        messages.error(request, str(e))

    return redirect("finanzas:detalle", pk=linea.approval.id)