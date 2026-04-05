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
    list_display = (
        "__str__",
        "anio",
        "mes",
        "cantidad_ventas",
        "ver_total_ventas",
        "ver_total_costos",
        "ver_total_abonado",
        "ver_total_por_cobrar",
        "ver_utilidad_bruta",
    )
    ordering = ("-anio", "-mes")
    inlines = [VentaInline]

    def cantidad_ventas(self, obj):
        return obj.ventas.count()
    cantidad_ventas.short_description = "Cant. ventas"

    def ver_total_ventas(self, obj):
        return obj.total_ventas_valor()
    ver_total_ventas.short_description = "Total vendido"

    def ver_total_costos(self, obj):
        return obj.total_costos()
    ver_total_costos.short_description = "Total costos"

    def ver_total_abonado(self, obj):
        return obj.total_abonado()
    ver_total_abonado.short_description = "Total abonado"

    def ver_total_por_cobrar(self, obj):
        return obj.total_por_cobrar()
    ver_total_por_cobrar.short_description = "Saldo pendiente"

    def ver_utilidad_bruta(self, obj):
        return obj.utilidad_bruta()
    ver_utilidad_bruta.short_description = "Utilidad bruta"


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "cliente",
        "tipo_prenda",
        "periodo",
        "costo",
        "precio",
        "status",
        "valor_abonado",
        "valor_deber",
        "fecha",
    )
    list_filter = ("status", "periodo__anio", "periodo__mes")
    search_fields = ("cliente", "tipo_prenda")