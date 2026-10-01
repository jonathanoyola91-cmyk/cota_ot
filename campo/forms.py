from django import forms
from .models import FieldService, FieldServiceDailyExpense


class AsignarTecnicosForm(forms.ModelForm):
    class Meta:
        model = FieldService
        fields = ["especialista_lider_usuario", "especialistas_apoyo_usuarios"]
        labels = {
            "especialista_lider_usuario": "Especialista líder",
            "especialistas_apoyo_usuarios": "Especialistas de apoyo",
        }
        widgets = {
            "especialista_lider_usuario": forms.Select(attrs={"class": "form-control"}),
            "especialistas_apoyo_usuarios": forms.SelectMultiple(attrs={"class": "form-control", "size": "7"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        UserModel = self._meta.model._meta.get_field("especialista_lider_usuario").remote_field.model
        qs = UserModel.objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        self.fields["especialista_lider_usuario"].queryset = qs
        self.fields["especialistas_apoyo_usuarios"].queryset = qs
        self.fields["especialistas_apoyo_usuarios"].required = False
        self.fields["especialistas_apoyo_usuarios"].help_text = "Puede seleccionar ninguno, uno o varios apoyos."

    def clean(self):
        cleaned = super().clean()
        lider = cleaned.get("especialista_lider_usuario")
        apoyos = cleaned.get("especialistas_apoyo_usuarios")
        if lider and apoyos and apoyos.filter(pk=lider.pk).exists():
            raise forms.ValidationError("El líder no puede estar también seleccionado como apoyo.")
        return cleaned

    def save(self, commit=True):
        servicio = super().save(commit=False)
        lider = self.cleaned_data.get("especialista_lider_usuario")
        apoyos = self.cleaned_data.get("especialistas_apoyo_usuarios")
        servicio.especialista_lider = (lider.get_full_name() or lider.username).strip() if lider else ""
        primer_apoyo = apoyos.first() if apoyos is not None else None
        servicio.especialista_apoyo_usuario = primer_apoyo
        servicio.especialista_apoyo = (primer_apoyo.get_full_name() or primer_apoyo.username).strip() if primer_apoyo else ""
        if commit:
            servicio.save()
            self.save_m2m()
        return servicio


class FieldServiceDailyExpenseForm(forms.ModelForm):
    class Meta:
        model = FieldServiceDailyExpense
        fields = [
            "fecha",
            "dia_numero",
            "actividades",
            "personas",
            "transporte",
            "apoyo_local",
            "comprado_por",
            "aprobado_por",
            "observaciones",
        ]

        labels = {
            "dia_numero": "Día",
            "actividades": "Actividades realizadas del día",
            "personas": "Cantidad de personas",
            "transporte": "Transporte",
            "apoyo_local": "Apoyo local / comunidad",
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
            "apoyo_local": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
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

from .models import FieldServiceBonusClaim

class FieldServiceBonusClaimForm(forms.ModelForm):
    class Meta:
        model = FieldServiceBonusClaim
        fields = [
            "dia_trabajado_campo", "salida_despues_mediodia", "regreso_despues_6pm",
            "solo_viaje_traslado", "alojamiento", "alimentacion", "hidratacion", "lavanderia",
            "transporte_personal", "vuelo_ida_aplica", "vuelo_ida_valor",
            "vuelo_regreso_aplica", "vuelo_regreso_valor", "observaciones",
        ]
        widgets = {
            "alojamiento": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "alimentacion": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "hidratacion": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "lavanderia": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "transporte_personal": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "vuelo_ida_valor": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "vuelo_regreso_valor": forms.NumberInput(attrs={"class":"form-control", "step":"0.01", "min":"0"}),
            "observaciones": forms.TextInput(attrs={"class":"form-control", "placeholder":"Observación opcional"}),
        }

    def clean(self):
        data = super().clean()
        if not any(data.get(x) for x in ["dia_trabajado_campo", "salida_despues_mediodia", "regreso_despues_6pm", "solo_viaje_traslado"]):
            raise forms.ValidationError("Selecciona al menos una condición del día.")
        if data.get("solo_viaje_traslado"):
            data["dia_trabajado_campo"] = False
            data["salida_despues_mediodia"] = False
            data["regreso_despues_6pm"] = False
        return data
