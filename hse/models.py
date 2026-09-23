from decimal import Decimal

from django.conf import settings
from django.db import models


class HSEStock(models.Model):
    """Bodega HSE: control físico de consumo, sin valorización contable."""
    catalogo = models.CharField(max_length=20, default="IMPETUS")
    catalogo_item_id = models.PositiveIntegerField()
    codigo = models.CharField(max_length=80, db_index=True)
    descripcion = models.CharField(max_length=300)
    unidad = models.CharField(max_length=30, default="UND")
    cantidad_fisica = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["catalogo", "catalogo_item_id"], name="hse_stock_catalogo_item")]
        ordering = ["codigo"]

    def __str__(self):
        return f"Bodega HSE · {self.codigo}"


class HSERequest(models.Model):
    class Tipo(models.TextChoices):
        EPP = "EPP", "Entrega de EPP"
        DOTACION = "DOTACION", "Entrega de dotación"
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de Inventario"
        EN_COMPRAS = "EN_COMPRAS", "En compras"
        LISTA = "LISTA", "Lista para entregar"
        ENTREGADA = "ENTREGADA", "Entregada"
        CANCELADA = "CANCELADA", "Cancelada"
    class MotivoEntrega(models.TextChoices):
        VIDA_UTIL = "VU", "Expiró su vida útil"
        PERDIDA = "RP", "Reposición por pérdida"
        DETERIORO = "CD", "Cambio por deterioro"
        PRIMERA = "PE", "Primera entrega"

    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    empleado = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hse_solicitudes_recibidas")
    solicitado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hse_solicitudes_creadas")
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.PENDIENTE)
    observacion = models.TextField(blank=True)
    motivo_entrega = models.CharField(max_length=2, choices=MotivoEntrega.choices, default=MotivoEntrega.PRIMERA)
    compra = models.OneToOneField("compras_oil.PurchaseRequest", null=True, blank=True, on_delete=models.PROTECT, related_name="solicitud_hse")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    entregado_en = models.DateTimeField(null=True, blank=True)
    entregado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="hse_entregas_realizadas")

    @property
    def codigo(self):
        return f"HSE-{self.pk:04d}" if self.pk else "HSE-PENDIENTE"

    @property
    def nombre_formato(self):
        return "ENTREGA DE DOTACIÓN" if self.tipo == self.Tipo.DOTACION else "ENTREGA DE EPP"


class HSERequestLine(models.Model):
    solicitud = models.ForeignKey(HSERequest, on_delete=models.CASCADE, related_name="lineas")
    catalogo = models.CharField(max_length=20, default="IMPETUS")
    catalogo_item_id = models.PositiveIntegerField()
    codigo = models.CharField(max_length=80)
    descripcion = models.CharField(max_length=300)
    unidad = models.CharField(max_length=30, default="UND")
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    cantidad_entregada = models.DecimalField(max_digits=12, decimal_places=3, default=0)


class HSEMovement(models.Model):
    class Tipo(models.TextChoices):
        RECEPCION = "RECEPCION", "Recepción en bodega HSE"
        ENTREGA = "ENTREGA", "Entrega al empleado"
        AJUSTE = "AJUSTE", "Ajuste de bodega HSE"
    stock = models.ForeignKey(HSEStock, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    saldo_anterior = models.DecimalField(max_digits=14, decimal_places=3)
    saldo_nuevo = models.DecimalField(max_digits=14, decimal_places=3)
    referencia = models.CharField(max_length=80, blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
