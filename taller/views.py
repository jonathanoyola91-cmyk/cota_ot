from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.roles import tiene_rol
from workorders.models import WorkOrder
from compras_oil.models import PurchaseRequest
from inventario.models import WorkshopDelivery


def obtener_bom_seguro(ot):
    try:
        return ot.bom
    except Exception:
        return None


def puede_editar_taller(user):
    return tiene_rol(user, ["TALLER", "ADMIN"])


@login_required
def dashboard(request):
    ots = WorkOrder.objects.select_related("paw").order_by("-numero")

    pendientes_bom = []
    bom_borrador = []
    esperando_material = []
    material_parcial = []
    material_entregado = []

    for ot in ots:
        bom = obtener_bom_seguro(ot)

        if not bom:
            pendientes_bom.append(ot)
            continue

        compra = PurchaseRequest.objects.filter(bom=bom).first()

        entrega = None
        if compra:
            entrega = (
                WorkshopDelivery.objects
                .filter(purchase_request=compra)
                .prefetch_related("lineas")
                .first()
            )

        total_lineas = 0
        entregadas = 0
        porcentaje_entrega = 0

        if entrega:
            total_req = Decimal("0")
            total_ent = Decimal("0")

            for linea in entrega.lineas.all():
                req = Decimal(linea.cantidad_requerida or 0)
                ent = Decimal(linea.cantidad_entregada or 0)

                if req <= 0:
                    continue

                total_req += req
                total_ent += min(ent, req)

                total_lineas += 1
                if ent >= req:
                    entregadas += 1

            if total_req > 0:
                porcentaje_entrega = round((total_ent / total_req) * 100)

        item = {
            "ot": ot,
            "bom": bom,
            "compra": compra,
            "entrega": entrega,
            "total_lineas": total_lineas,
            "entregadas": entregadas,
            "porcentaje_entrega": porcentaje_entrega,
        }

        estado_bom = getattr(bom, "estado", "")

        if estado_bom == "BORRADOR":
            bom_borrador.append(item)
        elif entrega and porcentaje_entrega >= 100:
            if not ot.ensamble_ok:
                material_entregado.append(item)
        elif entrega and porcentaje_entrega > 0:
            material_parcial.append(item)
        else:
            esperando_material.append(item)

    historial_ensamble = (
        WorkOrder.objects
        .select_related("paw", "ensamble_confirmado_por")
        .filter(ensamble_ok=True)
        .order_by("-fecha_ensamble_ok", "-actualizado_en")
    )

    return render(request, "taller/dashboard.html", {
        "pendientes_bom": pendientes_bom,
        "bom_borrador": bom_borrador,
        "esperando_material": esperando_material,
        "material_parcial": material_parcial,
        "material_entregado": material_entregado,
        "historial_ensamble": historial_ensamble,

        "total_pendientes_bom": len(pendientes_bom),
        "total_bom_borrador": len(bom_borrador),
        "total_esperando_material": len(esperando_material),
        "total_material_parcial": len(material_parcial),
        "total_material_entregado": len(material_entregado),
        "total_historial_ensamble": historial_ensamble.count(),

        "puede_editar_taller": puede_editar_taller(request.user),
    })


@require_POST
@login_required
def confirmar_ensamble_ok(request, ot_id):
    if not puede_editar_taller(request.user):
        messages.error(request, "No tienes permiso para modificar Taller.")
        return redirect("taller:dashboard")

    ot = get_object_or_404(
        WorkOrder.objects.select_related("paw"),
        numero=ot_id
    )

    if ot.ensamble_ok:
        messages.info(request, "Este ensamble ya fue confirmado.")
        return redirect("taller:dashboard")

    bom = obtener_bom_seguro(ot)

    if not bom:
        messages.error(request, "No se puede cerrar: la OT no tiene BOM.")
        return redirect("taller:dashboard")

    compra = PurchaseRequest.objects.filter(bom=bom).first()

    if not compra:
        messages.error(request, "No hay solicitud de compra.")
        return redirect("taller:dashboard")

    entrega = (
        WorkshopDelivery.objects
        .filter(purchase_request=compra)
        .prefetch_related("lineas")
        .first()
    )

    if not entrega:
        messages.error(request, "No hay entrega a taller.")
        return redirect("taller:dashboard")

    total_req = Decimal("0")
    total_ent = Decimal("0")

    for linea in entrega.lineas.all():
        req = Decimal(linea.cantidad_requerida or 0)
        ent = Decimal(linea.cantidad_entregada or 0)

        if req <= 0:
            continue

        total_req += req
        total_ent += min(ent, req)

    if total_req <= 0:
        messages.error(request, "No se puede confirmar: no hay cantidades requeridas válidas.")
        return redirect("taller:dashboard")

    if total_ent < total_req:
        messages.error(request, "Aún hay material pendiente.")
        return redirect("taller:dashboard")

    ot.ensamble_ok = True
    ot.fecha_ensamble_ok = timezone.now()
    ot.ensamble_confirmado_por = request.user
    ot.etapa_taller = WorkOrder.EtapaTaller.TERMINADO
    ot.estado = WorkOrder.Status.TERMINADA
    ot.terminado_en = timezone.now()
    ot.save(update_fields=[
        "ensamble_ok",
        "fecha_ensamble_ok",
        "ensamble_confirmado_por",
        "etapa_taller",
        "estado",
        "terminado_en",
        "actualizado_en",
    ])

    if ot.paw:
        ot.paw.estado_operativo = "PRODUCTO_OK"
        ot.paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Ensamble confirmado correctamente.")
    return redirect("taller:dashboard")