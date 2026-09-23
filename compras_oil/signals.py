"""Sincronizaciones de Compras con el flujo principal del PAW."""
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PurchaseRequest


def _entrega_totalmente_registrada(compra):
    """Incluye líneas compradas y las que Inventario tomó de bodega."""
    try:
        entrega = compra.entrega_taller
    except Exception:
        return False

    entregadas = {x.purchase_line_id: x for x in entrega.lineas.all()}
    for linea in compra.lineas.filter(cantidad_requerida__gt=0):
        linea_entrega = entregadas.get(linea.id)
        if not linea_entrega:
            return False
        if Decimal(linea_entrega.cantidad_entregada or 0) < Decimal(linea.cantidad_requerida or 0):
            return False
    return True


def _recepcion_totalmente_confirmada(compra):
    """Valida el recibido completo de una compra de Stock o HSE."""
    try:
        recepcion = compra.recepcion_inventario
    except Exception:
        return False

    recibidas = {x.purchase_line_id: x for x in recepcion.lineas.all()}
    for linea in compra.lineas.filter(cantidad_a_comprar__gt=0):
        recibida = recibidas.get(linea.id)
        if not recibida:
            return False
        if Decimal(recibida.cantidad_recibida or 0) < Decimal(linea.cantidad_a_comprar or 0):
            return False
    return True


def sincronizar_cierres_stock_hse():
    """Cierra solicitudes antiguas que ya habían sido recibidas antes del ajuste."""
    pendientes = (
        PurchaseRequest.objects
        .filter(origen__in=[PurchaseRequest.Origen.STOCK, PurchaseRequest.Origen.HSE])
        .exclude(estado=PurchaseRequest.Estado.CERRADA)
        .prefetch_related("lineas", "recepcion_inventario__lineas")
    )
    cerradas = 0
    for compra in pendientes:
        if _recepcion_totalmente_confirmada(compra):
            compra.estado = PurchaseRequest.Estado.CERRADA
            compra.save(update_fields=["estado", "actualizado_en"])
            cerradas += 1
    return cerradas


def sincronizar_cierres_paw_facturados():
    """Cierra compras históricas cuyo PAW ya llegó a Facturación.

    La relación se hace por BOM → OT → PAW, por lo que cada compra conserva
    su propio PAW y nunca toma el estado de otro proceso.
    """
    estados_finales = {"EN_FACTURACION", "FACTURADO", "RADICADO"}
    compras = (
        PurchaseRequest.objects
        .filter(origen=PurchaseRequest.Origen.PAW, bom__workorder__paw__estado_operativo__in=estados_finales)
        .exclude(estado=PurchaseRequest.Estado.CERRADA)
    )
    return compras.update(estado=PurchaseRequest.Estado.CERRADA)


@receiver(post_save, sender="paw_app.Paw")
def cerrar_compras_al_enviar_a_facturacion(sender, instance, **kwargs):
    """El PAW se cierra en Compras únicamente al entrar a Facturación."""
    if instance.estado_operativo not in {"EN_FACTURACION", "FACTURADO", "RADICADO"}:
        return

    compras = (
        PurchaseRequest.objects
        .filter(origen=PurchaseRequest.Origen.PAW, bom__workorder__paw=instance)
        .exclude(estado=PurchaseRequest.Estado.CERRADA)
        .prefetch_related("lineas", "entrega_taller__lineas")
    )
    # La transición a Facturación es la autoridad final del PAW. Si Comercial
    # ya lo facturó, Compras debe cerrarse aunque la entrega hubiera sido
    # registrada antes de activar esta automatización.
    compras.update(estado=PurchaseRequest.Estado.CERRADA)


@receiver(post_save, sender="inventario.InventoryReceptionLine")
def cerrar_stock_hse_al_recibir_inventario(sender, instance, **kwargs):
    """Stock y HSE no dependen de un PAW: cierran con el recibido completo."""
    compra = instance.recepcion.purchase_request
    if compra.origen not in {PurchaseRequest.Origen.STOCK, PurchaseRequest.Origen.HSE}:
        return
    if compra.estado == PurchaseRequest.Estado.CERRADA:
        return
    if _recepcion_totalmente_confirmada(compra):
        compra.estado = PurchaseRequest.Estado.CERRADA
        compra.save(update_fields=["estado", "actualizado_en"])
