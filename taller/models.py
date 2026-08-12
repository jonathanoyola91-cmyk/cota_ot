from datetime import datetime, timedelta, time
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


TECNICOS_TALLER_CHOICES = [
    ("Carlos Hende", "Carlos Hende"),
    ("Reison Vanegas", "Reison Vanegas"),
    ("Yeferson Muñoz", "Yeferson Muñoz"),
    ("Sergio Ortiz", "Sergio Ortiz"),
    ("Jose Oyola", "Jose Oyola"),
]


class CamaraTaller(models.Model):

    class Estado(models.TextChoices):
        RECIBIDA = "RECIBIDA", "Recibida"
        PENDIENTE_TD = "PENDIENTE_TD", "Pendiente Tear Down"
        TD_REALIZADO = "TD_REALIZADO", "Tear Down realizado"
        PENDIENTE_COTIZACION = (
            "PENDIENTE_COTIZACION",
            "Pendiente cotización"
        )
        COTIZACION_ENVIADA = (
            "COTIZACION_ENVIADA",
            "Cotización enviada"
        )
        PENDIENTE_APROBACION = (
            "PENDIENTE_APROBACION",
            "Pendiente aprobación"
        )
        APROBADA = "APROBADA", "Aprobada / Pendiente PAW"
        PAW_GENERADO = "PAW_GENERADO", "PAW generado"

    cliente = models.CharField(max_length=200)
    marca = models.CharField(max_length=150, blank=True)
    serial = models.CharField(max_length=100, db_index=True)
    modelo = models.CharField(max_length=150, blank=True)
    fecha_ingreso = models.DateField()
    fecha_tear_down = models.DateField(
        "Fecha Tear Down",
        null=True,
        blank=True,
    )
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.RECIBIDA
    )

    observaciones = models.TextField(blank=True)

    paw = models.ForeignKey(
        "paw_app.Paw",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="camaras_taller"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.serial} - {self.cliente}"


class EnsambleTaller(models.Model):
    """
    Control INTERNO del ensamble de una cámara.
    Finalizar este registro NO modifica el estado de CamaraTaller ni del PAW.
    """

    class Estado(models.TextChoices):
        EN_CURSO = "EN_CURSO", "En curso"
        FINALIZADO = "FINALIZADO", "Finalizado"

    # Relación principal del control de horas.
    # Se deja null=True temporalmente para que la migración desde la versión
    # anterior no solicite un valor por defecto. Las vistas siempre asignan PAW.
    paw = models.OneToOneField(
        "paw_app.Paw",
        on_delete=models.PROTECT,
        related_name="ensamble_horas_taller",
        null=True,
        blank=True,
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.EN_CURSO,
    )

    fecha_inicio = models.DateField(default=timezone.localdate)
    fecha_fin = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ensambles_taller_responsable",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-actualizado_en"]
        verbose_name = "Ensamble de taller"
        verbose_name_plural = "Ensambles de taller"

    @property
    def total_horas_ordinarias(self):
        return sum((j.horas_ordinarias for j in self.jornadas.all()), Decimal("0.00"))

    @property
    def total_extra_diurna(self):
        return sum((j.horas_extra_diurna for j in self.jornadas.all()), Decimal("0.00"))

    @property
    def total_extra_nocturna(self):
        return sum((j.horas_extra_nocturna for j in self.jornadas.all()), Decimal("0.00"))

    @property
    def total_horas_hombre(self):
        return sum((j.horas_totales for j in self.jornadas.all()), Decimal("0.00"))

    @property
    def cantidad_tecnicos(self):
        return self.tecnicos.count()

    def __str__(self):
        paw = self.paw.numero_paw if self.paw else "SIN PAW"
        nombre = self.paw.nombre_paw if self.paw else ""
        return f"Control horas PAW {paw} - {nombre}"


class EnsambleTallerTecnico(models.Model):
    ensamble = models.ForeignKey(
        EnsambleTaller,
        on_delete=models.CASCADE,
        related_name="tecnicos",
    )

    tecnico = models.CharField(
        "Técnico",
        max_length=120,
        choices=TECNICOS_TALLER_CHOICES,
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tecnico"]
        constraints = [
            models.UniqueConstraint(
                fields=["ensamble", "tecnico"],
                name="uniq_tecnico_por_ensamble_taller",
            )
        ]
        verbose_name = "Técnico de ensamble"
        verbose_name_plural = "Técnicos de ensamble"

    def __str__(self):
        return self.tecnico


class JornadaTaller(models.Model):
    """
    Reglas internas solicitadas:
    - Ordinario: 07:00-12:00 y 13:00-16:00 (máximo 8 h si cubre toda la jornada).
    - Almuerzo: 12:00-13:00, no suma tiempo trabajado.
    - Extra diurna: 16:00-19:00.
    - Extra nocturna: 19:00-06:00 del día siguiente.

    Para jornadas que cruzan medianoche, si hora_salida <= hora_entrada,
    la salida se interpreta como el día siguiente.
    """

    ensamble = models.ForeignKey(
        EnsambleTaller,
        on_delete=models.CASCADE,
        related_name="jornadas",
    )

    tecnico = models.ForeignKey(
        EnsambleTallerTecnico,
        on_delete=models.PROTECT,
        related_name="jornadas",
    )

    fecha = models.DateField(default=timezone.localdate)
    hora_entrada = models.TimeField()
    hora_salida = models.TimeField()
    actividades = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)

    horas_ordinarias = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    horas_extra_diurna = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    horas_extra_nocturna = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)
    horas_totales = models.DecimalField(max_digits=6, decimal_places=2, default=0, editable=False)

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="jornadas_taller_registradas",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["fecha", "hora_entrada", "tecnico__tecnico", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["ensamble", "tecnico", "fecha", "hora_entrada"],
                name="uniq_inicio_jornada_tecnico_taller",
            )
        ]
        verbose_name = "Jornada de taller"
        verbose_name_plural = "Jornadas de taller"

    @staticmethod
    def _horas_interseccion(inicio, fin, tramo_inicio, tramo_fin):
        desde = max(inicio, tramo_inicio)
        hasta = min(fin, tramo_fin)
        if hasta <= desde:
            return Decimal("0.00")
        segundos = Decimal(str((hasta - desde).total_seconds()))
        return (segundos / Decimal("3600")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _intervalo_real(self):
        inicio = datetime.combine(self.fecha, self.hora_entrada)
        fin = datetime.combine(self.fecha, self.hora_salida)

        if self.hora_salida <= self.hora_entrada:
            fin += timedelta(days=1)

        return inicio, fin

    def calcular_horas(self):
        inicio, fin = self._intervalo_real()
        dia = self.fecha
        dia_sig = dia + timedelta(days=1)

        ordinaria_1_ini = datetime.combine(dia, time(7, 0))
        ordinaria_1_fin = datetime.combine(dia, time(12, 0))
        ordinaria_2_ini = datetime.combine(dia, time(13, 0))
        ordinaria_2_fin = datetime.combine(dia, time(16, 0))

        extra_dia_ini = datetime.combine(dia, time(16, 0))
        extra_dia_fin = datetime.combine(dia, time(19, 0))

        extra_noche_ini = datetime.combine(dia, time(19, 0))
        extra_noche_fin = datetime.combine(dia_sig, time(6, 0))

        ordinarias = (
            self._horas_interseccion(inicio, fin, ordinaria_1_ini, ordinaria_1_fin)
            + self._horas_interseccion(inicio, fin, ordinaria_2_ini, ordinaria_2_fin)
        )
        extra_diurna = self._horas_interseccion(inicio, fin, extra_dia_ini, extra_dia_fin)
        extra_nocturna = self._horas_interseccion(inicio, fin, extra_noche_ini, extra_noche_fin)

        total = ordinarias + extra_diurna + extra_nocturna
        return ordinarias, extra_diurna, extra_nocturna, total

    def clean(self):
        super().clean()

        if not self.ensamble_id or not self.tecnico_id:
            return

        if self.ensamble.estado == EnsambleTaller.Estado.FINALIZADO:
            raise ValidationError("No se pueden registrar o modificar jornadas de un ensamble finalizado.")

        if self.tecnico.ensamble_id != self.ensamble_id:
            raise ValidationError("El técnico seleccionado no está asignado a este ensamble.")

        # La jornada operativa se registra desde las 07:00. La franja nocturna
        # posterior a medianoche debe pertenecer a una jornada iniciada el día anterior.
        if self.hora_entrada < time(7, 0):
            raise ValidationError({
                "hora_entrada": "La hora de entrada debe ser 07:00 o posterior. La franja nocturna después de medianoche se registra como continuación del día anterior."
            })

        inicio, fin = self._intervalo_real()
        if fin - inicio > timedelta(hours=23):
            raise ValidationError("La jornada registrada no puede superar 23 horas.")

        # Si cruza medianoche, solo clasificamos hasta 06:00 del día siguiente.
        if fin.date() > inicio.date() and self.hora_salida > time(6, 0):
            raise ValidationError({
                "hora_salida": "Si la jornada cruza medianoche, la salida debe ser máximo a las 06:00 del día siguiente."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        (
            self.horas_ordinarias,
            self.horas_extra_diurna,
            self.horas_extra_nocturna,
            self.horas_totales,
        ) = self.calcular_horas()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fecha} - {self.tecnico.tecnico} - {self.horas_totales} h"
