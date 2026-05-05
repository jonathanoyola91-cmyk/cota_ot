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
    Query base optimizada para el listado.

    Calcula en base de datos:
    - base_compra_calc
    - iva_calc
    - total_con_iva_calc
    - total_abonado_real_calc
    - total_abonado_calc
    - saldo_calc
    - tipo_pago_calc

    Nota: el modelo todavía conserva sus propiedades originales; estas anotaciones
    se usan principalmente para filtrar y resumir sin recorrer todas las facturas.
    """
    output_money = DecimalField(max_digits=16, decimal_places=2)

    base_subquery = (
        PurchaseLine.objects.filter(
            request_id=OuterRef("purchase_request_id"),
            proveedor_id=OuterRef("supplier_id"),
            cantidad_requerida__gt=0,
        )
        .values("request_id", "proveedor_id")
        .annotate(
            total=Sum(
                F("cantidad_a_comprar") * F("precio_unitario"),
                output_field=output_money,
            )
        )
        .values("total")[:1]
    )

    abonos_subquery = (
        SupplierPayment.objects.filter(
            supplier_invoice_id=OuterRef("pk"),
        )
        .values("supplier_invoice_id")
        .annotate(total=Sum("valor", output_field=output_money))
        .values("total")[:1]
    )

    tiene_contado = Exists(
        PurchaseLine.objects.filter(
            request_id=OuterRef("purchase_request_id"),
            proveedor_id=OuterRef("supplier_id"),
            cantidad_requerida__gt=0,
            tipo_pago="CONTADO",
        )
    )

    qs = (
        SupplierInvoice.objects.select_related(
            "supplier",
            "purchase_request",
            "purchase_request__bom",
            "purchase_request__bom__workorder",
        )
        .annotate(
            base_compra_calc=Coalesce(
                Subquery(base_subquery, output_field=output_money),
                Value(Decimal("0.00"), output_field=output_money),
            ),
            total_abonado_real_calc=Coalesce(
                Subquery(abonos_subquery, output_field=output_money),
                Value(Decimal("0.00"), output_field=output_money),
            ),
            es_contado=tiene_contado,
        )
        .annotate(
            iva_calc=F("base_compra_calc") * Value(IVA_RATE, output_field=output_money),
            total_con_iva_calc=F("base_compra_calc") + F("iva_calc"),
            tipo_pago_calc=Case(
                When(es_contado=True, then=Value("CONTADO")),
                default=Value("CREDITO"),
            ),
        )
        .annotate(
            total_abonado_calc=Case(
                When(es_contado=True, then=F("total_con_iva_calc")),
                default=F("total_abonado_real_calc"),
                output_field=output_money,
            ),
            saldo_calc=Case(
                When(es_contado=True, then=Value(Decimal("0.00"), output_field=output_money)),
                When(total_con_iva_calc__lte=F("total_abonado_real_calc"), then=Value(Decimal("0.00"), output_field=output_money)),
                default=F("total_con_iva_calc") - F("total_abonado_real_calc"),
                output_field=output_money,
            ),
        )
        .order_by("supplier__nombre", "-purchase_request__actualizado_en")
    )

    return qs


def _resumen_queryset(qs):
    """
    Resume usando campos anotados en BD, sin convertir todo a lista.
    """
    output_money = DecimalField(max_digits=16, decimal_places=2)

    data = qs.aggregate(
        base=Coalesce(Sum("base_compra_calc", output_field=output_money), Value(Decimal("0.00"), output_field=output_money)),
        iva=Coalesce(Sum("iva_calc", output_field=output_money), Value(Decimal("0.00"), output_field=output_money)),
        total=Coalesce(Sum("total_con_iva_calc", output_field=output_money), Value(Decimal("0.00"), output_field=output_money)),
        abonado=Coalesce(Sum("total_abonado_calc", output_field=output_money), Value(Decimal("0.00"), output_field=output_money)),
        saldo=Coalesce(Sum("saldo_calc", output_field=output_money), Value(Decimal("0.00"), output_field=output_money)),
    )

    return data


def _preparar_invoices_para_template(invoices):
    """
    El template actual usa propiedades del modelo (base_compra, iva, saldo).
    Para evitar consultas extra por cada fila, copiamos los valores anotados
    sobre atributos normales que el template puede mostrar con nombres *_calc.

    Si más adelante actualizas el template, usa:
    - inv.base_compra_calc
    - inv.iva_calc
    - inv.total_con_iva_calc
    - inv.total_abonado_calc
    - inv.saldo_calc
    - inv.tipo_pago_calc
    """
    for inv in invoices:
        # Alias útiles si actualizas el template después.
        inv.base_compra_view = inv.base_compra_calc or Decimal("0.00")
        inv.iva_view = inv.iva_calc or Decimal("0.00")
        inv.total_con_iva_view = inv.total_con_iva_calc or Decimal("0.00")
        inv.total_abonado_view = inv.total_abonado_calc or Decimal("0.00")
        inv.saldo_view = inv.saldo_calc or Decimal("0.00")
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
    # Ejemplo: /finanzas/proveedores-cxp/?sync=1
    # También sincroniza automáticamente cuando todavía no hay cuentas creadas.
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

    invoices = _queryset_cuentas_proveedores()

    if supplier_id:
        invoices = invoices.filter(supplier_id=supplier_id)

    if q:
        invoices = invoices.filter(
            Q(numero_factura_proveedor__icontains=q) |
            Q(supplier__nombre__icontains=q) |
            Q(purchase_request__paw_numero__icontains=q) |
            Q(purchase_request__paw_nombre__icontains=q)
        )

    if tipo_pago in ["CREDITO", "CONTADO"]:
        invoices = invoices.filter(tipo_pago_calc=tipo_pago)

    if estado == "PENDIENTE":
        invoices = invoices.filter(saldo_calc__gt=0)
    elif estado == "PAGADA":
        invoices = invoices.filter(saldo_calc__lte=0)

    resumen = _resumen_queryset(invoices)

    paginator = Paginator(invoices, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    invoices_page = _preparar_invoices_para_template(list(page_obj.object_list))

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
