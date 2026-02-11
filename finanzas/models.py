from django.conf import settings
from django.db import models


class FinanceApproval(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="finanzas"
    )

    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    comentario = models.TextField(blank=True)

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finanzas_enviados",
        null=True, blank=True
    )
    enviado_en = models.DateTimeField(null=True, blank=True)

    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="finanzas_aprobados",
        null=True, blank=True
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Finanzas - {self.purchase_request}"
