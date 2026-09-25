from django.db import models
from django.conf import settings


class Item(models.Model):
    codigo = models.CharField(
        "Código",
        max_length=30,
        unique=True
    )

    descripcion = models.TextField(
        "Descripción"
    )

    unidad_medida = models.CharField(
        "Unidad Medida",
        max_length=20,
        blank=True,
        null=True
    )

    clasificacion = models.CharField(
        "Clasificación",
        max_length=30,
        blank=True,
        null=True
    )

    grupo_inventario = models.CharField(
        "Grupo Inventario",
        max_length=255,
        blank=True,
        null=True
    )

    activo = models.BooleanField(default=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Item Oil & Gas"
        verbose_name_plural = "Items Oil & Gas"

    def __str__(self):
        return f"{self.codigo} - {self.descripcion[:60]}"


class ItemImpetus(models.Model):
    codigo = models.CharField(
        "Código",
        max_length=30,
        unique=True
    )

    descripcion = models.TextField(
        "Descripción"
    )

    unidad_medida = models.CharField(
        "Unidad Medida",
        max_length=20,
        blank=True,
        null=True
    )

    clasificacion = models.CharField(
        "Clasificación",
        max_length=30,
        blank=True,
        null=True
    )

    grupo_inventario = models.CharField(
        "Grupo Inventario",
        max_length=255,
        blank=True,
        null=True
    )

    activo = models.BooleanField(default=True)

    # Precio maestro de venta. Solo debe cambiar al publicar un cálculo de Pricing.
    precio_venta = models.DecimalField("Precio de venta", max_digits=18, decimal_places=2, default=0)
    precio_actualizado_en = models.DateTimeField(null=True, blank=True)
    precio_actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="precios_item_impetus_actualizados"
    )

    # Último costo cotizado por Compras para alimentar Pricing.
    costo_cotizado = models.DecimalField("Costo cotizado", max_digits=18, decimal_places=4, default=0)
    costo_cotizado_moneda = models.CharField(max_length=3, choices=[("COP", "COP"), ("USD", "USD")], default="COP")
    costo_cotizado_proveedor = models.CharField(max_length=160, blank=True, default="")
    costo_cotizado_fecha = models.DateField(null=True, blank=True)
    costo_cotizado_vigente_hasta = models.DateField(null=True, blank=True)
    costo_cotizado_referencia = models.CharField(max_length=120, blank=True, default="")
    costo_cotizado_observacion = models.CharField(max_length=300, blank=True, default="")
    costo_cotizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="costos_cotizados_item_impetus"
    )
    costo_cotizado_actualizado_en = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["codigo"]
        verbose_name = "Item IMPETUS"
        verbose_name_plural = "Items IMPETUS"

    def __str__(self):
        return f"{self.codigo} - {self.descripcion[:60]}"