from decimal import Decimal
from django import forms
from .models import PriceCalculation, PriceCalculationLine
from item_oil_gas.models import ItemImpetus

class PriceCalculationForm(forms.ModelForm):
    gm_porcentaje = forms.DecimalField(label='Gross Margin (%)', min_value=0, max_value=99.99, initial=40, decimal_places=2)
    class Meta:
        model = PriceCalculation
        fields = ['item_venta','trm','gm_porcentaje','observaciones']
        widgets = {'observaciones': forms.Textarea(attrs={'rows':2})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['item_venta'].queryset = ItemImpetus.objects.filter(activo=True).order_by('codigo')
        self.fields['item_venta'].label_from_instance = lambda x: f'{x.codigo} - {x.descripcion[:90]}'
        if self.instance.pk:
            self.fields['gm_porcentaje'].initial = self.instance.gm * 100
    def save(self,commit=True):
        obj=super().save(commit=False)
        obj.gm=Decimal(self.cleaned_data['gm_porcentaje'])/Decimal('100')
        if commit: obj.save()
        return obj

class PriceLineForm(forms.ModelForm):
    iva_porcentaje = forms.DecimalField(label='IVA (%)', min_value=0, max_value=100, initial=19, decimal_places=2)
    alistamiento_porcentaje = forms.DecimalField(label='Alistamiento (%)', min_value=0, max_value=100, initial=0, decimal_places=2)
    administrativo_porcentaje = forms.DecimalField(label='Administrativo (%)', min_value=0, max_value=100, initial=0, decimal_places=2)
    arancel_porcentaje = forms.DecimalField(label='Arancel (%)', min_value=0, max_value=100, initial=0, decimal_places=2)
    class Meta:
        model=PriceCalculationLine
        fields=['item','descripcion','tipo','importacion','moneda','cantidad','costo_unitario','iva_es_costo','iva_porcentaje','alistamiento_porcentaje','administrativo_porcentaje','arancel_porcentaje','costo_cero_justificado','motivo_costo_cero']
        widgets={'descripcion':forms.TextInput(attrs={'placeholder':'Se completa al seleccionar P/N o escriba un costo adicional'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['item'].required=False
        self.fields['item'].queryset=ItemImpetus.objects.filter(activo=True).order_by('codigo')
        self.fields['item'].label_from_instance=lambda x:f'{x.codigo} - {x.descripcion[:80]}'
    def save(self,commit=True):
        obj=super().save(commit=False)
        D=Decimal('100')
        obj.iva_pct=Decimal(self.cleaned_data['iva_porcentaje'])/D
        obj.alistamiento_pct=Decimal(self.cleaned_data['alistamiento_porcentaje'])/D
        obj.administrativo_pct=Decimal(self.cleaned_data['administrativo_porcentaje'])/D
        obj.arancel_pct=Decimal(self.cleaned_data['arancel_porcentaje'])/D
        if commit: obj.save()
        return obj

from .models import OperationalCost, LaborRate

class OperationalCostForm(forms.ModelForm):
    class Meta:
        model = OperationalCost
        fields = ['tipo', 'aplica', 'recurso_mod', 'concepto', 'descripcion', 'cantidad', 'tarifa_unitaria', 'observacion']
        widgets = {
            'recurso_mod': forms.Select(attrs={'id':'id_recurso_mod'}),
            'concepto': forms.Select(attrs={'id':'id_concepto'}),
            'descripcion': forms.TextInput(attrs={'placeholder':'Ej. Campo Cohembí, vehículo contratado, hotel 2 noches'}),
            'observacion': forms.TextInput(attrs={'placeholder':'Opcional'}),
            'cantidad': forms.NumberInput(attrs={'step':'0.001','min':'0'}),
            'tarifa_unitaria': forms.NumberInput(attrs={'step':'0.01','min':'0'}),
        }


class LaborRateForm(forms.ModelForm):
    class Meta:
        model = LaborRate
        fields = ['nombre','costo_empresa_mes','horas_productivas_mes','activo']
        widgets = {
            'costo_empresa_mes': forms.NumberInput(attrs={'step':'0.01','min':'0'}),
            'horas_productivas_mes': forms.NumberInput(attrs={'step':'0.01','min':'1'}),
        }

from .models import BankTestRate

class BankTestRateForm(forms.ModelForm):
    class Meta:
        model = BankTestRate
        fields = ['nombre','valor_banco_equipos','valor_residual','vida_util_anios','horas_uso_mes','potencia_promedio_kw','tarifa_energia_kwh','mantenimiento_anual','calibracion_anual','otros_costos_anuales','contingencia_pct','activo']
        widgets = {f: forms.NumberInput(attrs={'step':'0.01','min':'0'}) for f in ['valor_banco_equipos','valor_residual','vida_util_anios','horas_uso_mes','potencia_promedio_kw','tarifa_energia_kwh','mantenimiento_anual','calibracion_anual','otros_costos_anuales','contingencia_pct']}


from .models import ConsumablesPolicy

class ConsumablesPolicyForm(forms.ModelForm):
    class Meta:
        model = ConsumablesPolicy
        fields = ['nombre','metodo','valor_fijo','porcentaje_mod','activo']
        widgets = {
            'valor_fijo': forms.NumberInput(attrs={'step':'0.01','min':'0'}),
            'porcentaje_mod': forms.NumberInput(attrs={'step':'0.001','min':'0','max':'100'}),
        }


from .models import CifConfig, CifItem

class CifConfigForm(forms.ModelForm):
    class Meta:
        model = CifConfig
        fields = ['nombre','modo_base_horas','horas_productivas_base_mes','activo']
        widgets = {'horas_productivas_base_mes': forms.NumberInput(attrs={'step':'0.01','min':'1'})}

class CifItemForm(forms.ModelForm):
    class Meta:
        model = CifItem
        fields = ['categoria','concepto','costo_mes','participacion_pct','activo','observacion']
        widgets = {
            'costo_mes': forms.NumberInput(attrs={'step':'0.01','min':'0'}),
            'participacion_pct': forms.NumberInput(attrs={'step':'0.01','min':'0','max':'100'}),
            'concepto': forms.TextInput(attrs={'placeholder':'Ej. Gerencia administrativa, Compras, arriendo taller'}),
            'observacion': forms.TextInput(attrs={'placeholder':'Opcional'}),
        }
