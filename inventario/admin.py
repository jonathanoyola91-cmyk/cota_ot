from django.contrib import admin, messages
from django.db import models
from django.utils import timezone

from .models import InventoryReception, InventoryReceptionLine


class InventoryReceptionLineInline(admin.TabularInline):
    model = InventoryReceptionLine
    extra = 0

    fields = (
        "purchase_line",
        "cantidad_esperada",
        "cantidad_recibida",
        "fecha_llegada",
        "estado",
        "observacion_inventario",
    )

    readonly_fields = ("purchase_line", "cantidad_esperada")

    formfield_overrides = {
        models.TextField: {"widget": admin.widgets.AdminTextareaWidget(attrs={
            "rows": 1,
            "style": "width:220px; resize:horizontal;"
        })},
    }

    def get_readonly_fields(self, request, obj=None):
        # Admin: puede todo excepto lo fijo
        if request.user.is_superuser:
            return self.readonly_fields

        # Inventario: puede editar recibido/fecha/estado/obs (no puede tocar esperado)
        if request.user.groups.filter(name="Inventario").exists():
            return self.readonly_fields

        # Otros: todo solo lectura
        return [f.name for f in self.model._meta.fields]


@admin.register(InventoryReception)
class InventoryReceptionAdmin(admin.ModelAdmin):
    list_display = ("purchase_request", "creado_por", "actualizado_en")
    search_fields = (
        "purchase_request__bom__workorder__numero",
        "purchase_request__paw_numero",
        "purchase_request__paw_nombre",
    )
    inlines = [InventoryReceptionLineInline]

    actions = ["cerrar_paw_si_listo"]

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        if request.user.groups.filter(name="Inventario").exists():
            return ["creado_por", "creado_en", "actualizado_en"]
        return [f.name for f in self.model._meta.fields]

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Cerrar PAW (solo si todo está LISTO)")
    def cerrar_paw_si_listo(self, request, queryset):
        cerrados = 0
        for rec in queryset:
            if rec.lineas.filter(estado="PENDIENTE").exists():
                continue

            pr = rec.purchase_request
            bom = pr.bom
            wo = bom.workorder
            paw = getattr(wo, "paw", None)

            if paw:
                # Ajusta aquí el valor exacto de tu campo "estado_paw"
                paw.estado_paw = "TERMINADO"
                paw.save(update_fields=["estado_paw"])

            # Opcional: cerrar también la solicitud de compra
            if pr.estado != "CERRADA":
                pr.estado = "CERRADA"
                pr.save(update_fields=["estado"])

            cerrados += 1

        messages.success(request, f"Se cerraron {cerrados} PAW(s). (Solo los que estaban 100% LISTO)")
