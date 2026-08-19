from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import F, Q

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import InventoryReception, InventoryReceptionLine, WorkshopDelivery


@login_required
def inventario_dashboard(request):
    # ======================================================
    # RECEPCIONES: solo pendientes o parciales
    # ======================================================
    recepciones_qs = (
        InventoryReception.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    recepciones_pendientes = []
    recepciones_completas = []

    for r in recepciones_qs:
        lineas = list(r.lineas.all())
        total = len(lineas)
        listas = 0
        parciales = 0

        for linea in lineas:
            esperada = Decimal(linea.cantidad_esperada or 0)
            recibida = Decimal(linea.cantidad_recibida or 0)

            if esperada > 0 and recibida >= esperada:
                listas += 1
            elif recibida > 0:
                parciales += 1

        r.total_lineas = total
        r.lineas_listas = listas
        r.lineas_parciales = parciales
        r.recepcion_completa = total > 0 and listas == total

        if total > 0:
            r.porcentaje = round((listas / total) * 100)
        else:
            r.porcentaje = 0

        if r.recepcion_completa:
            recepciones_completas.append(r)
        else:
            recepciones_pendientes.append(r)

    # ======================================================
    # ENTREGAS: separar taller activo vs historial
    # ======================================================
    entregas_qs = (
        WorkshopDelivery.objects
        .select_related("purchase_request", "creado_por")
        .prefetch_related("lineas")
        .order_by("-actualizado_en")
    )

    entregas_taller_pendientes = []
    historial_entregas = []

    for entrega in entregas_qs:
        lineas = list(entrega.lineas.all())
        total_lineas = len(lineas)
        lineas_completas = 0
        cantidad_requerida_total = Decimal("0")
        cantidad_entregada_total = Decimal("0")

        for linea in lineas:
            requerida = Decimal(linea.cantidad_requerida or 0)
            entregada = Decimal(linea.cantidad_entregada or 0)

            cantidad_requerida_total += requerida
            if requerida > 0:
                cantidad_entregada_total += min(entregada, requerida)

            if requerida <= 0 or entregada >= requerida:
                lineas_completas += 1

        entrega.total_lineas = total_lineas
        entrega.lineas_completas = lineas_completas
        entrega.entrega_completa = (
            total_lineas > 0
            and lineas_completas == total_lineas
        )

        if cantidad_requerida_total > 0:
            entrega.porcentaje_entrega = min(
                100,
                round(float(
                    (cantidad_entregada_total / cantidad_requerida_total) * 100
                ))
            )
        else:
            entrega.porcentaje_entrega = 0

        destino = str(getattr(entrega, "destino", "TALLER") or "TALLER").upper()
        entrega.destino_codigo = destino

        # TALLER:
        # - pendiente/parcial permanece en el bloque operativo.
        # - completa pasa a historial.
        #
        # CAMPO / INVENTARIO (cliente):
        # - se consideran salida de Inventario y se muestran en historial,
        #   porque Inventario ya no tiene una entrega a Taller que gestionar.
        if destino == "TALLER" and not entrega.entrega_completa:
            entregas_taller_pendientes.append(entrega)
        else:
            historial_entregas.append(entrega)

    return render(request, "inventario/dashboard.html", {
        "recepciones": recepciones_pendientes,
        "recepciones_completas": recepciones_completas,
        "entregas": entregas_taller_pendientes,
        "historial_entregas": historial_entregas,

        "total_recepciones": len(recepciones_pendientes),
        "total_recepciones_completas": len(recepciones_completas),
        "total_entregas": len(entregas_taller_pendientes),
        "total_historial_entregas": len(historial_entregas),

        "lineas_pendientes": InventoryReceptionLine.objects.filter(
            estado="PENDIENTE"
        ).count(),
        "lineas_parciales": InventoryReceptionLine.objects.filter(
            estado="PARCIAL"
        ).count(),
        "lineas_listas": InventoryReceptionLine.objects.filter(
            estado="LISTO"
        ).count(),
    })

def _enviar_alerta_recepcion(recepcion, porcentaje, pendientes, umbral):
    """
    Envía una alerta inmediata cuando una recepción alcanza por primera vez
    el 80% o el 100%. Los destinatarios son COMPRAS, ALERTAS_TALLER y
    superusuarios activos con correo.
    """
    User = get_user_model()

    destinatarios = list(
        User.objects.filter(is_active=True)
        .filter(
            Q(groups__name="COMPRAS")
            | Q(groups__name="ALERTAS_TALLER")
            | Q(is_superuser=True)
        )
        .exclude(email="")
        .values_list("email", flat=True)
        .distinct()
    )

    if not destinatarios:
        return 0

    pr = recepcion.purchase_request
    paw_numero = getattr(pr, "paw_numero", None) or "-"
    paw_nombre = getattr(pr, "paw_nombre", "") or ""

    base_url = getattr(
        settings,
        "IMPETUS_CONTROL_URL",
        "https://www.impetuscontrol.com",
    ).rstrip("/")

    inventario_url = f"{base_url}/inventario/recepcion/{recepcion.pk}/"
    taller_url = f"{base_url}/taller/"

    if umbral == 100:
        asunto = f"IMPETUS CONTROL · PAW #{paw_numero} · Recepción 100% completa"
        titulo = "Recepción de material 100% completa"
        mensaje_estado = (
            "Inventario confirmó la recepción completa de los materiales "
            "asociados al PAW. Taller puede continuar con la programación "
            "correspondiente."
        )
    else:
        asunto = f"IMPETUS CONTROL · PAW #{paw_numero} · Recepción {porcentaje}%"
        titulo = "Recepción de material alcanzó el 80%"
        mensaje_estado = (
            "La recepción alcanzó al menos el 80%. Se recomienda a Taller "
            "evaluar si los componentes recibidos permiten iniciar o avanzar "
            "el ensamble."
        )

    pendientes_texto = ""
    pendientes_html = ""

    if pendientes:
        pendientes_texto = "\n\nMATERIALES AÚN PENDIENTES:\n"
        filas = []

        for item in pendientes:
            pendientes_texto += (
                f"- {item['codigo']} | {item['descripcion']} | "
                f"Pendiente: {item['faltante']} {item['unidad']}\n"
            )

            filas.append(
                "<tr>"
                f"<td style='padding:8px;border-bottom:1px solid #e5e7eb;'>{item['codigo']}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #e5e7eb;'>{item['descripcion']}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #e5e7eb;'>{item['faltante']}</td>"
                f"<td style='padding:8px;border-bottom:1px solid #e5e7eb;'>{item['unidad']}</td>"
                "</tr>"
            )

        pendientes_html = f"""
        <h3 style="margin-top:22px;">Materiales aún pendientes</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
                <tr style="background:#f8fafc;">
                    <th style="text-align:left;padding:8px;">Código</th>
                    <th style="text-align:left;padding:8px;">Descripción</th>
                    <th style="text-align:left;padding:8px;">Faltante</th>
                    <th style="text-align:left;padding:8px;">Unidad</th>
                </tr>
            </thead>
            <tbody>{''.join(filas)}</tbody>
        </table>
        """

    texto = (
        f"{titulo}\n\n"
        f"PAW #{paw_numero} - {paw_nombre}\n"
        f"Recepción actual: {porcentaje}%\n\n"
        f"{mensaje_estado}"
        f"{pendientes_texto}\n"
        f"Revisar recepción: {inventario_url}\n"
        f"Revisar Taller: {taller_url}\n"
    )

    html = f"""
    <!doctype html>
    <html>
    <body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#0f172a;">
        <div style="max-width:850px;margin:auto;padding:24px;">
            <div style="background:#0f172a;color:#fff;padding:22px 24px;border-radius:14px 14px 0 0;">
                <div style="font-size:12px;color:#cbd5e1;font-weight:700;">IMPETUS CONTROL</div>
                <div style="font-size:24px;font-weight:800;margin-top:6px;">{titulo}</div>
            </div>
            <div style="background:#fff;padding:24px;border-radius:0 0 14px 14px;">
                <p><strong>PAW #{paw_numero}</strong> — {paw_nombre}</p>
                <p style="font-size:28px;font-weight:800;margin:16px 0;">Recepción: {porcentaje}%</p>
                <p style="color:#475569;">{mensaje_estado}</p>

                {pendientes_html}

                <div style="margin-top:26px;">
                    <a href="{inventario_url}"
                       style="display:inline-block;background:#2563eb;color:#fff;
                              padding:11px 16px;border-radius:8px;text-decoration:none;
                              font-weight:800;margin-right:8px;">
                        Revisar recepción
                    </a>
                    <a href="{taller_url}"
                       style="display:inline-block;background:#16a34a;color:#fff;
                              padding:11px 16px;border-radius:8px;text-decoration:none;
                              font-weight:800;">
                        Revisar Taller
                    </a>
                </div>

                <p style="margin-top:24px;color:#64748b;font-size:12px;">
                    Notificación automática generada al alcanzar este umbral por primera vez.
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    enviados = 0
    for correo in destinatarios:
        try:
            msg = EmailMultiAlternatives(
                subject=asunto,
                body=texto,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[correo],
            )
            msg.attach_alternative(html, "text/html")
            enviados += msg.send(fail_silently=False)
        except Exception:
            # Una dirección inválida no debe impedir que Inventario guarde la recepción.
            continue

    return enviados


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

        # ======================================================
        # ALERTAS EN VIVO DE RECEPCIÓN: 80% Y 100%
        # Se calcula por cantidad recibida / cantidad esperada,
        # no por número de líneas, para representar mejor el avance real.
        # ======================================================
        cantidad_esperada_total = Decimal("0")
        cantidad_recibida_total = Decimal("0")
        pendientes = []

        for linea in recepcion.lineas.all():
            esperada = Decimal(linea.cantidad_esperada or 0)
            recibida = Decimal(linea.cantidad_recibida or 0)

            if esperada <= 0:
                continue

            cantidad_esperada_total += esperada
            cantidad_recibida_total += min(max(recibida, Decimal("0")), esperada)

            faltante = max(esperada - recibida, Decimal("0"))
            if faltante > 0:
                pendientes.append({
                    "codigo": linea.codigo or "-",
                    "descripcion": linea.descripcion or "",
                    "faltante": f"{faltante.normalize()}",
                    "unidad": linea.unidad or "",
                })

        if cantidad_esperada_total > 0:
            porcentaje_recepcion = int(
                (cantidad_recibida_total / cantidad_esperada_total) * Decimal("100")
            )
            porcentaje_recepcion = min(100, max(0, porcentaje_recepcion))
        else:
            porcentaje_recepcion = 0

        # Primero 80%. Si una recepción pasa directamente de <80 a 100,
        # se envía únicamente la alerta de 100% para evitar dos correos simultáneos.
        if porcentaje_recepcion >= 100 and not recepcion.notificacion_100_en:
            enviados = _enviar_alerta_recepcion(
                recepcion=recepcion,
                porcentaje=100,
                pendientes=[],
                umbral=100,
            )
            if enviados:
                ahora = timezone.now()
                recepcion.notificacion_100_en = ahora
                # También marcamos 80 como cumplido: no debe enviarse después.
                if not recepcion.notificacion_80_en:
                    recepcion.notificacion_80_en = ahora
                recepcion.save(
                    update_fields=[
                        "notificacion_80_en",
                        "notificacion_100_en",
                        "actualizado_en",
                    ]
                )

        elif porcentaje_recepcion >= 80 and not recepcion.notificacion_80_en:
            enviados = _enviar_alerta_recepcion(
                recepcion=recepcion,
                porcentaje=porcentaje_recepcion,
                pendientes=pendientes,
                umbral=80,
            )
            if enviados:
                recepcion.notificacion_80_en = timezone.now()
                recepcion.save(
                    update_fields=["notificacion_80_en", "actualizado_en"]
                )

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
        entrega.comentarios = request.POST.get("comentarios", "")
        entrega.save(update_fields=["comentarios", "actualizado_en"])

        for linea in entrega.lineas.all():
            raw = request.POST.get(f"cantidad_entregada_{linea.id}")
            if raw is None or raw == "":
                continue
            try:
                cantidad = Decimal(str(raw).replace(",", "."))
            except Exception:
                cantidad = Decimal("0")
            linea.cantidad_entregada = max(cantidad, Decimal("0"))
            linea.save(update_fields=["cantidad_entregada"])

        completa = True
        for linea in entrega.lineas.all():
            req = Decimal(linea.cantidad_requerida or 0)
            ent = Decimal(linea.cantidad_entregada or 0)
            if req > 0 and ent < req:
                completa = False
                break

        if completa:
            try:
                paw = entrega.purchase_request.bom.workorder.paw
                destino = getattr(entrega, "destino", "TALLER")
                if destino == "TALLER" and getattr(paw, "aplica_taller", True):
                    paw.estado_operativo = "ENTREGADO_TALLER"
                elif destino == "INVENTARIO" and not getattr(paw, "aplica_taller", False) and not getattr(paw, "aplica_campo", False):
                    paw.estado_operativo = "PRODUCTO_OK"
                else:
                    paw.estado_operativo = "MATERIAL_RECIBIDO"
                paw.save(update_fields=["estado_operativo"])
            except Exception:
                pass

        messages.success(request, f"Entrega a {entrega.get_destino_display()} actualizada correctamente.")
        return redirect("inventario:entrega_taller_detail", pk=entrega.pk)

    return render(request, "inventario/entrega_taller_detail.html", {"entrega": entrega})


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

    story.append(Paragraph(f"<b>ENTREGA {entrega.get_destino_display().upper()}</b>", styles["Title"]))
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