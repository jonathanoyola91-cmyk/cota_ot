from django.contrib import admin, messages
from django.utils import timezone

from .models import FinanceApproval


@admin.register(FinanceApproval)
class FinanceApprovalAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "paw_nombre",
        "purchase_request",
        "estado",
        "aprobado_por",
        "aprobado_en",
        "actualizado_en",
    )
    list_filter = ("estado",)
    search_fields = (
        "purchase_request__paw_numero",
        "purchase_request__paw_nombre",
        "purchase_request__bom__workorder__numero",
    )

    actions = ["aprobar", "rechazar"]

    # ---------- Columnas PAW ----------
    @admin.display(description="PAW #")
    def paw_numero(self, obj):
        return getattr(obj.purchase_request, "paw_numero", "") or "-"

    @admin.display(description="PAW Nombre")
    def paw_nombre(self, obj):
        return getattr(obj.purchase_request, "paw_nombre", "") or "-"

    # ---------- Permisos ----------
    def _is_finanzas(self, request):
        return request.user.is_superuser or request.user.groups.filter(name="Finanzas").exists()

    def get_readonly_fields(self, request, obj=None):
        if self._is_finanzas(request):
            # Finanzas solo decide aprobar/rechazar (no cambia request)
            return [
                "purchase_request",
                "aprobado_por",
                "aprobado_en",
                "creado_en",
                "actualizado_en",
            ]
        return [f.name for f in self.model._meta.fields]

    def has_module_permission(self, request):
        return self._is_finanzas(request)

    def has_view_permission(self, request, obj=None):
        return self._is_finanzas(request)

    def has_change_permission(self, request, obj=None):
        return self._is_finanzas(request)

    # ---------- Acciones ----------
    @admin.action(description="Aprobar (Finanzas)")
    def aprobar(self, request, queryset):
        updated = 0
        for fa in queryset:
            if fa.estado != "APROBADO":
                fa.estado = "APROBADO"
                fa.aprobado_por = request.user
                fa.aprobado_en = timezone.now()
                fa.save(update_fields=["estado", "aprobado_por", "aprobado_en", "actualizado_en"])
                updated += 1
        messages.success(request, f"Aprobadas {updated} solicitud(es).")

    @admin.action(description="Rechazar (Finanzas)")
    def rechazar(self, request, queryset):
        updated = queryset.update(estado="RECHAZADO")
        messages.success(request, f"Rechazadas {updated} solicitud(es).")
