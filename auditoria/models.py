from django.conf import settings
from django.db import models


class MovimientoSistema(models.Model):
    paw_numero = models.CharField(max_length=50, blank=True, db_index=True)
    modulo = models.CharField(max_length=50, db_index=True)
    accion = models.CharField(max_length=150, db_index=True)
    descripcion = models.TextField(blank=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="movimientos_sistema",
    )

    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    objeto_tipo = models.CharField(max_length=80, blank=True)
    objeto_id = models.PositiveBigIntegerField(null=True, blank=True)

    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["paw_numero", "-fecha"]),
            models.Index(fields=["modulo", "-fecha"]),
        ]

    def __str__(self):
        usuario = getattr(self.usuario, "username", None) or "Sistema"
        paw = self.paw_numero or "-"
        return f"PAW {paw} | {self.modulo} | {self.accion} | {usuario}"
