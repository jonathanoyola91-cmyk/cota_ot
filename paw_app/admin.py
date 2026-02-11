# paw_app/admin.py
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from .models import Paw
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

    # Para que sea más usable (no obligar numero/creado_por en inline)
    readonly_fields = ("cliente",)

    def get_readonly_fields(self, request, obj=None):
        # Superuser: todo editable
        if request.user.is_superuser:
            return []

        # Grupo Taller: solo edita etapa y comentario de taller (y estado si quieres)
        if request.user.groups.filter(name="Taller").exists():
            return [
                "titulo",
                "descripcion",
                "cliente",
                "equipo",
                "serial",
                "ubicacion",
                "prioridad",
                "creado_por",
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
    )

    search_fields = (
        "numero_paw",
        "nombre_paw",
        "cliente",
        "campo",
        "cotizacion__numero_cotizacion",
        "cotizacion__nombre_cotizacion",
    )

    # ✅ Aquí vuelve la magia: OT debajo del PAW
    inlines = [WorkOrderInline]

    # ✅ JS para auto-llenar cliente/campo al seleccionar cotización
    class Media:
        js = ("paw_app/paw_autofill.js",)

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
            # Si es una OT (WorkOrder) y no tiene creado_por, lo seteamos
            if isinstance(obj, WorkOrder) and not obj.creado_por_id:
                obj.creado_por = request.user

            obj.save()

        formset.save_m2m()

    def save_model(self, request, obj, form, change):
        if not obj.creado_por_id:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
