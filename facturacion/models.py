# facturacion/models.py
from django.db import models
from decimal import Decimal
from datetime import timedelta, date


class Factura(models.Model):
    TIPO_PAGO_CHOICES = [
        ("directo", "Directo"),
        ("endoso", "Endoso"),
    ]

    ESTADO_CHOICES = [
        ("radicacion", "Radicación"),
        ("facturado", "Facturado"),
        ("vencida", "Vencida"),
        ("pagada", "Pagada"),
    ]

    paw = models.OneToOneField(
        "paw_app.Paw",
        on_delete=models.PROTECT,
        related_name="factura",
    )

    # Diligencia admin PAW
    lugar_entrega = models.CharField(
        "Lugar de entrega",
        max_length=120,
        null=True,
        blank=True,
    )
    lugar_servicio = models.CharField(
        "Lugar de servicio",
        max_length=120,
        null=True,
        blank=True,
    )
    numero_servicio = models.CharField(
        "Número de servicio",
        max_length=60,
        null=True,
        blank=True,
    )

    item_factura = models.ForeignKey(
        "item_oil_gas.Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="facturas",
        verbose_name="Item factura",
    )

    # Diligencia finanzas
    numero_factura = models.CharField(
        "Número factura",
        max_length=60,
        unique=True,
        null=True,
        blank=True,
    )
    fecha_vencimiento = models.DateField(
        "Fecha vencimiento",
        null=True,
        blank=True,
    )
    fecha_radicacion = models.DateField(
        "Fecha radicación",
        default=date.today,
        null=True,
        blank=True,
    )
    tipo_pago = models.CharField(
        "Tipo de pago",
        max_length=10,
        choices=TIPO_PAGO_CHOICES,
        null=True,
        blank=True,
    )

    # Precio
    precio = models.DecimalField(
        "Precio",
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Estado
    estado = models.CharField(
        "Estado",
        max_length=12,
        choices=ESTADO_CHOICES,
        default="radicacion",
    )

    fecha_pago = models.DateField(
        "Fecha pago",
        null=True,
        blank=True,
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # --- Datos desde PAW ---
    @property
    def numero_paw(self):
        return self.paw.numero_paw

    @property
    def nombre_paw(self):
        return self.paw.nombre_paw

    @property
    def cliente(self):
        return self.paw.cliente

    @property
    def campo(self):
        return self.paw.campo

    # --- Cálculos financieros ---
    @property
    def iva(self):
        if self.precio:
            return self.precio * Decimal("0.19")
        return Decimal("0")

    @property
    def total_con_iva(self):
        if self.precio:
            return self.precio + self.iva
        return Decimal("0")

    @property
    def dias_para_vencer(self):
        if self.fecha_vencimiento:
            return (self.fecha_vencimiento - date.today()).days
        return None

    # --- Auto cálculo fecha vencimiento y estado ---
    def save(self, *args, **kwargs):
        # Si fecha_radicacion viene como datetime, convertirla a date
        if self.fecha_radicacion and hasattr(self.fecha_radicacion, "date"):
            self.fecha_radicacion = self.fecha_radicacion.date()

        # Calcular fecha de vencimiento solo si no existe
        if self.fecha_radicacion and not self.fecha_vencimiento:
            self.fecha_vencimiento = self.fecha_radicacion + timedelta(days=30)

        # Si tiene fecha de pago, siempre queda pagada
        if self.fecha_pago:
            self.estado = "pagada"

        # Si no está pagada y ya venció, queda vencida
        elif self.fecha_vencimiento and self.fecha_vencimiento < date.today():
            self.estado = "vencida"

        super().save(*args, **kwargs)

    def __str__(self):
        nf = self.numero_factura or "SIN NÚMERO"
        return f"Factura {nf} - PAW {self.paw.numero_paw}"