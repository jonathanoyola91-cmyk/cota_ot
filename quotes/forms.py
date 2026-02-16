from django import forms
from .models import Quotation

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = "__all__"

    def clean_valor(self):
        valor = self.cleaned_data.get("valor")

        # Si llega como texto con $ y puntos, lo limpiamos
        if isinstance(valor, str):
            valor = valor.replace("$", "").replace(".", "").replace(" ", "").strip()
            valor = valor or "0"

        return valor