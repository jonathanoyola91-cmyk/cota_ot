from django import forms
from .models import Factura


class FacturaForm(forms.ModelForm):
    class Meta:
        model = Factura
        fields = [
            "lugar_entrega",
            "lugar_servicio",
            "numero_servicio",
            "item_factura",
            "precio",
            "numero_factura",
            "fecha_vencimiento",
            "tipo_pago",
            "estado",
        ]

        widgets = {
            "numero_factura": forms.TextInput(attrs={"class": "form-control"}),
            "precio": forms.NumberInput(attrs={"class": "form-control"}),
            "fecha_vencimiento": forms.DateInput(attrs={"type":"date","class":"form-control"}),
            "tipo_pago": forms.Select(attrs={"class":"form-control"}),
            "lugar_entrega": forms.TextInput(attrs={"class":"form-control"}),
            "lugar_servicio": forms.TextInput(attrs={"class":"form-control"}),
            "numero_servicio": forms.TextInput(attrs={"class":"form-control"}),
            "estado": forms.Select(attrs={"class":"form-control"}),
            "item_factura": forms.Select(attrs={"class": "form-control"}),
        }