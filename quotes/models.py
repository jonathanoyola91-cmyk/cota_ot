# quotes/models.py
from django.db import models


class Quotation(models.Model):
    class Estado(models.TextChoices):
        ADJUDICADA = "ADJUDICADA", "Adjudicada"
        EVALUACION = "EVALUACION", "Evaluación"
        CERRADA = "CERRADA", "Cerrada"

    class Empresa(models.TextChoices):
        IMPETUS = "IMPETUS", "Impetus"
        OIL_GAS = "OIL_GAS", "Oil & Gas"

    numero_cotizacion = models.CharField(
        "Número de cotización",
        max_length=50,
        unique=True
    )
    nombre_cotizacion = models.CharField(
        "Nombre de cotización",
        max_length=150
    )

    cliente = models.CharField(max_length=120)
    campo = models.CharField(max_length=120, blank=True)

    fecha_cotizacion = models.DateField(null=True, blank=True)

    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.EVALUACION
    )
    empresa = models.CharField(
        max_length=12,
        choices=Empresa.choices,
        default=Empresa.IMPETUS
    )

    # ✅ NUEVO: Valor de la cotización
    valor = models.DecimalField(
        max_digits=14,
        decimal_places=0,
        default=0
    )

    observaciones = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"COT {self.numero_cotizacion} - {self.cliente}"
