from django.conf import settings
from django.db import models


class InventoryReception(models.Model):
    """
    Encabezado: una recepción por PurchaseRequest.
    """
    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="recepcion_inventario"
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name="recepciones_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Recepción Inventario - {self.purchase_request}"


class InventoryReceptionLine(models.Model):
    """
    Línea: una por cada PurchaseLine.
    """
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        LISTO = "LISTO", "Listo"

    recepcion = models.ForeignKey(
        InventoryReception,
        on_delete=models.CASCADE,
        related_name="lineas"
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="recepcion_linea"
    )

    cantidad_esperada = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cantidad_recibida = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    fecha_llegada = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    observacion_inventario = models.TextField(blank=True)

    def __str__(self):
        return f"Recepción {self.purchase_line.codigo} - {self.estado}"
