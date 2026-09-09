from decimal import Decimal
from io import BytesIO
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.db.models import F, Q, Count
from django.db import transaction
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import InventoryReception, InventoryReceptionLine, WorkshopDelivery
from auditoria.utils import registrar_movimiento


def inventario_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        permitido = (
            request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.groups.filter(name__iexact="INVENTARIO").exists()
            )
        )

        if not permitido:
            messages.error(
                request,
                "No tienes permiso para acceder al módulo de Inventario."
            )
            return redirect("/")

        return view_func(request, *args, **kwargs)

    return wrapper


@login_required
@inventario_required
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

    # ======================================================
    # BOM / SOLICITUDES PENDIENTES DE REVISIÓN DE INVENTARIO
    # La solicitud puede existir técnicamente, pero Compras no la ve hasta
    # que Inventario confirme cantidades disponibles.
    # ======================================================
    from compras_oil.models import PurchaseRequest

    revisiones_pendientes = (
        PurchaseRequest.objects
        .filter(inventario_revisado_en__isnull=True)
        .exclude(estado="CERRADA")
        .select_related("bom", "bom__workorder", "creado_por")
        .annotate(
            total_lineas_bom=Count(
                "lineas",
                filter=Q(lineas__cantidad_requerida__gt=0),
                distinct=True,
            )
        )
        .order_by("creado_en")
    )

    # PAW revisados que ya tienen todo el material necesario disponible
    # (por stock o por recepción de compra) y aún no tienen entrega generada.
    candidatos_entrega = (
        PurchaseRequest.objects
        .filter(inventario_revisado_en__isnull=False)
        .exclude(estado="CERRADA")
        .select_related("bom", "bom__workorder")
        .prefetch_related("lineas", "recepcion_inventario__lineas")
        .order_by("actualizado_en")
    )
    listos_para_entrega = []
    for compra in candidatos_entrega:
        try:
            compra.entrega_taller
            continue
        except Exception:
            pass
        if _material_comprado_completamente_recibido(compra):
            listos_para_entrega.append(compra)

    return render(request, "inventario/dashboard.html", {
        "revisiones_pendientes": revisiones_pendientes,
        "total_revisiones_pendientes": revisiones_pendientes.count(),
        "listos_para_entrega": listos_para_entrega,
        "total_listos_para_entrega": len(listos_para_entrega),
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

@login_required
@inventario_required
def revision_bom_detail(request, pk):
    """
    Inventario valida disponibilidad por línea antes de que Compras gestione el BOM.
    No mueve stock contable: registra la cantidad físicamente verificada/reservable
    en el campo histórico cantidad_disponible de PurchaseLine.
    """
    from compras_oil.models import PurchaseRequest

    compra = get_object_or_404(
        PurchaseRequest.objects
        .select_related("bom", "bom__workorder", "creado_por")
        .prefetch_related("lineas__bom_item"),
        pk=pk,
    )

    lineas = compra.lineas.filter(cantidad_requerida__gt=0).order_by("id")

    if request.method == "POST":
        if compra.inventario_revisado_en:
            messages.info(request, "Este BOM ya fue revisado por Inventario.")
            return redirect("inventario:revision_bom_detail", pk=compra.pk)

        errores = []
        cantidades = {}
        for linea in lineas:
            raw = (request.POST.get(f"cantidad_disponible_{linea.id}") or "0").strip()
            try:
                cantidad = Decimal(raw.replace(",", "."))
            except Exception:
                errores.append(f"Cantidad inválida para {linea.codigo or linea.descripcion}.")
                continue

            requerida = Decimal(linea.cantidad_requerida or 0)
            if cantidad < 0:
                errores.append(f"La disponibilidad de {linea.codigo or linea.descripcion} no puede ser negativa.")
            if cantidad > requerida:
                # Para este flujo interesa cuánto se reserva para el PAW, no todo el stock físico.
                cantidad = requerida
            cantidades[linea.id] = cantidad

        if errores:
            for error in errores:
                messages.error(request, error)
        else:
            with transaction.atomic():
                for linea in lineas:
                    linea.cantidad_disponible = cantidades.get(linea.id, Decimal("0"))
                    linea.save(update_fields=["cantidad_disponible", "cantidad_a_comprar"])

                compra.inventario_revisado_en = timezone.now()
                compra.inventario_revisado_por = request.user
                compra.save(update_fields=[
                    "inventario_revisado_en",
                    "inventario_revisado_por",
                    "actualizado_en",
                ])

                registrar_movimiento(
                    request=request,
                    paw_numero=compra.paw_numero,
                    modulo="INVENTARIO",
                    accion="BOM revisado por Inventario",
                    descripcion="Inventario confirmó las cantidades disponibles del BOM.",
                    objeto=compra,
                    datos_nuevos={
                        "inventario_revisado_en": str(compra.inventario_revisado_en),
                        "inventario_revisado_por": request.user.username,
                    },
                )

                faltantes = compra.lineas.filter(cantidad_a_comprar__gt=0).exists()
                try:
                    paw = compra.bom.workorder.paw
                    paw.estado_operativo = "EN_COMPRAS" if faltantes else "MATERIAL_RECIBIDO"
                    paw.save(update_fields=["estado_operativo"])
                except Exception:
                    pass

                if faltantes:
                    registrar_movimiento(
                        request=request,
                        paw_numero=compra.paw_numero,
                        modulo="COMPRAS",
                        accion="Faltantes habilitados para Compras",
                        descripcion=(
                            "Inventario confirmó la revisión y existen materiales "
                            "faltantes que requieren compra."
                        ),
                        objeto=compra,
                    )
                else:
                    registrar_movimiento(
                        request=request,
                        paw_numero=compra.paw_numero,
                        modulo="INVENTARIO",
                        accion="BOM completo con inventario",
                        descripcion=(
                            "Inventario confirmó disponibilidad total. "
                            "No se requiere compra."
                        ),
                        objeto=compra,
                    )

            if faltantes:
                messages.success(
                    request,
                    "Revisión confirmada. Solo los faltantes quedaron habilitados para Compras."
                )
                return redirect("inventario:dashboard")

            messages.success(
                request,
                "Revisión confirmada. Todo el material está disponible; no se requiere compra. Ya puedes generar la entrega."
            )
            return redirect("inventario:revision_bom_detail", pk=compra.pk)

    total_requerido = sum((Decimal(x.cantidad_requerida or 0) for x in lineas), Decimal("0"))
    total_disponible = sum((Decimal(x.cantidad_disponible or 0) for x in lineas), Decimal("0"))
    total_comprar = sum((Decimal(x.cantidad_a_comprar or 0) for x in lineas), Decimal("0"))

    return render(request, "inventario/revision_bom_detail.html", {
        "compra": compra,
        "lineas": lineas,
        "total_requerido": total_requerido,
        "total_disponible": total_disponible,
        "total_comprar": total_comprar,
    })


def _material_comprado_completamente_recibido(compra):
    """True si cada faltante que debía comprarse ya fue recibido por Inventario."""
    lineas_compra = list(compra.lineas.filter(cantidad_a_comprar__gt=0))
    if not lineas_compra:
        return True
    try:
        recepcion = compra.recepcion_inventario
    except Exception:
        return False
    recibidas = {x.purchase_line_id: x for x in recepcion.lineas.all()}
    for linea in lineas_compra:
        r = recibidas.get(linea.id)
        if not r:
            return False
        if Decimal(r.cantidad_recibida or 0) < Decimal(linea.cantidad_a_comprar or 0):
            return False
    return True


@require_POST
@login_required
@inventario_required
def generar_entrega(request, pk):
    """Inventario define el destino y genera la salida física del material del PAW."""
    from compras_oil.models import PurchaseRequest
    from .models import WorkshopDeliveryLine

    compra = get_object_or_404(
        PurchaseRequest.objects.prefetch_related("lineas", "recepcion_inventario__lineas"),
        pk=pk,
    )

    if not compra.inventario_revisado_en:
        messages.error(request, "Primero debes revisar el BOM en Inventario.")
        return redirect("inventario:revision_bom_detail", pk=compra.pk)

    if not _material_comprado_completamente_recibido(compra):
        messages.error(request, "Aún existen materiales comprados pendientes de recepción.")
        return redirect("inventario:dashboard")

    destino = (request.POST.get("destino") or "").upper().strip()
    destinos_validos = {"TALLER", "CAMPO", "INVENTARIO"}
    if destino not in destinos_validos:
        messages.error(request, "Selecciona Taller, Campo o Despacho.")
        return redirect("inventario:dashboard")

    try:
        paw = compra.bom.workorder.paw
    except Exception:
        paw = None

    if destino == "TALLER" and paw and not getattr(paw, "aplica_taller", False):
        messages.error(request, "Este PAW no tiene habilitado Taller.")
        return redirect("inventario:dashboard")
    if destino == "CAMPO" and paw and not getattr(paw, "aplica_campo", False):
        messages.error(request, "Este PAW no tiene habilitado Campo.")
        return redirect("inventario:dashboard")

    with transaction.atomic():
        entrega, created = WorkshopDelivery.objects.get_or_create(
            purchase_request=compra,
            defaults={"creado_por": request.user, "destino": destino},
        )
        if not created and entrega.destino != destino:
            if entrega.lineas.filter(cantidad_entregada__gt=0).exists():
                messages.error(request, "No puedes cambiar el destino porque la entrega ya inició.")
                return redirect("inventario:entrega_taller_detail", pk=entrega.pk)
            entrega.destino = destino
            entrega.save(update_fields=["destino", "actualizado_en"])

        creadas = 0
        for linea in compra.lineas.filter(cantidad_requerida__gt=0):
            _, nueva = WorkshopDeliveryLine.objects.get_or_create(
                delivery=entrega,
                purchase_line=linea,
                defaults={
                    "codigo": linea.codigo or "",
                    "descripcion": linea.descripcion or "",
                    "unidad": linea.unidad or "",
                    # Inventario entrega el total requerido por el BOM:
                    # stock disponible + material comprado.
                    "cantidad_requerida": Decimal(linea.cantidad_requerida or 0),
                },
            )
            creadas += int(nueva)

    messages.success(
        request,
        f"Entrega a {entrega.get_destino_display()} generada por Inventario. Líneas nuevas: {creadas}."
    )
    return redirect("inventario:entrega_taller_detail", pk=entrega.pk)


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
        <div style="margin-top:24px;">
            <div style="font-size:16px;font-weight:800;color:#0f172a;margin-bottom:10px;">
                Materiales aún pendientes
            </div>
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                   style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #e2e8f0;">
                <thead>
                    <tr style="background:#f8fafc;">
                        <th align="left" style="padding:9px;border-bottom:1px solid #e2e8f0;">Código</th>
                        <th align="left" style="padding:9px;border-bottom:1px solid #e2e8f0;">Descripción</th>
                        <th align="left" style="padding:9px;border-bottom:1px solid #e2e8f0;">Faltante</th>
                        <th align="left" style="padding:9px;border-bottom:1px solid #e2e8f0;">Unidad</th>
                    </tr>
                </thead>
                <tbody>{''.join(filas)}</tbody>
            </table>
        </div>
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
    <body style="margin:0;padding:0;background:#eef2f7;font-family:Arial,Helvetica,sans-serif;color:#0f172a;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="background:#eef2f7;padding:24px 12px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="760" cellspacing="0" cellpadding="0" border="0"
                           style="width:760px;max-width:760px;background:#ffffff;border-radius:14px;overflow:hidden;
                                  box-shadow:0 4px 14px rgba(15,23,42,.08);">

                        <tr>
                            <td style="background:#0f172a;padding:20px 24px;">
                                <div style="font-size:12px;letter-spacing:.8px;font-weight:800;color:#cbd5e1;">
                                    IMPETUS CONTROL
                                </div>
                                <div style="font-size:24px;line-height:1.25;font-weight:800;color:#ffffff;margin-top:6px;">
                                    {titulo}
                                </div>
                            </td>
                        </tr>

                        <tr>
                            <td style="padding:24px;">
                                <div style="font-size:14px;color:#64748b;margin-bottom:8px;">
                                    PAW #{paw_numero}
                                </div>

                                <div style="font-size:19px;font-weight:800;color:#0f172a;margin-bottom:18px;">
                                    {paw_nombre}
                                </div>

                                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
                                       style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">
                                    <tr>
                                        <td style="padding:18px 20px;">
                                            <div style="font-size:12px;font-weight:800;color:#64748b;
                                                        text-transform:uppercase;letter-spacing:.5px;">
                                                Avance de recepción
                                            </div>
                                            <div style="font-size:34px;line-height:1.1;font-weight:900;
                                                        color:{'#16a34a' if umbral == 100 else '#f59e0b'};
                                                        margin-top:6px;">
                                                {porcentaje}%
                                            </div>
                                            <div style="font-size:14px;line-height:1.6;color:#475569;margin-top:10px;">
                                                {mensaje_estado}
                                            </div>
                                        </td>
                                    </tr>
                                </table>

                                {pendientes_html}

                                <table role="presentation" cellspacing="0" cellpadding="0" border="0"
                                       style="margin-top:24px;">
                                    <tr>
                                        <td style="padding-right:10px;">
                                            <a href="{inventario_url}"
                                               style="display:inline-block;background:#2563eb;color:#ffffff;
                                                      text-decoration:none;padding:11px 16px;border-radius:8px;
                                                      font-size:13px;font-weight:800;">
                                                Revisar recepción
                                            </a>
                                        </td>
                                        <td>
                                            <a href="{taller_url}"
                                               style="display:inline-block;background:#16a34a;color:#ffffff;
                                                      text-decoration:none;padding:11px 16px;border-radius:8px;
                                                      font-size:13px;font-weight:800;">
                                                Revisar Taller
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;
                                            color:#94a3b8;font-size:11px;line-height:1.5;">
                                    Notificación automática generada por Impetus Control al alcanzar este umbral
                                    por primera vez.
                                </div>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
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
@inventario_required
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
@inventario_required
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
@inventario_required
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