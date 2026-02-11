# finanzas/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone


# =========================
# ENCABEZADO FINANZAS (PAW)
# =========================

class FinanceApproval(models.Model):
    """
    Encabezado financiero por PurchaseRequest.
    Se crea/actualiza desde Compras (acción Enviar a Finanzas).
    NO altera la lógica de compras.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",   # <-- ajusta app_label si aplica
        on_delete=models.CASCADE,
        related_name="finance_approval",
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="finance_approvals_enviados",
    )
    enviado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        pr = self.purchase_request
        return f"Finanzas PAW {pr.paw_numero or pr.id}"


# =========================
# LINEAS FINANZAS (CONTADO)
# =========================

class FinanceApprovalLine(models.Model):
    """
    Control financiero por línea de compra (PurchaseLine).

    SOLO para líneas CONTADO:
    - Admin decide qué se paga y qué espera
    - Finanzas ejecuta solo lo aprobado
    """

    class Decision(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado para pagar"
        PROGRAMADO = "PROGRAMADO", "Programado"
        EN_ESPERA = "EN_ESPERA", "En espera"
        RECHAZADO = "RECHAZADO", "Rechazado"

    approval = models.ForeignKey(
        FinanceApproval,
        on_delete=models.CASCADE,
        related_name="lineas",
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",   # <-- ajusta app_label si aplica
        on_delete=models.CASCADE,
        related_name="finance_line",
    )

    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDIENTE,
    )

    # Si decision = PROGRAMADO
    scheduled_date = models.DateField(null=True, blank=True)

    # Notas del admin financiero
    nota_admin = models.TextField(blank=True)

    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="finance_line_decisions",
    )
    decidido_en = models.DateTimeField(null=True, blank=True)

    # Ejecución de pago
    pagado = models.BooleanField(default=False)
    pagado_en = models.DateTimeField(null=True, blank=True)
    pagado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="finance_line_payments",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["decision"]),
            models.Index(fields=["pagado"]),
            models.Index(fields=["scheduled_date"]),
        ]

    # ------------------------
    # PRESENTACIÓN (ADMIN)
    # ------------------------

    def __str__(self):
        """
        Texto claro para el admin (no técnico).
        """
        pl = self.purchase_line
        return f"{pl.codigo} - {pl.descripcion} | {self.decision}"

    # ------------------------
    # HELPERS FINANZAS
    # ------------------------

    def mark_decision(self, decision: str, user, scheduled_date=None, nota_admin=None):
        """
        Admin define la decisión financiera de la línea.
        """
        self.decision = decision
        self.scheduled_date = scheduled_date
        if nota_admin is not None:
            self.nota_admin = nota_admin
        self.decidido_por = user
        self.decidido_en = timezone.now()
        self.save(
            update_fields=[
                "decision",
                "scheduled_date",
                "nota_admin",
                "decidido_por",
                "decidido_en",
                "actualizado_en",
            ]
        )

    def can_be_paid_today(self, today=None) -> bool:
        """
        Regla de pago:
        - APROBADO → se puede pagar
        - PROGRAMADO → se paga si scheduled_date <= hoy
        """
        if self.pagado:
            return False

        today = today or timezone.localdate()

        if self.decision == self.Decision.APROBADO:
            return True

        if self.decision == self.Decision.PROGRAMADO and self.scheduled_date:
            return self.scheduled_date <= today

        return False

    def mark_paid(self, user):
        """
        Marca la línea como pagada (validando reglas).
        """
        if not self.can_be_paid_today():
            raise ValueError(
                "Esta línea no está autorizada para pago hoy o ya fue pagada."
            )

        self.pagado = True
        self.pagado_en = timezone.now()
        self.pagado_por = user
        self.save(
            update_fields=[
                "pagado",
                "pagado_en",
                "pagado_por",
                "actualizado_en",
            ]
        )
