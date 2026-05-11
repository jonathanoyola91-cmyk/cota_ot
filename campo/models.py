from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


BONO_LIDER = Decimal("90000")
BONO_APOYO = Decimal("75000")
BONO_MOVILIZACION_PERSONA = Decimal("70000")


class FieldService(models.Model):
    TECNICOS_CHOICES = [
        ("Carlos Hende", "Carlos Hende"),
        ("Reison Vanegas", "Reison Vanegas"),
        ("Yeferson Muñoz", "Yeferson Muñoz"),
        ("Sergio Ortiz", "Sergio Ortiz"),
        ("Jose Oyola", "Jose Oyola"),
    ]

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

    especialista_lider = models.CharField(
        "Especialista líder",
        max_length=100,
        choices=TECNICOS_CHOICES,
        blank=True,
        default="",
    )

    especialista_apoyo = models.CharField(
        "Especialista apoyo",
        max_length=100,
        choices=TECNICOS_CHOICES,
        blank=True,
        default="",
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
    def total_bonos(self):
        total = Decimal("0.00")
        for gasto in self.gastos.all():
            total += gasto.total_bonos
        return total

    @property
    def total_dias(self):
        return self.gastos.count()

    @property
    def cantidad_tecnicos_asignados(self):
        cantidad = 0
        if self.especialista_lider:
            cantidad += 1
        if self.especialista_apoyo:
            cantidad += 1
        return cantidad

    def __str__(self):
        return f"Servicio campo - PAW {self.paw.numero_paw}"


class FieldServiceDailyExpense(models.Model):
    APROBADO_POR_CHOICES = [
        ("", "---------"),
        ("Jose Oyola", "Jose Oyola"),
        ("Marcela Cutiva", "Marcela Cutiva"),
        ("Gerencia", "Gerencia"),
    ]

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

    # Clasificación operativa LEGADA.
    # Se conserva para no romper reportes anteriores ni registros ya creados.
    # En los registros nuevos, la clasificación principal se captura por persona
    # en FieldServicePersonExpense.
    dia_trabajado_campo = models.BooleanField(
        "Día trabajado en campo",
        default=True,
        help_text="Marcar cuando el personal trabajó en campo y aplica bono según rol.",
    )
    salida_despues_mediodia = models.BooleanField(
        "Salida después del mediodía",
        default=False,
        help_text="Si solo hubo salida después de las 12:00, no aplica bono campo; aplica movilización.",
    )
    regreso_despues_6pm = models.BooleanField(
        "Regreso después de las 6:00 pm",
        default=False,
        help_text="Si ya trabajó el día, suma movilización adicional por persona.",
    )
    solo_viaje_traslado = models.BooleanField(
        "Solo viaje / traslado",
        default=False,
        help_text="Día sin trabajo en campo. Solo aplica movilización por persona.",
    )

    transporte = models.DecimalField(
        "Transporte comunidad / operación",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Valor manual que cobra la operación/comunidad por movilización diaria.",
    )

    # Campo legado: se conserva para no romper registros/migraciones anteriores.
    apoyo_local = models.DecimalField(
        "Apoyo local / comunidad (legado)",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Campo legado. Ya no se captura en el formulario.",
    )

    # Campos legados: se conservan para reportes/registros anteriores.
    # Para registros nuevos se usa el detalle por persona.
    alojamiento = models.DecimalField(
        "Alojamiento unitario",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Campo legado. En registros nuevos se captura por persona.",
    )

    personas = models.PositiveIntegerField(
        default=1,
        help_text="Cantidad de personas para habilitar el detalle individual de gastos.",
    )
    tarifa_alimentacion = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    hidratacion_por_persona = models.DecimalField(max_digits=14, decimal_places=2, default=10000)

    vuelo_ida_aplica = models.BooleanField(default=False)
    vuelo_ida_valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    vuelo_regreso_aplica = models.BooleanField(default=False)
    vuelo_regreso_valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    gastos_adicionales = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    comprado_por = models.CharField(
        "Quién compró",
        max_length=120,
        blank=True,
        default="",
        help_text="Registro informativo. No genera flujo de aprobación.",
    )

    aprobado_por = models.CharField(
        "Quién aprobó",
        max_length=120,
        choices=APROBADO_POR_CHOICES,
        blank=True,
        default="",
        help_text="Registro informativo. No genera flujo de aprobación.",
    )

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

    def _tiene_detalle_personas(self):
        if not self.pk:
            return False
        return self.detalle_personas.exists()

    @property
    def cantidad_personas_bono(self):
        """
        Para registros nuevos, la movilización se liquida por cada línea individual
        de FieldServicePersonExpense. Para registros antiguos, se conserva la
        lógica original por técnicos asignados al servicio.
        """
        if self._tiene_detalle_personas():
            return self.detalle_personas.count()

        cantidad = self.servicio.cantidad_tecnicos_asignados if self.servicio_id else 0
        return cantidad or int(self.personas or 0)

    @property
    def aplica_bono_campo(self):
        if self._tiene_detalle_personas():
            return self.detalle_personas.filter(
                clasificacion__in=[
                    FieldServicePersonExpense.Clasificacion.DIA_TRABAJADO_CAMPO,
                    FieldServicePersonExpense.Clasificacion.REGRESO_DESPUES_6PM,
                ]
            ).exists()

        if self.solo_viaje_traslado:
            return False
        if self.salida_despues_mediodia and not self.dia_trabajado_campo:
            return False
        return bool(self.dia_trabajado_campo)

    @property
    def aplica_bono_movilizacion(self):
        if self._tiene_detalle_personas():
            return self.detalle_personas.filter(
                clasificacion__in=[
                    FieldServicePersonExpense.Clasificacion.SALIDA_DESPUES_MEDIODIA,
                    FieldServicePersonExpense.Clasificacion.REGRESO_DESPUES_6PM,
                    FieldServicePersonExpense.Clasificacion.SOLO_VIAJE_TRASLADO,
                ]
            ).exists()

        return bool(
            self.solo_viaje_traslado
            or self.salida_despues_mediodia
            or self.regreso_despues_6pm
        )

    @property
    def bono_lider(self):
        if self._tiene_detalle_personas():
            if not self.servicio.especialista_lider:
                return Decimal("0.00")

            linea = self.detalle_personas.filter(
                persona=self.servicio.especialista_lider
            ).first()

            if linea:
                return linea.bono_campo

            return Decimal("0.00")

        if self.aplica_bono_campo and self.servicio.especialista_lider:
            return BONO_LIDER
        return Decimal("0.00")

    @property
    def bono_apoyo(self):
        if self._tiene_detalle_personas():
            if not self.servicio.especialista_apoyo:
                return Decimal("0.00")

            linea = self.detalle_personas.filter(
                persona=self.servicio.especialista_apoyo
            ).first()

            if linea:
                return linea.bono_campo

            return Decimal("0.00")

        if self.aplica_bono_campo and self.servicio.especialista_apoyo:
            return BONO_APOYO
        return Decimal("0.00")

    @property
    def bono_campo_total(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += linea.bono_campo
            return total

        return self.bono_lider + self.bono_apoyo

    @property
    def bono_movilizacion_total(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += linea.bono_movilizacion
            return total

        if not self.aplica_bono_movilizacion:
            return Decimal("0.00")
        return Decimal(self.cantidad_personas_bono or 0) * BONO_MOVILIZACION_PERSONA

    @property
    def total_bonos(self):
        return self.bono_campo_total + self.bono_movilizacion_total

    @property
    def alojamiento_total(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += Decimal(linea.alojamiento or 0)
            return total

        return Decimal(self.personas or 0) * Decimal(self.alojamiento or 0)

    @property
    def alimentacion_total(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += Decimal(linea.alimentacion or 0)
            return total

        return Decimal(self.personas or 0) * Decimal(self.tarifa_alimentacion or 0)

    @property
    def hidratacion_total(self):
        return Decimal(self.personas or 0) * Decimal(self.hidratacion_por_persona or 0)

    @property
    def lavanderia_total(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += Decimal(linea.lavanderia or 0)
            return total

        return Decimal("0.00")

    @property
    def transporte_personal_total(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += Decimal(linea.transporte_personal or 0)
            return total

        return Decimal("0.00")

    @property
    def total_vuelos(self):
        if self._tiene_detalle_personas():
            total = Decimal("0.00")
            for linea in self.detalle_personas.all():
                total += linea.total_vuelos
            return total

        total = Decimal("0.00")
        if self.vuelo_ida_aplica:
            total += Decimal(self.vuelo_ida_valor or 0)
        if self.vuelo_regreso_aplica:
            total += Decimal(self.vuelo_regreso_valor or 0)
        return total

    @property
    def total_detalle_personas(self):
        if not self._tiene_detalle_personas():
            return Decimal("0.00")

        total = Decimal("0.00")
        for linea in self.detalle_personas.all():
            total += linea.total_gastos
        return total

    @property
    def total_dia(self):
        """
        Total de costos operativos del día.
        Los bonos técnicos quedan separados en total_bonos.
        """
        if self._tiene_detalle_personas():
            return (
                Decimal(self.transporte or 0)
                + self.total_detalle_personas
                + Decimal(self.gastos_adicionales or 0)
            )

        return (
            Decimal(self.transporte or 0)
            + self.alojamiento_total
            + self.alimentacion_total
            + self.hidratacion_total
            + self.total_vuelos
            + Decimal(self.gastos_adicionales or 0)
        )

    def __str__(self):
        return f"Día {self.dia_numero} - {self.servicio}"


class FieldServicePersonExpense(models.Model):
    class Clasificacion(models.TextChoices):
        DIA_TRABAJADO_CAMPO = "DIA_TRABAJADO_CAMPO", "Día trabajado en campo"
        SALIDA_DESPUES_MEDIODIA = "SALIDA_DESPUES_MEDIODIA", "Salida después del mediodía"
        REGRESO_DESPUES_6PM = "REGRESO_DESPUES_6PM", "Regreso después de las 6:00 pm"
        SOLO_VIAJE_TRASLADO = "SOLO_VIAJE_TRASLADO", "Solo viaje / traslado"

    gasto_diario = models.ForeignKey(
        FieldServiceDailyExpense,
        on_delete=models.CASCADE,
        related_name="detalle_personas",
    )

    persona = models.CharField("Persona / técnico", max_length=120)
    clasificacion = models.CharField(
        "Clasificación operativa",
        max_length=40,
        choices=Clasificacion.choices,
        default=Clasificacion.DIA_TRABAJADO_CAMPO,
    )

    alojamiento = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    alimentacion = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    lavanderia = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    transporte_personal = models.DecimalField(
        "Transporte personal",
        max_digits=14,
        decimal_places=2,
        default=0,
        help_text="Taxi, transporte al aeropuerto u otros transportes personales.",
    )

    vuelo_ida_aplica = models.BooleanField(default=False)
    vuelo_ida_valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    vuelo_regreso_aplica = models.BooleanField(default=False)
    vuelo_regreso_valor = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    observaciones = models.CharField(max_length=250, blank=True, default="")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Gasto por persona de campo"
        verbose_name_plural = "Gastos por persona de campo"

    @property
    def es_lider(self):
        if not self.gasto_diario_id:
            return False
        return self.persona == self.gasto_diario.servicio.especialista_lider

    @property
    def es_apoyo(self):
        if not self.gasto_diario_id:
            return False
        return self.persona == self.gasto_diario.servicio.especialista_apoyo

    @property
    def aplica_bono_campo(self):
        return self.clasificacion in [
            self.Clasificacion.DIA_TRABAJADO_CAMPO,
            self.Clasificacion.REGRESO_DESPUES_6PM,
        ]

    @property
    def aplica_bono_movilizacion(self):
        return self.clasificacion in [
            self.Clasificacion.SALIDA_DESPUES_MEDIODIA,
            self.Clasificacion.REGRESO_DESPUES_6PM,
            self.Clasificacion.SOLO_VIAJE_TRASLADO,
        ]

    @property
    def bono_campo(self):
        if not self.aplica_bono_campo:
            return Decimal("0.00")

        if self.es_lider:
            return BONO_LIDER

        if self.es_apoyo:
            return BONO_APOYO

        return Decimal("0.00")

    @property
    def bono_movilizacion(self):
        if self.aplica_bono_movilizacion:
            return BONO_MOVILIZACION_PERSONA
        return Decimal("0.00")

    @property
    def total_vuelos(self):
        total = Decimal("0.00")
        if self.vuelo_ida_aplica:
            total += Decimal(self.vuelo_ida_valor or 0)
        if self.vuelo_regreso_aplica:
            total += Decimal(self.vuelo_regreso_valor or 0)
        return total

    @property
    def total_gastos(self):
        return (
            Decimal(self.alojamiento or 0)
            + Decimal(self.alimentacion or 0)
            + Decimal(self.lavanderia or 0)
            + Decimal(self.transporte_personal or 0)
            + self.total_vuelos
        )

    @property
    def total_bonos(self):
        return self.bono_campo + self.bono_movilizacion

    def __str__(self):
        return f"{self.persona} - Día {self.gasto_diario.dia_numero}"
