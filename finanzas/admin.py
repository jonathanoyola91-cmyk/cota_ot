# finanzas/admin.py
from django.contrib import admin, messages
from django.utils import timezone

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

    fields = (
        "purchase_line",
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
        "decidido_por",
        "decidido_en",
        "pagado_en",
        "pagado_por",
    )

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

        # FINANZAS puede marcar pagado, pero NO decide
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

    actions = [
        "marcar_pendiente",
        "marcar_aprobado",
        "marcar_rechazado",
    ]

    # --------------------------------------------------
    # Sync líneas al abrir
    # --------------------------------------------------

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if obj:
            sync_finance_lines(obj)
        return super().change_view(request, object_id, form_url, extra_context)

    # --------------------------------------------------
    # COLUMNAS
    # --------------------------------------------------

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
    # ACCIONES DE ESTADO (ENCABEZADO)
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

    # --------------------------------------------------
    # Guardado inline (pagado)
    # --------------------------------------------------

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
