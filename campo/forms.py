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
            "dia_trabajado_campo",
            "salida_despues_mediodia",
            "regreso_despues_6pm",
            "solo_viaje_traslado",
            "transporte",
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
            "dia_trabajado_campo": "Día trabajado en campo",
            "salida_despues_mediodia": "Salida después del mediodía",
            "regreso_despues_6pm": "Regreso después de las 6:00 pm",
            "solo_viaje_traslado": "Solo viaje / traslado",
            "transporte": "Transporte comunidad / operación",
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
            "dia_trabajado_campo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "salida_despues_mediodia": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "regreso_despues_6pm": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "solo_viaje_traslado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "transporte": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
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

        help_texts = {
            "transporte": "Valor manual que cobra la operación/comunidad por movilización diaria.",
            "personas": "Cantidad de personas para gastos operativos. Los bonos se calculan por líder/apoyo asignados.",
            "dia_trabajado_campo": "Aplica bono de campo según rol: líder/apoyo.",
            "salida_despues_mediodia": "Si no trabajó campo, aplica solo movilización por persona.",
            "regreso_despues_6pm": "Si trabajó el día, suma movilización adicional por persona.",
            "solo_viaje_traslado": "No aplica bono de campo; aplica solo movilización por persona.",
        }

    def clean(self):
        cleaned_data = super().clean()

        dia_trabajado = cleaned_data.get("dia_trabajado_campo")
        salida_tarde = cleaned_data.get("salida_despues_mediodia")
        regreso_tarde = cleaned_data.get("regreso_despues_6pm")
        solo_viaje = cleaned_data.get("solo_viaje_traslado")

        if solo_viaje and dia_trabajado:
            raise forms.ValidationError(
                "Si marcas 'Solo viaje / traslado', no debes marcar 'Día trabajado en campo'."
            )

        if solo_viaje and regreso_tarde:
            raise forms.ValidationError(
                "Si es solo viaje / traslado, no marques 'Regreso después de las 6:00 pm'."
            )

        if not dia_trabajado and not salida_tarde and not solo_viaje:
            raise forms.ValidationError(
                "Debes marcar al menos una clasificación: día trabajado, salida después del mediodía o solo viaje."
            )

        return cleaned_data
