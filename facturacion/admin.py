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
        "tipo_pago",
        "precio",
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

    # --- Campos de PAW solo lectura (siempre) ---
    readonly_fields = ("paw",)

    # ---- Helpers para “arrastrar” datos del PAW ----
    def get_numero_paw(self, obj): return obj.paw.numero_paw
    get_numero_paw.short_description = "Número PAW"

    def get_nombre_paw(self, obj): return obj.paw.nombre_paw
    get_nombre_paw.short_description = "Nombre PAW"

    def get_cliente(self, obj): return obj.paw.cliente
    get_cliente.short_description = "Cliente"

    def get_campo(self, obj): return obj.paw.campo
    get_campo.short_description = "Campo"

    # ---- Control de campos por rol ----
    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))

        if request.user.is_superuser:
            return ro  # superuser edita todo (excepto paw)

        es_facturacion = request.user.groups.filter(name="Facturacion").exists()
        es_paw = request.user.groups.filter(name="Paw").exists()

        # Si es Facturación: bloquear campos que son del PAW admin
        if es_facturacion and not es_paw:
            ro += ["municipio", "numero_servicio"]
            return ro

        # Si es PAW: bloquear campos de facturación + estado
        if es_paw and not es_facturacion:
            ro += [
                "numero_factura",
                "fecha_vencimiento",
                "fecha_radicacion",
                "tipo_pago",
                "precio",
                "estado",
            ]
            return ro

        # Si está en ambos grupos o ninguno: bloquear todo lo sensible
        ro += [
            "municipio", "numero_servicio",
            "numero_factura", "fecha_vencimiento", "fecha_radicacion",
            "tipo_pago", "precio", "estado"
        ]
        return ro

    # (Opcional) Evitar “Add” manual si quieres que solo se cree desde PAW
    def has_add_permission(self, request):
        return request.user.is_superuser
