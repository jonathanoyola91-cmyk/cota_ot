"""Incorpora requerimientos revisados a una entrega existente, sin mover stock."""
from decimal import Decimal

from django.db import transaction

from compras_oil.models import PurchaseRequest
from .models import InventoryReservation, WorkshopDelivery, WorkshopDeliveryLine


@transaction.atomic
def sincronizar_entrega_existente(compra_id):
    # Mismo orden que la revisión: solicitud, entrega y líneas.
    compra = PurchaseRequest.objects.select_for_update().get(pk=compra_id)
    if compra.estado == "CERRADA" or compra.bom.workorder.paw.estado_operativo in ("FACTURADO", "RADICADO"):
        return 0, 0
    entrega = WorkshopDelivery.objects.select_for_update().filter(purchase_request=compra).first()
    if entrega is None:
        return 0, 0  # Inventario sigue eligiendo el destino al generar la entrega.
    creadas = actualizadas = 0
    for linea in compra.lineas.select_for_update().filter(cantidad_requerida__gt=0).order_by("pk"):
        # Admite reservas históricas vinculadas al PAW aunque no tengan marcador de revisión.
        reservas = InventoryReservation.objects.filter(purchase_request=compra, purchase_line=linea)
        cubierta = Decimal("0")
        for reserva in reservas:
            consumida = Decimal(reserva.cantidad_consumida or 0)
            cubierta += consumida
            if reserva.estado == InventoryReservation.Estado.ACTIVA:
                cubierta += max(Decimal(reserva.cantidad or 0) - consumida, Decimal("0"))
        revisada = max(Decimal(linea.cantidad_revisada_inventario or 0), cubierta)
        requerida = min(Decimal(linea.cantidad_requerida or 0), revisada)
        if requerida <= 0:
            continue
        fila, nueva = WorkshopDeliveryLine.objects.get_or_create(
            delivery=entrega, purchase_line=linea,
            defaults={"codigo": linea.codigo or "", "descripcion": linea.descripcion or "",
                      "unidad": linea.unidad or "", "cantidad_requerida": requerida},
        )
        if nueva:
            creadas += 1
        elif requerida > Decimal(fila.cantidad_requerida or 0):
            # Solo incorpora incrementos revisados. No reduce cantidades ni toca entregas/liberaciones.
            fila.cantidad_requerida = requerida
            fila.save(update_fields=["cantidad_requerida"])
            actualizadas += 1
    return creadas, actualizadas
