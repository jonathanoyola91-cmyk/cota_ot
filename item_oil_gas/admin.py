from django.contrib import admin

from .models import Item, ItemImpetus


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "descripcion",
        "unidad_medida",
        "clasificacion",
        "grupo_inventario",
        "activo",
    )

    search_fields = (
        "codigo",
        "descripcion",
        "clasificacion",
        "grupo_inventario",
    )

    list_filter = (
        "activo",
        "clasificacion",
        "grupo_inventario",
    )

    ordering = (
        "codigo",
    )

    fields = (
        "codigo",
        "descripcion",
        "unidad_medida",
        "clasificacion",
        "grupo_inventario",
        "activo",
    )


@admin.register(ItemImpetus)
class ItemImpetusAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "descripcion",
        "unidad_medida",
        "clasificacion",
        "grupo_inventario",
        "activo",
    )

    search_fields = (
        "codigo",
        "descripcion",
        "clasificacion",
        "grupo_inventario",
    )

    list_filter = (
        "activo",
        "clasificacion",
        "grupo_inventario",
    )

    ordering = (
        "codigo",
    )

    fields = (
        "codigo",
        "descripcion",
        "unidad_medida",
        "clasificacion",
        "grupo_inventario",
        "activo",
    )