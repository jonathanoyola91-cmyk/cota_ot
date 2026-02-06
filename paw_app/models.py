from django.conf import settings
from django.db import models

class Paw(models.Model):
    numero_paw = models.CharField("Número PAW", max_length=50, unique=True)
    nombre_paw = models.CharField("Nombre del PAW", max_length=150)

    cotizacion = models.ForeignKey(
        "quotes.Quotation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paws",
    )


    cliente = models.CharField(max_length=120)
    campo = models.CharField(max_length=120, blank=True)

    fecha_entrega = models.DateField(null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="paws_creados"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PAW {self.numero_paw} - {self.cliente}"
