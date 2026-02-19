# aprobacion/admin.py
from django.contrib import admin
from django.utils import timezone

from .models import PurchaseApproval, PurchaseApprovalLine


def sync_purchase_approval_lines(approval: PurchaseApproval, refresh_snapshot: bool = False):
    """
    Crea líneas si no existen.
    Por defecto NO refresca snapshot si ya existe (para no “pisar” histórico).
    """
    pr = approval.purchase_request

    for pl in pr.lineas.all():
        line, created = PurchaseApprovalLine.objects.get_or_create(
            approval=approval,
            purchase_line=pl,
        )
        if created or refresh_snapshot:
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
        "observacion_finanzas",   # ✅ editable (más pequeño)
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

    # ✅ FILTRO: no mostrar líneas con cantidad_a_comprar = 0
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(cantidad_a_comprar__gt=0)

    # ✅ UI: hacer "observacion_finanzas" más pequeño (2 renglones y angosto)
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

    def change_view(self, request, object_id, form_url="", extra_context=None):
        obj = self.get_object(request, object_id)
        if obj:
            sync_purchase_approval_lines(obj, refresh_snapshot=False)
        return super().change_view(request, object_id, form_url, extra_context)

    @admin.display(description="PAW")
    def paw_numero(self, obj):
        return obj.purchase_request.paw_numero or "-"

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for ln in instances:
            if isinstance(ln, PurchaseApprovalLine):
                # Auditoría al decidir algo
                if ln.estado_aprobacion in ("APROBADO", "RECHAZADO"):
                    if not ln.decidido_en:
                        ln.touch_decision_audit(request.user)

                if ln.estado_aprobacion == "PENDIENTE":
                    # opcional: limpiar auditoría si vuelve a pendiente
                    ln.decidido_en = None
                    ln.decidido_por = None

                ln.save()

        formset.save_m2m()

        approval = form.instance
        approval.recalcular_estado()
        approval.save(update_fields=["estado", "actualizado_en"])

    def has_add_permission(self, request):
        return False
