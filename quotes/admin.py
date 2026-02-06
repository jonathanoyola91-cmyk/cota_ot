from django.contrib import admin
from .models import Quotation

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "numero_cotizacion",
        "nombre_cotizacion",
        "cliente",
        "campo",
        "fecha_cotizacion",
        "estado",
        "empresa",
        "actualizado_en",
    )
    search_fields = ("numero_cotizacion", "nombre_cotizacion", "cliente", "campo")
    list_filter = ("estado", "empresa", "fecha_cotizacion")

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
