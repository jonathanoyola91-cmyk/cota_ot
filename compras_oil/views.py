from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from core.roles import tiene_rol
from .forms import SupplierForm
from .models import PurchaseRequest, Supplier


@login_required
def dashboard(request):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes acceso a Compras.")
        return redirect("/")

    compras_all = PurchaseRequest.objects.all().order_by("-actualizado_en")

    compras = (
        PurchaseRequest.objects
        .exclude(estado="CERRADA")
        .select_related("bom", "bom__workorder", "creado_por")
        .annotate(
            total_lineas=Count("lineas", distinct=True),
            lineas_diligenciadas=Count(
                "lineas",
                filter=(
                    Q(lineas__proveedor__isnull=False) &
                    Q(lineas__precio_unitario__isnull=False)
                ),
                distinct=True
            ),
            lineas_pagadas=Count(
                "lineas__finance_line",
                filter=Q(lineas__finance_line__pagado=True),
                distinct=True
            )
        )
        .order_by("-actualizado_en")
    )

    for compra in compras:
        compra.porcentaje_avance = int(
            (compra.lineas_diligenciadas / compra.total_lineas) * 100
        ) if compra.total_lineas > 0 else 0

    context = {
        "compras": compras,
        "total_solicitudes": compras_all.count(),
        "total_borrador": compras_all.filter(estado="BORRADOR").count(),
        "total_revision": compras_all.filter(estado="EN_REVISION").count(),
        "total_cerrada": compras_all.filter(estado="CERRADA").count(),
        "total_activas": compras.count(),
    }

    return render(request, "compras_oil/dashboard.html", context)


@login_required
def compras_dashboard(request):
    return dashboard(request)


@login_required
def cerrar_solicitud(request, pk):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para cerrar solicitudes.")
        return redirect("/")

    compra = get_object_or_404(PurchaseRequest, pk=pk)

    if request.method == "POST":
        compra.estado = "CERRADA"
        compra.save(update_fields=["estado", "actualizado_en"])
        messages.success(
            request,
            f"Solicitud PAW {compra.paw_numero} cerrada correctamente."
        )

    return redirect("compras_oil:dashboard")


@login_required
def supplier_detail(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)

    return render(request, "compras_oil/supplier_detail.html", {
        "supplier": supplier,
    })


@login_required
def supplier_create(request):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para crear proveedores.")
        return redirect("/")

    next_url = request.GET.get("next")

    if request.method == "POST":
        form = SupplierForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Proveedor creado correctamente.")

            if next_url:
                return redirect(next_url)

            return redirect("compras_oil:dashboard")
    else:
        form = SupplierForm()

    return render(request, "compras_oil/supplier_form.html", {
        "form": form,
        "next_url": next_url,
    })


@login_required
def purchase_request_pdf(request, pk: int):
    pr = get_object_or_404(
        PurchaseRequest.objects
        .select_related("bom", "bom__workorder")
        .prefetch_related("lineas", "lineas__proveedor"),
        pk=pk,
    )

    buffer = BytesIO()

    try:
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        story = []

        wo_num = getattr(getattr(pr.bom, "workorder", None), "numero", "-")

        story.append(Paragraph("Solicitud de Compra", styles["Title"]))
        story.append(Spacer(1, 8))
        story.append(Paragraph(f"<b>OT:</b> {wo_num}", styles["Normal"]))
        story.append(Paragraph(f"<b>BOM:</b> {pr.bom}", styles["Normal"]))
        story.append(Paragraph(f"<b>Estado:</b> {pr.estado}", styles["Normal"]))
        story.append(Spacer(1, 12))

        header = [
            "Plano", "Código", "Descripción", "U/M",
            "Req.", "Disp.", "A comprar",
            "Proveedor", "P.Unit", "Subtotal"
        ]

        data = [header]
        total = Decimal("0")

        cell_style = styles["Normal"]
        cell_style.fontSize = 8
        cell_style.leading = 9

        for ln in pr.lineas.all():
            a = Decimal(ln.cantidad_a_comprar or 0)
            p = Decimal(ln.precio_unitario or 0)
            subtotal = a * p
            total += subtotal

            descripcion = Paragraph(
                (ln.descripcion or "").replace("\n", "<br/>"),
                cell_style
            )

            proveedor = Paragraph(
                (ln.proveedor.nombre if ln.proveedor else ""),
                cell_style
            )

            data.append([
                ln.plano or "",
                ln.codigo or "",
                descripcion,
                ln.unidad or "",
                f"{Decimal(ln.cantidad_requerida or 0):,.3f}",
                f"{Decimal(ln.cantidad_disponible or 0):,.3f}",
                f"{a:,.3f}",
                proveedor,
                f"{p:,.2f}",
                f"{subtotal:,.2f}",
            ])

        data.append(["", "", "", "", "", "", "", "", "TOTAL", f"{total:,.2f}"])

        table = Table(
            data,
            colWidths=[45, 55, 180, 30, 35, 35, 45, 80, 45, 55],
            repeatRows=1,
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))

        story.append(table)
        doc.build(story)

        buffer.seek(0)

        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = (
            f'attachment; filename="solicitud_compra_{pr.pk}.pdf"'
        )
        return resp

    finally:
        buffer.close()


@login_required
def purchase_request_excel(request, pk: int):
    pr = get_object_or_404(
        PurchaseRequest.objects
        .select_related("bom", "bom__workorder")
        .prefetch_related("lineas", "lineas__proveedor"),
        pk=pk,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Solicitud de Compra"

    wo_num = getattr(getattr(pr.bom, "workorder", None), "numero", "-")

    ws.append(["Solicitud de Compra"])
    ws.append(["OT", str(wo_num)])
    ws.append(["BOM", str(pr.bom)])
    ws.append(["Estado", str(pr.estado)])
    ws.append([])

    headers = [
        "Plano", "Código", "Descripción", "U/M",
        "Req.", "Disp.", "A comprar",
        "Proveedor", "P.Unit", "Subtotal"
    ]

    ws.append(headers)

    total = Decimal("0")

    for ln in pr.lineas.all():
        a = Decimal(ln.cantidad_a_comprar or 0)
        p = Decimal(ln.precio_unitario or 0)
        subtotal = a * p
        total += subtotal

        ws.append([
            ln.plano or "",
            ln.codigo or "",
            ln.descripcion or "",
            ln.unidad or "",
            float(Decimal(ln.cantidad_requerida or 0)),
            float(Decimal(ln.cantidad_disponible or 0)),
            float(a),
            ln.proveedor.nombre if ln.proveedor else "",
            float(p),
            float(subtotal),
        ])

    ws.append(["", "", "", "", "", "", "", "", "TOTAL", float(total)])

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18

    response = HttpResponse(
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
    response["Content-Disposition"] = (
        f'attachment; filename="solicitud_compra_{pr.pk}.xlsx"'
    )

    wb.save(response)
    return response


@login_required
def paw_detail(request, pk):
    compra = get_object_or_404(
        PurchaseRequest.objects
        .select_related("bom", "bom__workorder", "creado_por")
        .prefetch_related("lineas__proveedor"),
        pk=pk
    )

    from .forms import PurchaseLineFormSet

    queryset = compra.lineas.filter(cantidad_a_comprar__gt=0).order_by("id")

    if request.method == "POST":
        if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
            messages.error(request, "No tienes permiso para editar esta solicitud.")
            return redirect("compras_oil:paw_detail", pk=compra.pk)

        nuevo_estado = request.POST.get("estado")

        if nuevo_estado in ["BORRADOR", "EN_REVISION", "CERRADA"]:
            compra.estado = nuevo_estado
            compra.save(update_fields=["estado", "actualizado_en"])

        formset = PurchaseLineFormSet(request.POST, queryset=queryset)

        if formset.is_valid():
            formset.save()
            messages.success(
                request,
                "Solicitud de compra actualizada correctamente."
            )
            return redirect("compras_oil:paw_detail", pk=compra.pk)
    else:
        formset = PurchaseLineFormSet(queryset=queryset)

    total_requerido = Decimal("0")
    total_a_comprar = Decimal("0")

    for ln in queryset:
        precio = ln.precio_unitario or Decimal("0")
        total_requerido += (ln.cantidad_requerida or Decimal("0")) * precio
        total_a_comprar += (ln.cantidad_a_comprar or Decimal("0")) * precio

    return render(request, "compras_oil/paw_detail.html", {
        "compra": compra,
        "lineas": queryset,
        "formset": formset,
        "total_requerido": total_requerido,
        "total_a_comprar": total_a_comprar,
        "puede_compras": tiene_rol(request.user, ["COMPRAS", "ADMIN"]),
    })


@require_POST
@login_required
def enviar_finanzas(request, pk):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para enviar a Finanzas.")
        return redirect("/")

    from finanzas.models import FinanceApproval

    compra = get_object_or_404(PurchaseRequest, pk=pk)

    if not compra.lineas.filter(tipo_pago="CONTADO").exists():
        messages.error(
            request,
            "No hay líneas de pago contado para enviar a Finanzas."
        )
        return redirect("compras_oil:paw_detail", pk=compra.pk)

    paw = compra.bom.workorder.paw

    if paw:
        paw.estado_operativo = "EN_FINANZAS"
        paw.save(update_fields=["estado_operativo"])

    FinanceApproval.objects.get_or_create(
        purchase_request=compra,
        defaults={
            "estado": FinanceApproval.Estado.PENDIENTE,
            "enviado_por": request.user,
        },
    )

    messages.success(request, "PAW enviado a Finanzas correctamente.")
    return redirect("compras_oil:paw_detail", pk=compra.pk)


@require_POST
@login_required
def enviar_aprobacion(request, pk):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para enviar a Aprobación.")
        return redirect("/")

    from aprobacion.models import PurchaseApproval
    from aprobacion.admin import sync_purchase_approval_lines

    compra = get_object_or_404(PurchaseRequest, pk=pk)

    if not compra.lineas.filter(tipo_pago="CREDITO").exists():
        messages.error(
            request,
            "No hay líneas de crédito para enviar a Aprobación."
        )
        return redirect("compras_oil:paw_detail", pk=compra.pk)

    paw = compra.bom.workorder.paw

    if paw:
        paw.estado_operativo = "EN_APROBACION"
        paw.save(update_fields=["estado_operativo"])

    aprobacion, created = PurchaseApproval.objects.get_or_create(
        purchase_request=compra,
        defaults={
            "estado": PurchaseApproval.Estado.PENDIENTE,
            "enviado_por": request.user,
        },
    )

    sync_purchase_approval_lines(aprobacion, refresh_pending_only=True)
    aprobacion.recalcular_estado()
    aprobacion.save()

    messages.success(
        request,
        "PAW enviado a Aprobación de Compras correctamente."
    )
    return redirect("compras_oil:paw_detail", pk=compra.pk)


@require_POST
@login_required
def enviar_inventario(request, pk):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para enviar a Inventario.")
        return redirect("/")

    from inventario.models import InventoryReception, InventoryReceptionLine

    compra = get_object_or_404(
        PurchaseRequest.objects.prefetch_related("lineas"),
        pk=pk,
    )

    paw = compra.bom.workorder.paw

    if paw:
        paw.estado_operativo = "MATERIAL_RECIBIDO"
        paw.save(update_fields=["estado_operativo"])

    recepcion, _ = InventoryReception.objects.get_or_create(
        purchase_request=compra,
        defaults={"creado_por": request.user},
    )

    for ln in compra.lineas.all():

        cantidad = ln.cantidad_a_comprar or 0

        # 🔥 FILTRO CLAVE
        if cantidad <= 0:
            continue

        InventoryReceptionLine.objects.get_or_create(
            recepcion=recepcion,
            purchase_line=ln,
            defaults={
                "codigo": ln.codigo or "",
                "descripcion": ln.descripcion or "",
                "unidad": ln.unidad or "",
                "cantidad_esperada": cantidad,
                "cantidad_recibida": 0,
                "estado": "PENDIENTE",
            },
        )

    messages.success(request, "PAW enviado a Inventario correctamente.")
    return redirect("compras_oil:paw_detail", pk=compra.pk)

@require_POST
@login_required
def generar_entrega_taller(request, pk):
    if not tiene_rol(request.user, ["COMPRAS", "ADMIN"]):
        messages.error(request, "No tienes permiso para generar entrega a taller.")
        return redirect("/")

    from inventario.models import WorkshopDelivery, WorkshopDeliveryLine

    compra = get_object_or_404(
        PurchaseRequest.objects.prefetch_related("lineas"),
        pk=pk,
    )

    paw = compra.bom.workorder.paw

    if paw:
        paw.estado_operativo = "ENTREGADO_TALLER"
        paw.save(update_fields=["estado_operativo"])

    entrega, _ = WorkshopDelivery.objects.get_or_create(
        purchase_request=compra,
        defaults={"creado_por": request.user},
    )

    creadas = 0

    for ln in compra.lineas.all():

        cantidad = ln.cantidad_requerida or 0

        # 🔥 FILTRO CLAVE
        if cantidad <= 0:
            continue

        _, created = WorkshopDeliveryLine.objects.get_or_create(
            delivery=entrega,
            purchase_line=ln,
            defaults={
                "codigo": ln.codigo or "",
                "descripcion": ln.descripcion or "",
                "unidad": ln.unidad or "",
                "cantidad_requerida": cantidad,
            },
        )

        if created:
            creadas += 1

    messages.success(
        request,
        f"Entrega a Taller generada correctamente. Líneas nuevas: {creadas}."
    )
    return redirect("compras_oil:paw_detail", pk=compra.pk)