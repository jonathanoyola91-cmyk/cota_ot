# paw_app/models.py
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

    # 🔧 IMPORTANTE: blank=True para permitir auto-llenado desde cotización
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
        """
        Auto-completa cliente y campo desde la cotización seleccionada.
        - No pisa valores si el usuario ya los escribió.
        - Funciona incluso sin JS (al guardar).
        """
        if self.cotizacion:
            if not self.cliente:
                self.cliente = self.cotizacion.cliente or ""
            if not self.campo:
                self.campo = self.cotizacion.campo or ""
        super().save(*args, **kwargs)

    def __str__(self):
        return f"PAW {self.numero_paw} - {self.cliente}"
