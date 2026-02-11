from django.contrib import admin, messages
from django.db import models
from django.utils import timezone

from .models import Supplier, PurchaseRequest, PurchaseLine
from inventario.models import InventoryReception, InventoryReceptionLine


# ---------------- PROVEEDORES ----------------

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "nit",
        "banco",
        "cuenta_bancaria",
        "tipo_cuenta",
        "contacto",
        "telefono",
        "email",
    )
    search_fields = ("nombre", "nit", "banco")


# ---------------- LINEAS DE COMPRA (INLINE) ----------------

class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 0
    can_delete = False

    fields = (
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_disponible",
        "cantidad_a_comprar",
        "tipo_pago",
        "proveedor",
        "precio_unitario",
        "observaciones_bom",
        "observaciones_compras",
    )

    readonly_fields = (
        "codigo",
        "descripcion",
        "unidad",
        "cantidad_requerida",
        "cantidad_a_comprar",
        "observaciones_bom",
    )

    formfield_overrides = {
        models.TextField: {
            "widget": admin.widgets.AdminTextareaWidget(
                attrs={"rows": 1, "style": "width:220px; resize:horizontal;"}
            )
        }
    }

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == "codigo":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:90px;"}
            )
        elif db_field.name == "unidad":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:60px; text-align:center;"}
            )
        elif db_field.name in ("cantidad_requerida", "cantidad_disponible", "cantidad_a_comprar"):
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:70px; text-align:right;"}
            )
        elif db_field.name == "precio_unitario":
            kwargs["widget"] = admin.widgets.AdminTextInputWidget(
                attrs={"style": "width:90px; text-align:right;"}
            )
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Importante: si el usuario NO tiene change perm del modelo, Django lo deja read-only.
    # Aquí no forzamos visibilidad del módulo, solo controlamos qué queda readonly.
    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return self.readonly_fields

        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            return self.readonly_fields

        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------- SOLICITUD DE COMPRA ----------------

@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "paw_nombre",
        "bom",
        "estado",
        "tipo_pago",
        "creado_por",
        "actualizado_en",
    )

    list_filter = ("estado", "tipo_pago")

    search_fields = (
        "bom__workorder__numero",
        "bom__template__nombre",
        "paw_numero",
        "paw_nombre",
    )

    inlines = [PurchaseLineInline]

    actions = [
        "marcar_en_revision",
        "cerrar_solicitud",
        "enviar_a_finanzas",
        "enviar_a_inventario",
    ]

    readonly_fields = (
        "creado_por",
        "creado_en",
        "actualizado_en",
        "paw_numero",
        "paw_nombre",
    )

    @admin.display(description="PAW Número")
    def paw_numero(self, obj):
        return obj.paw_numero or "-"

    @admin.display(description="PAW Nombre")
    def paw_nombre(self, obj):
        return obj.paw_nombre or "-"

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return list(self.readonly_fields)

        if request.user.groups.filter(name="COMPRAS_OIL").exists():
            # ✅ Compras puede editar siempre (excepto readonly_fields base)
            return list(self.readonly_fields)

        return [f.name for f in self.model._meta.fields]

    def save_model(self, request, obj, form, change):
        if not obj.creado_por:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    # ---------------- ACCIONES ----------------

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
                req.save(update_fields=["estado", "actualizado_en"])
                cerradas += 1
        messages.success(request, f"{cerradas} solicitud(es) cerradas.")

    @admin.action(description="Enviar a Finanzas")
    def enviar_a_finanzas(self, request, queryset):
        if not (
            request.user.is_superuser
            or request.user.groups.filter(name="COMPRAS_OIL").exists()
        ):
            messages.error(request, "No tienes permisos para enviar solicitudes a Finanzas.")
            return

        try:
            from finanzas.models import FinanceApproval
        except Exception as e:
            messages.error(request, f"No se pudo importar finanzas.FinanceApproval. Error: {e}")
            return

        enviados = 0
        for pr in queryset:
            fa, created = FinanceApproval.objects.get_or_create(
                purchase_request=pr,
                defaults={
                    "estado": FinanceApproval.Estado.PENDIENTE,
                    "enviado_por": request.user,
                    "enviado_en": timezone.now(),
                },
            )

            if not created:
                fa.estado = FinanceApproval.Estado.PENDIENTE
                fa.enviado_por = request.user
                fa.enviado_en = timezone.now()
                fa.save(update_fields=["estado", "enviado_por", "enviado_en", "actualizado_en"])

            enviados += 1

        messages.success(request, f"{enviados} solicitud(es) enviadas a Finanzas.")

    @admin.action(description="Enviar a Inventario (crear recepción por línea)")
    def enviar_a_inventario(self, request, queryset):
        if not (
            request.user.is_superuser
            or request.user.groups.filter(name="COMPRAS_OIL").exists()
        ):
            messages.error(request, "No tienes permisos para enviar solicitudes a Inventario.")
            return

        enviados = 0
        for pr in queryset:
            recepcion, _ = InventoryReception.objects.get_or_create(
                purchase_request=pr,
                defaults={"creado_por": request.user},
            )

            for line in pr.lineas.all():
                InventoryReceptionLine.objects.get_or_create(
                    recepcion=recepcion,
                    purchase_line=line,
                    defaults={
                        "cantidad_esperada": line.cantidad_a_comprar or 0,
                        "cantidad_recibida": 0,
                        "estado": "PENDIENTE",
                    },
                )

            enviados += 1

        messages.success(request, f"Enviadas {enviados} solicitud(es) a Inventario.")
