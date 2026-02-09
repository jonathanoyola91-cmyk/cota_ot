from django.contrib import admin, messages
from django.db import models
from django.urls import reverse
from django.utils.html import format_html

from .models import Supplier, PurchaseRequest, PurchaseLine


def es_compras(user):
    return user.is_superuser or user.groups.filter(name__iexact="Compras").exists()


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("nombre", "contacto", "telefono", "email")
    search_fields = ("nombre",)

    def has_change_permission(self, request, obj=None):
        return es_compras(request.user)

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0

    fields = (
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_disponible",
        "cantidad_a_comprar",
        "proveedor",
        "precio_unitario",
        "observaciones_compras",
    )

    readonly_fields = (
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_a_comprar",
    )

    # ✅ Observaciones compactas (1 línea)
    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(
                attrs={"rows": 1, "style": "width:180px; resize:horizontal;"}
            )
        }
    }

    def has_change_permission(self, request, obj=None):
        return es_compras(request.user)

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def get_readonly_fields(self, request, obj=None):
        # Admin/Compras: solo bloquea los calculados/base
        if es_compras(request.user):
            return self.readonly_fields
        # Otros: todo readonly
        return [f.name for f in self.model._meta.fields]


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("bom", "estado", "creado_por", "actualizado_en", "pdf")
    list_filter = ("estado",)
    search_fields = ("bom__workorder__numero", "bom__template__nombre")
    inlines = [PurchaseLineInline]

    def pdf(self, obj):
        url = reverse("purchase_request_pdf", args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank">PDF</a>', url)

    pdf.short_description = "Imprimir"

    actions = ["marcar_en_revision", "cerrar_solicitud"]

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        # ✅ Permite edición a Compras (si no está cerrada)
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name__iexact="Compras").exists():
            if obj and obj.estado == "CERRADA":
                return False
            return True
        return False

    def has_add_permission(self, request):
        # se crea desde BOM
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []

        if request.user.groups.filter(name__iexact="Compras").exists():
            if obj and obj.estado == "CERRADA":
                return [f.name for f in self.model._meta.fields]
            # deja editable estado y líneas
            return ("bom", "creado_por", "creado_en", "actualizado_en")

        return [f.name for f in self.model._meta.fields]

    @admin.action(description="Marcar como EN REVISIÓN")
    def marcar_en_revision(self, request, queryset):
        if not es_compras(request.user):
            messages.error(request, "No tienes permisos para esta acción.")
            return
        updated = queryset.update(estado="EN_REVISION")
        messages.success(request, f"{updated} solicitud(es) en revisión.")

    @admin.action(description="Cerrar solicitud de compra")
    def cerrar_solicitud(self, request, queryset):
        if not es_compras(request.user):
            messages.error(request, "No tienes permisos para esta acción.")
            return
        cerradas = 0
        for req in queryset:
            if req.estado != "CERRADA":
                req.estado = "CERRADA"
                req.save(update_fields=["estado"])
                cerradas += 1
        messages.success(request, f"{cerradas} solicitud(es) cerradas.")
