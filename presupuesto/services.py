from decimal import Decimal
from django.db.models import F, Sum, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce

from compras_oil.models import PurchaseRequest

def total_paw_desde_compras(paw_numero: str) -> Decimal:
    """
    Total = sum(lineas.cantidad_a_comprar * lineas.precio_unitario)
    para el PurchaseRequest con paw_numero dado.
    Nota: si hay precio_unitario NULL, lo tratamos como 0.
    """
    expr = ExpressionWrapper(
        F("lineas__cantidad_a_comprar") * Coalesce(F("lineas__precio_unitario"), Decimal("0.00")),
        output_field=DecimalField(max_digits=18, decimal_places=2),
    )

    total = (
        PurchaseRequest.objects
        .filter(paw_numero=paw_numero)
        .aggregate(total=Coalesce(Sum(expr), Decimal("0.00")))
        .get("total")
    )

    return total or Decimal("0.00")