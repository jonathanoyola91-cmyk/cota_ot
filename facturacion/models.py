# facturacion/models.py
from django.db import models
from django.utils import timezone


class Factura(models.Model):
    TIPO_PAGO_CHOICES = [
        ("directo", "Directo"),
        ("endoso", "Endoso"),
    ]

    ESTADO_CHOICES = [
        ("radicacion", "Radicación"),
        ("facturado", "Facturado"),
        ("vencida", "Vencida"),
    ]

    paw = models.OneToOneField(
        "paw_app.Paw",
        on_delete=models.PROTECT,
        related_name="factura",
    )

    # ✅ Diligencia admin PAW
    lugar_entrega = models.CharField("Lugar de entrega", max_length=120, null=True, blank=True)  # antes municipio
    lugar_servicio = models.CharField("Lugar de servicio", max_length=120, null=True, blank=True)
    numero_servicio = models.CharField("Número de servicio", max_length=60, null=True, blank=True)

    item_factura = models.ForeignKey(
        "item_oil_gas.Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="facturas",
        verbose_name="Item factura",
    )

    # ✅ Diligencia finanzas
    numero_factura = models.CharField("Número factura", max_length=60, unique=True, null=True, blank=True)
    fecha_vencimiento = models.DateField("Fecha vencimiento", null=True, blank=True)
    fecha_radicacion = models.DateField("Fecha radicación", default=timezone.now, null=True, blank=True)
    tipo_pago = models.CharField("Tipo de pago", max_length=10, choices=TIPO_PAGO_CHOICES, null=True, blank=True)

    # ✅ Precio (lo diligencia PAW y/o Finanzas según tu admin)
    precio = models.DecimalField("Precio", max_digits=14, decimal_places=2, null=True, blank=True)

    # ✅ Estado final (Finanzas)
    estado = models.CharField("Estado", max_length=12, choices=ESTADO_CHOICES, default="radicacion")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # --- “Arrastre” desde PAW (solo lectura) ---
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

    def __str__(self):
        nf = self.numero_factura or "SIN NÚMERO"
        return f"Factura {nf} - PAW {self.paw.numero_paw}"
