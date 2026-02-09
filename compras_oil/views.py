from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from io import BytesIO
from decimal import Decimal

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

from .models import PurchaseRequest


@login_required
def purchase_request_pdf(request, pk: int):
    pr = get_object_or_404(
        PurchaseRequest.objects.select_related("bom", "bom__workorder").prefetch_related("lineas", "lineas__proveedor"),
        pk=pk,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story = []

    wo_num = getattr(getattr(pr.bom, "workorder", None), "numero", "-")

    story.append(Paragraph("Solicitud de Compra", styles["Title"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>OT:</b> {wo_num}", styles["Normal"]))
    story.append(Paragraph(f"<b>BOM:</b> {pr.bom}", styles["Normal"]))
    story.append(Paragraph(f"<b>Estado:</b> {pr.estado}", styles["Normal"]))
    story.append(Spacer(1, 12))

    data = [[
        "Plano", "Código", "Descripción", "U/M",
        "Req.", "Disp.", "A comprar",
        "Proveedor", "P.Unit", "Subtotal"
    ]]

    total = Decimal("0")

    for ln in pr.lineas.all():
        a = Decimal(ln.cantidad_a_comprar or 0)
        p = Decimal(ln.precio_unitario or 0)
        subtotal = a * p
        total += subtotal
        data.append([
            ln.plano or "",
            ln.codigo or "",
            ln.descripcion or "",
            ln.unidad or "",
            f"{Decimal(ln.cantidad_requerida or 0):,.3f}",
            f"{Decimal(ln.cantidad_disponible or 0):,.3f}",
            f"{a:,.3f}",
            (ln.proveedor.nombre if ln.proveedor else ""),
            (f"{p:,.2f}" if ln.precio_unitario is not None else ""),
            (f"{subtotal:,.2f}" if subtotal else ""),
        ])

    data.append(["", "", "", "", "", "", "", "", "TOTAL", f"{total:,.2f}"])

    table = Table(data, colWidths=[45, 55, 180, 30, 35, 35, 45, 80, 45, 55], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
    ]))

    story.append(table)
    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="solicitud_compra_{pr.pk}.pdf"'
    return resp
