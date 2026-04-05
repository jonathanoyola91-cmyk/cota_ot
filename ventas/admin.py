from django.contrib import admin
from .models import PeriodoVenta, Venta


class VentaInline(admin.TabularInline):
    model = Venta
    extra = 1
    fields = (
        "cliente",
        "tipo_prenda",
        "costo",
        "precio",
        "status",
        "valor_abonado",
        "valor_deber",
        "fecha",
    )
    readonly_fields = ("valor_deber", "fecha")


@admin.register(PeriodoVenta)
class PeriodoVentaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "anio", "mes", "total_ventas")
    ordering = ("-anio", "-mes")
    inlines = [VentaInline]

    def total_ventas(self, obj):
        return obj.ventas.count()
    total_ventas.short_description = "Cantidad ventas"


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "cliente",
        "tipo_prenda",
        "periodo",
        "precio",
        "status",
        "valor_abonado",
        "valor_deber",
        "fecha",
    )
    list_filter = ("status", "periodo__anio", "periodo__mes")
    search_fields = ("cliente", "tipo_prenda")