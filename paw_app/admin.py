# paw_app/admin.py
from django.contrib import admin, messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Paw
from facturacion.models import Factura
from quotes.models import Quotation
from workorders.models import WorkOrder


# ---------------------------------------------------------
# Inline para crear/editar WorkOrders (OT) debajo del PAW
# ---------------------------------------------------------
class WorkOrderInline(admin.TabularInline):
    model = WorkOrder
    extra = 0
    show_change_link = True

    # Campos que se ven dentro del PAW
    fields = (
        "titulo",
        "estado",
        "prioridad",
        "cliente",
        "equipo",
        "serial",
        "ubicacion",
        "asignado_a",
        "asignado_grupo",
        "visibilidad",
        "etapa_taller",
        "comentario_taller",
    )

    readonly_fields = ("cliente",)

    def get_readonly_fields(self, request, obj=None):
        # Superuser: todo editable
        if request.user.is_superuser:
            return []

        # Grupo Taller: solo edita etapa y comentario de taller (y estado si quieres)
        if request.user.groups.filter(name="Taller").exists():
            # OJO: NO incluyo "descripcion" porque no está en fields y puede no existir en el modelo
            return [
                "titulo",
                "estado",
                "cliente",
                "equipo",
                "serial",
                "ubicacion",
                "prioridad",
                "asignado_a",
                "asignado_grupo",
                "visibilidad",
            ]
        return []


@admin.register(Paw)
class PawAdmin(admin.ModelAdmin):
    list_display = (
        "numero_paw",
        "nombre_paw",
        "cotizacion",
        "cliente",
        "campo",
        "fecha_entrega",
        "fecha_salida",
        "creado_por",
        "actualizado_en",
        "link_factura",   # ✅ nuevo: acceso rápido a la factura
    )

    search_fields = (
        "numero_paw",
        "nombre_paw",
        "cliente",
        "campo",
        "cotizacion__numero_cotizacion",
        "cotizacion__nombre_cotizacion",
    )

    inlines = [WorkOrderInline]

    actions = ["enviar_a_facturacion"]

    class Media:
        js = ("paw_app/paw_autofill.js",)

    # ---------------------------------------------------------
    # ✅ Link rápido: abrir la factura asociada (si existe)
    # ---------------------------------------------------------
    def link_factura(self, obj: Paw):
        try:
            factura = obj.factura  # related_name="factura" en Factura.paw
        except Exception:
            return "Sin factura"

        url = reverse("admin:facturacion_factura_change", args=[factura.id])
        return format_html('<a href="{}">Abrir factura</a>', url)

    link_factura.short_description = "Factura"

    # ---------------------------------------------------------
    # ✅ ACCIÓN: enviar a facturación (crear/abrir factura)
    # ---------------------------------------------------------
    @admin.action(description="Enviar a facturación (crear/abrir factura)")
    def enviar_a_facturacion(self, request, queryset):
        if not queryset.exists():
            messages.warning(request, "No seleccionaste ningún PAW.")
            return None

        # 1 seleccionado: abre directamente el formulario de la factura
        if queryset.count() == 1:
            paw = queryset.first()
            factura, created = Factura.objects.get_or_create(paw=paw)

            if created:
                messages.success(request, f"Factura creada para PAW {paw.numero_paw}.")
            else:
                messages.info(request, f"Ya existía factura para PAW {paw.numero_paw}. Abriendo...")

            url = reverse("admin:facturacion_factura_change", args=[factura.id])
            return redirect(url)

        # Varios seleccionados: crear las que falten y llevar al listado filtrado
        creadas = 0
        existentes = 0
        factura_ids = []

        for paw in queryset:
            factura, created = Factura.objects.get_or_create(paw=paw)
            factura_ids.append(str(factura.id))
            if created:
                creadas += 1
            else:
                existentes += 1

        messages.success(
            request,
            f"Proceso terminado. Creadas: {creadas}. Ya existentes: {existentes}. "
            f"Te muestro el listado filtrado con esas facturas."
        )

        changelist_url = reverse("admin:facturacion_factura_changelist")
        # Nota: este filtro funciona bien en el changelist aunque no haya un filtro UI,
        # porque es querystring directo.
        return redirect(f"{changelist_url}?id__in={','.join(factura_ids)}")

    # ---------------------------------------------------------
    # Endpoint para traer cliente/campo de la cotización (AJAX)
    # ---------------------------------------------------------
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "quotation-info/<int:quotation_id>/",
                self.admin_site.admin_view(self.quotation_info),
                name="paw_app_paw_quotation_info",
            ),
        ]
        return custom + urls

    def quotation_info(self, request, quotation_id: int):
        q = Quotation.objects.get(pk=quotation_id)
        return JsonResponse({
            "cliente": q.cliente or "",
            "campo": q.campo or "",
        })

    # ---------------------------------------------------------
    # CLAVE: cuando se crean OT en inline, setear creado_por
    # ---------------------------------------------------------
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in instances:
            if isinstance(obj, WorkOrder) and not obj.creado_por_id:
                obj.creado_por = request.user
            obj.save()

        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
