# paw_app/models.py
from django.conf import settings
from django.db import models


class Paw(models.Model):
    numero_paw = models.CharField(
        "Número PAW",
        max_length=50,
        unique=True,
        blank=True,
    )

    nombre_paw = models.CharField(
        "Nombre del PAW",
        max_length=150,
        blank=True,
    )

    cotizacion = models.ForeignKey(
        "quotes.Quotation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paws",
    )

    cliente = models.CharField(max_length=120, blank=True)
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

    def save(self, *args, **kwargs):
        if not self.numero_paw:
            ultimo = (
                Paw.objects
                .exclude(numero_paw__isnull=True)
                .exclude(numero_paw="")
                .order_by("-id")
                .first()
            )

            if ultimo and str(ultimo.numero_paw).isdigit():
                self.numero_paw = str(int(ultimo.numero_paw) + 1)
            else:
                self.numero_paw = "1160"

        if self.cotizacion:
            if not self.nombre_paw:
                self.nombre_paw = self.cotizacion.nombre_cotizacion or ""

            if not self.cliente:
                self.cliente = self.cotizacion.cliente or ""

            if not self.campo:
                self.campo = self.cotizacion.campo or ""

        super().save(*args, **kwargs)

    def __str__(self):
        return f"PAW {self.numero_paw} - {self.cliente}"