from django.contrib import admin, messages
from django.utils import timezone
from django.db import models

from .models import BomTemplate, BomTemplateItem, Bom, BomItem
from compras_oil.models import PurchaseRequest, PurchaseLine

admin.site.site_header = "IMPETUS CONTROL"
admin.site.site_title = "Sistema BOM"
admin.site.index_title = "Control Impetus"


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

    # Taller no debe modificar estándar
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

    def has_change_permission(self, request, obj=None):
        """
        OJO: aquí `obj` es el BOM padre (en inline). Si ya está en SOLICITUD,
        Taller no puede modificar los items.
        """
        if obj and obj.estado == "SOLICITUD" and request.user.groups.filter(name="Taller").exists():
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and obj.estado == "SOLICITUD" and request.user.groups.filter(name="Taller").exists():
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.estado == "SOLICITUD" and request.user.groups.filter(name="Taller").exists():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Bom)
class BomAdmin(admin.ModelAdmin):
    list_display = ("paw_numero", "paw_nombre", "workorder", "template", "estado", "actualizado_en")
    list_filter = ("estado", "template")
    search_fields = (
        "workorder__numero",
        "workorder__titulo",
        "template__nombre",
        "workorder__paw__numero_paw",
        "workorder__paw__nombre_paw",
    )
    inlines = [BomItemInline]

    actions = ["cargar_desde_plantilla", "solicitud_inventario"]

    @admin.display(description="PAW #")
    def paw_numero(self, obj):
        paw = getattr(obj.workorder, "paw", None)
        return getattr(paw, "numero_paw", "-") if paw else "-"

    @admin.display(description="PAW Nombre")
    def paw_nombre(self, obj):
        paw = getattr(obj.workorder, "paw", None)
        return getattr(paw, "nombre_paw", "-") if paw else "-"

    def has_change_permission(self, request, obj=None):
        perm = super().has_change_permission(request, obj)
        if not perm:
            return False

        # Taller NO puede editar el BOM después de solicitud
        if obj and obj.estado == "SOLICITUD" and request.user.groups.filter(name="Taller").exists():
            return False

        return True

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
                bom.save(update_fields=["estado", "solicitado_en", "actualizado_en"])

            # Crear / obtener solicitud compra
            pr, _ = PurchaseRequest.objects.get_or_create(
                bom=bom,
                defaults={"estado": "BORRADOR", "creado_por": request.user},
            )

            # Guardar PAW en encabezado del PurchaseRequest
            paw = getattr(bom.workorder, "paw", None)
            if paw:
                pr.paw_numero = paw.numero_paw
                pr.paw_nombre = paw.nombre_paw
                pr.save(update_fields=["paw_numero", "paw_nombre"])

            # Crear / actualizar líneas (sin tocar lo que Compras haya llenado)
            for it in bom.items.all():
                line, created = PurchaseLine.objects.get_or_create(
                    request=pr,
                    codigo=(it.codigo or ""),
                    descripcion=it.descripcion,
                    plano=(getattr(it, "plano", "") or ""),
                    defaults={
                        "unidad": getattr(it, "unidad", "") or "",
                        "cantidad_requerida": getattr(it, "cantidad_solicitada", 0) or 0,
                        "observaciones_bom": getattr(it, "observaciones", "") or "",
                    },
                )

                if not created:
                    line.cantidad_requerida = getattr(it, "cantidad_solicitada", 0) or 0
                    line.observaciones_bom = getattr(it, "observaciones", "") or ""
                    line.save(update_fields=["cantidad_requerida", "observaciones_bom"])

            updated += 1

        messages.success(request, f"{updated} BOM(s) enviados a Compras.")

    def get_readonly_fields(self, request, obj=None):
        if not obj:
            return []

        # Superuser puede editar si necesita (opcional)
        if request.user.is_superuser:
            return []

        # Cuando ya es solicitud, se bloquea edición del encabezado para Taller
        if obj.estado == "SOLICITUD" and request.user.groups.filter(name="Taller").exists():
            return [f.name for f in self.model._meta.fields]

        return []
