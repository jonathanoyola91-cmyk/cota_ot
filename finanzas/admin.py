from django.contrib import admin, messages
from django.utils import timezone
from django.db import models
from django.forms import Textarea
from django.utils.formats import number_format

from .models import FinanceApproval, FinanceApprovalLine


# ======================================================
# UTILIDAD: sincronizar líneas CONTADO desde Compras
# ======================================================

def sync_finance_lines(approval: FinanceApproval):
    pr = approval.purchase_request
    contado_qs = pr.lineas.filter(tipo_pago="CONTADO")

    for pl in contado_qs:
        FinanceApprovalLine.objects.get_or_create(
            approval=approval,
            purchase_line=pl,
        )


# ======================================================
# INLINE: Líneas financieras
# ======================================================

class FinanceApprovalLineInline(admin.TabularInline):
    model = FinanceApprovalLine
    extra = 0
    can_delete = False

    # ----------------------------------------------
    # Nota admin en 2 renglones (control de ancho)
    # ----------------------------------------------
    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(attrs={
                "rows": 2,
                "style": "width: 420px; max-width: 420px;",
            })
        }
    }

    # ----------------------------------------------
    # Columnas del inline
    # ----------------------------------------------
    fields = (
        "purchase_line",
        "proveedor",
        "precio",
        "decision",
        "scheduled_date",
        "nota_admin",
        "decidido_por",
        "decidido_en",
        "pagado",
        "pagado_en",
        "pagado_por",
    )

    readonly_fields = (
        "purchase_line",
        "proveedor",
        "precio",
        "decidido_por",
        "decidido_en",
        "pagado_en",
        "pagado_por",
    )

    # ----------------------------------------------
    # Columnas calculadas
    # ----------------------------------------------

    @admin.display(description="Proveedor")
    def proveedor(self, obj: FinanceApprovalLine):
        pl = obj.purchase_line

        # Campo típico en compras
        value = (
            getattr(pl, "proveedor", None)
            or getattr(pl, "supplier", None)
            or getattr(pl, "vendor", None)
        )

        return str(value) if value else "-"

    @admin.display(description="Precio unitario")
    def precio(self, obj: FinanceApprovalLine):
        """
        Lee el PRECIO UNITARIO real desde PurchaseLine,
        incluso si el nombre del campo cambia.
        """
        pl = obj.purchase_line

        # 1) Intentos directos (casos más comunes)
        for name in (
            "precio_unitario",
            "precio_unit",
            "valor_unitario",
            "unit_price",
        ):
            if hasattr(pl, name):
                val = getattr(pl, name)
                if callable(val):
                    try:
                        val = val()
                    except TypeError:
                        pass

                if val not in (None, ""):
                    return number_format(val, decimal_pos=2, force_grouping=True)

        # 2) Búsqueda automática en campos reales del modelo
        for field in pl._meta.fields:
            fname = field.name.lower()
            if "precio" in fname and ("unit" in fname or "unitario" in fname):
                val = getattr(pl, field.name, None)
                if val not in (None, ""):
                    return number_format(val, decimal_pos=2, force_grouping=True)

        return "-"

    # ----------------------------------------------
    # Permisos
    # ----------------------------------------------

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name="FINANZAS").exists():
            return True
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        base = list(self.readonly_fields)

        if request.user.is_superuser:
            return base

        # FINANZAS puede marcar pagado, pero NO decidir
        if request.user.groups.filter(name="FINANZAS").exists():
            return base + ["decision", "scheduled_date", "nota_admin"]

        return [f.name for f in self.model._meta.fields]


# ======================================================
# ADMIN: ENCABEZADO FINANZAS
# ======================================================

@admin.register(FinanceApproval)
class FinanceApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "estado",
        "enviado_por",
        "enviado_en",
        "ultima_decision_por",
        "ultima_decision_en",
        "actualizado_en",
    )

    list_filter = ("estado",)
    search_fields = (
        "purchase_request__paw_numero",
        "purchase_request__paw_nombre",
    )

    readonly_fields = (
        "enviado_por",
        "enviado_en",
        "creado_en",
        "actualizado_en",
    )

    inlines = [FinanceApprovalLineInline]

    actions = (
        "marcar_pendiente",
        "marcar_aprobado",
        "marcar_rechazado",
    )

    # ----------------------------------------------
    # Sincronizar líneas al abrir
    # ----------------------------------------------
    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if obj:
            sync_finance_lines(obj)
        return super().change_view(request, object_id, form_url, extra_context)

    # ----------------------------------------------
    # Columnas
    # ----------------------------------------------
    @admin.display(description="PAW")
    def paw_numero(self, obj):
        return obj.purchase_request.paw_numero or "-"

    @admin.display(description="Última decisión por")
    def ultima_decision_por(self, obj):
        last = obj.lineas.exclude(decidido_en__isnull=True).order_by("-decidido_en").first()
        return last.decidido_por if last else "-"

    @admin.display(description="Última decisión en")
    def ultima_decision_en(self, obj):
        last = obj.lineas.exclude(decidido_en__isnull=True).order_by("-decidido_en").first()
        return last.decidido_en if last else "-"

    # ==================================================
    # ACCIONES DE ESTADO
    # ==================================================

    def _check_finance_permission(self, request):
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name="FINANZAS").exists():
            return True
        messages.error(request, "No tienes permisos para cambiar el estado financiero.")
        return False

    @admin.action(description="Marcar como PENDIENTE")
    def marcar_pendiente(self, request, queryset):
        if not self._check_finance_permission(request):
            return
        updated = queryset.update(estado=FinanceApproval.Estado.PENDIENTE)
        messages.success(request, f"{updated} PAW(s) marcados como PENDIENTE.")

    @admin.action(description="Marcar como APROBADO")
    def marcar_aprobado(self, request, queryset):
        if not self._check_finance_permission(request):
            return
        updated = queryset.update(estado=FinanceApproval.Estado.APROBADO)
        messages.success(request, f"{updated} PAW(s) marcados como APROBADO.")

    @admin.action(description="Marcar como RECHAZADO")
    def marcar_rechazado(self, request, queryset):
        if not self._check_finance_permission(request):
            return
        updated = queryset.update(estado=FinanceApproval.Estado.RECHAZADO)
        messages.success(request, f"{updated} PAW(s) marcados como RECHAZADO.")

    # ----------------------------------------------
    # Guardado inline (pagado)
    # ----------------------------------------------
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in instances:
            if isinstance(obj, FinanceApprovalLine):
                if obj.pagado and not obj.pagado_en:
                    obj.pagado_en = timezone.now()
                    obj.pagado_por = request.user

                if not obj.pagado:
                    obj.pagado_en = None
                    obj.pagado_por = None

            obj.save()

        formset.save_m2m()

    def has_add_permission(self, request):
        return False