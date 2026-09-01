from pathlib import Path
import uuid

from django.contrib.auth.models import User
from django.db import models


def ruta_adjunto_chat(instance, filename):
    """
    Genera una ruta única dentro de Cloudflare R2.
    Ejemplo:
    chat/12/uuid_factura.pdf
    """
    extension = Path(filename).suffix.lower()
    nombre_unico = f"{uuid.uuid4().hex}{extension}"

    conversacion_id = (
        instance.mensaje.conversacion_id
        if instance.mensaje_id
        else "sin_conversacion"
    )

    return f"chat/{conversacion_id}/{nombre_unico}"


class Conversacion(models.Model):
    TIPO_CHOICES = [
        ("PRIVADA", "Privada"),
        ("GRUPO", "Grupo"),
        ("PAW", "PAW"),
        ("OT", "OT"),
    ]

    tipo = models.CharField(
        max_length=20,
        choices=TIPO_CHOICES,
        default="PRIVADA",
    )

    nombre = models.CharField(
        max_length=200,
        blank=True,
    )

    participantes = models.ManyToManyField(
        User,
        related_name="conversaciones_chat",
    )

    # Relación directa y única con un PAW.
    # Se deja nullable para no afectar chats PRIVADA / GRUPO existentes.
    paw = models.OneToOneField(
        "paw_app.Paw",
        related_name="conversacion_chat",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    activa = models.BooleanField(
        default=True,
    )

    def __str__(self):
        if self.nombre:
            return self.nombre

        return f"Conversación {self.pk}"


class Mensaje(models.Model):
    conversacion = models.ForeignKey(
        Conversacion,
        related_name="mensajes",
        on_delete=models.CASCADE,
    )

    autor = models.ForeignKey(
        User,
        related_name="mensajes_chat",
        on_delete=models.PROTECT,
    )

    texto = models.TextField(
        blank=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    editado = models.BooleanField(
        default=False,
    )

    eliminado = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return f"{self.autor.username}: {self.texto[:50]}"


class AdjuntoMensaje(models.Model):
    mensaje = models.ForeignKey(
        Mensaje,
        related_name="adjuntos",
        on_delete=models.CASCADE,
    )

    archivo = models.FileField(
        upload_to=ruta_adjunto_chat,
    )

    nombre_original = models.CharField(
        max_length=255,
    )

    tipo_mime = models.CharField(
        max_length=150,
        blank=True,
    )

    tamano = models.PositiveBigIntegerField(
        default=0,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    def __str__(self):
        return self.nombre_original

    @property
    def extension(self):
        return Path(self.nombre_original).suffix.lower()

    @property
    def es_imagen(self):
        return self.tipo_mime.startswith("image/")


class MensajeLeido(models.Model):
    mensaje = models.ForeignKey(
        Mensaje,
        related_name="lecturas",
        on_delete=models.CASCADE,
    )

    usuario = models.ForeignKey(
        User,
        related_name="mensajes_leidos_chat",
        on_delete=models.CASCADE,
    )

    leido_en = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["mensaje", "usuario"],
                name="unique_mensaje_leido_usuario",
            )
        ]
