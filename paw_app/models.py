from django.conf import settings
from django.db import models


class Criticidad(models.TextChoices):
    ALTA = "ALTA", "Alta"
    MEDIA = "MEDIA", "Media"
    BAJA = "BAJA", "Baja"


class EstadoGestion(models.TextChoices):
    ASIGNADO = "ASIGNADO", "Asignado"
    EN_PROCESO = "EN_PROCESO", "En proceso"
    PENDIENTE = "PENDIENTE", "Pendiente"


class EstadoOperativo(models.TextChoices):
    PAW_CREADO = "PAW_CREADO", "PAW creado"
    OT_CREADA = "OT_CREADA", "OT creada"
    BOM_CREADO = "BOM_CREADO", "BOM creado"
    EN_COMPRAS = "EN_COMPRAS", "En compras"
    EN_FINANZAS = "EN_FINANZAS", "En finanzas"
    EN_APROBACION = "EN_APROBACION", "En aprobación"
    PAGO_OK = "PAGO_OK", "Pago OK"
    MATERIAL_RECIBIDO = "MATERIAL_RECIBIDO", "Material recibido"
    ENTREGADO_TALLER = "ENTREGADO_TALLER", "Entregado a taller"
    PRODUCTO_OK = "PRODUCTO_OK", "Producto OK"
    EN_FACTURACION = "EN_FACTURACION", "En facturación"
    FACTURADO = "FACTURADO", "Facturado"
    RADICADO = "RADICADO", "Radicado"


class Paw(models.Model):

    class TipoOperacion(models.TextChoices):
        ENSAMBLE = "ENSAMBLE", "Ensamble / Taller"
        SERVICIO_CAMPO = "SERVICIO_CAMPO", "Servicio técnico en campo"

    numero_paw = models.CharField(
        "Número PAW",
        max_length=50,
        unique=True,
        blank=True,
    )

    nombre_paw = models.CharField(
        "Nombre del PAW",
        max_length=150,
        blank=True,
    )

    cotizacion = models.ForeignKey(
        "quotes.Quotation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="paws",
    )

    cliente = models.CharField(max_length=120, blank=True)
    campo = models.CharField(max_length=120, blank=True)

    fecha_entrega = models.DateField(null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)

    tipo_operacion = models.CharField(
        "Tipo de operación",
        max_length=30,
        choices=TipoOperacion.choices,
        default=TipoOperacion.ENSAMBLE,
        help_text="Campo legado. Se conserva para no afectar los PAW existentes durante la transición.",
    )

    # FASE 1 - Alcance operativo flexible.
    # Se dejan en NULL para que los PAW existentes continúen usando tipo_operacion
    # hasta que sean migrados/actualizados explícitamente.
    requiere_taller = models.BooleanField(
        "Requiere taller / ensamble",
        null=True,
        blank=True,
        help_text="Si está vacío, se conserva la lógica histórica basada en tipo_operacion.",
    )

    requiere_campo = models.BooleanField(
        "Requiere servicio en campo",
        null=True,
        blank=True,
        help_text="Si está vacío, se conserva la lógica histórica basada en tipo_operacion.",
    )

    requiere_compras = models.BooleanField(
        "Requiere compras / materiales",
        null=True,
        blank=True,
        help_text="Si está vacío, el flujo actual de compras no se modifica todavía.",
    )

    @property
    def aplica_taller(self):
        """Compatibilidad: nuevo campo si fue definido; si no, usa tipo_operacion legado."""
        if self.requiere_taller is not None:
            return self.requiere_taller
        return self.tipo_operacion == self.TipoOperacion.ENSAMBLE

    @property
    def aplica_campo(self):
        """Compatibilidad: nuevo campo si fue definido; si no, usa tipo_operacion legado."""
        if self.requiere_campo is not None:
            return self.requiere_campo
        return self.tipo_operacion == self.TipoOperacion.SERVICIO_CAMPO

    @property
    def aplica_compras(self):
        """FASE 1: mientras no se defina, conserva el comportamiento actual (compras aplica)."""
        if self.requiere_compras is not None:
            return self.requiere_compras
        return True

    @property
    def compras_finalizadas(self):
        if not self.aplica_compras:
            return True

        estados_ok = {
            EstadoOperativo.MATERIAL_RECIBIDO,
            EstadoOperativo.ENTREGADO_TALLER,
            EstadoOperativo.PRODUCTO_OK,
            EstadoOperativo.EN_FACTURACION,
            EstadoOperativo.FACTURADO,
            EstadoOperativo.RADICADO,
        }

        if self.estado_operativo in estados_ok:
            return True

        try:
            return bool(self.factura)
        except Exception:
            return False

    @property
    def taller_finalizado(self):
        if not self.aplica_taller:
            return True

        return self.estado_operativo in {
            EstadoOperativo.PRODUCTO_OK,
            EstadoOperativo.EN_FACTURACION,
            EstadoOperativo.FACTURADO,
            EstadoOperativo.RADICADO,
        }

    @property
    def campo_finalizado(self):
        if not self.aplica_campo:
            return True

        try:
            return self.servicio_campo.estado == "FINALIZADO"
        except Exception:
            return False

    @property
    def listo_para_facturar(self):
        return (
            self.compras_finalizadas
            and self.taller_finalizado
            and self.campo_finalizado
        )

    estado_operativo = models.CharField(
        max_length=30,
        choices=EstadoOperativo.choices,
        default=EstadoOperativo.PAW_CREADO,
    )

    criticidad = models.CharField(
        "Criticidad",
        max_length=10,
        choices=Criticidad.choices,
        default=Criticidad.MEDIA,
        help_text="Prioridad manual para revisión en reunión de operaciones.",
    )

    estado_gestion = models.CharField(
        "Estado de gestión",
        max_length=20,
        choices=EstadoGestion.choices,
        default=EstadoGestion.ASIGNADO,
        help_text="Estado manual para reunión: asignado, en proceso o pendiente.",
    )

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="paws_creados",
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.numero_paw:
            ultimo = (
                Paw.objects
                .exclude(numero_paw__isnull=True)
                .exclude(numero_paw="")
                .order_by("-id")
                .first()
            )

            if ultimo and str(ultimo.numero_paw).isdigit():
                self.numero_paw = str(int(ultimo.numero_paw) + 1)
            else:
                self.numero_paw = "1160"

        if self.cotizacion:
            if not self.nombre_paw:
                self.nombre_paw = self.cotizacion.nombre_cotizacion or ""

            if not self.cliente:
                self.cliente = self.cotizacion.cliente or ""

            if not self.campo:
                self.campo = self.cotizacion.campo or ""

        super().save(*args, **kwargs)

    def __str__(self):
        return f"PAW {self.numero_paw} - {self.cliente}"