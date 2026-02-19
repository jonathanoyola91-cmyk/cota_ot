# compras_oil/models.py
from decimal import Decimal

from django.conf import settings
from django.db import models


# ---------------- PROVEEDORES ----------------

class Supplier(models.Model):
    class TipoCuenta(models.TextChoices):
        AHORROS = "AHORROS", "Ahorros"
        CORRIENTE = "CORRIENTE", "Corriente"

    nombre = models.CharField(max_length=150, unique=True)
    contacto = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=60, blank=True)
    email = models.EmailField(blank=True)

    nit = models.CharField(max_length=50, blank=True)
    banco = models.CharField(max_length=120, blank=True)
    cuenta_bancaria = models.CharField(max_length=60, blank=True)
    tipo_cuenta = models.CharField(max_length=20, choices=TipoCuenta.choices, blank=True)

    def __str__(self):
        return self.nombre


# ---------------- SOLICITUD DE COMPRA ----------------

class PurchaseRequest(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EN_REVISION = "EN_REVISION", "En revisión"
        CERRADA = "CERRADA", "Cerrada"

    class TipoPago(models.TextChoices):
        CREDITO = "CREDITO", "Crédito"
        CONTADO = "CONTADO", "Contado"

    bom = models.OneToOneField(
        "bom.Bom",
        on_delete=models.PROTECT,
        related_name="compra"
    )

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR
    )

    # Tipo de pago a nivel encabezado (opcional / referencia)
    tipo_pago = models.CharField(
        max_length=20,
        choices=TipoPago.choices,
        blank=True
    )

    # Encabezado PAW (IDENTIFICADOR)
    paw_numero = models.CharField(max_length=50, blank=True)
    paw_nombre = models.CharField(max_length=120, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes_compra",
        null=True,
        blank=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        """
        IMPORTANTE:
        Esto es lo que se ve en el selector/autocomplete del admin.
        Debe mostrar PAW (no OT) porque PAW es el identificador del proceso.
        """
        paw = self.paw_numero or "-"
        nombre = (self.paw_nombre or "").strip()
        nombre = nombre[:80]
        return f"PAW #{paw} - {nombre}"


# ---------------- LINEAS DE COMPRA ----------------

class PurchaseLine(models.Model):
    request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.CASCADE,
        related_name="lineas"
    )

    # ✅ NUEVO: vínculo directo al ítem del BOM para “arrastrar” plano/código/etc sin riesgo
    bom_item = models.ForeignKey(
        "bom.BomItem",
        on_delete=models.PROTECT,
        related_name="purchase_lines",
        null=True,
        blank=True
    )

    # Datos visibles en compras
    plano = models.CharField(max_length=120, blank=True)
    codigo = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=200)
    unidad = models.CharField(max_length=20, blank=True)

    # Viene del BOM (solo lectura para compras)
    observaciones_bom = models.TextField(blank=True)

    cantidad_requerida = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # Calculado automáticamente
    cantidad_a_comprar = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    proveedor = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Notas de compras
    observaciones_compras = models.TextField(blank=True)

    # tipo de pago por ítem
    tipo_pago = models.CharField(
        max_length=20,
        choices=PurchaseRequest.TipoPago.choices,
        default=PurchaseRequest.TipoPago.CREDITO,
    )

    def save(self, *args, **kwargs):
        """
        - Hereda tipo_pago desde encabezado al crear.
        - ✅ Arrastra plano/código/desc/unidad/observaciones y cantidad_requerida desde BomItem si existe.
        - Calcula cantidad_a_comprar = max(cantidad_requerida - cantidad_disponible, 0)
        """

        # Si la línea es nueva y el encabezado tiene tipo_pago, heredarlo
        if not self.pk and self.request and self.request.tipo_pago:
            self.tipo_pago = self.request.tipo_pago

        # ✅ Arrastrar datos desde BOM ITEM (si está enlazado)
        if self.bom_item_id:
            bi = self.bom_item

            # Si están vacíos, se rellenan desde BOM Item
            if not self.plano:
                self.plano = (bi.plano or "")[:120]
            if not self.codigo:
                self.codigo = (bi.codigo or "")[:80]
            if not self.descripcion:
                self.descripcion = bi.descripcion  # este campo no permite blank, así que es importante
            if not self.unidad:
                self.unidad = (bi.unidad or "")[:20]

            # Observaciones del BOM
            if not self.observaciones_bom:
                self.observaciones_bom = bi.observaciones or ""

            # Cantidad requerida en compras viene de BOM Item: cantidad_solicitada
            # Solo la forzamos si está en 0 (para no sobreescribir ediciones manuales si ustedes las hacen)
            if (self.cantidad_requerida is None) or (Decimal(self.cantidad_requerida) <= Decimal("0")):
                self.cantidad_requerida = bi.cantidad_solicitada or Decimal("0")

        req = self.cantidad_requerida or Decimal("0")
        disp = self.cantidad_disponible or Decimal("0")
        x = req - disp
        self.cantidad_a_comprar = x if x > 0 else Decimal("0")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"
