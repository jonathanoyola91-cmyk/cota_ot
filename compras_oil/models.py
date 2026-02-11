from django.conf import settings
from django.db import models


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

    # ✅ NUEVO: modo de pago (Compras selecciona)
    tipo_pago = models.CharField(max_length=20, choices=TipoPago.choices, blank=True)

    # ✅ Encabezado PAW (se llena al enviar desde BOM)
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
        try:
            return f"Solicitud Compra - OT #{self.bom.workorder.numero}"
        except Exception:
            return "Solicitud Compra"


class PurchaseLine(models.Model):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lineas")

    plano = models.CharField(max_length=120, blank=True)
    codigo = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=200)
    unidad = models.CharField(max_length=20, blank=True)

    # ✅ viene del BOM (no lo toca Compras)
    observaciones_bom = models.TextField(blank=True)

    cantidad_requerida = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # ✅ calculado automáticamente
    cantidad_a_comprar = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    proveedor = models.ForeignKey(Supplier, on_delete=models.PROTECT, null=True, blank=True)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    # ✅ notas de Compras (editable por Compras)
    observaciones_compras = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        req = self.cantidad_requerida or 0
        disp = self.cantidad_disponible or 0
        x = req - disp
        self.cantidad_a_comprar = x if x > 0 else 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"
