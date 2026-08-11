from django.db import models


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

    cliente = models.CharField(
        max_length=200
    )

    marca = models.CharField(
        max_length=150,
        blank=True
    )

    serial = models.CharField(
        max_length=100,
        db_index=True
    )

    modelo = models.CharField(
        max_length=150,
        blank=True
    )

    fecha_ingreso = models.DateField()

    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.RECIBIDA
    )

    observaciones = models.TextField(
        blank=True
    )

    paw = models.ForeignKey(
        "paw_app.Paw",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="camaras_taller"
    )

    creado_en = models.DateTimeField(
        auto_now_add=True
    )

    actualizado_en = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.serial} - {self.cliente}"