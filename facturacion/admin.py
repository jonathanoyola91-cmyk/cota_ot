from django.contrib import admin
from .models import Factura


@admin.register(Factura)
class FacturaAdmin(admin.ModelAdmin):
    autocomplete_fields = ("item_factura",)

    list_display = (
        "estado",
        "numero_factura",
        "get_numero_paw",
        "get_nombre_paw",
        "get_cliente",
        "get_campo",
        "lugar_entrega",     # ✅ antes municipio
        "lugar_servicio",
        "numero_servicio",
        "get_item_codigo",
        "get_item_descripcion",
        "precio",
        "tipo_pago",
        "fecha_radicacion",
        "fecha_vencimiento",
    )

    search_fields = (
        "numero_factura",
        "numero_servicio",
        "lugar_entrega",
        "lugar_servicio",
        "paw__numero_paw",
        "paw__nombre_paw",
        "paw__cliente",
        "paw__campo",
        "item_factura__codigo",
        "item_factura__descripcion",
    )

    list_filter = (
        "estado",
        "tipo_pago",
        "fecha_radicacion",
        "fecha_vencimiento",
        "lugar_entrega",     # ✅ antes municipio
    )

    readonly_fields = ("paw",)

    def _es_finanzas(self, request):
        return request.user.groups.filter(name="FINANZAS").exists()

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))

        # SOLO FINANZAS
        solo_finanzas = [
            "numero_factura",
            "fecha_vencimiento",
            "fecha_radicacion",
            "tipo_pago",
            "estado",
        ]

        # SOLO PAW (NO FINANZAS)
        solo_paw = [
            "lugar_entrega",
            "lugar_servicio",
            "numero_servicio",
            "item_factura",
        ]

        if request.user.is_superuser:
            return ro

        if self._es_finanzas(request):
            # Finanzas NO edita lo operativo
            return ro + solo_paw

        # PAW/NO FINANZAS no edita lo financiero (pero sí precio)
        return ro + solo_finanzas

    # --- Datos arrastrados desde PAW ---
    def get_numero_paw(self, obj): return obj.paw.numero_paw
    get_numero_paw.short_description = "Número PAW"

    def get_nombre_paw(self, obj): return obj.paw.nombre_paw
    get_nombre_paw.short_description = "Nombre PAW"

    def get_cliente(self, obj): return obj.paw.cliente
    get_cliente.short_description = "Cliente"

    def get_campo(self, obj): return obj.paw.campo
    get_campo.short_description = "Campo"

    # --- Item factura (codigo/descripcion) ---
    def get_item_codigo(self, obj):
        return obj.item_factura.codigo if obj.item_factura else ""
    get_item_codigo.short_description = "Código item"

    def get_item_descripcion(self, obj):
        return obj.item_factura.descripcion if obj.item_factura else ""
    get_item_descripcion.short_description = "Descripción item"
