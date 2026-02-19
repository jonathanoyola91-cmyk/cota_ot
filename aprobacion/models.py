# aprobacion/models.py
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class PurchaseApproval(models.Model):
    """
    Encabezado de aprobación de compras por PAW (PurchaseRequest).
    Flujo independiente del módulo finanzas.FinanceApproval.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PARCIAL = "PARCIAL", "Parcial"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="purchase_approval",
    )

    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_approvals_enviados",
    )
    enviado_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        pr = self.purchase_request
        return f"Aprobación Compras PAW {pr.paw_numero or pr.id}"

    def recalcular_estado(self):
        qs = self.lineas.all()
        if not qs.exists():
            self.estado = self.Estado.PENDIENTE
            return self.estado

        estados = list(qs.values_list("estado_aprobacion", flat=True))

        if all(e == PurchaseApprovalLine.EstadoAprobacion.PENDIENTE for e in estados):
            self.estado = self.Estado.PENDIENTE
        elif all(e == PurchaseApprovalLine.EstadoAprobacion.APROBADO for e in estados):
            self.estado = self.Estado.APROBADO
        elif all(e == PurchaseApprovalLine.EstadoAprobacion.RECHAZADO for e in estados):
            self.estado = self.Estado.RECHAZADO
        else:
            self.estado = self.Estado.PARCIAL

        return self.estado


class PurchaseApprovalLine(models.Model):
    """
    Línea de aprobación por ítem de compra (PurchaseLine).
    Guarda snapshot de datos del PAW.
    """

    class EstadoAprobacion(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    approval = models.ForeignKey(
        PurchaseApproval,
        on_delete=models.CASCADE,
        related_name="lineas",
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="purchase_approval_line",
    )

    # -------- SNAPSHOT desde Compras --------
    codigo = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=200, blank=True)

    cantidad_requerida = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    cantidad_a_comprar = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))

    tipo_pago = models.CharField(max_length=20, blank=True)
    proveedor = models.CharField(max_length=150, blank=True)

    valor_unidad = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    valor_total = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal("0"))

    observaciones = models.TextField(blank=True)

    # -------- Editable por Finanzas --------
    estado_aprobacion = models.CharField(
        max_length=20,
        choices=EstadoAprobacion.choices,
        default=EstadoAprobacion.PENDIENTE,
    )
    observacion_finanzas = models.TextField(blank=True)

    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_approval_decisions",
    )
    decidido_en = models.DateTimeField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["estado_aprobacion"]),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.descripcion} | {self.estado_aprobacion}"

    def snapshot_from_purchase_line(self):
        pl = self.purchase_line

        self.codigo = pl.codigo or ""
        self.descripcion = pl.descripcion or ""

        self.cantidad_requerida = pl.cantidad_requerida or Decimal("0")
        self.cantidad_a_comprar = pl.cantidad_a_comprar or Decimal("0")

        self.tipo_pago = pl.tipo_pago or ""
        self.proveedor = (pl.proveedor.nombre if pl.proveedor else "")

        self.valor_unidad = pl.precio_unitario or Decimal("0")
        self.valor_total = (self.cantidad_a_comprar or Decimal("0")) * (self.valor_unidad or Decimal("0"))

        obs = []
        if pl.observaciones_bom:
            obs.append(f"BOM: {pl.observaciones_bom}")
        if pl.observaciones_compras:
            obs.append(f"COMPRAS: {pl.observaciones_compras}")
        self.observaciones = "\n".join(obs).strip()

    def touch_decision_audit(self, user):
        self.decidido_por = user
        self.decidido_en = timezone.now()
