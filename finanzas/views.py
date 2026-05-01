from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import Q

from core.roles import tiene_rol
from compras_oil.models import PurchaseLine, Supplier
from .forms import SupplierInvoiceForm, SupplierPaymentForm
from .models import (
    FinanceApproval,
    FinanceApprovalLine,
    SupplierInvoice,
)


def _puede_ver_finanzas(user):
    return tiene_rol(user, ["FINANZAS", "GERENTE", "ADMIN"])


def _sync_supplier_invoices(user=None):
    """
    Crea una cuenta por pagar por cada combinación:
    proveedor + solicitud de compra.

    No borra registros existentes y no modifica abonos.
    Se ejecuta al entrar al módulo para que tome datos históricos ya cargados.
    """
    pares = (
        PurchaseLine.objects
        .filter(
            proveedor__isnull=False,
            cantidad_requerida__gt=0,
            cantidad_a_comprar__gt=0,
        )
        .values("proveedor_id", "request_id")
        .distinct()
    )

    creadas = 0
    for par in pares:
        _, created = SupplierInvoice.objects.get_or_create(
            supplier_id=par["proveedor_id"],
            purchase_request_id=par["request_id"],
            defaults={"creado_por": user if getattr(user, "is_authenticated", False) else None},
        )
        if created:
            creadas += 1

    return creadas


def _resumen_supplier_invoices(invoices):
    base = Decimal("0")
    iva = Decimal("0")
    total = Decimal("0")
    abonado = Decimal("0")
    saldo = Decimal("0")

    for inv in invoices:
        base += inv.base_compra
        iva += inv.iva
        total += inv.total_con_iva
        abonado += inv.total_abonado
        saldo += inv.saldo

    return {
        "base": base,
        "iva": iva,
        "total": total,
        "abonado": abonado,
        "saldo": saldo,
    }


@login_required
def dashboard_finanzas(request):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Finanzas.")
        return redirect("/")

    items = FinanceApproval.objects.select_related(
        "purchase_request"
    ).order_by("-actualizado_en")

    return render(request, "finanzas/dashboard.html", {
        "items": items
    })


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
def detalle_finanzas(request, pk):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Finanzas.")
        return redirect("/")

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


# =======================================
# CUENTAS POR PAGAR A PROVEEDORES
# =======================================

@login_required
def cuentas_proveedores(request):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Cuentas por pagar proveedores.")
        return redirect("/")

    creadas = _sync_supplier_invoices(request.user)
    if creadas:
        messages.info(request, f"Se sincronizaron {creadas} cuentas de proveedores desde Compras.")

    supplier_id = request.GET.get("proveedor")
    tipo_pago = request.GET.get("tipo_pago")
    estado = request.GET.get("estado")
    q = request.GET.get("q", "").strip()

    invoices = SupplierInvoice.objects.select_related(
        "supplier",
        "purchase_request",
        "purchase_request__bom",
        "purchase_request__bom__workorder",
    ).prefetch_related("abonos").order_by(
        "supplier__nombre",
        "-purchase_request__actualizado_en",
    )

    if supplier_id:
        invoices = invoices.filter(supplier_id=supplier_id)

    if q:
        invoices = invoices.filter(
            Q(numero_factura_proveedor__icontains=q) |
            Q(supplier__nombre__icontains=q) |
            Q(purchase_request__paw_numero__icontains=q) |
            Q(purchase_request__paw_nombre__icontains=q)
        )

    # tipo_pago y estado se calculan por propiedades; por eso se filtra en memoria.
    invoices_list = list(invoices)

    if tipo_pago in ["CREDITO", "CONTADO"]:
        invoices_list = [inv for inv in invoices_list if inv.tipo_pago == tipo_pago]

    if estado == "PENDIENTE":
        invoices_list = [inv for inv in invoices_list if inv.saldo > 0]
    elif estado == "PAGADA":
        invoices_list = [inv for inv in invoices_list if inv.saldo <= 0]

    resumen = _resumen_supplier_invoices(invoices_list)
    suppliers = Supplier.objects.all().order_by("nombre")

    return render(request, "finanzas/cuentas_proveedores.html", {
        "invoices": invoices_list,
        "suppliers": suppliers,
        "resumen": resumen,
        "supplier_id": supplier_id,
        "tipo_pago": tipo_pago,
        "estado": estado,
        "q": q,
    })


@login_required
def cuenta_proveedor_detalle(request, pk):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Cuentas por pagar proveedores.")
        return redirect("/")

    invoice = get_object_or_404(
        SupplierInvoice.objects.select_related(
            "supplier",
            "purchase_request",
            "purchase_request__bom",
            "purchase_request__bom__workorder",
        ).prefetch_related("abonos"),
        pk=pk,
    )

    lineas = invoice.purchase_request.lineas.filter(
        proveedor=invoice.supplier,
        cantidad_requerida__gt=0,
    ).order_by("id")

    if request.method == "POST":
        accion = request.POST.get("accion")

        if accion == "guardar_factura":
            invoice_form = SupplierInvoiceForm(request.POST, instance=invoice)
            payment_form = SupplierPaymentForm()

            if invoice_form.is_valid():
                invoice_form.save()
                messages.success(request, "Factura del proveedor actualizada correctamente.")
                return redirect("finanzas:cuenta_proveedor_detalle", pk=invoice.pk)

        elif accion == "registrar_abono":
            invoice_form = SupplierInvoiceForm(instance=invoice)
            payment_form = SupplierPaymentForm(request.POST)

            if invoice.tipo_pago == "CONTADO":
                messages.error(request, "Esta compra es de contado. El saldo ya queda en cero automáticamente.")
                return redirect("finanzas:cuenta_proveedor_detalle", pk=invoice.pk)

            if payment_form.is_valid():
                abono = payment_form.save(commit=False)
                abono.supplier_invoice = invoice
                abono.creado_por = request.user
                abono.save()
                messages.success(request, "Abono registrado correctamente.")
                return redirect("finanzas:cuenta_proveedor_detalle", pk=invoice.pk)
        else:
            invoice_form = SupplierInvoiceForm(instance=invoice)
            payment_form = SupplierPaymentForm()
            messages.error(request, "Acción no válida.")
    else:
        invoice_form = SupplierInvoiceForm(instance=invoice)
        payment_form = SupplierPaymentForm()

    return render(request, "finanzas/cuenta_proveedor_detalle.html", {
        "invoice": invoice,
        "lineas": lineas,
        "invoice_form": invoice_form,
        "payment_form": payment_form,
    })
