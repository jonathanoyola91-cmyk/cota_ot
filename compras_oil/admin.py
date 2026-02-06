from django.contrib import admin, messages
from .models import Supplier, PurchaseRequest, PurchaseLine


# ---------------- PROVEEDORES ----------------

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("nombre", "contacto", "telefono", "email")
    search_fields = ("nombre",)


# ---------------- LINEAS DE COMPRA ----------------

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

    def get_readonly_fields(self, request, obj=None):
        # Solo Compras y Admin pueden editar disponibilidad/precio
        if request.user.is_superuser or request.user.groups.filter(name="Compras").exists():
            return (
                "codigo",
                "descripcion",
                "unidad",
                "cantidad_requerida",
                "cantidad_a_comprar",
            )

        # Otros grupos: todo bloqueado
        return [f.name for f in self.model._meta.fields]


# ---------------- SOLICITUD DE COMPRA ----------------

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("bom", "estado", "creado_por", "actualizado_en")
    list_filter = ("estado",)
    search_fields = ("bom__workorder__numero", "bom__template__nombre")
    inlines = [PurchaseLineInline]

    actions = ["marcar_en_revision", "cerrar_solicitud"]

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []

        # Compras puede trabajar mientras no esté cerrada
        if request.user.groups.filter(name="Compras").exists():
            if obj and obj.estado == "CERRADA":
                return [f.name for f in self.model._meta.fields]
            return []

        # Otros grupos: solo lectura
        return [f.name for f in self.model._meta.fields]

    @admin.action(description="Marcar como EN REVISIÓN")
    def marcar_en_revision(self, request, queryset):
        updated = queryset.update(estado="EN_REVISION")
        messages.success(request, f"{updated} solicitud(es) en revisión.")

    @admin.action(description="Cerrar solicitud de compra")
    def cerrar_solicitud(self, request, queryset):
        cerradas = 0
        for req in queryset:
            if req.estado != "CERRADA":
                req.estado = "CERRADA"
                req.save()
                cerradas += 1
        messages.success(request, f"{cerradas} solicitud(es) cerradas.")
