from django.contrib import admin
from .models import Item

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    search_fields = ("codigo", "descripcion")
    list_display = ("codigo", "descripcion", "activo")
    list_filter = ("activo", "clasificacion", "grupo_inventario")
