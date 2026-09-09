from django.contrib import admin
from .models import MovimientoSistema


@admin.register(MovimientoSistema)
class MovimientoSistemaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "paw_numero",
        "modulo",
        "accion",
        "usuario",
        "objeto_tipo",
        "objeto_id",
    )
    list_filter = ("modulo", "accion", "fecha")
    search_fields = (
        "paw_numero",
        "accion",
        "descripcion",
        "usuario__username",
        "usuario__first_name",
        "usuario__last_name",
    )
    readonly_fields = (
        "fecha",
        "paw_numero",
        "modulo",
        "accion",
        "descripcion",
        "usuario",
        "objeto_tipo",
        "objeto_id",
        "datos_anteriores",
        "datos_nuevos",
        "ip",
        "user_agent",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
