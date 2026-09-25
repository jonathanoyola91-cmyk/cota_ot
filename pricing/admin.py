from django.contrib import admin
from .models import PriceCalculation, PriceCalculationLine
class LineInline(admin.TabularInline):
    model=PriceCalculationLine; extra=0
@admin.register(PriceCalculation)
class PriceCalculationAdmin(admin.ModelAdmin):
    list_display=('id','item_venta','estado','gm','precio_comercial','creado_en','publicado_en'); list_filter=('estado',); search_fields=('item_venta__codigo','item_venta__descripcion'); inlines=[LineInline]
