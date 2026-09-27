from django import forms
from paw_app.models import Paw
from .models import InspeccionEje, PlantillaEje, InstrumentoMetrologico


class NuevaInspeccionEjeForm(forms.ModelForm):
    class Meta:
        model = InspeccionEje
        fields = ["paw", "tipo_trabajo", "plantilla", "serial_equipo", "serial_eje"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["paw"].queryset = Paw.objects.all().order_by("-id")
        self.fields["plantilla"].queryset = PlantillaEje.objects.filter(activo=True).order_by("nombre")
        self.fields["serial_equipo"].label = "Serial equipo / cámara"
        self.fields["serial_eje"].label = "Serial de la pieza"
        self.fields["serial_equipo"].help_text = "Identifica el equipo principal de la PAW. Si la PAW ya tiene inspecciones, se conservará automáticamente el mismo serial."
        self.fields["serial_eje"].help_text = "Opcional. Úselo si el eje, housing u otra pieza tiene serial propio."

    def clean(self):
        cleaned = super().clean()
        paw = cleaned.get("paw")
        tipo = cleaned.get("tipo_trabajo")
        if paw and tipo:
            existente = InspeccionEje.objects.filter(paw=paw).values_list("tipo_trabajo", flat=True).first()
            if existente and existente != tipo:
                self.add_error("tipo_trabajo", "Esta PAW ya tiene inspecciones como %s. Todas las inspecciones de una PAW deben usar el mismo tipo de trabajo." % dict(InspeccionEje.TipoTrabajo.choices).get(existente, existente))
            serial_existente = InspeccionEje.objects.filter(paw=paw).exclude(serial_equipo="").values_list("serial_equipo", flat=True).first()
            if serial_existente:
                cleaned["serial_equipo"] = serial_existente
        return cleaned


class DictamenInspeccionEjeForm(forms.ModelForm):
    class Meta:
        model = InspeccionEje
        fields = ["dictamen", "observaciones"]
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 4})}
