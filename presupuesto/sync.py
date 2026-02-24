# presupuesto/sync.py
from django.db import transaction
from paw_app.models import Paw
from .models import Presupuesto
from .services import total_paw_desde_compras

@transaction.atomic
def upsert_presupuesto_de_paw(paw: Paw) -> Presupuesto:
    total = total_paw_desde_compras(paw.numero_paw)
    obj, _ = Presupuesto.objects.get_or_create(paw=paw)
    if obj.total_paw != total:
        obj.total_paw = total
        obj.save(update_fields=["total_paw", "actualizado_en"])
    return obj

@transaction.atomic
def sync_presupuestos() -> int:
    n = 0
    for paw in Paw.objects.all():   # ✅ TODOS
        upsert_presupuesto_de_paw(paw)
        n += 1
    return n