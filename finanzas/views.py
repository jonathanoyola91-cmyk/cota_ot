from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
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
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from compras_oil.models import PurchaseLine, Supplier
from .forms import (SupplierInvoiceForm, SupplierPaymentForm, FixedExpenseForm, InvestorLoanForm, InvestorPaymentForm)
from .models import (
    FinanceApproval,
    FinanceApprovalLine,
    SupplierInvoice,
    SupplierPayment,
    FixedExpense,
    InvestorLoan,
    InvestorPayment,
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
        .exclude(tipo_pago="NA")
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

    if tipo_operacion == "CARGA":
        return subtotal * Decimal("0.01"), "Carga 1%"

    if tipo_operacion == "PASAJERO":
        return subtotal * Decimal("0.035"), "Pasajero 3.5%"

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

    # Separamos el tablero en dos bloques:
    # - pendientes: PAW con al menos una linea que Finanzas todavia debe atender/pagar.
    # - historial: PAW cuyas lineas financieras ya quedaron pagadas.
    #
    # Se hace por LINEA para que un PAW con pagos parciales no desaparezca
    # de pendientes hasta que Finanzas termine todas sus lineas.
    items = list(
        FinanceApproval.objects
        .select_related("purchase_request")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    pendientes = []
    historial = []

    for item in items:
        lineas = list(item.lineas.all())

        item.total_lineas_finanzas = len(lineas)
        item.total_pagadas = sum(1 for linea in lineas if linea.pagado)
        item.total_pendientes = item.total_lineas_finanzas - item.total_pagadas

        # Si aun existe por lo menos una linea sin pagar, permanece arriba.
        # Cuando todas las lineas quedan pagadas pasa automaticamente al historial.
        if item.total_lineas_finanzas == 0 or item.total_pendientes > 0:
            pendientes.append(item)
        else:
            historial.append(item)

    today = timezone.localdate()
    periodo = today.replace(day=1)
    gastos_mes = list(FixedExpense.objects.filter(periodo=periodo).order_by("fecha_vencimiento", "concepto"))
    total_gastos = sum((g.valor for g in gastos_mes), Decimal("0"))
    pagado_gastos = sum((g.valor for g in gastos_mes if g.pagado), Decimal("0"))
    pendiente_gastos = total_gastos - pagado_gastos
    vencido_gastos = sum((g.valor for g in gastos_mes if g.vencido), Decimal("0"))

    prestamos = list(InvestorLoan.objects.filter(activo=True).prefetch_related("pagos"))
    cuotas = list(InvestorPayment.objects.filter(prestamo__activo=True).select_related("prestamo"))
    total_prestado = sum((p.valor_prestado for p in prestamos), Decimal("0"))
    total_cuotas_pendientes = sum((c.valor for c in cuotas if not c.pagado), Decimal("0"))
    total_cuotas_vencidas = sum((c.valor for c in cuotas if c.vencido), Decimal("0"))

    return render(request, "finanzas/dashboard.html", {
        # Se conserva items para no romper el template actual mientras se actualiza.
        "items": items,
        "pendientes": pendientes,
        "historial": historial,
        "total_pendientes": len(pendientes),
        "total_historial": len(historial),
        "periodo_actual": periodo,
        "gastos_mes": gastos_mes,
        "gastos_resumen": {"total": total_gastos, "pagado": pagado_gastos, "pendiente": pendiente_gastos, "vencido": vencido_gastos},
        "prestamos": prestamos,
        "inversionistas_resumen": {"prestado": total_prestado, "pendiente": total_cuotas_pendientes, "vencido": total_cuotas_vencidas},
    })


@login_required
def aprobacion_pagos(request):
    if not tiene_rol(request.user, ["GERENTE", "ADMIN"]):
        messages.error(request, "Solo gerencia puede aprobar pagos.")
        return redirect("/")

    lineas = list(
        FinanceApprovalLine.objects.select_related(
            "approval",
            "approval__purchase_request",
            "purchase_line",
            "purchase_line__proveedor",
        ).filter(
            pagado=False
        ).order_by(
            "approval__purchase_request__paw_numero",
            "purchase_line__id",
        )
    )

    # La aprobación se presenta por PAW y no como una lista plana de ítems.
    # La decisión sigue siendo individual por línea; solo cambia la organización
    # visual para que Gerencia pueda trabajar PAW por PAW.
    grupos_por_id = {}
    for linea in lineas:
        approval = linea.approval
        pr = approval.purchase_request
        key = approval.pk

        if key not in grupos_por_id:
            grupos_por_id[key] = {
                "approval": approval,
                "purchase_request": pr,
                "paw_numero": pr.paw_numero or pr.pk,
                "paw_nombre": getattr(pr, "paw_nombre", "") or "",
                "lineas": [],
                "total_items": 0,
                "pendientes": 0,
                "gestionados": 0,
            }

        grupo = grupos_por_id[key]
        grupo["lineas"].append(linea)
        grupo["total_items"] += 1
        if linea.decision == "PENDIENTE":
            grupo["pendientes"] += 1
        else:
            grupo["gestionados"] += 1

    grupos = list(grupos_por_id.values())

    # Primero PAW con decisiones pendientes; dentro de cada grupo se conservan
    # todos los ítems de contado aún no pagados.
    grupos.sort(
        key=lambda g: (
            0 if g["pendientes"] > 0 else 1,
            str(g["paw_numero"]),
        )
    )

    return render(request, "finanzas/aprobacion_pagos.html", {
        "grupos": grupos,
        "total_paws": len(grupos),
        "total_lineas": len(lineas),
    })

@require_POST
@login_required
def aprobar_paw_pago(request, approval_id):
    """Guarda en un solo envío todas las decisiones editadas de un PAW."""
    if not tiene_rol(request.user, ["GERENTE", "ADMIN"]):
        messages.error(request, "Solo gerencia puede aprobar pagos.")
        return redirect("/")

    approval = get_object_or_404(
        FinanceApproval.objects.select_related("purchase_request"),
        pk=approval_id,
    )
    lineas = list(approval.lineas.filter(pagado=False))
    decisiones_validas = {"PENDIENTE", "APROBADO", "PROGRAMADO", "EN_ESPERA", "RECHAZADO"}
    actualizadas = 0

    with transaction.atomic():
        for linea in lineas:
            decision = request.POST.get(f"decision_{linea.id}")
            if decision is None:
                continue
            if decision not in decisiones_validas:
                messages.error(request, f"Decisión no válida en la línea {linea.id}.")
                return redirect(f'{reverse("finanzas:aprobacion_pagos")}#paw-{approval.id}')

            scheduled_date = request.POST.get(f"scheduled_date_{linea.id}") or None
            nota_admin = request.POST.get(f"nota_admin_{linea.id}", "")

            linea.decision = decision
            linea.scheduled_date = scheduled_date
            linea.nota_admin = nota_admin
            linea.decidido_por = request.user
            linea.decidido_en = timezone.now()
            linea.save(update_fields=[
                "decision", "scheduled_date", "nota_admin",
                "decidido_por", "decidido_en", "actualizado_en",
            ])
            actualizadas += 1

    paw = approval.purchase_request.paw_numero or approval.purchase_request.pk
    messages.success(request, f"PAW {paw}: {actualizadas} ítem(s) guardados correctamente.")
    return redirect(f'{reverse("finanzas:aprobacion_pagos")}#paw-{approval.id}')


@require_POST
@login_required
def actualizar_tipo_operacion(request, linea_id):
    if not tiene_rol(request.user, ["FINANZAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para cambiar el tipo de operación.")
        return redirect("/")

    linea = get_object_or_404(FinanceApprovalLine, id=linea_id)

    tipo_operacion = request.POST.get("tipo_operacion")

    if tipo_operacion not in ["COMPRA", "SERVICIO", "CARGA", "PASAJERO", "NA"]:
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
         
        approval = linea.approval

        lineas_pendientes = approval.lineas.filter(pagado=False).exists()

        if not lineas_pendientes:
            approval.estado = "APROBADO"
            approval.save(update_fields=["estado", "actualizado_en"])

            compra = approval.purchase_request
            compra.estado = "EN_REVISION"
            compra.save(update_fields=["estado", "actualizado_en"])

            paw = compra.bom.workorder.paw
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

    # Sincroniza siempre antes de mostrar Cuentas por Pagar.
    # Esto permite que los cambios hechos en compras_oil se reflejen sin depender de ?sync=1.
    creadas = _sync_supplier_invoices(request.user)

    if request.GET.get("sync") == "1":
        if creadas:
            messages.info(request, f"Se sincronizaron {creadas} cuentas de proveedores desde Compras.")
        else:
            messages.info(request, "Cuentas por pagar ya estaba sincronizado con Compras.")

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
        action = request.POST.get("accion")

        if action == "guardar_factura":
            invoice_form = SupplierInvoiceForm(request.POST, instance=invoice)
            payment_form = SupplierPaymentForm()

            if invoice_form.is_valid():
                invoice_form.save()
                messages.success(request, "Información de factura proveedor actualizada correctamente.")
                return redirect("finanzas:cuenta_proveedor_detalle", pk=invoice.pk)

        elif action == "registrar_abono":
            calc_actual = _calcular_cuenta_proveedor(invoice)

            if calc_actual["saldo"] <= 0:
                messages.info(request, "Esta cuenta no tiene saldo pendiente para registrar abonos.")
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

    calc = _calcular_cuenta_proveedor(invoice)

    invoice.base_compra_calc = calc["base"]
    invoice.iva_calc = calc["iva"]
    invoice.retencion_calc = calc["retencion"]
    invoice.total_con_iva_calc = calc["total_neto"]
    invoice.pagado_contado_calc = calc["pagado_contado"]
    invoice.total_abonado_real_calc = calc["abonos_reales"]
    invoice.total_abonado_calc = calc["total_abonado"]
    invoice.saldo_calc = calc["saldo"]
    invoice.tipo_pago_calc = calc["tipo_pago"]
    invoice.trazabilidad_calc = calc["trazabilidad"]


    return render(request, "finanzas/cuenta_proveedor_detalle.html", {
        "invoice": invoice,
        "lineas": lineas,
        "abonos": abonos,
        "invoice_form": invoice_form,
        "payment_form": payment_form,
    })

@login_required
def gastos_fijos(request):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Finanzas.")
        return redirect("/")

    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
        if month < 1 or month > 12 or year < 2000 or year > 2100:
            raise ValueError("Periodo inválido")
        periodo = today.replace(year=year, month=month, day=1)
    except (TypeError, ValueError):
        periodo = today.replace(day=1)

    anterior = (periodo - timedelta(days=1)).replace(day=1)
    if periodo.month == 12:
        siguiente = periodo.replace(year=periodo.year + 1, month=1)
    else:
        siguiente = periodo.replace(month=periodo.month + 1)
    meses = [
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    ]
    anios = range(today.year - 5, today.year + 3)

    if request.method == "POST" and request.POST.get("accion") == "crear":
        form = FixedExpenseForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.periodo = periodo
            obj.creado_por = request.user
            obj.save()
            messages.success(request, "Gasto fijo agregado.")
            return redirect(f"{request.path}?year={periodo.year}&month={periodo.month}")
    else:
        form = FixedExpenseForm()

    gastos = list(FixedExpense.objects.filter(periodo=periodo).order_by("fecha_vencimiento", "concepto"))
    total = sum((g.valor for g in gastos), Decimal("0"))
    pagado = sum((g.valor for g in gastos if g.pagado), Decimal("0"))
    vencido = sum((g.valor for g in gastos if g.vencido), Decimal("0"))

    # Promedio por concepto/categoría de hasta los 3 meses anteriores.
    historico = FixedExpense.objects.filter(periodo__lt=periodo).order_by("-periodo")
    promedios = {}
    for gasto in gastos:
        vals = list(historico.filter(categoria=gasto.categoria, concepto__iexact=gasto.concepto).values_list("valor", flat=True)[:3])
        gasto.promedio_historico = (sum(vals, Decimal("0")) / len(vals)) if vals else None

    return render(request, "finanzas/gastos_fijos.html", {
        "periodo": periodo, "gastos": gastos, "form": form,
        "meses": meses, "anios": anios, "anterior": anterior, "siguiente": siguiente, "hoy": today,
        "anterior_nombre": dict(meses)[anterior.month],
        "periodo_nombre": dict(meses)[periodo.month],
        "resumen": {"total": total, "pagado": pagado, "pendiente": total - pagado, "vencido": vencido},
    })


@login_required
@require_POST
def copiar_gastos_mes_anterior(request):
    if not _puede_ver_finanzas(request.user):
        return redirect("/")
    today = timezone.localdate()
    year = int(request.POST.get("year", today.year))
    month = int(request.POST.get("month", today.month))
    periodo = today.replace(year=year, month=month, day=1)
    anterior = (periodo - timedelta(days=1)).replace(day=1)
    existentes = set(FixedExpense.objects.filter(periodo=periodo).values_list("categoria", "concepto"))
    creados = 0
    for g in FixedExpense.objects.filter(periodo=anterior):
        if (g.categoria, g.concepto) in existentes:
            continue
        vencimiento = None
        if g.fecha_vencimiento:
            import calendar
            dia = min(g.fecha_vencimiento.day, calendar.monthrange(periodo.year, periodo.month)[1])
            vencimiento = periodo.replace(day=dia)
        FixedExpense.objects.create(periodo=periodo, categoria=g.categoria, concepto=g.concepto, valor=g.valor,
                                    fecha_vencimiento=vencimiento, observacion=g.observacion, creado_por=request.user)
        creados += 1
    if creados:
        messages.success(request, f"Se copiaron {creados} gastos de {dict([(1, 'enero'), (2, 'febrero'), (3, 'marzo'), (4, 'abril'), (5, 'mayo'), (6, 'junio'), (7, 'julio'), (8, 'agosto'), (9, 'septiembre'), (10, 'octubre'), (11, 'noviembre'), (12, 'diciembre')])[anterior.month]} {anterior.year} a {dict([(1, 'enero'), (2, 'febrero'), (3, 'marzo'), (4, 'abril'), (5, 'mayo'), (6, 'junio'), (7, 'julio'), (8, 'agosto'), (9, 'septiembre'), (10, 'octubre'), (11, 'noviembre'), (12, 'diciembre')])[periodo.month]} {periodo.year}.")
    else:
        if FixedExpense.objects.filter(periodo=anterior).exists():
            messages.info(request, "No se copiaron gastos porque los conceptos del mes anterior ya existen en el mes seleccionado.")
        else:
            messages.warning(request, "El mes anterior no tiene gastos para copiar.")
    return redirect(f"/finanzas/gastos-fijos/?year={periodo.year}&month={periodo.month}")


@login_required
def editar_gasto_fijo(request, pk):
    if not _puede_ver_finanzas(request.user):
        return redirect("/")
    gasto = get_object_or_404(FixedExpense, pk=pk)
    if request.method == "POST":
        form = FixedExpenseForm(request.POST, instance=gasto)
        if form.is_valid():
            form.save()
            messages.success(request, "Gasto actualizado.")
            return redirect(f"/finanzas/gastos-fijos/?year={gasto.periodo.year}&month={gasto.periodo.month}")
    else:
        form = FixedExpenseForm(instance=gasto)
    return render(request, "finanzas/gasto_form.html", {"form": form, "gasto": gasto})


@login_required
@require_POST
def pagar_gasto_fijo(request, pk):
    if not _puede_ver_finanzas(request.user):
        return redirect("/")
    gasto = get_object_or_404(FixedExpense, pk=pk)
    gasto.pagado = True
    gasto.fecha_pago = timezone.localdate()
    gasto.referencia_pago = request.POST.get("referencia_pago", "").strip()
    gasto.pagado_por = request.user
    gasto.save(update_fields=["pagado", "fecha_pago", "referencia_pago", "pagado_por", "actualizado_en"])
    messages.success(request, f"{gasto.concepto} marcado como pagado.")
    return redirect(request.META.get("HTTP_REFERER", "/finanzas/gastos-fijos/"))


@login_required
def inversionistas(request):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Finanzas.")
        return redirect("/")

    hoy = timezone.localdate()
    try:
        year = int(request.GET.get("year", hoy.year))
        month = int(request.GET.get("month", hoy.month))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        year, month = hoy.year, hoy.month

    if request.method == "POST" and request.POST.get("accion") == "crear_prestamo":
        form = InvestorLoanForm(request.POST)
        if form.is_valid():
            prestamo = form.save(commit=False)
            prestamo.creado_por = request.user
            prestamo.save()
            messages.success(request, f"Inversionista registrado. Interés mensual calculado: ${prestamo.cuota_programada:,.0f}.")
            return redirect(f"{reverse('finanzas:inversionistas')}?year={year}&month={month}")
    else:
        form = InvestorLoanForm()

    prestamos = list(InvestorLoan.objects.prefetch_related("pagos").all())
    cuotas = list(InvestorPayment.objects.select_related("prestamo").filter(
        prestamo__activo=True, fecha_programada__year=year, fecha_programada__month=month
    ))
    total_prestado = sum((p.valor_prestado for p in prestamos if p.activo), Decimal("0"))
    interes_estimado = sum((p.interes_mensual_valor for p in prestamos if p.activo), Decimal("0"))
    pagado = sum((c.valor for c in cuotas if c.pagado), Decimal("0"))
    pendiente = sum((c.valor for c in cuotas if not c.pagado), Decimal("0"))
    vencido = sum((c.valor for c in cuotas if c.vencido), Decimal("0"))

    meses = [(i, n) for i, n in enumerate(["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]) if i]
    return render(request, "finanzas/inversionistas.html", {
        "form": form, "prestamos": prestamos, "cuotas": cuotas, "year": year, "month": month,
        "meses": meses, "years": range(hoy.year - 5, hoy.year + 3),
        "resumen": {"prestado": total_prestado, "interes_mes": interes_estimado, "pagado": pagado, "pendiente": pendiente, "vencido": vencido},
    })


@login_required
def editar_inversionista(request, pk):
    if not _puede_ver_finanzas(request.user):
        messages.error(request, "No tienes acceso a Finanzas.")
        return redirect("/")

    prestamo = get_object_or_404(InvestorLoan, pk=pk)
    if request.method == "POST":
        form = InvestorLoanForm(request.POST, instance=prestamo)
        if form.is_valid():
            prestamo = form.save()
            messages.success(
                request,
                f"Inversionista actualizado. Nuevo interés mensual: ${prestamo.interes_mensual_valor:,.0f}. "
                "Los intereses ya programados o pagados conservan su valor histórico."
            )
            year = request.POST.get("year", timezone.localdate().year)
            month = request.POST.get("month", timezone.localdate().month)
            return redirect(f"{reverse('finanzas:inversionistas')}?year={year}&month={month}")
    else:
        form = InvestorLoanForm(instance=prestamo)

    return render(request, "finanzas/inversionista_form.html", {
        "form": form,
        "prestamo": prestamo,
        "year": request.GET.get("year", timezone.localdate().year),
        "month": request.GET.get("month", timezone.localdate().month),
    })


@login_required
def agregar_cuota_inversionista(request, prestamo_id):
    if not _puede_ver_finanzas(request.user):
        return redirect("/")
    prestamo = get_object_or_404(InvestorLoan, pk=prestamo_id)
    if request.method == "POST":
        form = InvestorPaymentForm(request.POST)
        if form.is_valid():
            cuota = form.save(commit=False)
            cuota.prestamo = prestamo
            cuota.save()
            messages.success(request, "Pago de interés programado.")
            return redirect("finanzas:inversionistas")
    else:
        form = InvestorPaymentForm(initial={"valor": prestamo.interes_mensual_valor, "fecha_programada": prestamo.fecha_primera_cuota})
    return render(request, "finanzas/cuota_inversionista_form.html", {"form": form, "prestamo": prestamo})


@login_required
@require_POST
def pagar_cuota_inversionista(request, pk):
    if not _puede_ver_finanzas(request.user):
        return redirect("/")
    cuota = get_object_or_404(InvestorPayment, pk=pk)
    cuota.pagado = True
    cuota.fecha_pago = timezone.localdate()
    cuota.referencia_pago = request.POST.get("referencia_pago", "").strip()
    cuota.pagado_por = request.user
    cuota.save(update_fields=["pagado", "fecha_pago", "referencia_pago", "pagado_por", "actualizado_en"])
    messages.success(request, "Interés mensual marcado como pagado. El capital no fue modificado.")
    return redirect("finanzas:inversionistas")
