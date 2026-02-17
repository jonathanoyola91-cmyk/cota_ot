from django.contrib import admin
from .models import Item

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("codigo", "descripcion", "unidad_medida", "clasificacion", "grupo_inventario", "activo")
    search_fields = ("codigo", "descripcion", "grupo_inventario")
    list_filter = ("clasificacion", "activo")