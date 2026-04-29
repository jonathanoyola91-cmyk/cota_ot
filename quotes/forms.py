from django import forms
from .models import Quotation, Cliente


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = [
            "nombre",
            "nit",
            "ciudad",
            "contacto",
            "telefono",
            "correo",
            "activo",
        ]


class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = [
            "nombre_cotizacion",
            "cliente_registrado",
            "campo",
            "fecha_cotizacion",
            "estado",
            "empresa",
            "valor",
            "observaciones",
        ]

        widgets = {
            "fecha_cotizacion": forms.DateInput(
                attrs={"type": "date"},
                format="%Y-%m-%d"
            ),
            "observaciones": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["cliente_registrado"].queryset = Cliente.objects.all().order_by("nombre")
        self.fields["cliente_registrado"].empty_label = "Seleccione un cliente"

        if self.instance and self.instance.fecha_cotizacion:
            self.initial["fecha_cotizacion"] = self.instance.fecha_cotizacion.strftime("%Y-%m-%d")

    def clean_valor(self):
        valor = self.cleaned_data.get("valor")

        if isinstance(valor, str):
            valor = valor.replace("$", "").replace(".", "").replace(" ", "").strip()
            valor = valor or "0"

        return valor