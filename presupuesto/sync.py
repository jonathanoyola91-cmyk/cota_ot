from decimal import Decimal
from django.db import transaction
from django.db.models import OuterRef, Exists

from paw_app.models import Paw
from facturacion.models import Factura
from .models import Presupuesto
from .services import total_paw_desde_compras


@transaction.atomic
def upsert_presupuesto_de_paw(paw: Paw) -> Presupuesto | None:
    """
    - Si PAW ya tiene factura -> no se muestra en admin (y opcionalmente lo podemos borrar).
    - Si no tiene factura -> crea/actualiza Presupuesto y recalcula total_paw.
    """
    # Si ya tiene factura, no aplica presupuesto "pendiente"
    if hasattr(paw, "factura") and paw.factura_id:
        # OPCIONAL: borrar el presupuesto si existe
        Presupuesto.objects.filter(paw=paw).delete()
        return None

    total = total_paw_desde_compras(paw.numero_paw)
    obj, _ = Presupuesto.objects.get_or_create(paw=paw)

    if obj.total_paw != total:
        obj.total_paw = total
        obj.save(update_fields=["total_paw", "actualizado_en"])
    return obj


@transaction.atomic
def sync_presupuestos() -> int:
    """
    Recalcula todos los PAWs sin factura.
    """
    factura_exists = Factura.objects.filter(paw_id=OuterRef("pk"))
    paws = Paw.objects.annotate(tiene_factura=Exists(factura_exists)).filter(tiene_factura=False)

    n = 0
    for paw in paws:
        upsert_presupuesto_de_paw(paw)
        n += 1
    return n