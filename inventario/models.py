# inventario/models.py
from django.conf import settings
from django.db import models


# ======================================================
# RECEPCIÓN INVENTARIO
# ======================================================

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
        null=True,
        blank=True,
        related_name="recepciones_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        pr = getattr(self, "purchase_request", None)
        paw = getattr(pr, "paw_numero", None) if pr else None
        return f"Recepción Inventario - PAW #{paw or self.id}"


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
        pl = getattr(self, "purchase_line", None)
        codigo = getattr(pl, "codigo", "") if pl else ""
        return f"Recepción {codigo} - {self.estado}"


# ======================================================
# ENTREGA TALLER
# ======================================================

class WorkshopDelivery(models.Model):
    """
    Encabezado: ENTREGA TALLER por PurchaseRequest (PAW).
    """
    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="entrega_taller"
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entregas_taller_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Comentarios que se imprimirán en el PDF encima de firmas
    comentarios = models.TextField(blank=True)

    def __str__(self):
        pr = getattr(self, "purchase_request", None)
        paw = getattr(pr, "paw_numero", None) if pr else None
        nombre = getattr(pr, "paw_nombre", "") if pr else ""
        nombre = (nombre or "")[:60]
        return f"ENTREGA TALLER - PAW #{paw or self.id} - {nombre}"


class WorkshopDeliveryLine(models.Model):
    """
    Línea: snapshot de PurchaseLine para ENTREGA TALLER.
    'cantidad_entregada' NO es obligatoria (se llena manual en físico).
    """
    delivery = models.ForeignKey(
        WorkshopDelivery,
        on_delete=models.CASCADE,
        related_name="lineas"
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="entrega_taller_linea"
    )

    # Snapshot de la línea de compra
    codigo = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=200, blank=True)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad_requerida = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # Diligenciado manualmente (en papel) → debe poder ir vacío
    cantidad_entregada = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"
