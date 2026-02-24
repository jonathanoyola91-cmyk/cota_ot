from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from paw_app.models import Paw
from compras_oil.models import PurchaseRequest, PurchaseLine
from facturacion.models import Factura

from .sync import upsert_presupuesto_de_paw


def _get_paw_by_numero(paw_numero: str):
    if not paw_numero:
        return None
    try:
        return Paw.objects.get(numero_paw=paw_numero)
    except Paw.DoesNotExist:
        return None


@receiver(post_save, sender=PurchaseRequest)
def presupuesto_on_purchase_request_save(sender, instance: PurchaseRequest, **kwargs):
    paw = _get_paw_by_numero(instance.paw_numero)
    if paw:
        upsert_presupuesto_de_paw(paw)


@receiver(post_save, sender=PurchaseLine)
def presupuesto_on_purchase_line_save(sender, instance: PurchaseLine, **kwargs):
    # La línea pertenece a un request
    pr = instance.request
    paw = _get_paw_by_numero(pr.paw_numero)
    if paw:
        upsert_presupuesto_de_paw(paw)


@receiver(post_delete, sender=PurchaseLine)
def presupuesto_on_purchase_line_delete(sender, instance: PurchaseLine, **kwargs):
    pr = instance.request
    paw = _get_paw_by_numero(pr.paw_numero)
    if paw:
        upsert_presupuesto_de_paw(paw)


@receiver(post_save, sender=Factura)
def presupuesto_on_factura_save(sender, instance: Factura, **kwargs):
    # Si se crea/actualiza factura -> ya no debe existir presupuesto pendiente
    upsert_presupuesto_de_paw(instance.paw)