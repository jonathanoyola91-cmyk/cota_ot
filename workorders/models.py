from django.conf import settings
from django.db import models
from django.contrib.auth.models import Group


class WorkOrder(models.Model):
    class Priority(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"
        CRITICA = "CRITICA", "Crítica"

    class Status(models.TextChoices):
        NUEVA = "NUEVA", "Nueva"
        ASIGNADA = "ASIGNADA", "Asignada"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        EN_ESPERA = "EN_ESPERA", "En espera"
        TERMINADA = "TERMINADA", "Terminada"
        CERRADA = "CERRADA", "Cerrada"

    class Visibility(models.TextChoices):
        PUBLICA = "PUBLICA", "Pública (todos la ven)"
        RESTRINGIDA = "RESTRINGIDA", "Restringida (solo asignados)"

    numero = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)

    cliente = models.CharField(max_length=120, blank=True)
    equipo = models.CharField(max_length=120, blank=True)
    serial = models.CharField(max_length=80, blank=True)
    ubicacion = models.CharField(max_length=120, blank=True)

    prioridad = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIA
    )

    estado = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NUEVA
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ot_creadas"
    )

    asignado_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ot_asignadas"
    )

    asignado_grupo = models.ForeignKey(
        Group,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ot_asignadas_grupo"
    )

    paw = models.ForeignKey(
        "paw_app.Paw",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ots"
    )

    visibilidad = models.CharField(
        max_length=15,
        choices=Visibility.choices,
        default=Visibility.RESTRINGIDA
    )

    iniciado_en = models.DateTimeField(null=True, blank=True)
    terminado_en = models.DateTimeField(null=True, blank=True)

    class EtapaTaller(models.TextChoices):
        DESARME = "DESARME", "Desarme"
        ALISTAMIENTO = "ALISTAMIENTO", "Alistamiento"
        ENSAMBLANDO = "ENSAMBLANDO", "Ensamblando"
        PRUEBA = "PRUEBA", "Prueba"

    etapa_taller = models.CharField(
        max_length=20,
        choices=EtapaTaller.choices,
        null=True,
        blank=True
    )

    comentario_taller = models.TextField(blank=True)


    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"OT #{self.numero} - {self.titulo}"


class WorkOrderTask(models.Model):
    class Status(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        HECHA = "HECHA", "Hecha"

    workorder = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="tareas")
    titulo = models.CharField(max_length=160)
    estado = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDIENTE)

    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="tareas_asignadas"
    )

    comentario = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OT #{self.workorder.numero} - {self.titulo}"
