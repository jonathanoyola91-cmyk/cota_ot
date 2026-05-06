from django import forms
from .models import FieldService, FieldServiceDailyExpense


class AsignarTecnicosForm(forms.ModelForm):
    class Meta:
        model = FieldService
        fields = [
            "especialista_lider",
            "especialista_apoyo",
        ]

        labels = {
            "especialista_lider": "Especialista líder",
            "especialista_apoyo": "Especialista apoyo",
        }

        widgets = {
            "especialista_lider": forms.Select(attrs={"class": "form-control"}),
            "especialista_apoyo": forms.Select(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()

        lider = cleaned_data.get("especialista_lider")
        apoyo = cleaned_data.get("especialista_apoyo")

        if lider and apoyo and lider == apoyo:
            raise forms.ValidationError(
                "El especialista líder y el especialista apoyo no pueden ser la misma persona."
            )

        return cleaned_data


class FieldServiceDailyExpenseForm(forms.ModelForm):
    class Meta:
        model = FieldServiceDailyExpense
        fields = [
            "fecha",
            "dia_numero",
            "actividades",
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
            "dia_numero": "Día",
            "actividades": "Actividades realizadas del día",
            "apoyo_local": "Apoyo local / comunidad",
            "alojamiento": "Alojamiento unitario",
            "tarifa_alimentacion": "Alimentación unitaria",
            "hidratacion_por_persona": "Hidratación por persona",
            "gastos_adicionales": "Gastos adicionales",
            "observaciones": "Observaciones internas",
        }

        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "dia_numero": forms.NumberInput(attrs={"class": "form-control", "min": 1, "readonly": "readonly"}),
            "actividades": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 5,
                "placeholder": "Ej: Se realizó charla de seguridad, instalación del equipo, pruebas funcionales y validación con el cliente.",
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
