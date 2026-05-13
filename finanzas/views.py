from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from compras_oil.models import PurchaseLine, Supplier
from .forms import SupplierInvoiceForm, SupplierPaymentForm
from .models import (
    FinanceApproval,
    FinanceApprovalLine,
    SupplierInvoice,
    SupplierPayment,
)

IVA_RATE = Decimal("0.19")
PAGE_SIZE = 50


def _puede_ver_finanzas(user):
    return tiene_rol(user, ["FINANZAS", "GERENTE", "ADMIN"])


# =========================
# 🔥 FIX PRINCIPAL
# =========================
def _sync_supplier_invoices(user=None):
    """
    Sincroniza cuentas por pagar desde Compras.
    Crea cuentas nuevas si aparecen nuevos proveedores o compras.
    NO borra ni modifica existentes (para no perder abonos ni historial).
    """

    pares = list(
        PurchaseLine.objects.filter(
            proveedor__isnull=False,
            cantidad_requerida__gt=0,
            cantidad_a_comprar__gt=0,
        )
        .exclude(tipo_pago="NA")
        .values_list("proveedor_id", "request_id")
        .distinct()
    )

    if not pares:
        return 0

    supplier_ids = [p[0] for p in pares]
    purchase_request_ids = [p[1] for p in pares]

    existentes = set(
        SupplierInvoice.objects.filter(
            supplier_id__in=supplier_ids,
            purchase_request_id__in=purchase_request_ids,
        ).values_list("supplier_id", "purchase_request_id")
    )

    creado_por = user if getattr(user, "is_authenticated", False) else None

    nuevos = [
        SupplierInvoice(
            supplier_id=supplier_id,
            purchase_request_id=purchase_request_id,
            creado_por=creado_por,
        )
        for supplier_id, purchase_request_id in pares
        if (supplier_id, purchase_request_id) not in existentes
    ]

    if nuevos:
        SupplierInvoice.objects.bulk_create(
            nuevos,
            ignore_conflicts=True,
            batch_size=500
        )

    return len(nuevos)


# =========================
# CALCULO FINANCIERO REAL
# =========================
def _retencion_por_linea(linea):
    subtotal = Decimal(linea.cantidad_a_comprar or 0) * Decimal(linea.precio_unitario or 0)
    finance_line = getattr(linea, "finance_line", None)
    tipo_operacion = getattr(finance_line, "tipo_operacion", "COMPRA") or "COMPRA"

    if tipo_operacion == "SERVICIO":
        return subtotal * Decimal("0.04")
    if tipo_operacion == "COMPRA":
        return subtotal * Decimal("0.025")

    return Decimal("0.00")


def _calcular_cuenta_proveedor(invoice):
    lineas = invoice.purchase_request.lineas.filter(
        proveedor=invoice.supplier,
        cantidad_requerida__gt=0,
        cantidad_a_comprar__gt=0,
    )

    base = Decimal("0")
    iva = Decimal("0")
    retencion = Decimal("0")
    total = Decimal("0")
    pagado_contado = Decimal("0")

    for linea in lineas:
        subtotal = Decimal(linea.cantidad_a_comprar or 0) * Decimal(linea.precio_unitario or 0)
        iva_linea = subtotal * IVA_RATE
        ret = _retencion_por_linea(linea)

        total_linea = subtotal + iva_linea - ret

        base += subtotal
        iva += iva_linea
        retencion += ret
        total += total_linea

        if linea.tipo_pago == "CONTADO":
            porcentaje = Decimal(linea.porcentaje_pago or 0)
            pagado_contado += total_linea * (porcentaje / Decimal("100"))

    abonos = sum((Decimal(a.valor or 0) for a in invoice.abonos.all()), Decimal("0"))

    total_abonado = pagado_contado + abonos
    saldo = total - total_abonado

    if saldo < 0:
        saldo = Decimal("0")

    return {
        "base": base,
        "iva": iva,
        "retencion": retencion,
        "total": total,
        "pagado_contado": pagado_contado,
        "abonado": abonos,
        "total_abonado": total_abonado,
        "saldo": saldo,
    }


# =========================
# VISTA PRINCIPAL
# =========================
@login_required
def cuentas_proveedores(request):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso.")
        return redirect("/")

    # 🔥 FIX: SIEMPRE sincroniza
    creadas = _sync_supplier_invoices(request.user)

    if request.GET.get("sync") == "1":
        if creadas:
            messages.info(request, f"Se sincronizaron {creadas} cuentas nuevas.")
        else:
            messages.info(request, "Ya estaba actualizado.")

    supplier_id = request.GET.get("proveedor")
    q = request.GET.get("q", "").strip()

    qs = SupplierInvoice.objects.select_related(
        "supplier",
        "purchase_request"
    ).prefetch_related(
        "abonos",
        "purchase_request__lineas"
    )

    if supplier_id:
        qs = qs.filter(supplier_id=supplier_id)

    if q:
        qs = qs.filter(
            Q(supplier__nombre__icontains=q) |
            Q(numero_factura_proveedor__icontains=q)
        )

    invoices = list(qs)

    # calcular
    for inv in invoices:
        calc = _calcular_cuenta_proveedor(inv)

        inv.base_compra_calc = calc["base"]
        inv.iva_calc = calc["iva"]
        inv.total_con_iva_calc = calc["total"]
        inv.total_abonado_calc = calc["total_abonado"]
        inv.saldo_calc = calc["saldo"]

    paginator = Paginator(invoices, PAGE_SIZE)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)

    suppliers = Supplier.objects.all().order_by("nombre")

    return render(request, "finanzas/cuentas_proveedores.html", {
        "invoices": page_obj,
        "page_obj": page_obj,
        "suppliers": suppliers,
        "q": q,
        "supplier_id": supplier_id,
    })


# =========================
# DETALLE + ABONOS
# =========================
@login_required
def cuenta_proveedor_detalle(request, pk):
    invoice = get_object_or_404(
        SupplierInvoice.objects.prefetch_related("abonos"),
        pk=pk
    )

    if request.method == "POST":
        form = SupplierPaymentForm(request.POST)

        if form.is_valid():
            abono = form.save(commit=False)
            abono.supplier_invoice = invoice
            abono.creado_por = request.user
            abono.save()

            messages.success(request, "Abono registrado")
            return redirect("finanzas:cuenta_proveedor_detalle", pk=pk)

    else:
        form = SupplierPaymentForm()

    calc = _calcular_cuenta_proveedor(invoice)

    invoice.total_con_iva_calc = calc["total"]
    invoice.total_abonado_calc = calc["total_abonado"]
    invoice.saldo_calc = calc["saldo"]

    return render(request, "finanzas/cuenta_proveedor_detalle.html", {
        "invoice": invoice,
        "form": form,
        "abonos": invoice.abonos.all()
    })