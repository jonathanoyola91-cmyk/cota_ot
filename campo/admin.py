from django.contrib import admin
from .models import FieldService, FieldServiceDailyExpense, FieldServiceBonusClaim


class FieldServiceDailyExpenseInline(admin.TabularInline):
    model = FieldServiceDailyExpense
    extra = 0
    readonly_fields = ["total_dia"]


@admin.register(FieldService)
class FieldServiceAdmin(admin.ModelAdmin):
    list_display = ["paw", "estado", "fecha_inicio", "fecha_fin", "responsable", "total_gastos"]
    list_filter = ["estado", "fecha_inicio"]
    search_fields = ["paw__numero_paw", "paw__cliente", "paw__campo"]
    inlines = [FieldServiceDailyExpenseInline]


@admin.register(FieldServiceDailyExpense)
class FieldServiceDailyExpenseAdmin(admin.ModelAdmin):
    list_display = ["servicio", "fecha", "dia_numero", "personas", "total_dia"]
    list_filter = ["fecha"]
    search_fields = ["servicio__paw__numero_paw", "observaciones"]
    readonly_fields = ["alimentacion_total", "hidratacion_total", "total_vuelos", "total_dia"]


@admin.register(FieldServiceBonusClaim)
class FieldServiceBonusClaimAdmin(admin.ModelAdmin):
    list_display = ["fecha", "servicio", "tecnico_nombre", "rol", "estado"]
    list_filter = ["estado", "rol", "fecha"]
    search_fields = ["tecnico_nombre", "servicio__paw__numero_paw"]
