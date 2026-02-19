# aprobacion/admin.py
from django.contrib import admin, messages
from django.utils import timezone

from .models import PurchaseApproval, PurchaseApprovalLine


def sync_purchase_approval_lines(
    approval: PurchaseApproval,
    refresh_pending_only: bool = True,
):
    """
    Sincroniza líneas desde compras sin afectar decisiones ya tomadas.

    - Crea líneas nuevas si aparecen nuevas PurchaseLine en el PAW.
    - Actualiza snapshot SOLO si la línea está PENDIENTE (por defecto).
    - NO cambia estado_aprobacion de líneas APROBADO/RECHAZADO.
    """
    pr = approval.purchase_request

    for pl in pr.lineas.all():
        line, created = PurchaseApprovalLine.objects.get_or_create(
            approval=approval,
            purchase_line=pl,
        )

        # Si es nueva, siempre llenamos snapshot
        if created:
            line.snapshot_from_purchase_line()
            line.save()
            continue

        # Si ya existe:
        if refresh_pending_only:
            # Solo refrescar si sigue pendiente (no tocar aprobados/rechazados)
            if line.estado_aprobacion == PurchaseApprovalLine.EstadoAprobacion.PENDIENTE:
                line.snapshot_from_purchase_line()
                line.save()
        else:
            # refrescar siempre (no recomendado para tu requerimiento)
            line.snapshot_from_purchase_line()
            line.save()


class PurchaseApprovalLineInline(admin.TabularInline):
    model = PurchaseApprovalLine
    extra = 0
    can_delete = False

    fields = (
        "codigo",
        "descripcion",
        "cantidad_requerida",
        "cantidad_a_comprar",
        "tipo_pago",
        "proveedor",
        "valor_unidad",
        "valor_total",
        "observaciones",
        "estado_aprobacion",
        "observacion_finanzas",
        "decidido_por",
        "decidido_en",
    )

    readonly_fields = (
        "codigo",
        "descripcion",
        "cantidad_requerida",
        "cantidad_a_comprar",
        "tipo_pago",
        "proveedor",
        "valor_unidad",
        "valor_total",
        "observaciones",
        "decidido_por",
        "decidido_en",
    )


    # ✅ no requiere aprobación si cantidad_a_comprar == 0
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(cantidad_a_comprar__gt=0)

    # ✅ cuadro observaciones finanzas pequeño
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if "observacion_finanzas" in formset.form.base_fields:
            formset.form.base_fields["observacion_finanzas"].widget = admin.widgets.AdminTextareaWidget(
                attrs={"rows": 2, "cols": 20, "style": "width:220px; resize:vertical;"}
            )
        return formset

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name="FINANZAS").exists():
            return True
        return False


@admin.register(PurchaseApproval)
class PurchaseApprovalAdmin(admin.ModelAdmin):
    list_display = ("paw_numero", "estado", "enviado_por", "enviado_en", "actualizado_en")
    list_filter = ("estado",)
    search_fields = ("purchase_request__paw_numero", "purchase_request__paw_nombre")

    readonly_fields = ("enviado_por", "enviado_en", "creado_en", "actualizado_en")

    inlines = [PurchaseApprovalLineInline]

    actions = ["resincronizar_desde_compras"]

    @admin.display(description="PAW")
    def paw_numero(self, obj):
        return obj.purchase_request.paw_numero or "-"

    # ✅ al abrir, sincroniza pendientes (sin tocar aprobados/rechazados)
    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if obj:
            sync_purchase_approval_lines(obj, refresh_pending_only=True)
        return super().change_view(request, object_id, form_url, extra_context)

    # ✅ acción manual por si finanzas quiere forzar resync
    @admin.action(description="Resincronizar desde Compras (solo pendientes)")
    def resincronizar_desde_compras(self, request, queryset):
        count = 0
        for approval in queryset:
            sync_purchase_approval_lines(approval, refresh_pending_only=True)
            approval.enviado_en = timezone.now()
            approval.enviado_por = request.user
            approval.save(update_fields=["enviado_en", "enviado_por", "actualizado_en"])
            count += 1
        messages.success(request, f"{count} PAW(s) resincronizados (solo líneas pendientes).")

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for ln in instances:
            if isinstance(ln, PurchaseApprovalLine):
                # Auditoría si decide
                if ln.estado_aprobacion in (
                    PurchaseApprovalLine.EstadoAprobacion.APROBADO,
                    PurchaseApprovalLine.EstadoAprobacion.RECHAZADO,
                ):
                    if not ln.decidido_en:
                        ln.touch_decision_audit(request.user)

                # Si vuelve a pendiente, limpiar auditoría (opcional)
                if ln.estado_aprobacion == PurchaseApprovalLine.EstadoAprobacion.PENDIENTE:
                    ln.decidido_en = None
                    ln.decidido_por = None

                ln.save()

        formset.save_m2m()

        approval = form.instance
        approval.recalcular_estado()
        approval.save(update_fields=["estado", "actualizado_en"])

    def has_add_permission(self, request):
        return False
