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


from .models import FixedExpense, InvestorLoan, InvestorPayment


class FixedExpenseForm(forms.ModelForm):
    class Meta:
        model = FixedExpense
        fields = ["categoria", "concepto", "valor", "fecha_vencimiento", "observacion"]
        widgets = {
            "categoria": forms.Select(attrs={"class": "form-control"}),
            "concepto": forms.TextInput(attrs={"class": "form-control"}),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "fecha_vencimiento": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class InvestorLoanForm(forms.ModelForm):
    class Meta:
        model = InvestorLoan
        fields = ["inversionista", "valor_prestado", "interes_mensual", "fecha_prestamo", "fecha_primera_cuota", "observacion"]
        widgets = {
            "inversionista": forms.TextInput(attrs={"class": "form-control"}),
            "valor_prestado": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "interes_mensual": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
            "fecha_prestamo": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "fecha_primera_cuota": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class InvestorPaymentForm(forms.ModelForm):
    class Meta:
        model = InvestorPayment
        fields = ["fecha_programada", "valor", "observacion"]
        widgets = {
            "fecha_programada": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "observacion": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
