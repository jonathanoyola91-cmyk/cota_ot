from django.db import models
from django.db.models import Sum
from decimal import Decimal


class PeriodoVenta(models.Model):
    anio = models.PositiveIntegerField("Año")
    mes = models.PositiveIntegerField("Mes")

    class Meta:
        unique_together = ("anio", "mes")
        ordering = ["-anio", "-mes"]
        verbose_name = "Periodo de venta"
        verbose_name_plural = "Periodos de venta"

    def __str__(self):
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        return f"{meses.get(self.mes, self.mes)} {self.anio}"

    def total_ventas_valor(self):
        total = self.ventas.aggregate(total=Sum("precio"))["total"]
        return total or Decimal("0")

    def total_costos(self):
        total = self.ventas.aggregate(total=Sum("costo"))["total"]
        return total or Decimal("0")

    def total_abonado(self):
        total = self.ventas.aggregate(total=Sum("valor_abonado"))["total"]
        return total or Decimal("0")

    def total_por_cobrar(self):
        total = self.ventas.aggregate(total=Sum("valor_deber"))["total"]
        return total or Decimal("0")

    def utilidad_bruta(self):
        return self.total_ventas_valor() - self.total_costos()


class Venta(models.Model):
    STATUS_CHOICES = [
        ("DEBE", "Debe"),
        ("ABONADO", "Abonado"),
        ("PAGADO", "Pagado"),
    ]

    periodo = models.ForeignKey(
        PeriodoVenta,
        on_delete=models.CASCADE,
        related_name="ventas",
    )
    cliente = models.CharField(max_length=100)
    tipo_prenda = models.CharField(max_length=100)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="DEBE")
    valor_abonado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_deber = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"

    def save(self, *args, **kwargs):
        precio = self.precio or Decimal("0")
        abonado = self.valor_abonado or Decimal("0")

        if self.status == "PAGADO":
            self.valor_abonado = precio
        elif self.status == "DEBE":
            self.valor_abonado = Decimal("0")
        else:
            if abonado > precio:
                self.valor_abonado = precio

        self.valor_deber = precio - self.valor_abonado
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} - {self.tipo_prenda} - {self.periodo}"