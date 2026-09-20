# inventario/models.py
from django.conf import settings
from django.db import models


# ======================================================
# RECEPCIÓN INVENTARIO
# ======================================================

class InventoryReception(models.Model):
    """
    Encabezado: una recepción por PurchaseRequest.
    """
    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="recepcion_inventario"
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recepciones_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Controla que las alertas de recepción se envíen una sola vez por umbral.
    notificacion_80_en = models.DateTimeField(null=True, blank=True)
    notificacion_100_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        pr = getattr(self, "purchase_request", None)
        paw = getattr(pr, "paw_numero", None) if pr else None
        return f"Recepción Inventario - PAW #{paw or self.id}"


class InventoryReceptionLine(models.Model):

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PARCIAL = "PARCIAL", "Parcial"
        LISTO = "LISTO", "Listo"

    recepcion = models.ForeignKey(
        InventoryReception,
        on_delete=models.CASCADE,
        related_name="lineas"
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="recepcion_linea"
    )

    # Snapshot del ítem comprado
    codigo = models.CharField(max_length=80, blank=True, default="")
    descripcion = models.CharField(max_length=200, blank=True, default="")
    unidad = models.CharField(max_length=20, blank=True, default="")

    cantidad_esperada = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    cantidad_recibida = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0
    )

    fecha_llegada = models.DateField(null=True, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE
    )

    observacion_inventario = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        return f"Recepción {self.codigo} - {self.estado}"
        
# ======================================================
# ENTREGA TALLER
# ======================================================

class WorkshopDelivery(models.Model):
    """
    Encabezado de entrega de material por PurchaseRequest (PAW).
    Se conserva el nombre histórico del modelo para no romper relaciones existentes.
    """

    class Destino(models.TextChoices):
        TALLER = "TALLER", "Taller"
        CAMPO = "CAMPO", "Campo"
        CLIENTE = "CLIENTE", "Cliente / despacho"
        INVENTARIO = "INVENTARIO", "Inventario / bodega"
    purchase_request = models.OneToOneField(
        "compras_oil.PurchaseRequest",
        on_delete=models.PROTECT,
        related_name="entrega_taller"
    )

    destino = models.CharField(
        max_length=20,
        choices=Destino.choices,
        default=Destino.TALLER,
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entregas_taller_creadas"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # Comentarios que se imprimirán en el PDF encima de firmas
    comentarios = models.TextField(blank=True)

    def __str__(self):
        pr = getattr(self, "purchase_request", None)
        paw = getattr(pr, "paw_numero", None) if pr else None
        nombre = getattr(pr, "paw_nombre", "") if pr else ""
        nombre = (nombre or "")[:60]
        return f"ENTREGA {self.get_destino_display().upper()} - PAW #{paw or self.id} - {nombre}"


class WorkshopDeliveryLine(models.Model):
    """
    Línea: snapshot de PurchaseLine para ENTREGA TALLER.
    'cantidad_entregada' NO es obligatoria (se llena manual en físico).
    """
    delivery = models.ForeignKey(
        WorkshopDelivery,
        on_delete=models.CASCADE,
        related_name="lineas"
    )

    purchase_line = models.OneToOneField(
        "compras_oil.PurchaseLine",
        on_delete=models.PROTECT,
        related_name="entrega_taller_linea"
    )

    # Snapshot de la línea de compra
    codigo = models.CharField(max_length=80, blank=True)
    descripcion = models.CharField(max_length=200, blank=True)
    unidad = models.CharField(max_length=20, blank=True)
    cantidad_requerida = models.DecimalField(max_digits=12, decimal_places=3, default=0)

    # Diligenciado manualmente (en papel) → debe poder ir vacío
    cantidad_entregada = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"
# ======================================================
# SALIDAS DE INVENTARIO SIN PAW
# ======================================================

class InventoryExit(models.Model):
    """Salida física de componentes que no está asociada a un PAW."""

    destino = models.CharField(max_length=160)
    solicitado_por = models.CharField(max_length=160, blank=True)
    recibido_por = models.CharField(max_length=160, blank=True)
    motivo = models.TextField(blank=True)
    comentarios = models.TextField(blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="salidas_inventario_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def codigo(self):
        return f"SAL-{self.pk:06d}" if self.pk else "SAL-PENDIENTE"

    def __str__(self):
        return f"{self.codigo} - {self.destino}"


class InventoryExitLine(models.Model):
    salida = models.ForeignKey(
        InventoryExit,
        on_delete=models.CASCADE,
        related_name="lineas",
    )
    # Referencia informativa al catálogo. No se usa FK porque existen dos catálogos.
    catalogo = models.CharField(max_length=20, blank=True, default="")
    catalogo_item_id = models.PositiveIntegerField(null=True, blank=True)
    codigo = models.CharField(max_length=80, blank=True, default="")
    descripcion = models.CharField(max_length=300)
    unidad = models.CharField(max_length=30, blank=True, default="")
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    numero_serial = models.CharField(max_length=120, blank=True, default="")

    def __str__(self):
        return f"{self.codigo or '-'} - {self.descripcion[:80]}"


# ======================================================
# REMISIONES DE SALIDA
# ======================================================

class RemissionSequence(models.Model):
    """Contador transaccional independiente por empresa emisora."""

    empresa = models.CharField(max_length=12, unique=True)
    ultimo = models.PositiveIntegerField(default=0)

    def __str__(self):
        prefijo = "REM" if self.empresa == "IMPETUS" else "OGS-RM"
        return f"Última remisión {self.empresa}: {prefijo}-{self.ultimo:03d}"


class DispatchRemission(models.Model):
    class Empresa(models.TextChoices):
        IMPETUS = "IMPETUS", "IMPETUS HPS"
        OIL_GAS = "OIL_GAS", "OIL & GAS SUPPORT"

    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        ANULADA = "ANULADA", "Anulada"

    consecutivo = models.PositiveIntegerField()
    empresa = models.CharField(max_length=12, choices=Empresa.choices, default=Empresa.IMPETUS)
    cliente_registrado = models.ForeignKey(
        "quotes.Cliente", on_delete=models.PROTECT, null=True, blank=True,
        related_name="remisiones_salida"
    )

    cliente = models.CharField(max_length=200)
    nit = models.CharField(max_length=60, blank=True)
    contacto_cliente = models.CharField(max_length=160, blank=True)
    telefono_cliente = models.CharField(max_length=80, blank=True)
    direccion_cliente = models.CharField(max_length=260, blank=True)

    fecha_envio = models.DateField()
    contacto_envio = models.CharField(max_length=160, blank=True)
    telefono_envio = models.CharField(max_length=80, blank=True)
    direccion_envio = models.CharField(max_length=260, blank=True)

    tipo_vehiculo = models.CharField(max_length=100, blank=True)
    placa = models.CharField(max_length=40, blank=True)
    nombre_conductor = models.CharField(max_length=160, blank=True)
    celular_conductor = models.CharField(max_length=80, blank=True)
    observaciones = models.TextField(blank=True)

    # Una remisión emitida no se edita ni se elimina: si hay un error se anula
    # conservando la trazabilidad documental.
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVA)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="remisiones_salida_anuladas",
    )
    anulada_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="remisiones_salida_creadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def numero(self):
        if self.empresa == self.Empresa.IMPETUS:
            return f"REM-{self.consecutivo:03d}"
        return f"OGS-RM-{self.consecutivo}"

    @property
    def empresa_nombre(self):
        return "IMPETUS HPS" if self.empresa == self.Empresa.IMPETUS else "OIL & GAS SUPPORT"

    @property
    def empresa_nit(self):
        return "901.862.818" if self.empresa == self.Empresa.IMPETUS else "901.288.858"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "consecutivo"],
                name="uniq_remision_empresa_consecutivo",
            )
        ]

    def __str__(self):
        return f"{self.numero} - {self.cliente}"


class DispatchRemissionLine(models.Model):
    remision = models.ForeignKey(
        DispatchRemission,
        on_delete=models.CASCADE,
        related_name="lineas",
    )
    catalogo = models.CharField(max_length=20, blank=True, default="")
    catalogo_item_id = models.PositiveIntegerField(null=True, blank=True)
    descripcion = models.CharField(max_length=300)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    unidad = models.CharField(max_length=30, blank=True, default="UND")
    parte_numero = models.CharField(max_length=100, blank=True, default="")
    numero_serial = models.CharField(max_length=120, blank=True, default="")

    def __str__(self):
        return f"{self.remision.numero} - {self.descripcion[:80]}"

# ======================================================
# EXISTENCIAS / KARDEX (ETAPA 1)
# ======================================================
class InventoryStock(models.Model):
    class Empresa(models.TextChoices):
        IMPETUS = "IMPETUS", "IMPETUS HPS"
        OIL_GAS = "OIL_GAS", "OIL & GAS SUPPORT"

    empresa = models.CharField(max_length=12, choices=Empresa.choices)
    catalogo = models.CharField(max_length=20)
    catalogo_item_id = models.PositiveIntegerField()
    codigo = models.CharField(max_length=80, db_index=True)
    descripcion = models.CharField(max_length=300, blank=True, default="")
    unidad = models.CharField(max_length=30, blank=True, default="UND")
    cantidad_fisica = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    cantidad_reservada = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    costo_promedio = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["empresa", "catalogo", "catalogo_item_id"], name="uniq_stock_empresa_catalogo_item")]
        ordering = ["empresa", "codigo"]

    @property
    def cantidad_disponible(self):
        return self.cantidad_fisica - self.cantidad_reservada

    @property
    def valor_inventario(self):
        return self.cantidad_fisica * self.costo_promedio

    def __str__(self):
        return f"{self.get_empresa_display()} - {self.codigo}"


class InventoryMovement(models.Model):
    class Tipo(models.TextChoices):
        INVENTARIO_INICIAL = "INICIAL", "Inventario inicial"
        AJUSTE_ENTRADA = "AJUSTE_ENTRADA", "Ajuste positivo"
        AJUSTE_SALIDA = "AJUSTE_SALIDA", "Ajuste negativo"
        TRANSFERENCIA_ENTRADA = "TRF_ENTRADA", "Transferencia entrada"
        TRANSFERENCIA_SALIDA = "TRF_SALIDA", "Transferencia salida"
        RECEPCION = "RECEPCION", "Recepción de compra"
        ENTREGA = "ENTREGA", "Entrega / salida"

    stock = models.ForeignKey(InventoryStock, on_delete=models.PROTECT, related_name="movimientos")
    tipo = models.CharField(max_length=24, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)  # + entrada / - salida
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    saldo_anterior = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    saldo_nuevo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    costo_promedio_anterior = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    costo_promedio_nuevo = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    referencia = models.CharField(max_length=80, blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="movimientos_stock_creados")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en", "-id"]


class InventoryReservation(models.Model):
    class Estado(models.TextChoices):
        ACTIVA = "ACTIVA", "Activa"
        CONSUMIDA = "CONSUMIDA", "Consumida/entregada"
        LIBERADA = "LIBERADA", "Liberada"

    stock = models.ForeignKey(InventoryStock, on_delete=models.PROTECT, related_name="reservas")
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    # Cantidad ya consumida físicamente en entregas a Taller/Campo/Despacho.
    # Se mantiene separada de ``cantidad`` para conservar el histórico original
    # de cuánto fue reservado para el PAW.
    cantidad_consumida = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    purchase_request = models.ForeignKey("compras_oil.PurchaseRequest", on_delete=models.PROTECT, null=True, blank=True, related_name="reservas_inventario")
    purchase_line = models.ForeignKey("compras_oil.PurchaseLine", on_delete=models.PROTECT, null=True, blank=True, related_name="reservas_inventario")
    es_transicion = models.BooleanField(default=False, help_text="Reserva creada para PAW ya activo al momento de iniciar el control de existencias.")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.ACTIVA)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="reservas_inventario_creadas")
    creado_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(blank=True, default="")


class InventoryTransfer(models.Model):
    class Estado(models.TextChoices):
        COMPLETADA = "COMPLETADA", "Completada"
        ANULADA = "ANULADA", "Anulada"

    empresa_origen = models.CharField(max_length=12, choices=InventoryStock.Empresa.choices)
    empresa_destino = models.CharField(max_length=12, choices=InventoryStock.Empresa.choices)
    stock_origen = models.ForeignKey(InventoryStock, on_delete=models.PROTECT, related_name="transferencias_salida")
    stock_destino = models.ForeignKey(InventoryStock, on_delete=models.PROTECT, related_name="transferencias_entrada")
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    motivo = models.TextField(blank=True, default="")
    documento = models.CharField(max_length=100, blank=True, default="")
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.COMPLETADA)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="transferencias_inventario_creadas")
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def numero(self):
        return f"TRF-{self.pk:06d}" if self.pk else "TRF-PENDIENTE"
