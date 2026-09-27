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
        ENTREGADA = "ENTREGADA", "Entregada / Salió de Taller"

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
        """
        Calcula las horas del intervalo registrado para ESTE PAW/cámara.

        La hora de entrada y salida representan el tiempo real dedicado a una
        actividad específica, no necesariamente la jornada laboral completa
        del técnico.

        Franjas internas:
        - 00:00-06:00  -> extra nocturna
        - 06:00-07:00  -> extra diurna
        - 07:00-12:00  -> ordinaria
        - 12:00-13:00  -> almuerzo (no suma)
        - 13:00-16:00  -> ordinaria
        - 16:00-19:00  -> extra diurna
        - 19:00-24:00  -> extra nocturna

        Si el intervalo cruza medianoche, se continúa clasificando hasta la
        hora real de salida del día siguiente.
        """
        inicio, fin = self._intervalo_real()

        ordinarias = Decimal("0.00")
        extra_diurna = Decimal("0.00")
        extra_nocturna = Decimal("0.00")

        dia_cursor = inicio.date()
        dia_fin = fin.date()

        while dia_cursor <= dia_fin:
            dia_sig = dia_cursor + timedelta(days=1)

            # Extra nocturna 00:00-06:00
            nocturna_manana_ini = datetime.combine(dia_cursor, time(0, 0))
            nocturna_manana_fin = datetime.combine(dia_cursor, time(6, 0))

            # Extra diurna 06:00-07:00
            extra_pre_ini = datetime.combine(dia_cursor, time(6, 0))
            extra_pre_fin = datetime.combine(dia_cursor, time(7, 0))

            # Ordinaria
            ordinaria_1_ini = datetime.combine(dia_cursor, time(7, 0))
            ordinaria_1_fin = datetime.combine(dia_cursor, time(12, 0))
            ordinaria_2_ini = datetime.combine(dia_cursor, time(13, 0))
            ordinaria_2_fin = datetime.combine(dia_cursor, time(16, 0))

            # Extra diurna
            extra_dia_ini = datetime.combine(dia_cursor, time(16, 0))
            extra_dia_fin = datetime.combine(dia_cursor, time(19, 0))

            # Extra nocturna 19:00-24:00
            nocturna_noche_ini = datetime.combine(dia_cursor, time(19, 0))
            nocturna_noche_fin = datetime.combine(dia_sig, time(0, 0))

            ordinarias += (
                self._horas_interseccion(inicio, fin, ordinaria_1_ini, ordinaria_1_fin)
                + self._horas_interseccion(inicio, fin, ordinaria_2_ini, ordinaria_2_fin)
            )

            extra_diurna += (
                self._horas_interseccion(inicio, fin, extra_pre_ini, extra_pre_fin)
                + self._horas_interseccion(inicio, fin, extra_dia_ini, extra_dia_fin)
            )

            extra_nocturna += (
                self._horas_interseccion(inicio, fin, nocturna_manana_ini, nocturna_manana_fin)
                + self._horas_interseccion(inicio, fin, nocturna_noche_ini, nocturna_noche_fin)
            )

            dia_cursor = dia_sig

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

        # Hora de entrada y salida son libres porque representan el intervalo
        # real dedicado a este PAW/cámara. Puede empezar antes de las 07:00,
        # después de las 16:00 o cruzar medianoche.
        inicio, fin = self._intervalo_real()

        if fin <= inicio:
            raise ValidationError("La hora de salida debe ser posterior a la hora de entrada.")

        if fin - inicio > timedelta(hours=23):
            raise ValidationError("El intervalo registrado no puede superar 23 horas.")

        # Evitar doble contabilización del mismo técnico en el mismo intervalo,
        # incluso si estaba trabajando sobre PAW diferentes.
        otras = (
            JornadaTaller.objects
            .filter(
                tecnico__tecnico=self.tecnico.tecnico,
                fecha__in=[
                    self.fecha - timedelta(days=1),
                    self.fecha,
                    self.fecha + timedelta(days=1),
                ],
            )
            .exclude(pk=self.pk)
            .select_related("tecnico")
        )

        for otra in otras:
            otro_inicio, otro_fin = otra._intervalo_real()
            if inicio < otro_fin and fin > otro_inicio:
                raise ValidationError(
                    "El técnico ya tiene otra actividad registrada que se cruza "
                    "con este intervalo. Ajuste la hora de entrada o salida."
                )

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

# =========================
# METROLOGIA / CALIDAD
# =========================


class TipoPiezaMetrologia(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "Tipo de pieza metrológica"
        verbose_name_plural = "Tipos de pieza metrológica"

    def __str__(self):
        return self.nombre

class PlantillaEje(models.Model):
    class TipoPieza(models.TextChoices):
        EJE = "EJE", "Eje"
        HOUSING = "HOUSING", "Housing"
        SLEEVE = "SLEEVE", "Sleeve / camisa"
        CAMARA = "CAMARA", "Cámara"
        BOMBA = "BOMBA", "Bomba"
        OTRO = "OTRO", "Otra pieza"

    nombre = models.CharField(max_length=180, unique=True)
    tipo_pieza = models.CharField(max_length=20, choices=TipoPieza.choices, default=TipoPieza.EJE)
    tipo_pieza_ref = models.ForeignKey("TipoPiezaMetrologia", on_delete=models.PROTECT, null=True, blank=True, related_name="plantillas")
    codigo_plano = models.CharField(max_length=120, blank=True)
    revision = models.CharField(max_length=30, blank=True)
    material = models.CharField(max_length=100, blank=True)
    imagen_mapa = models.CharField(max_length=160, blank=True, help_text="Imagen técnica histórica incluida con el sistema")
    imagen_archivo = models.ImageField(upload_to="taller/metrologia/plantillas/%Y/%m/", null=True, blank=True, help_text="Plano o imagen técnica cargada para configurar los puntos")
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Plantilla metrológica de eje"
        verbose_name_plural = "Plantillas metrológicas de ejes"
        permissions = [("gestionar_plantillas_metrologicas", "Puede crear y editar plantillas metrológicas")]

    def __str__(self):
        rev = f" Rev. {self.revision}" if self.revision else ""
        return f"{self.nombre}{rev}"


class PuntoMedicionEje(models.Model):
    class Tipo(models.TextChoices):
        DIAMETRO = "DIAMETRO", "Diámetro"
        LONGITUD = "LONGITUD", "Longitud"
        RUNOUT = "RUNOUT", "Runout"
        ANCHO = "ANCHO", "Ancho"
        PROFUNDIDAD = "PROFUNDIDAD", "Profundidad"
        OTRO = "OTRO", "Otro"

    plantilla = models.ForeignKey(PlantillaEje, on_delete=models.CASCADE, related_name="puntos")
    codigo = models.CharField(max_length=20)
    descripcion = models.CharField(max_length=220)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.DIAMETRO)
    nominal = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    minimo = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    maximo = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    minimo_reutilizable = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text="Límite mínimo para reutilización en reparaciones")
    permite_mecanizado = models.BooleanField(default=True, help_text="Permite recuperar este punto mediante mecanizado autorizado")
    unidad = models.CharField(max_length=20, default="mm")
    instrumento_sugerido = models.CharField(max_length=120, blank=True)
    critico = models.BooleanField(default=True)
    obligatorio = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)
    nota = models.CharField(max_length=250, blank=True)
    posicion_x = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Posición horizontal del marcador sobre el plano (0-100%)")
    posicion_y = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Posición vertical del marcador sobre el plano (0-100%)")

    class Meta:
        ordering = ["orden", "id"]
        constraints = [models.UniqueConstraint(fields=["plantilla", "codigo"], name="uniq_punto_eje_plantilla")]

    def __str__(self):
        return f"{self.plantilla.nombre} - {self.codigo}: {self.descripcion}"


class InstrumentoMetrologico(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        FUERA_SERVICIO = "FUERA_SERVICIO", "Fuera de servicio"
        BAJA = "BAJA", "Dado de baja"

    nombre = models.CharField(max_length=120, help_text="Tipo de instrumento: Micrómetro, Comparador, Calibrador, etc.")
    codigo = models.CharField(max_length=60, unique=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    serial = models.CharField(max_length=100, blank=True)
    rango = models.CharField(max_length=100, blank=True)
    resolucion = models.CharField(max_length=60, blank=True)
    unidad = models.CharField(max_length=30, blank=True)
    ubicacion = models.CharField(max_length=120, blank=True)
    responsable = models.CharField(max_length=120, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)
    fecha_calibracion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    laboratorio = models.CharField(max_length=150, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    certificado = models.FileField(upload_to="taller/metrologia/certificados/%Y/%m/", null=True, blank=True)
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["codigo"]

    @property
    def calibracion_vigente(self):
        return bool(self.fecha_vencimiento and self.fecha_vencimiento >= timezone.localdate())

    @property
    def estado_calibracion(self):
        if self.estado != self.Estado.ACTIVO or not self.activo:
            return "FUERA_SERVICIO"
        if not self.fecha_vencimiento:
            return "SIN_CALIBRACION"
        dias = (self.fecha_vencimiento - timezone.localdate()).days
        if dias < 0:
            return "VENCIDO"
        if dias <= 30:
            return "PROXIMO"
        return "VIGENTE"

    @property
    def dias_para_vencer(self):
        if not self.fecha_vencimiento:
            return None
        return (self.fecha_vencimiento - timezone.localdate()).days

    @property
    def disponible_para_medicion(self):
        return self.activo and self.estado == self.Estado.ACTIVO and self.calibracion_vigente

    def __str__(self):
        partes = [self.codigo, self.nombre]
        if self.marca:
            partes.append(self.marca)
        if self.rango:
            partes.append(self.rango)
        if self.serial:
            partes.append(f"S/N {self.serial}")
        return " | ".join(partes)


class CalibracionInstrumento(models.Model):
    instrumento = models.ForeignKey(InstrumentoMetrologico, on_delete=models.CASCADE, related_name="historial_calibraciones")
    fecha_calibracion = models.DateField()
    fecha_vencimiento = models.DateField()
    laboratorio = models.CharField(max_length=150, blank=True)
    numero_certificado = models.CharField(max_length=100, blank=True)
    certificado = models.FileField(upload_to="taller/metrologia/certificados/%Y/%m/", null=True, blank=True)
    observaciones = models.TextField(blank=True)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="calibraciones_metrologia_registradas")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_calibracion", "-id"]

    def __str__(self):
        return f"{self.instrumento.codigo} - {self.fecha_calibracion:%d/%m/%Y}"


class InspeccionEje(models.Model):
    class TipoTrabajo(models.TextChoices):
        REPARACION = "REPARACION", "Reparación"
        FABRICACION = "FABRICACION", "Fabricación"

    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "En medición"
        REVISADA = "REVISADA", "Mediciones revisadas"
        CERRADA = "CERRADA", "Dictamen emitido"

    class Resultado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        CONFORME = "CONFORME", "Conforme"
        NO_CONFORME = "NO_CONFORME", "No conforme"

    class Dictamen(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        CONCESION = "CONCESION", "Aprobado bajo concesión"
        MECANIZADO = "MECANIZADO", "Requiere mecanizado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    paw = models.ForeignKey("paw_app.Paw", on_delete=models.PROTECT, related_name="inspecciones_eje")
    tipo_trabajo = models.CharField(max_length=20, choices=TipoTrabajo.choices, default=TipoTrabajo.REPARACION)
    plantilla = models.ForeignKey(PlantillaEje, on_delete=models.PROTECT, related_name="inspecciones")
    camara = models.ForeignKey(CamaraTaller, on_delete=models.SET_NULL, null=True, blank=True, related_name="inspecciones_eje")
    serial_equipo = models.CharField(max_length=100, blank=True, verbose_name="Serial equipo / cámara")
    serial_eje = models.CharField(max_length=100, blank=True, verbose_name="Serial de la pieza")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    resultado_dimensional = models.CharField(max_length=20, choices=Resultado.choices, default=Resultado.PENDIENTE)
    dictamen = models.CharField(max_length=20, choices=Dictamen.choices, default=Dictamen.PENDIENTE)
    observaciones = models.TextField(blank=True)
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inspecciones_eje_realizadas")
    revisado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="inspecciones_eje_revisadas")
    fecha_revision = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    inspeccion_origen = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="reinspecciones")
    numero_inspeccion = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-creado_en"]

    @property
    def es_reinspeccion(self):
        return bool(self.inspeccion_origen_id)

    @property
    def condicion_reparacion(self):
        if self.tipo_trabajo != self.TipoTrabajo.REPARACION:
            return None
        estados = [m.condicion_reparacion for m in self.mediciones.select_related("punto") if m.valor is not None]
        if not estados:
            return "PENDIENTE"
        if "NO_REUTILIZABLE" in estados:
            return "NO_REUTILIZABLE"
        if "REQUIERE_MECANIZADO" in estados:
            return "REQUIERE_MECANIZADO"
        return "REUTILIZABLE"

    def recalcular_resultado(self):
        mediciones = list(self.mediciones.select_related("punto"))
        obligatorias = [m for m in mediciones if m.punto.obligatorio]
        if not obligatorias or any(m.valor is None for m in obligatorias):
            self.resultado_dimensional = self.Resultado.PENDIENTE
        elif any(not m.conforme for m in obligatorias):
            self.resultado_dimensional = self.Resultado.NO_CONFORME
        else:
            self.resultado_dimensional = self.Resultado.CONFORME
        self.save(update_fields=["resultado_dimensional", "actualizado_en"])

    def __str__(self):
        return f"Inspección eje PAW {self.paw} - {self.plantilla.nombre}"


class MedicionEje(models.Model):
    inspeccion = models.ForeignKey(InspeccionEje, on_delete=models.CASCADE, related_name="mediciones")
    punto = models.ForeignKey(PuntoMedicionEje, on_delete=models.PROTECT, related_name="mediciones")
    valor = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    instrumento = models.ForeignKey(InstrumentoMetrologico, on_delete=models.SET_NULL, null=True, blank=True, related_name="mediciones")
    instrumento_texto = models.CharField(max_length=120, blank=True)
    observacion = models.CharField(max_length=250, blank=True)
    evidencia = models.ImageField(upload_to="taller/metrologia/ejes/%Y/%m/", null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["punto__orden", "id"]
        constraints = [models.UniqueConstraint(fields=["inspeccion", "punto"], name="uniq_medicion_punto_inspeccion_eje")]

    @property
    def condicion_reparacion(self):
        if self.valor is None:
            return "PENDIENTE"
        if self.punto.minimo_reutilizable is not None and self.valor < self.punto.minimo_reutilizable:
            return "NO_REUTILIZABLE"
        if self.conforme:
            return "REUTILIZABLE"
        if self.punto.permite_mecanizado:
            return "REQUIERE_MECANIZADO"
        return "NO_REUTILIZABLE"

    @property
    def conforme(self):
        if self.valor is None:
            return None
        if self.punto.minimo is not None and self.valor < self.punto.minimo:
            return False
        if self.punto.maximo is not None and self.valor > self.punto.maximo:
            return False
        return True

    def __str__(self):
        return f"{self.inspeccion_id} - {self.punto.codigo}: {self.valor}"

class OrdenMecanizadoEje(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        TERMINADO = "TERMINADO", "Terminado / listo para reinspección"
        REINSPECCIONADO = "REINSPECCIONADO", "Reinspeccionado"

    inspeccion_origen = models.OneToOneField(InspeccionEje, on_delete=models.PROTECT, related_name="orden_mecanizado")
    trabajo_requerido = models.TextField()
    medida_objetivo = models.CharField(max_length=250, blank=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="mecanizados_eje_asignados")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    observaciones_taller = models.TextField(blank=True)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mecanizados_eje_creados")
    creado_en = models.DateTimeField(auto_now_add=True)
    terminado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]

    def __str__(self):
        return f"Mecanizado eje PAW {self.inspeccion_origen.paw} - inspección {self.inspeccion_origen_id}"
