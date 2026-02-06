from django.contrib import admin, messages
from django.utils import timezone
from django.db import models

from .models import BomTemplate, BomTemplateItem, Bom, BomItem
from compras_oil.models import PurchaseRequest, PurchaseLine


# --------- Templates (Base de datos) ---------

class BomTemplateItemInline(admin.TabularInline):
    model = BomTemplateItem
    extra = 1
    fields = ("plano", "codigo", "descripcion", "unidad", "cantidad_estandar", "observaciones")

    formfield_overrides = {
        models.TextField: {"widget": admin.widgets.AdminTextareaWidget(attrs={
            "rows": 1,
            "style": "width:200px; resize:horizontal;"
        })},
    }

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "codigo":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:90px;"})
        elif db_field.name == "unidad":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:60px; text-align:center;"})
        elif db_field.name == "plano":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:90px;"})
        elif db_field.name == "descripcion":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:320px;"})
        elif db_field.name == "cantidad_estandar":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:70px; text-align:right;"})

        return super().formfield_for_dbfield(db_field, **kwargs)


@admin.register(BomTemplate)
class BomTemplateAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)
    inlines = [BomTemplateItemInline]


# --------- BOM por OT (Taller) ---------

class BomItemInline(admin.TabularInline):
    model = BomItem
    extra = 0

    readonly_fields = ("cantidad_estandar",)

    fields = (
        "plano",
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_estandar",
        "cantidad_solicitada",
        "observaciones",
    )

    formfield_overrides = {
        models.TextField: {"widget": admin.widgets.AdminTextareaWidget(attrs={
            "rows": 1,
            "style": "width:160px; resize:horizontal;"
        })},
    }

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "codigo":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:70px;"})
        elif db_field.name == "unidad":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:45px; text-align:center;"})
        elif db_field.name == "plano":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:70px;"})
        elif db_field.name == "descripcion":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:240px;"})
        elif db_field.name == "cantidad_solicitada":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(attrs={"style": "width:50px; text-align:right;"})

        return super().formfield_for_dbfield(db_field, **kwargs)


@admin.register(Bom)
class BomAdmin(admin.ModelAdmin):
    list_display = ("workorder", "template", "estado", "actualizado_en")
    list_filter = ("estado", "template")
    search_fields = ("workorder__numero", "workorder__titulo", "template__nombre")
    inlines = [BomItemInline]

    actions = ["cargar_desde_plantilla", "solicitud_inventario"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Auto-cargar items al guardar BOM por primera vez (si está vacío)
        if obj.items.exists():
            return
        if not obj.template:
            return

        for it in obj.template.items.all():
            BomItem.objects.create(
                bom=obj,
                plano=getattr(it, "plano", ""),
                codigo=getattr(it, "codigo", ""),
                descripcion=it.descripcion,
                unidad=getattr(it, "unidad", ""),
                cantidad_estandar=getattr(it, "cantidad_estandar", 0) or 0,
                cantidad_solicitada=getattr(it, "cantidad_estandar", 0) or 0,
                observaciones=getattr(it, "observaciones", ""),
            )

    @admin.action(description="Cargar items desde plantilla (solo si está vacío)")
    def cargar_desde_plantilla(self, request, queryset):
        count = 0
        for bom in queryset:
            if not bom.template:
                continue
            if bom.items.exists():
                continue

            for it in bom.template.items.all():
                BomItem.objects.create(
                    bom=bom,
                    plano=getattr(it, "plano", ""),
                    codigo=getattr(it, "codigo", ""),
                    descripcion=it.descripcion,
                    unidad=getattr(it, "unidad", ""),
                    cantidad_estandar=getattr(it, "cantidad_estandar", 0) or 0,
                    cantidad_solicitada=getattr(it, "cantidad_estandar", 0) or 0,
                    observaciones=getattr(it, "observaciones", ""),
                )
            count += 1

        messages.success(request, f"Plantilla cargada en {count} BOM(s).")

    @admin.action(description="Solicitud Inventario (marcar y enviar a Compras)")
    def solicitud_inventario(self, request, queryset):
        updated = 0

        for bom in queryset:
            # Marcar como solicitud si no lo está
            if bom.estado != "SOLICITUD":
                bom.estado = "SOLICITUD"
                bom.solicitado_en = timezone.now()
                bom.save()

            # Crear / obtener solicitud compra
            pr, _ = PurchaseRequest.objects.get_or_create(
                bom=bom,
                defaults={"estado": "BORRADOR", "creado_por": request.user},
            )

            # Crear / actualizar líneas
            for it in bom.items.all():
                line, created = PurchaseLine.objects.get_or_create(
                    request=pr,
                    codigo=(it.codigo or ""),
                    descripcion=it.descripcion,
                    plano=(getattr(it, "plano", "") or ""),
                    defaults={
                        "unidad": getattr(it, "unidad", "") or "",
                        "cantidad_requerida": getattr(it, "cantidad_solicitada", 0) or 0,
                    },
                )
                if not created:
                    line.cantidad_requerida = getattr(it, "cantidad_solicitada", 0) or 0
                    line.save(update_fields=["cantidad_requerida"])

            updated += 1

        messages.success(request, f"{updated} BOM(s) enviados a Compras.")


    def get_readonly_fields(self, request, obj=None):
        if not obj:
            return []
        # Cuando ya es solicitud, se bloquea edición del encabezado del BOM
        if obj.estado == "SOLICITUD":
            return [f.name for f in self.model._meta.fields]
        return []
