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
            "personas",
            "transporte",
            "gastos_adicionales",
            "comprado_por",
            "aprobado_por",
            "observaciones",
        ]

        labels = {
            "dia_numero": "Día",
            "actividades": "Actividades realizadas del día",
            "personas": "Cantidad de personas",
            "transporte": "Transporte comunidad / operación",
            "gastos_adicionales": "Gastos adicionales",
            "comprado_por": "Quién compró",
            "aprobado_por": "Quién aprobó",
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
            "personas": forms.NumberInput(attrs={
                "class": "form-control",
                "min": 1,
                "id": "id_personas",
            }),
            "transporte": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "gastos_adicionales": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "comprado_por": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Ej: Carlos Hende, Reison Vanegas, Jose Oyola",
            }),
            "aprobado_por": forms.Select(attrs={"class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

        help_texts = {
            "transporte": "Valor manual que cobra la operación/comunidad por movilización diaria.",
            "personas": "Cantidad de personas. Este valor habilita las filas del detalle individual.",
            "gastos_adicionales": "Valor global adicional del día. Registrar quién compró y quién aprobó solo como control interno.",
            "comprado_por": "Registro informativo. No genera flujo de aprobación.",
            "aprobado_por": "Registro informativo. No genera flujo de aprobación.",
        }

    def clean_personas(self):
        personas = self.cleaned_data.get("personas") or 1

        if personas < 1:
            raise forms.ValidationError("La cantidad de personas debe ser mínimo 1.")

        if personas > 20:
            raise forms.ValidationError("La cantidad de personas no puede superar 20 por día.")

        return personas
