from django.contrib import admin
from django import forms
from django.forms.models import BaseInlineFormSet

from .models import Paw
from workorders.models import WorkOrder


class WorkOrderInline(admin.TabularInline):
    model = WorkOrder
    extra = 0

    fields = (
        "numero",
        "titulo",
        "estado",
        "etapa_taller",
        "asignado_grupo",
        "asignado_a",
        "iniciado_en",
        "terminado_en",
    )
    readonly_fields = ("numero",)
    show_change_link = True

    def get_formset(self, request, obj=None, **kwargs):
        """
        Inyectamos el request al formset para poder setear creado_por
        cuando se crean OTs desde el inline.
        """
        FormSet = super().get_formset(request, obj, **kwargs)

        class RequestFormSet(FormSet):
            def save_new(self, form, commit=True):
                instance = super().save_new(form, commit=False)

                # ✅ Aquí se corrige el NOT NULL: creado_por siempre se llena
                if not getattr(instance, "creado_por_id", None):
                    instance.creado_por = request.user

                if commit:
                    instance.save()
                    form.save_m2m()
                return instance

        return RequestFormSet


@admin.register(Paw)
class PawAdmin(admin.ModelAdmin):
    list_display = (
        "numero_paw",
        "nombre_paw",
        "cotizacion",
        "cliente",
        "campo",
        "estado_paw",
        "ots_abiertas",
        "etapa_actual",
        "fecha_salida",
        "fecha_entrega",
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

    list_filter = (
        "fecha_salida",
        "fecha_entrega",
    )

    inlines = [WorkOrderInline]

    @admin.display(description="OT abiertas")
    def ots_abiertas(self, obj):
        return obj.ots.exclude(estado="CERRADA").count()

    @admin.display(description="Etapa actual")
    def etapa_actual(self, obj):
        qs = (
            obj.ots.exclude(estado="CERRADA")
            .exclude(etapa_taller__isnull=True)
            .exclude(etapa_taller__exact="")
        )
        if not qs.exists():
            return "-"
        from django.db.models import Count
        top = qs.values("etapa_taller").annotate(c=Count("*")).order_by("-c").first()
        return top["etapa_taller"]

    @admin.display(description="Estado PAW")
    def estado_paw(self, obj):
        qs = obj.ots.all()
        if not qs.exists():
            return "SIN OT"
        if qs.exclude(estado="CERRADA").count() == 0:
            return "TERMINADO"
        if qs.filter(etapa_taller="PRUEBA").exclude(estado="CERRADA").exists():
            return "EN PRUEBA"
        return "EN PROCESO"

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return []
        if request.user.groups.filter(name="Comercial").exists():
            return ["creado_por", "creado_en", "actualizado_en"]
        return [f.name for f in self.model._meta.fields]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name="Comercial").exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name="Comercial").exists()

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
