from django.contrib import admin
from .models import Factura


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    list_display = (
        "estado",
        "numero_factura",
        "get_numero_paw",
        "get_nombre_paw",
        "get_cliente",
        "get_campo",
        "municipio",
        "numero_servicio",
        "precio",
        "tipo_pago",
        "fecha_radicacion",
        "fecha_vencimiento",
    )

    search_fields = (
        "numero_factura",
        "numero_servicio",
        "municipio",
        "paw__numero_paw",
        "paw__nombre_paw",
        "paw__cliente",
        "paw__campo",
    )

    list_filter = ("estado", "tipo_pago", "fecha_radicacion", "fecha_vencimiento", "municipio")

    readonly_fields = ("paw",)

    def _es_finanzas(self, request):
        return request.user.groups.filter(name="FINANZAS").exists()

    # ---- Datos arrastrados desde PAW ----
    def get_numero_paw(self, obj): return obj.paw.numero_paw
    get_numero_paw.short_description = "Número PAW"

    def get_nombre_paw(self, obj): return obj.paw.nombre_paw
    get_nombre_paw.short_description = "Nombre PAW"

    def get_cliente(self, obj): return obj.paw.cliente
    get_cliente.short_description = "Cliente"

    def get_campo(self, obj): return obj.paw.campo
    get_campo.short_description = "Campo"

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))

        # Campos que SOLO FINANZAS debe editar
        solo_finanzas = [
            "numero_factura",
            "fecha_vencimiento",
            "fecha_radicacion",
            "tipo_pago",
            "estado",
        ]

        # Campos que SOLO PAW debe editar
        solo_paw = [
            "municipio",
            "numero_servicio",
        ]

        # Superuser: todo (excepto paw)
        if request.user.is_superuser:
            return ro

        # FINANZAS: no edita municipio/servicio
        if self._es_finanzas(request):
            return ro + solo_paw

        # PAW / NO FINANZAS:
        # bloquea lo financiero EXCEPTO precio
        return ro + solo_finanzas

    # Opcional: evitar crear facturas manualmente
    def has_add_permission(self, request):
        return request.user.is_superuser
