from django import forms

from .models import EnsambleTaller, EnsambleTallerTecnico, JornadaTaller, TECNICOS_TALLER_CHOICES


class IniciarEnsambleForm(forms.ModelForm):
    class Meta:
        model = EnsambleTaller
        fields = ["fecha_inicio", "observaciones"]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }


class AsignarTecnicosTallerForm(forms.Form):
    tecnicos = forms.MultipleChoiceField(
        label="Técnicos involucrados",
        choices=TECNICOS_TALLER_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )

    def __init__(self, *args, ensamble=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ensamble = ensamble
        if ensamble and not self.is_bound:
            self.fields["tecnicos"].initial = list(
                ensamble.tecnicos.values_list("tecnico", flat=True)
            )

    def save(self):
        seleccionados = set(self.cleaned_data["tecnicos"])
        existentes = {
            obj.tecnico: obj
            for obj in self.ensamble.tecnicos.all()
        }

        # No elimina técnicos que ya tengan jornadas; evita perder trazabilidad.
        for nombre, obj in existentes.items():
            if nombre not in seleccionados and not obj.jornadas.exists():
                obj.delete()

        for nombre in seleccionados:
            EnsambleTallerTecnico.objects.get_or_create(
                ensamble=self.ensamble,
                tecnico=nombre,
            )

        return self.ensamble


class JornadaTallerForm(forms.ModelForm):
    class Meta:
        model = JornadaTaller
        fields = [
            "tecnico",
            "fecha",
            "hora_entrada",
            "hora_salida",
            "actividades",
            "observaciones",
        ]
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "hora_entrada": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "hora_salida": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "actividades": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "observaciones": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, ensamble=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ensamble = ensamble or getattr(self.instance, "ensamble", None)
        if self.ensamble:
            self.fields["tecnico"].queryset = self.ensamble.tecnicos.all()
        else:
            self.fields["tecnico"].queryset = EnsambleTallerTecnico.objects.none()

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.ensamble:
            obj.ensamble = self.ensamble
        if commit:
            obj.save()
        return obj
