from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from workorders.models import WorkOrder
from bom.models import Bom
from compras_oil.models import PurchaseRequest
from inventario.models import WorkshopDelivery


def obtener_bom_seguro(ot):
    try:
        return ot.bom
    except Exception:
        return None


@login_required
def dashboard(request):
    ots = WorkOrder.objects.select_related("paw").order_by("-id")

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

                total_req += req
                total_ent += min(ent, req)

                total_lineas += 1
                if req > 0 and ent >= req:
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
            material_entregado.append(item)
        elif entrega and porcentaje_entrega > 0:
            material_parcial.append(item)
        else:
            esperando_material.append(item)

    return render(request, "taller/dashboard.html", {
        "pendientes_bom": pendientes_bom,
        "bom_borrador": bom_borrador,
        "esperando_material": esperando_material,
        "material_parcial": material_parcial,
        "material_entregado": material_entregado,

        "total_pendientes_bom": len(pendientes_bom),
        "total_bom_borrador": len(bom_borrador),
        "total_esperando_material": len(esperando_material),
        "total_material_parcial": len(material_parcial),
        "total_material_entregado": len(material_entregado),
    })


@require_POST
@login_required
def confirmar_ensamble_ok(request, ot_id):
    ot = get_object_or_404(
        WorkOrder.objects.select_related("paw"),
        numero=ot_id
    )

    bom = obtener_bom_seguro(ot)

    if not bom:
        messages.error(request, "No se puede cerrar: la OT no tiene BOM.")
        return redirect("taller:dashboard")

    compra = PurchaseRequest.objects.filter(bom=bom).first()

    if not compra:
        messages.error(request, "No se puede cerrar: el BOM aún no tiene solicitud de compra.")
        return redirect("taller:dashboard")

    entrega = (
        WorkshopDelivery.objects
        .filter(purchase_request=compra)
        .prefetch_related("lineas")
        .first()
    )

    if not entrega:
        messages.error(request, "No se puede cerrar: inventario aún no ha generado entrega a taller.")
        return redirect("taller:dashboard")

    total_requerido = Decimal("0")
    total_entregado = Decimal("0")

    for linea in entrega.lineas.all():
        req = Decimal(linea.cantidad_requerida or 0)
        ent = Decimal(linea.cantidad_entregada or 0)

        total_requerido += req
        total_entregado += min(ent, req)

    if total_requerido <= 0:
        messages.error(request, "No se puede cerrar: no hay cantidades requeridas para validar.")
        return redirect("taller:dashboard")

    if total_entregado < total_requerido:
        messages.error(request, "No se puede cerrar: todavía hay material pendiente por entregar.")
        return redirect("taller:dashboard")

    if ot.paw:
        ot.paw.estado_operativo = "ENSAMBLE_OK"
        ot.paw.save(update_fields=["estado_operativo"])

    messages.success(request, "Ensamble confirmado OK. El PAW fue actualizado correctamente.")
    return redirect("taller:dashboard")