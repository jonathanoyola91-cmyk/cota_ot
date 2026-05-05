from django import forms
from django.forms import modelformset_factory
from .models import Supplier, PurchaseLine
from decimal import Decimal


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            "nombre",
            "contacto",
            "telefono",
            "email",
            "nit",
            "banco",
            "cuenta_bancaria",
            "tipo_cuenta",
        ]

        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "contacto": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "nit": forms.TextInput(attrs={"class": "form-control"}),
            "banco": forms.TextInput(attrs={"class": "form-control"}),
            "cuenta_bancaria": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_cuenta": forms.Select(attrs={"class": "form-control"}),
        }


class PurchaseLineForm(forms.ModelForm):
    porcentaje_pago = forms.DecimalField(
        required=True,
        initial=Decimal("100.00"),
        widget=forms.Select(
            choices=[
                (Decimal("50.00"), "50%"),
                (Decimal("100.00"), "100%"),
            ],
            attrs={"class": "form-control"}
        )
    )

    class Meta:
        model = PurchaseLine
        fields = [
            "cantidad_disponible",
            "proveedor",
            "precio_unitario",
            "tipo_pago",
            "porcentaje_pago",
            "observaciones_compras",
        ]

        widgets = {
            "cantidad_disponible": forms.NumberInput(attrs={"class": "form-control"}),
            "proveedor": forms.Select(attrs={"class": "form-control"}),
            "precio_unitario": forms.NumberInput(attrs={"class": "form-control"}),
            "tipo_pago": forms.Select(attrs={"class": "form-control"}),
            "observaciones_compras": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Ej: Pago 50% anticipado / 50% contra entrega"
            }),
        }

    def clean_porcentaje_pago(self):
        value = self.cleaned_data.get("porcentaje_pago")
        return value or Decimal("100.00")

PurchaseLineFormSet = modelformset_factory(
    PurchaseLine,
    form=PurchaseLineForm,
    extra=0,
    can_delete=False,
)