from decimal import Decimal

from django import forms
from django.forms import modelformset_factory

from .models import Supplier, PurchaseLine, PurchaseRequest


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
    porcentaje_pago = forms.TypedChoiceField(
        required=False,
        choices=[
            ("0.00", "0%"),
            ("50.00", "50%"),
            ("100.00", "100%"),
        ],
        coerce=Decimal,
        empty_value=Decimal("0.00"),
        widget=forms.Select(attrs={"class": "form-control"}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Garantiza que el select muestre el valor real guardado en BD
        # para evitar que 100.00 se vea como 50% por defecto.
        if self.instance and self.instance.pk:
            valor = self.instance.porcentaje_pago
            if valor is None:
                valor = Decimal("0.00")
            self.initial["porcentaje_pago"] = f"{Decimal(valor):.2f}"
        else:
            self.initial.setdefault("porcentaje_pago", "0.00")

    def clean(self):
        cleaned_data = super().clean()

        tipo_pago = cleaned_data.get("tipo_pago")
        porcentaje = cleaned_data.get("porcentaje_pago") or Decimal("0.00")

        if tipo_pago == PurchaseRequest.TipoPago.NA:
            cleaned_data["porcentaje_pago"] = Decimal("0.00")

        elif tipo_pago == PurchaseRequest.TipoPago.CREDITO:
            cleaned_data["porcentaje_pago"] = Decimal("100.00")

        elif tipo_pago == PurchaseRequest.TipoPago.CONTADO:
            if porcentaje not in [Decimal("50.00"), Decimal("100.00")]:
                raise forms.ValidationError(
                    "Para pago contado debes seleccionar 50% o 100%. Usa N/A para stock o compras locales sin pago financiero."
                )
            cleaned_data["porcentaje_pago"] = porcentaje

        return cleaned_data


PurchaseLineFormSet = modelformset_factory(
    PurchaseLine,
    form=PurchaseLineForm,
    extra=0,
    can_delete=False,
)
