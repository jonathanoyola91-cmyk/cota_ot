# finanzas/forms.py
from django import forms

from .models import SupplierInvoice, SupplierPayment


class SupplierInvoiceForm(forms.ModelForm):
    class Meta:
        model = SupplierInvoice
        fields = [
            "numero_factura_proveedor",
            "fecha_factura_proveedor",
            "fecha_vencimiento",
            "observacion",
            "tipo_operacion",
            "aplica_iva",
        ]
        widgets = {
            "numero_factura_proveedor": forms.TextInput(attrs={"class": "form-control"}),
            "fecha_factura_proveedor": forms.DateInput(
                attrs={"class": "form-control", "type": "date"},
                format="%Y-%m-%d"
            ),
            "fecha_vencimiento": forms.DateInput(
                attrs={"class": "form-control", "type": "date"},
                format="%Y-%m-%d",
            ),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "tipo_operacion": forms.Select(attrs={"class": "form-control"}),
            "aplica_iva": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SupplierPaymentForm(forms.ModelForm):
    class Meta:
        model = SupplierPayment
        fields = ["fecha", "valor", "referencia", "observacion"]
        widgets = {
            "fecha": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "valor": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "min": "0",
                "placeholder": "Valor abonado",
            }),
            "referencia": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Transferencia, comprobante, recibo, etc.",
            }),
            "observacion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Observación del abono",
            }),
        }
