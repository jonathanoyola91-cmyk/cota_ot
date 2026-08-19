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

    # Controla que las alertas de recepción se envíen una sola vez por umbral.
    notificacion_80_en = models.DateTimeField(null=True, blank=True)
    notificacion_100_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        pr = getattr(self, "purchase_request", None)
        paw = getattr(pr, "paw_numero", None) if pr else None
        return f"Recepción Inventario - PAW #{paw or self.id}"


class InventoryReceptionLine(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PARCIAL = "PARCIAL", "Parcial"
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

    # Snapshot del ítem comprado
    codigo = models.CharField(max_length=80, blank=True, default="")
    descripcion = models.CharField(max_length=200, blank=True, default="")
    unidad = models.CharField(max_length=20, blank=True, default="")

    cantidad_esperada = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    cantidad_recibida = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    fecha_llegada = models.DateField(null=True, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE
    )

    observacion_inventario = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Recepción {self.codigo} - {self.estado}"
        
# ======================================================
# ENTREGA TALLER
# ======================================================

class WorkshopDelivery(models.Model):
    """
    Encabezado de entrega de material por PurchaseRequest (PAW).
    Se conserva el nombre histórico del modelo para no romper relaciones existentes.
    """

    class Destino(models.TextChoices):
        TALLER = "TALLER", "Taller"
        CAMPO = "CAMPO", "Campo"
        INVENTARIO = "INVENTARIO", "Inventario / despacho al cliente"
    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="entrega_taller"
    )

    destino = models.CharField(
        max_length=20,
        choices=Destino.choices,
        default=Destino.TALLER,
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
        return f"ENTREGA {self.get_destino_display().upper()} - PAW #{paw or self.id} - {nombre}"


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