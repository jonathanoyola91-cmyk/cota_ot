from decimal import Decimal
from django.db import models
from paw_app.models import Paw


class Presupuesto(models.Model):
    paw = models.OneToOneField(
        Paw,
        on_delete=models.CASCADE,
        related_name="presupuesto",
    )

    # snapshot del total calculado desde compras_oil
    total_paw = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    presupuesto_aprobado = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Presupuesto"
        verbose_name_plural = "Presupuestos"

    @property
    def presupuesto_disponible(self):
        aprobado = self.presupuesto_aprobado or Decimal("0.00")
        total = self.total_paw or Decimal("0.00")
        return aprobado - total

    def __str__(self):
        return f"Presupuesto - PAW {self.paw.numero_paw}"