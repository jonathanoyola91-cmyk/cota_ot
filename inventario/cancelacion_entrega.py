"""Cancela exclusivamente el saldo no entregado de una línea sin reserva activa."""
from decimal import Decimal
from django.db import transaction
from django.shortcuts import get_object_or_404
from compras_oil.models import PurchaseRequest
from .models import WorkshopDelivery, WorkshopDeliveryLine, InventoryReservation, DeliveryPendingCancellation


@transaction.atomic
def cancelar_pendiente(compra_id, entrega_id, linea_id, motivo, usuario):
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("Escriba el motivo de la cancelación.")
    compra = PurchaseRequest.objects.select_for_update().get(pk=compra_id)
    if compra.estado == "CERRADA" or compra.bom.workorder.paw.estado_operativo in ("FACTURADO", "RADICADO"):
        raise ValueError("No se puede cancelar el pendiente de un PAW cerrado o facturado.")
    entrega = get_object_or_404(WorkshopDelivery.objects.select_for_update(), pk=entrega_id, purchase_request=compra)
    linea = get_object_or_404(WorkshopDeliveryLine.objects.select_for_update(), pk=linea_id, delivery=entrega)
    # Serializa con sincronización y revisión del mismo requerimiento.
    compra.lineas.select_for_update().get(pk=linea.purchase_line_id)
    reservas = InventoryReservation.objects.select_for_update().filter(
        purchase_line_id=linea.purchase_line_id, purchase_request=compra,
        estado=InventoryReservation.Estado.ACTIVA,
    )
    if any(Decimal(r.cantidad or 0) > Decimal(r.cantidad_consumida or 0) for r in reservas):
        raise ValueError("La línea aún tiene reserva activa. Debe gestionar su liberación antes de cancelar el pendiente.")
    pendiente = max(Decimal(linea.cantidad_requerida_neta) - Decimal(linea.cantidad_entregada or 0), Decimal("0"))
    if pendiente <= 0:
        raise ValueError("Esta línea ya no tiene cantidad pendiente para cancelar.")
    return DeliveryPendingCancellation.objects.create(
        delivery_line=linea, cantidad=pendiente, motivo=motivo, creado_por=usuario,
    )
