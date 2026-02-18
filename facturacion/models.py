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

    # Completa PAW admin
    municipio = models.CharField(max_length=120, null=True, blank=True)
    numero_servicio = models.CharField(max_length=60, null=True, blank=True)

    # Completa Facturación admin
    numero_factura = models.CharField(max_length=60, unique=True, null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_radicacion = models.DateField(default=timezone.now, null=True, blank=True)
    tipo_pago = models.CharField(max_length=10, choices=TIPO_PAGO_CHOICES, null=True, blank=True)
    precio = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default="radicacion")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Factura {self.numero_factura or 'SIN NÚMERO'} - {self.paw.numero_paw}"
