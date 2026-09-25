from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from item_oil_gas.models import ItemImpetus


class PriceCalculation(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'

    item_venta = models.ForeignKey(ItemImpetus, on_delete=models.PROTECT, related_name='calculos_precio')
    gm = models.DecimalField('Gross Margin', max_digits=6, decimal_places=4, default=Decimal('0.4000'))
    trm = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal('1'))
    precio_comercial = models.DecimalField(max_digits=18, decimal_places=2, default=0,
        help_text='Precio final que se publicará. Puede redondearse respecto al precio calculado.')
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    observaciones = models.TextField(blank=True, default='')
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='calculos_precio_creados')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    publicado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='precios_publicados')
    publicado_en = models.DateTimeField(null=True, blank=True)
    precio_anterior = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']

    @property
    def costo_integral(self):
        return (sum((x.costo_total for x in self.lineas.all()), Decimal('0')) + sum((x.costo_total for x in self.costos_operativos.all()), Decimal('0')))

    @property
    def precio_calculado(self):
        if self.gm >= 1:
            return Decimal('0')
        return (self.costo_integral / (Decimal('1') - self.gm)).quantize(Decimal('0.01'))

    def __str__(self):
        return f'{self.item_venta.codigo} - cálculo #{self.pk or "nuevo"}'


class PriceCalculationLine(models.Model):
    class Tipo(models.TextChoices):
        INSUMO = 'INSUMO', 'Insumo / repuesto'
        MANO_OBRA = 'MANO_OBRA', 'Mano de obra'
        MECANIZADO = 'MECANIZADO', 'Mecanizado / terceros'
        BANCO = 'BANCO', 'Banco de prueba / QA-QC'
        CONSUMIBLE = 'CONSUMIBLE', 'Consumibles'
        FLETE = 'FLETE', 'Transporte / movilización'
        VIATICOS = 'VIATICOS', 'Viáticos'
        CIF = 'CIF', 'CIF / costos indirectos'
        SERVICIO = 'SERVICIO', 'Servicio / costo directo'
        OTRO = 'OTRO', 'Otro costo'

    calculo = models.ForeignKey(PriceCalculation, on_delete=models.CASCADE, related_name='lineas')
    item = models.ForeignKey(ItemImpetus, on_delete=models.PROTECT, null=True, blank=True, related_name='lineas_calculo_precio')
    codigo = models.CharField(max_length=80, blank=True, default='')
    descripcion = models.CharField(max_length=300)
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.INSUMO)
    importacion = models.BooleanField(default=False)
    moneda = models.CharField(max_length=3, choices=[('COP','COP'),('USD','USD')], default='COP')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    costo_unitario = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    fuente_costo = models.CharField(max_length=120, blank=True, default='Manual')
    iva_pct = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal('0.1900'))
    iva_es_costo = models.BooleanField(default=False, help_text='Active solo cuando el IVA realmente constituye mayor costo.')
    alistamiento_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    administrativo_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    arancel_pct = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    costo_cero_justificado = models.BooleanField(default=False)
    motivo_costo_cero = models.CharField(max_length=220, blank=True, default='')

    class Meta:
        ordering = ['id']

    @property
    def costo_unitario_cop(self):
        if self.moneda == 'USD':
            return self.costo_unitario * self.calculo.trm
        return self.costo_unitario

    @property
    def subtotal(self):
        return self.costo_unitario_cop * self.cantidad

    @property
    def costo_iva(self):
        return self.subtotal * self.iva_pct if self.iva_es_costo else Decimal('0')

    @property
    def costo_total(self):
        base = self.subtotal
        recargos = base * (self.alistamiento_pct + self.administrativo_pct + self.arancel_pct)
        return (base + self.costo_iva + recargos).quantize(Decimal('0.01'))

    def save(self, *args, **kwargs):
        if self.item_id:
            self.codigo = self.item.codigo
            if not self.descripcion:
                self.descripcion = self.item.descripcion[:300]
        super().save(*args, **kwargs)

class OperationalCost(models.Model):
    class Tipo(models.TextChoices):
        MANO_OBRA = 'MANO_OBRA', 'Mano de obra'
        BANCO = 'BANCO', 'Banco de prueba / QA-QC'
        CONSUMIBLES = 'CONSUMIBLES', 'Consumibles generales'
        FLETE = 'FLETE', 'Transporte / movilización'
        VIATICOS = 'VIATICOS', 'Viáticos'
        CIF = 'CIF', 'CIF / costos indirectos'

    class Concepto(models.TextChoices):
        PERSONAL = 'PERSONAL', 'Movilización de personal'
        EQUIPO = 'EQUIPO', 'Transporte de equipo'
        COMBUSTIBLE = 'COMBUSTIBLE', 'Combustible / peajes'
        TIQUETES = 'TIQUETES', 'Tiquetes'
        ALOJAMIENTO = 'ALOJAMIENTO', 'Alojamiento'
        ALIMENTACION = 'ALIMENTACION', 'Alimentación'
        OTRO = 'OTRO', 'Otro'

    calculo = models.ForeignKey(PriceCalculation, on_delete=models.CASCADE, related_name='costos_operativos')
    recurso_mod = models.ForeignKey('LaborRate', on_delete=models.PROTECT, null=True, blank=True, related_name='costos_usados')
    tarifa_origen_nombre = models.CharField(max_length=140, blank=True, default='')
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    aplica = models.BooleanField(default=True)
    revisado = models.BooleanField(default=True)
    concepto = models.CharField(max_length=20, choices=Concepto.choices, blank=True, default='')
    descripcion = models.CharField(max_length=220, blank=True, default='')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1, help_text='Horas para mano de obra/banco; unidades para otros costos.')
    tarifa_unitaria = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    observacion = models.CharField(max_length=220, blank=True, default='')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tipo', 'id']

    @property
    def costo_total(self):
        if not self.aplica:
            return Decimal('0')
        return (self.cantidad * self.tarifa_unitaria).quantize(Decimal('0.01'))

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.calculo_id}'


class LaborRate(models.Model):
    nombre = models.CharField(max_length=140, unique=True)
    costo_empresa_mes = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    participacion_pct = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    horas_productivas_mes = models.DecimalField(max_digits=8, decimal_places=2, default=176)
    activo = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='tarifas_mod_actualizadas')
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def costo_hora(self):
        if not self.horas_productivas_mes:
            return Decimal('0')
        return (self.costo_empresa_mes / self.horas_productivas_mes).quantize(Decimal('0.01'))

    def __str__(self):
        return self.nombre


class LaborRateHistory(models.Model):
    tarifa = models.ForeignKey(LaborRate, on_delete=models.CASCADE, related_name='historial')
    costo_empresa_mes = models.DecimalField(max_digits=18, decimal_places=2)
    participacion_pct = models.DecimalField(max_digits=6, decimal_places=2)
    horas_productivas_mes = models.DecimalField(max_digits=8, decimal_places=2)
    costo_hora = models.DecimalField(max_digits=18, decimal_places=2)
    vigente_desde = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-vigente_desde']

class BankTestRate(models.Model):
    nombre = models.CharField(max_length=140, default='Banco de prueba / QA-QC')
    valor_banco_equipos = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    valor_residual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    vida_util_anios = models.DecimalField(max_digits=8, decimal_places=2, default=10)
    horas_uso_mes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    potencia_promedio_kw = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tarifa_energia_kwh = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    mantenimiento_anual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    calibracion_anual = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    otros_costos_anuales = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    contingencia_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='tarifas_banco_actualizadas')
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def costo_infraestructura_hora(self):
        if self.vida_util_anios <= 0 or self.horas_uso_mes <= 0:
            return Decimal('0')
        depreciable = max(Decimal('0'), self.valor_banco_equipos - self.valor_residual)
        return depreciable / (self.vida_util_anios * Decimal('12') * self.horas_uso_mes)

    @property
    def costo_energia_hora(self):
        return self.potencia_promedio_kw * self.tarifa_energia_kwh

    def _anual_hora(self, valor):
        if self.horas_uso_mes <= 0:
            return Decimal('0')
        return valor / (Decimal('12') * self.horas_uso_mes)

    @property
    def costo_mantenimiento_hora(self): return self._anual_hora(self.mantenimiento_anual)
    @property
    def costo_calibracion_hora(self): return self._anual_hora(self.calibracion_anual)
    @property
    def costo_otros_hora(self): return self._anual_hora(self.otros_costos_anuales)

    @property
    def costo_hora(self):
        base = self.costo_infraestructura_hora + self.costo_energia_hora + self.costo_mantenimiento_hora + self.costo_calibracion_hora + self.costo_otros_hora
        return (base * (Decimal('1') + self.contingencia_pct / Decimal('100'))).quantize(Decimal('0.01'))

    @property
    def configuracion_completa(self):
        return all([self.valor_banco_equipos > 0, self.vida_util_anios > 0, self.horas_uso_mes > 0, self.potencia_promedio_kw > 0, self.tarifa_energia_kwh > 0])

    def __str__(self): return self.nombre


class BankTestRateHistory(models.Model):
    tarifa = models.ForeignKey(BankTestRate, on_delete=models.CASCADE, related_name='historial')
    datos = models.JSONField(default=dict)
    costo_hora = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    configuracion_completa = models.BooleanField(default=False)
    vigente_desde = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-vigente_desde']


class ConsumablesPolicy(models.Model):
    class Metodo(models.TextChoices):
        FIJO = 'FIJO', 'Valor fijo por trabajo'
        PCT_MOD = 'PCT_MOD', 'Porcentaje sobre MOD directa'
        MANUAL = 'MANUAL', 'Manual por trabajo'

    nombre = models.CharField(max_length=140, default='Consumibles generales')
    metodo = models.CharField(max_length=12, choices=Metodo.choices, default=Metodo.MANUAL)
    valor_fijo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    porcentaje_mod = models.DecimalField(max_digits=7, decimal_places=3, default=0, help_text='Porcentaje sobre el total de MOD directa.')
    activo = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='politicas_consumibles_actualizadas')
    actualizado_en = models.DateTimeField(auto_now=True)

    def calcular(self, calculo):
        if self.metodo == self.Metodo.FIJO:
            return self.valor_fijo.quantize(Decimal('0.01'))
        if self.metodo == self.Metodo.PCT_MOD:
            mod = sum((c.costo_total for c in calculo.costos_operativos.filter(tipo=OperationalCost.Tipo.MANO_OBRA, aplica=True)), Decimal('0'))
            return (mod * self.porcentaje_mod / Decimal('100')).quantize(Decimal('0.01'))
        return Decimal('0')

    def __str__(self):
        return self.nombre


class ConsumablesPolicyHistory(models.Model):
    politica = models.ForeignKey(ConsumablesPolicy, on_delete=models.CASCADE, related_name='historial')
    metodo = models.CharField(max_length=12)
    valor_fijo = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    porcentaje_mod = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    vigente_desde = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-vigente_desde']


class CifConfig(models.Model):
    class ModoBase(models.TextChoices):
        AUTOMATICA = 'AUTOMATICA', 'Automática desde MOD activa'
        MANUAL = 'MANUAL', 'Manual / excepción'

    nombre = models.CharField(max_length=140, default='CIF / Costos indirectos')
    modo_base_horas = models.CharField(max_length=12, choices=ModoBase.choices, default=ModoBase.AUTOMATICA)
    horas_productivas_base_mes = models.DecimalField(max_digits=10, decimal_places=2, default=176, help_text='Base manual. Solo se usa cuando el modo de distribución es Manual.')
    activo = models.BooleanField(default=True)
    actualizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='cif_config_actualizada')
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def costo_indirecto_mes(self):
        # Una configuración nueva aún sin PK no puede consultar relaciones inversas.
        # Devolvemos 0 para que la UI y cualquier cálculo sean seguros.
        if not self.pk:
            return Decimal('0')
        return sum((x.costo_imputable_mes for x in self.conceptos.filter(activo=True)), Decimal('0'))

    @property
    def horas_productivas_automaticas_mes(self):
        return sum((x.horas_productivas_mes for x in LaborRate.objects.filter(activo=True)), Decimal('0'))

    @property
    def horas_productivas_efectivas_mes(self):
        if self.modo_base_horas == self.ModoBase.MANUAL:
            return self.horas_productivas_base_mes or Decimal('0')
        return self.horas_productivas_automaticas_mes

    @property
    def tarifa_hora(self):
        horas = self.horas_productivas_efectivas_mes
        if horas <= 0:
            return Decimal('0')
        return (self.costo_indirecto_mes / horas).quantize(Decimal('0.01'))

    def __str__(self):
        return self.nombre


class CifItem(models.Model):
    class Categoria(models.TextChoices):
        PERSONAL = 'PERSONAL', 'Personal indirecto'
        INSTALACIONES = 'INSTALACIONES', 'Instalaciones / servicios'
        HSE = 'HSE', 'HSE / seguridad industrial'
        MANTENIMIENTO = 'MANTENIMIENTO', 'Mantenimiento general'
        ADMIN = 'ADMIN', 'Administrativo'
        OTRO = 'OTRO', 'Otro indirecto'

    configuracion = models.ForeignKey(CifConfig, on_delete=models.CASCADE, related_name='conceptos')
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.PERSONAL)
    concepto = models.CharField(max_length=160)
    costo_mes = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    participacion_pct = models.DecimalField(max_digits=6, decimal_places=2, default=100, help_text='Porcentaje del costo mensual atribuible a la operación HPS/taller.')
    activo = models.BooleanField(default=True)
    observacion = models.CharField(max_length=240, blank=True, default='')

    @property
    def costo_imputable_mes(self):
        return (self.costo_mes * self.participacion_pct / Decimal('100')).quantize(Decimal('0.01'))

    def __str__(self):
        return self.concepto


class CifConfigHistory(models.Model):
    configuracion = models.ForeignKey(CifConfig, on_delete=models.CASCADE, related_name='historial')
    datos = models.JSONField(default=dict)
    costo_indirecto_mes = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    tarifa_hora = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    vigente_desde = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['-vigente_desde']
