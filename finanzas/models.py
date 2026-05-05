# finanzas/models.py
from decimal import Decimal

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
        "compras_oil.PurchaseRequest",
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

    class TipoOperacion(models.TextChoices):
        COMPRA = "COMPRA", "Compra - retención 2.5%"
        SERVICIO = "SERVICIO", "Servicio - retención 4%"
        NA = "NA", "N/A - sin retención"

    approval = models.ForeignKey(
        FinanceApproval,
        on_delete=models.CASCADE,
        related_name="lineas",
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",
        on_delete=models.CASCADE,
        related_name="finance_line",
    )

    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
        default=Decision.PENDIENTE,
    )

    tipo_operacion = models.CharField(
        max_length=20,
        choices=TipoOperacion.choices,
        default=TipoOperacion.COMPRA,
    )

    scheduled_date = models.DateField(null=True, blank=True)
    nota_admin = models.TextField(blank=True)

    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="finance_line_decisions",
    )
    decidido_en = models.DateTimeField(null=True, blank=True)

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

    def __str__(self):
        pl = self.purchase_line
        return f"{pl.codigo} - {pl.descripcion} | {self.decision}"

    def mark_decision(self, decision: str, user, scheduled_date=None, nota_admin=None):
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
        if self.pagado:
            return False

        today = today or timezone.localdate()

        if self.decision == self.Decision.APROBADO:
            return True

        if self.decision == self.Decision.PROGRAMADO and self.scheduled_date:
            return self.scheduled_date <= today

        return False

    def mark_paid(self, user):
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


# =======================================
# CUENTAS POR PAGAR A PROVEEDORES (CRÉDITO)
# =======================================

class SupplierInvoice(models.Model):
    """
    Factura emitida por proveedor para una solicitud de compra.

    Se usa para controlar cuentas por pagar:
    - El valor comprado se calcula desde líneas de compra del proveedor.
    - El IVA se calcula al 19%.
    - Si la compra es CONTADO, el saldo queda en 0.
    - Si la compra es CRÉDITO, el saldo se calcula contra los abonos registrados.
    """

    supplier = models.ForeignKey(
        "compras_oil.Supplier",
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
        verbose_name="Proveedor",
    )
    purchase_request = models.ForeignKey(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="supplier_invoices",
        verbose_name="Solicitud de compra",
    )

    numero_factura_proveedor = models.CharField(
        "Número factura proveedor",
        max_length=80,
        blank=True,
    )
    fecha_factura_proveedor = models.DateField(
        "Fecha factura proveedor",
        null=True,
        blank=True,
    )
    observacion = models.TextField("Observación", blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_invoices_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-actualizado_en"]
        unique_together = [("supplier", "purchase_request")]
        indexes = [
            models.Index(fields=["supplier"]),
            models.Index(fields=["purchase_request"]),
            models.Index(fields=["numero_factura_proveedor"]),
        ]
        verbose_name = "Cuenta por pagar proveedor"
        verbose_name_plural = "Cuentas por pagar proveedores"

    def __str__(self):
        factura = self.numero_factura_proveedor or "Sin factura"
        return f"{self.supplier} - {factura}"

    @property
    def paw_numero(self):
        return self.purchase_request.paw_numero or f"Compra #{self.purchase_request_id}"

    @property
    def tipo_pago(self):
        qs = self.purchase_request.lineas.filter(
            proveedor=self.supplier,
            cantidad_requerida__gt=0,
        )
        if qs.filter(tipo_pago="CONTADO").exists():
            return "CONTADO"
        return "CREDITO"

    @property
    def base_compra(self):
        total = Decimal("0")
        lineas = self.purchase_request.lineas.filter(
            proveedor=self.supplier,
            cantidad_requerida__gt=0,
        )
        for linea in lineas:
            cantidad = Decimal(linea.cantidad_a_comprar or 0)
            precio = Decimal(linea.precio_unitario or 0)
            total += cantidad * precio
        return total

    @property
    def iva(self):
        return self.base_compra * Decimal("0.19")

    @property
    def total_con_iva(self):
        return self.base_compra + self.iva

    @property
    def total_abonado_real(self):
        total = Decimal("0")
        for abono in self.abonos.all():
            total += Decimal(abono.valor or 0)
        return total

    @property
    def total_abonado(self):
        if self.tipo_pago == "CONTADO":
            return self.total_con_iva
        return self.total_abonado_real

    @property
    def saldo(self):
        if self.tipo_pago == "CONTADO":
            return Decimal("0")
        saldo = self.total_con_iva - self.total_abonado_real
        return saldo if saldo > 0 else Decimal("0")


class SupplierPayment(models.Model):
    """
    Abonos manuales registrados por Finanzas sobre una factura de proveedor.
    Permite trazabilidad: normalmente habrá 1, 2 o más abonos por factura.
    """

    supplier_invoice = models.ForeignKey(
        SupplierInvoice,
        on_delete=models.CASCADE,
        related_name="abonos",
        verbose_name="Factura proveedor",
    )
    fecha = models.DateField("Fecha abono", default=timezone.localdate)
    valor = models.DecimalField("Valor abonado", max_digits=14, decimal_places=2)
    referencia = models.CharField("Referencia / comprobante", max_length=120, blank=True)
    observacion = models.TextField("Observación", blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_payments_creados",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-creado_en"]
        indexes = [
            models.Index(fields=["fecha"]),
            models.Index(fields=["supplier_invoice"]),
        ]
        verbose_name = "Abono proveedor"
        verbose_name_plural = "Abonos proveedores"

    def __str__(self):
        return f"Abono {self.valor} - {self.supplier_invoice}"
