from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import F

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import InventoryReception, InventoryReceptionLine, WorkshopDelivery


@login_required
def inventario_dashboard(request):
    recepciones = (
        InventoryReception.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    for r in recepciones:
        total = r.lineas.count()
        listas = r.lineas.filter(cantidad_recibida__gte=F("cantidad_esperada")).count()

        r.total_lineas = total
        r.lineas_listas = listas

        if total > 0:
            r.porcentaje = round((listas / total) * 100)
        else:
            r.porcentaje = 0

    entregas = (
        WorkshopDelivery.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    return render(request, "inventario/dashboard.html", {
        "recepciones": recepciones,
        "entregas": entregas,
        "total_recepciones": recepciones.count(),
        "total_entregas": entregas.count(),
        "lineas_pendientes": InventoryReceptionLine.objects.filter(estado="PENDIENTE").count(),
        "lineas_parciales": InventoryReceptionLine.objects.filter(estado="PARCIAL").count(),
        "lineas_listas": InventoryReceptionLine.objects.filter(estado="LISTO").count(),
    })


@login_required
def recepcion_detail(request, pk):
    recepcion = get_object_or_404(
        InventoryReception.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas__purchase_line"),
        pk=pk
    )

    # Corrige recepciones antiguas que fueron creadas sin código/descripcion/unidad.
    for linea in recepcion.lineas.all():
        if linea.purchase_line:
            actualizado = False

            if not linea.codigo:
                linea.codigo = linea.purchase_line.codigo or ""
                actualizado = True

            if not linea.descripcion:
                linea.descripcion = linea.purchase_line.descripcion or ""
                actualizado = True

            if not linea.unidad:
                linea.unidad = linea.purchase_line.unidad or ""
                actualizado = True

            if actualizado:
                linea.save(update_fields=["codigo", "descripcion", "unidad"])

    if request.method == "POST":
        for linea in recepcion.lineas.all():
            raw = request.POST.get(f"cantidad_recibida_{linea.id}") or "0"

            try:
                cantidad = Decimal(raw.replace(",", "."))
            except Exception:
                cantidad = Decimal("0")

            fecha = request.POST.get(f"fecha_llegada_{linea.id}") or None
            observacion = request.POST.get(f"observacion_{linea.id}") or ""

            linea.cantidad_recibida = cantidad
            linea.fecha_llegada = fecha
            linea.observacion_inventario = observacion

            esperada = Decimal(linea.cantidad_esperada or 0)

            if cantidad <= 0:
                linea.estado = "PENDIENTE"
            elif cantidad < esperada:
                linea.estado = "PARCIAL"
            else:
                linea.estado = "LISTO"

            linea.save()

        total = recepcion.lineas.count()
        listas = recepcion.lineas.filter(estado="LISTO").count()
        parciales = recepcion.lineas.filter(estado="PARCIAL").count()

        try:
            paw = recepcion.purchase_request.bom.workorder.paw

            if total > 0 and listas == total:
                paw.estado_operativo = "MATERIAL_RECIBIDO"
            elif listas > 0 or parciales > 0:
                paw.estado_operativo = "MATERIAL_PARCIAL"

            paw.save(update_fields=["estado_operativo"])
        except Exception:
            pass

        messages.success(request, "Recepción de inventario actualizada correctamente.")
        return redirect("inventario:recepcion_detail", pk=recepcion.pk)

    return render(request, "inventario/recepcion_detail.html", {
        "recepcion": recepcion
    })


@login_required
def entrega_taller_detail(request, pk):
    entrega = get_object_or_404(
        WorkshopDelivery.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas"),
        pk=pk
    )

    if request.method == "POST":

        for linea in entrega.lineas.all():
            raw = request.POST.get(f"cantidad_entregada_{linea.id}") or "0"

            try:
                cantidad = Decimal(raw.replace(",", "."))
            except Exception:
                cantidad = Decimal("0")

            linea.cantidad_entregada = cantidad

            requerida = Decimal(linea.cantidad_requerida or 0)

            if cantidad <= 0:
                linea.estado = "PENDIENTE"
            elif cantidad < requerida:
                linea.estado = "PARCIAL"
            else:
                linea.estado = "ENTREGADO"

            linea.save()

        entrega.comentarios = request.POST.get("comentarios", "")
        entrega.save(update_fields=["comentarios"])

        messages.success(request, "Entrega a taller actualizada correctamente.")
        return redirect("inventario:entrega_taller_detail", pk=entrega.pk)

    return render(request, "inventario/entrega_taller_detail.html", {
        "entrega": entrega
    })

@login_required
def entrega_taller_pdf(request, pk):
    entrega = get_object_or_404(
        WorkshopDelivery.objects
        .select_related("purchase_request")
        .prefetch_related("lineas"),
        pk=pk
    )

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>ENTREGA TALLER</b>", styles["Title"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"<b>Paw #:</b> {entrega.purchase_request.paw_numero} "
        f"&nbsp;&nbsp;&nbsp; <b>Nombre PAW:</b> {entrega.purchase_request.paw_nombre}",
        styles["Normal"]
    ))

    story.append(Paragraph(
        f"<b>Fecha impresión:</b> {timezone.now().date()}",
        styles["Normal"]
    ))

    story.append(Spacer(1, 12))

    data = [[
        "CÓDIGO",
        "DESCRIPCIÓN",
        "UNID",
        "CANT. REQ",
        "CANT. ENT",
    ]]

    for linea in entrega.lineas.all():
        data.append([
            linea.codigo or "",
            Paragraph(linea.descripcion or "", styles["Normal"]),
            linea.unidad or "",
            f"{Decimal(linea.cantidad_requerida or 0):.0f}",
            f"{Decimal(linea.cantidad_entregada or 0):.0f}",
        ])

    table = Table(
        data,
        colWidths=[70, 270, 45, 65, 65],
        repeatRows=1,
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    story.append(table)

    story.append(Spacer(1, 18))
    story.append(Paragraph("<b>Comentarios</b>", styles["Heading3"]))
    story.append(Paragraph(entrega.comentarios or " ", styles["Normal"]))

    story.append(Spacer(1, 36))
    story.append(Paragraph("<b>Firmas</b>", styles["Heading3"]))
    story.append(Spacer(1, 32))

    firmas = Table([
        ["__________________________", "__________________________"],
        ["Firma entrega", "Firma recibe (Taller)"],
        ["", ""],
        ["Fecha", "Fecha"],
    ], colWidths=[250, 250])

    firmas.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))

    story.append(firmas)
    doc.build(story)

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="ENTREGA_TALLER_{entrega.purchase_request.paw_numero}.pdf"'
    )
    return response