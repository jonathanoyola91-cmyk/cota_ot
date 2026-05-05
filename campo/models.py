from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class FieldService(models.Model):
    class Estado(models.TextChoices):
        EN_CURSO = "EN_CURSO", "En curso"
        FINALIZADO = "FINALIZADO", "Finalizado"

    paw = models.OneToOneField(
        "paw_app.Paw",
        on_delete=models.PROTECT,
        related_name="servicio_campo",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.EN_CURSO,
    )

    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(null=True, blank=True)

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="servicios_campo_responsable",
        null=True,
        blank=True,
    )

    observaciones = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-actualizado_en"]
        verbose_name = "Servicio de campo"
        verbose_name_plural = "Servicios de campo"

    @property
    def total_gastos(self):
        total = Decimal("0.00")
        for gasto in self.gastos.all():
            total += gasto.total_dia
        return total

    @property
    def total_dias(self):
        return self.gastos.count()

    def __str__(self):
        return f"Servicio campo - PAW {self.paw.numero_paw}"


class FieldServiceDailyExpense(models.Model):
    servicio = models.ForeignKey(
        FieldService,
        on_delete=models.CASCADE,
        related_name="gastos",
    )

    fecha = models.DateField(default=timezone.localdate)
    dia_numero = models.PositiveIntegerField(default=1)

    # Actividades: reporte técnico/preliminar para cliente, sin costos.
    actividades = models.TextField(
        "Actividades realizadas",
        blank=True,
        help_text="Resumen técnico de actividades realizadas durante el día. No incluir valores económicos.",
    )

    transporte = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    apoyo_local = models.DecimalField(
        "Apoyo local / comunidad",
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    alojamiento = models.DecimalField(
        "Alojamiento unitario",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Valor unitario por persona. El sistema lo multiplica por personas.",
    )

    personas = models.PositiveIntegerField(default=1)
    tarifa_alimentacion = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    hidratacion_por_persona = models.DecimalField(max_digits=14, decimal_places=2, default=10000)

    vuelo_ida_aplica = models.BooleanField(default=False)
    vuelo_ida_valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    vuelo_regreso_aplica = models.BooleanField(default=False)
    vuelo_regreso_valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    gastos_adicionales = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    observaciones = models.TextField(blank=True)

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="gastos_campo_registrados",
        null=True,
        blank=True,
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha", "dia_numero", "id"]
        verbose_name = "Gasto diario de campo"
        verbose_name_plural = "Gastos diarios de campo"

    @property
    def alojamiento_total(self):
        return Decimal(self.personas or 0) * Decimal(self.alojamiento or 0)

    @property
    def alimentacion_total(self):
        return Decimal(self.personas or 0) * Decimal(self.tarifa_alimentacion or 0)

    @property
    def hidratacion_total(self):
        return Decimal(self.personas or 0) * Decimal(self.hidratacion_por_persona or 0)

    @property
    def total_vuelos(self):
        total = Decimal("0.00")
        if self.vuelo_ida_aplica:
            total += Decimal(self.vuelo_ida_valor or 0)
        if self.vuelo_regreso_aplica:
            total += Decimal(self.vuelo_regreso_valor or 0)
        return total

    @property
    def total_dia(self):
        return (
            Decimal(self.transporte or 0)
            + Decimal(self.apoyo_local or 0)
            + self.alojamiento_total
            + self.alimentacion_total
            + self.hidratacion_total
            + self.total_vuelos
            + Decimal(self.gastos_adicionales or 0)
        )

    def __str__(self):
        return f"Día {self.dia_numero} - {self.servicio}"
