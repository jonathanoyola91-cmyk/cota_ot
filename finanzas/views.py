from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Case,
    DecimalField,
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
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


def _sync_supplier_invoices(user=None):
    """
    Sincroniza cuentas por pagar desde Compras.

    Versión optimizada:
    - Lee combinaciones proveedor + solicitud compra.
    - Lee existentes en una sola consulta.
    - Crea faltantes con bulk_create.

    Esto evita hacer get_or_create uno por uno cuando hay muchas líneas.
    """
    pares = list(
        PurchaseLine.objects.filter(
            proveedor__isnull=False,
            cantidad_requerida__gt=0,
            cantidad_a_comprar__gt=0,
        )
        .values_list("proveedor_id", "request_id")
        .distinct()
    )

    if not pares:
        return 0

    existentes = set(
        SupplierInvoice.objects.filter(
            supplier_id__in=[p[0] for p in pares],
            purchase_request_id__in=[p[1] for p in pares],
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
        SupplierInvoice.objects.bulk_create(nuevos, ignore_conflicts=True, batch_size=500)

    return len(nuevos)


def _queryset_cuentas_proveedores():
    """
    Query base para cuentas por pagar.

    Los valores financieros finales se calculan en Python en
    _preparar_invoices_para_template(), porque el saldo ahora depende de:
    - porcentaje pagado de contado por línea,
    - tipo de pago CONTADO / CREDITO / NA,
    - retención según tipo de operación de la línea financiera,
    - abonos manuales registrados a la cuenta por pagar.
    """
    return (
        SupplierInvoice.objects.select_related(
            "supplier",
            "purchase_request",
            "purchase_request__bom",
            "purchase_request__bom__workorder",
        )
        .prefetch_related(
            "abonos",
            "purchase_request__lineas",
            "purchase_request__lineas__proveedor",
            "purchase_request__lineas__finance_line",
        )
        .order_by("supplier__nombre", "-purchase_request__actualizado_en")
    )

def _resumen_queryset(invoices):
    """Resume una lista de cuentas ya preparadas para el template."""
    data = {
        "base": Decimal("0.00"),
        "iva": Decimal("0.00"),
        "retencion": Decimal("0.00"),
        "total": Decimal("0.00"),
        "pagado_contado": Decimal("0.00"),
        "abonado": Decimal("0.00"),
        "saldo": Decimal("0.00"),
    }

    for inv in invoices:
        data["base"] += Decimal(getattr(inv, "base_compra_calc", Decimal("0.00")) or 0)
        data["iva"] += Decimal(getattr(inv, "iva_calc", Decimal("0.00")) or 0)
        data["retencion"] += Decimal(getattr(inv, "retencion_calc", Decimal("0.00")) or 0)
        data["total"] += Decimal(getattr(inv, "total_con_iva_calc", Decimal("0.00")) or 0)
        data["pagado_contado"] += Decimal(getattr(inv, "pagado_contado_calc", Decimal("0.00")) or 0)
        data["abonado"] += Decimal(getattr(inv, "total_abonado_calc", Decimal("0.00")) or 0)
        data["saldo"] += Decimal(getattr(inv, "saldo_calc", Decimal("0.00")) or 0)

    return data


def _retencion_por_linea(linea):
    """Calcula retención por línea según el tipo de operación financiera."""
    subtotal = Decimal(linea.cantidad_a_comprar or 0) * Decimal(linea.precio_unitario or 0)
    finance_line = getattr(linea, "finance_line", None)
    tipo_operacion = getattr(finance_line, "tipo_operacion", "COMPRA") or "COMPRA"

    if tipo_operacion == "SERVICIO":
        return subtotal * Decimal("0.04"), "Servicio 4%"

    if tipo_operacion == "COMPRA":
        return subtotal * Decimal("0.025"), "Compra 2.5%"

    return Decimal("0.00"), "N/A sin retención"


def _calcular_cuenta_proveedor(invoice):
    """
    Calcula la trazabilidad real de una cuenta por pagar por proveedor.

    Reglas:
    - N/A no genera saldo financiero.
    - CONTADO paga el porcentaje indicado en compras.
    - CREDITO queda pendiente hasta registrar abonos.
    - El saldo considera: subtotal + IVA - retención - pago contado - abonos.
    """
    lineas = invoice.purchase_request.lineas.filter(
        proveedor=invoice.supplier,
        cantidad_requerida__gt=0,
        cantidad_a_comprar__gt=0,
    ).select_related("proveedor").prefetch_related("finance_line")

    base = Decimal("0.00")
    iva = Decimal("0.00")
    retencion = Decimal("0.00")
    total_neto = Decimal("0.00")
    pagado_contado = Decimal("0.00")
    base_credito = Decimal("0.00")
    base_na = Decimal("0.00")
    tipos = set()
    trazabilidad = []

    for linea in lineas:
        tipo_pago = linea.tipo_pago or "CREDITO"
        porcentaje = Decimal(linea.porcentaje_pago or 0)
        subtotal = Decimal(linea.cantidad_a_comprar or 0) * Decimal(linea.precio_unitario or 0)

        if tipo_pago == "NA":
            tipos.add("NA")
            base_na += subtotal
            trazabilidad.append({
                "codigo": linea.codigo,
                "tipo_pago": "N/A",
                "porcentaje": Decimal("0.00"),
                "subtotal": subtotal,
                "iva": Decimal("0.00"),
                "retencion": Decimal("0.00"),
                "total_neto": Decimal("0.00"),
                "pagado_contado": Decimal("0.00"),
                "pendiente": Decimal("0.00"),
                "nota": "No genera cuenta por pagar",
            })
            continue

        tipos.add(tipo_pago)
        iva_linea = subtotal * IVA_RATE
        retencion_linea, tipo_operacion_label = _retencion_por_linea(linea)
        total_linea = subtotal + iva_linea - retencion_linea

        pago_contado_linea = Decimal("0.00")
        pendiente_linea = total_linea

        if tipo_pago == "CONTADO":
            pago_contado_linea = total_linea * (porcentaje / Decimal("100"))
            pendiente_linea = total_linea - pago_contado_linea
        elif tipo_pago == "CREDITO":
            base_credito += total_linea

        base += subtotal
        iva += iva_linea
        retencion += retencion_linea
        total_neto += total_linea
        pagado_contado += pago_contado_linea

        trazabilidad.append({
            "codigo": linea.codigo,
            "tipo_pago": tipo_pago,
            "porcentaje": porcentaje,
            "subtotal": subtotal,
            "iva": iva_linea,
            "retencion": retencion_linea,
            "tipo_operacion": tipo_operacion_label,
            "total_neto": total_linea,
            "pagado_contado": pago_contado_linea,
            "pendiente": pendiente_linea,
            "nota": "",
        })

    total_abonado_real = sum((Decimal(a.valor or 0) for a in invoice.abonos.all()), Decimal("0.00"))
    total_abonado = pagado_contado + total_abonado_real
    saldo = total_neto - total_abonado
    if saldo < 0:
        saldo = Decimal("0.00")

    tipos_financieros = {t for t in tipos if t != "NA"}
    if len(tipos_financieros) > 1:
        tipo_pago_view = "MIXTO"
    elif "CONTADO" in tipos_financieros:
        tipo_pago_view = "CONTADO"
    elif "CREDITO" in tipos_financieros:
        tipo_pago_view = "CREDITO"
    elif "NA" in tipos:
        tipo_pago_view = "NA"
    else:
        tipo_pago_view = "-"

    return {
        "base": base,
        "iva": iva,
        "retencion": retencion,
        "total_neto": total_neto,
        "pagado_contado": pagado_contado,
        "abonos_reales": total_abonado_real,
        "total_abonado": total_abonado,
        "saldo": saldo,
        "base_credito": base_credito,
        "base_na": base_na,
        "tipo_pago": tipo_pago_view,
        "trazabilidad": trazabilidad,
    }

def _preparar_invoices_para_template(invoices):
    """
    Prepara cada cuenta para mostrar trazabilidad financiera completa:
    subtotal, IVA, retención, pagado de contado, abonos y saldo real.
    """
    for inv in invoices:
        calc = _calcular_cuenta_proveedor(inv)

        inv.base_compra_calc = calc["base"]
        inv.iva_calc = calc["iva"]
        inv.retencion_calc = calc["retencion"]
        inv.total_con_iva_calc = calc["total_neto"]
        inv.pagado_contado_calc = calc["pagado_contado"]
        inv.total_abonado_real_calc = calc["abonos_reales"]
        inv.total_abonado_calc = calc["total_abonado"]
        inv.saldo_calc = calc["saldo"]
        inv.base_credito_calc = calc["base_credito"]
        inv.base_na_calc = calc["base_na"]
        inv.tipo_pago_calc = calc["tipo_pago"]
        inv.trazabilidad_calc = calc["trazabilidad"]

        # Alias para templates existentes.
        inv.base_compra_view = inv.base_compra_calc
        inv.iva_view = inv.iva_calc
        inv.retencion_view = inv.retencion_calc
        inv.total_con_iva_view = inv.total_con_iva_calc
        inv.pagado_contado_view = inv.pagado_contado_calc
        inv.total_abonado_view = inv.total_abonado_calc
        inv.saldo_view = inv.saldo_calc
        inv.tipo_pago_view = inv.tipo_pago_calc

    return invoices


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

@require_POST
@login_required
def actualizar_tipo_operacion(request, linea_id):
    if not tiene_rol(request.user, ["FINANZAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para cambiar el tipo de operación.")
        return redirect("/")

    linea = get_object_or_404(FinanceApprovalLine, id=linea_id)

    tipo_operacion = request.POST.get("tipo_operacion")

    if tipo_operacion not in ["COMPRA", "SERVICIO", "NA"]:
        messages.error(request, "Tipo de operación no válido.")
        return redirect("finanzas:detalle", pk=linea.approval.id)

    linea.tipo_operacion = tipo_operacion
    linea.save(update_fields=["tipo_operacion", "actualizado_en"])

    messages.success(request, "Tipo de operación actualizado.")
    return redirect("finanzas:detalle", pk=linea.approval.id)

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

    # 🔥 AQUI VA TU LOGICA (BIEN INDENTADA)
    for linea in lineas:
        cantidad = linea.purchase_line.cantidad_a_comprar or 0
        precio = linea.purchase_line.precio_unitario or 0

        subtotal = cantidad * precio
        iva = subtotal * Decimal("0.19")

        porcentaje = Decimal(linea.purchase_line.porcentaje_pago or Decimal("100.00"))

        if linea.tipo_operacion == "SERVICIO":
            retencion = subtotal * Decimal("0.04")
            linea.tipo_operacion_label = "Servicio - retención 4%"
        elif linea.tipo_operacion == "COMPRA":
            retencion = subtotal * Decimal("0.025")
            linea.tipo_operacion_label = "Compra - retención 2.5%"
        else:
            retencion = Decimal("0.00")
            linea.tipo_operacion_label = "N/A - sin retención"

        # Fórmula correcta:
        # 1) subtotal + IVA - retención = base neta
        # 2) aplicar el porcentaje de pago al final
        base_total = subtotal + iva - retencion
        total_pagar = base_total * (porcentaje / Decimal("100"))

        linea.subtotal_calc = subtotal
        linea.iva_calc = iva
        linea.retencion_calc = retencion
        linea.base_total_calc = base_total
        linea.total_pagar_calc = total_pagar
        linea.porcentaje_pago_calc = porcentaje

    # 🔥 ESTE RETURN DEBE ESTAR DENTRO DEL DEF
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

    # Para que no sea pesado en cada apertura, puedes sincronizar manualmente con ?sync=1.
    sync_requested = request.GET.get("sync") == "1"
    if sync_requested or not SupplierInvoice.objects.exists():
        creadas = _sync_supplier_invoices(request.user)
        if creadas:
            messages.info(request, f"Se sincronizaron {creadas} cuentas de proveedores desde Compras.")
        elif sync_requested:
            messages.info(request, "No había cuentas nuevas para sincronizar.")

    supplier_id = request.GET.get("proveedor")
    tipo_pago = request.GET.get("tipo_pago")
    estado = request.GET.get("estado")
    q = request.GET.get("q", "").strip()

    invoices_qs = _queryset_cuentas_proveedores()

    if supplier_id:
        invoices_qs = invoices_qs.filter(supplier_id=supplier_id)

    if q:
        invoices_qs = invoices_qs.filter(
            Q(numero_factura_proveedor__icontains=q) |
            Q(supplier__nombre__icontains=q) |
            Q(purchase_request__paw_numero__icontains=q) |
            Q(purchase_request__paw_nombre__icontains=q)
        )

    invoices_all = _preparar_invoices_para_template(list(invoices_qs))

    if tipo_pago in ["CREDITO", "CONTADO", "MIXTO", "NA"]:
        invoices_all = [inv for inv in invoices_all if inv.tipo_pago_calc == tipo_pago]

    if estado == "PENDIENTE":
        invoices_all = [inv for inv in invoices_all if inv.saldo_calc > 0]
    elif estado == "PAGADA":
        invoices_all = [inv for inv in invoices_all if inv.saldo_calc <= 0]

    resumen = _resumen_queryset(invoices_all)

    paginator = Paginator(invoices_all, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    invoices_page = list(page_obj.object_list)

    suppliers = Supplier.objects.only("id", "nombre").order_by("nombre")

    return render(request, "finanzas/cuentas_proveedores.html", {
        "invoices": invoices_page,
        "page_obj": page_obj,
        "paginator": paginator,
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
        ).prefetch_related(
            "abonos",
            "purchase_request__lineas",
            "purchase_request__lineas__proveedor",
        ),
        pk=pk,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "guardar_factura":
            invoice_form = SupplierInvoiceForm(request.POST, instance=invoice)
            payment_form = SupplierPaymentForm()

            if invoice_form.is_valid():
                invoice_form.save()
                messages.success(request, "Información de factura proveedor actualizada correctamente.")
                return redirect("finanzas:cuenta_proveedor_detalle", pk=invoice.pk)

        elif action == "registrar_abono":
            if invoice.tipo_pago == "CONTADO":
                messages.info(request, "Esta compra es de contado. El saldo ya queda en cero automáticamente.")
                return redirect("finanzas:cuenta_proveedor_detalle", pk=invoice.pk)

            invoice_form = SupplierInvoiceForm(instance=invoice)
            payment_form = SupplierPaymentForm(request.POST)

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

    lineas = invoice.purchase_request.lineas.filter(
        proveedor=invoice.supplier,
        cantidad_requerida__gt=0,
    ).select_related("proveedor")

    abonos = invoice.abonos.all()

    return render(request, "finanzas/cuenta_proveedor_detalle.html", {
        "invoice": invoice,
        "lineas": lineas,
        "abonos": abonos,
        "invoice_form": invoice_form,
        "payment_form": payment_form,
    })
