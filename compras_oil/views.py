from decimal import Decimal
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from .models import PurchaseRequest

@login_required
def purchase_request_pdf(request, pk: int):
    pr = get_object_or_404(
        PurchaseRequest.objects.select_related("bom", "bom__workorder").prefetch_related("lineas", "lineas__proveedor"),
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

        # Estilo compacto para celdas largas
        cell_style = styles["Normal"]
        cell_style.fontSize = 8
        cell_style.leading = 9

        for ln in pr.lineas.all():
            a = Decimal(ln.cantidad_a_comprar or 0)
            p = Decimal(ln.precio_unitario or 0)
            subtotal = a * p
            total += subtotal

            descripcion = Paragraph((ln.descripcion or "").replace("\n", "<br/>"), cell_style)
            proveedor = Paragraph((ln.proveedor.nombre if ln.proveedor else ""), cell_style)

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

        # Fila TOTAL
        data.append(["", "", "", "", "", "", "", "", "TOTAL", f"{total:,.2f}"])

        table = Table(
            data,
            colWidths=[45, 55, 180, 30, 35, 35, 45, 80, 45, 55],
            repeatRows=1,
        )

        table.setStyle(TableStyle([
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),

            # Grid
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),

            # Align números (desde fila 1 para no afectar header)
            ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),

            # TOTAL row styling (última fila)
            ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]))

        story.append(table)
        doc.build(story)

        buffer.seek(0)
        resp = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="solicitud_compra_{pr.pk}.pdf"'
        return resp

    finally:
        buffer.close()

@login_required
def purchase_request_excel(request, pk: int):
    pr = get_object_or_404(
        PurchaseRequest.objects.select_related("bom", "bom__workorder")
        .prefetch_related("lineas", "lineas__proveedor"),
        pk=pk,
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Solicitud de Compra"

    # Cabecera
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
            (ln.proveedor.nombre if ln.proveedor else ""),
            float(p),
            float(subtotal),
        ])

    ws.append(["", "", "", "", "", "", "", "", "TOTAL", float(total)])

    # Ajustar ancho columnas
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="solicitud_compra_{pr.pk}.xlsx"'
    )

    wb.save(response)
    return response

