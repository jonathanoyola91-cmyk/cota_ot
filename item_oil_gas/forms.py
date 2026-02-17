from django import forms
from .models import Item

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ["codigo", "descripcion", "unidad_medida", "clasificacion", "grupo_inventario", "activo"]

class ItemImportForm(forms.Form):
    archivo = forms.FileField(help_text="Sube un .xlsx con las columnas: Código, Descripción, Unidad Medida, Clasificacion, Grupo Inventario")