from django.contrib import admin, messages
from django.utils import timezone
from django.utils.safestring import mark_safe  # ✅ FIX para Django 6

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
            # Finanzas solo decide aprobar/rechazar
            return [
                "purchase_request",
                "lineas_contado_html",  # ✅ visible pero no editable
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

    # ---------- Visualización líneas CONTADO ----------
    @admin.display(description="Líneas CONTADO (items que Finanzas debe revisar)")
    def lineas_contado_html(self, obj):
        pr = obj.purchase_request
        qs = pr.lineas.filter(tipo_pago="CONTADO").order_by("id")

        if not qs.exists():
            return "No hay líneas a CONTADO para esta solicitud."

        header = """
            <thead>
                <tr>
                    <th style="text-align:left;padding:6px;">Código</th>
                    <th style="text-align:left;padding:6px;">Descripción</th>
                    <th style="text-align:center;padding:6px;">Und</th>
                    <th style="text-align:right;padding:6px;">A comprar</th>
                    <th style="text-align:left;padding:6px;">Proveedor</th>
                    <th style="text-align:right;padding:6px;">Precio</th>
                    <th style="text-align:left;padding:6px;">Obs Compras</th>
                </tr>
            </thead>
        """

        rows = []
        for l in qs:
            rows.append(f"""
                <tr>
                    <td style="padding:6px;border-top:1px solid #ddd;">{l.codigo or ""}</td>
                    <td style="padding:6px;border-top:1px solid #ddd;">{l.descripcion or ""}</td>
                    <td style="padding:6px;border-top:1px solid #ddd;text-align:center;">{l.unidad or ""}</td>
                    <td style="padding:6px;border-top:1px solid #ddd;text-align:right;">{l.cantidad_a_comprar or 0}</td>
                    <td style="padding:6px;border-top:1px solid #ddd;">{l.proveedor.nombre if l.proveedor else ""}</td>
                    <td style="padding:6px;border-top:1px solid #ddd;text-align:right;">{l.precio_unitario if l.precio_unitario is not None else ""}</td>
                    <td style="padding:6px;border-top:1px solid #ddd;">{l.observaciones_compras or ""}</td>
                </tr>
            """)

        table = f"""
            <div style="overflow:auto; max-width:100%;">
                <table style="border-collapse:collapse; width:100%; font-size:12px;">
                    {header}
                    <tbody>
                        {''.join(rows)}
                    </tbody>
                </table>
            </div>
        """

        return mark_safe(table)

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
