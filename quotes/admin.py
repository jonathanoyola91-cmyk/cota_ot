from django.contrib import admin
from django import forms
from .models import Quotation


class QuotationAdminForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = "__all__"
        widgets = {
            # Para permitir mostrar "$ 1.234.567" en el admin
            "valor": forms.TextInput(attrs={"inputmode": "numeric"}),
        }

    def clean_valor(self):
        valor = self.cleaned_data.get("valor")

        # Si llega como texto con $ y puntos, lo limpiamos
        if isinstance(valor, str):
            valor = (
                valor.replace("$", "")
                     .replace(".", "")
                     .replace(" ", "")
                     .strip()
            )
            valor = valor or "0"

        return valor


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    form = QuotationAdminForm

    list_display = (
        "numero_cotizacion",
        "nombre_cotizacion",
        "cliente",
        "campo",
        "fecha_cotizacion",
        "estado",
        "empresa",
        "valor",  # (Opcional) si quieres verlo en la lista, puedes quitarlo si no lo deseas
        "actualizado_en",
    )
    search_fields = ("numero_cotizacion", "nombre_cotizacion", "cliente", "campo")
    list_filter = ("estado", "empresa", "fecha_cotizacion")

    class Media:
        js = ("quotes/js/valor_format.js",)

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []

        # Solo Comercial edita
        if request.user.groups.filter(name="Comercial").exists():
            return ["creado_en", "actualizado_en"]

        # Otros grupos: todo solo lectura
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name="Comercial").exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name="Comercial").exists()

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False