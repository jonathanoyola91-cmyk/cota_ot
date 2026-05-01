# finanzas/forms.py
from django import forms

from .models import SupplierInvoice, SupplierPayment


class SupplierInvoiceForm(forms.ModelForm):
    class Meta:
        model = SupplierInvoice
        fields = [
            "numero_factura_proveedor",
            "fecha_factura_proveedor",
            "observacion",
        ]
        widgets = {
            "numero_factura_proveedor": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: FV-12345",
            }),
            "fecha_factura_proveedor": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date",
            }),
            "observacion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Notas internas de Finanzas",
            }),
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
