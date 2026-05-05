from django import forms
from django.utils import timezone

from .models import FieldServiceDailyExpense


class FieldServiceDailyExpenseForm(forms.ModelForm):
    class Meta:
        model = FieldServiceDailyExpense
        fields = [
            "fecha",
            "dia_numero",
            "transporte",
            "apoyo_local",
            "alojamiento",
            "personas",
            "tarifa_alimentacion",
            "hidratacion_por_persona",
            "vuelo_ida_aplica",
            "vuelo_ida_valor",
            "vuelo_regreso_aplica",
            "vuelo_regreso_valor",
            "gastos_adicionales",
            "observaciones",
        ]

        labels = {
            "dia_numero": "Día número",
            "apoyo_local": "Apoyo local / comunidad",
            "alojamiento": "Alojamiento por persona",
            "personas": "Cantidad de personas",
            "tarifa_alimentacion": "Alimentación por persona",
            "hidratacion_por_persona": "Hidratación por persona",
            "vuelo_ida_aplica": "¿Aplica vuelo ida?",
            "vuelo_ida_valor": "Valor vuelo ida",
            "vuelo_regreso_aplica": "¿Aplica vuelo regreso?",
            "vuelo_regreso_valor": "Valor vuelo regreso",
            "gastos_adicionales": "Gastos adicionales",
        }

        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "dia_numero": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 1,
                "readonly": "readonly",
            }),
            "transporte": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "apoyo_local": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "alojamiento": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "personas": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "tarifa_alimentacion": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "hidratacion_por_persona": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "vuelo_ida_aplica": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "vuelo_ida_valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "vuelo_regreso_aplica": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "vuelo_regreso_valor": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "gastos_adicionales": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        siguiente_dia = kwargs.pop("siguiente_dia", None)
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.initial.setdefault("fecha", timezone.localdate())
            if siguiente_dia:
                self.initial["dia_numero"] = siguiente_dia

        self.fields["dia_numero"].disabled = True

    def clean_personas(self):
        personas = self.cleaned_data.get("personas") or 1
        if personas < 1:
            raise forms.ValidationError("Debe registrar al menos una persona.")
        return personas
