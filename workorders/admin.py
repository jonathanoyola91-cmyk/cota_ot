from django.contrib import admin
from .models import WorkOrder, WorkOrderTask

class WorkOrderTaskInline(admin.TabularInline):
    model = WorkOrderTask
    extra = 1

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("numero", "titulo", "paw", "estado", "etapa_taller", "prioridad", "cliente", "asignado_a", "creado_en")
    list_filter = ("estado", "prioridad")
    search_fields = ("numero", "titulo", "cliente", "equipo", "serial", "paw__numero_paw", "paw__nombre_paw")
    inlines = [WorkOrderTaskInline]

    actions = ["set_desarme", "set_alistamiento", "set_ensamblando", "set_prueba"]

    def _set_etapa(self, request, queryset, etapa):
        queryset.update(etapa_taller=etapa)

    @admin.action(description="Taller: Etapa -> Desarme")
    def set_desarme(self, request, queryset):
        self._set_etapa(request, queryset, "DESARME")

    @admin.action(description="Taller: Etapa -> Alistamiento")
    def set_alistamiento(self, request, queryset):
        self._set_etapa(request, queryset, "ALISTAMIENTO")

    @admin.action(description="Taller: Etapa -> Ensamblando")
    def set_ensamblando(self, request, queryset):
        self._set_etapa(request, queryset, "ENSAMBLANDO")

    @admin.action(description="Taller: Etapa -> Prueba")
    def set_prueba(self, request, queryset):
        self._set_etapa(request, queryset, "PRUEBA")

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Superusuario ve todo
        if request.user.is_superuser:
            return qs

        # OT públicas
        publicas = qs.filter(visibilidad="PUBLICA")

        # OT donde el usuario está involucrado
        involucrado = qs.filter(creado_por=request.user) | qs.filter(asignado_a=request.user)

        # OT asignadas al grupo del usuario
        grupos_usuario = request.user.groups.all()
        por_grupo = qs.filter(asignado_grupo__in=grupos_usuario)

        return (publicas | involucrado | por_grupo).distinct()

    def get_readonly_fields(self, request, obj=None):
        # Superusuario puede editar todo
        if request.user.is_superuser:
            return []

        # Taller: solo puede editar estado y tiempos
        if request.user.groups.filter(name="Taller").exists():
            return [
               "numero", "titulo", "descripcion", "cliente", "equipo", "serial",
                "ubicacion", "prioridad", "creado_por", "asignado_a",
                "asignado_grupo", "visibilidad", "creado_en", "actualizado_en",
            ]

        return []

@admin.register(WorkOrderTask)
class WorkOrderTaskAdmin(admin.ModelAdmin):
    list_display = ("workorder", "titulo", "estado", "responsable", "creado_en")
    list_filter = ("estado",)
    search_fields = ("titulo", "workorder__titulo", "workorder__cliente")
