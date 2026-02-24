# presupuesto/admin.py
from django.contrib import admin, messages

from facturacion.models import Factura
from .models import Presupuesto
from .sync import sync_presupuestos


@admin.register(Presupuesto)
class PresupuestoAdmin(admin.ModelAdmin):
    list_display = (
        "paw_numero",
        "paw_nombre",
        "cliente",
        "campo",
        "facturado",
        "total_paw",
        "presupuesto_aprobado",
        "presupuesto_disponible",
        "actualizado_en",
    )

    list_editable = ("presupuesto_aprobado",)
    readonly_fields = ("paw", "total_paw", "creado_en", "actualizado_en")

    search_fields = (
        "paw__numero_paw",
        "paw__nombre_paw",
        "paw__cliente",
        "paw__campo",
    )

    actions = ["accion_sync"]

    # ✅ Importante: como esto se llena automático, bloqueamos crear manual
    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        # ✅ SIN FILTRO: muestra TODOS los presupuestos
        return super().get_queryset(request).select_related("paw")

    @admin.display(description="PAW #")
    def paw_numero(self, obj):
        return obj.paw.numero_paw

    @admin.display(description="PAW Nombre")
    def paw_nombre(self, obj):
        return obj.paw.nombre_paw

    @admin.display(description="Cliente")
    def cliente(self, obj):
        return obj.paw.cliente

    @admin.display(description="Campo")
    def campo(self, obj):
        return obj.paw.campo

    @admin.display(description="Facturado")
    def facturado(self, obj):
        # Factura tiene related_name="factura" en Paw
        return "Sí" if hasattr(obj.paw, "factura") else "No"

    @admin.display(description="Presupuesto disponible")
    def presupuesto_disponible(self, obj):
        return obj.presupuesto_disponible

    @admin.action(description="Sincronizar: crear/actualizar presupuestos desde TODOS los PAWs")
    def accion_sync(self, request, queryset):
        total = sync_presupuestos()
        messages.success(request, f"Sincronización OK. PAWs procesados: {total}.")