from django.urls import path

from . import views

app_name = "taller"

urlpatterns = [
    # TALLER ACTUAL
    path("", views.dashboard, name="dashboard"),
    path("material/<int:entrega_id>/", views.detalle_material, name="detalle_material"),
    path("cerrar-ensamble/<int:ot_id>/", views.confirmar_ensamble_ok, name="confirmar_ensamble_ok"),
    path("camaras/", views.camaras_taller, name="camaras_taller"),
    path("camaras/nueva/", views.camara_nueva, name="camara_nueva"),
    path("camaras/<int:camara_id>/editar/", views.camara_editar, name="camara_editar"),

    # METROLOGIA / CALIDAD - EJES
    path("metrologia/ejes/", views.metrologia_ejes, name="metrologia_ejes"),
    path("metrologia/paw/<int:paw_id>/", views.metrologia_paw_detalle, name="metrologia_paw_detalle"),
    path("metrologia/plantillas/", views.metrologia_plantillas, name="metrologia_plantillas"),
    path("metrologia/tipos-pieza/", views.metrologia_tipos_pieza, name="metrologia_tipos_pieza"),
    path("metrologia/plantillas/nueva/", views.metrologia_plantilla_form, name="metrologia_plantilla_nueva"),
    path("metrologia/plantillas/<int:plantilla_id>/editar/", views.metrologia_plantilla_form, name="metrologia_plantilla_editar"),
    path("metrologia/instrumentos/", views.metrologia_instrumentos, name="metrologia_instrumentos"),
    path("metrologia/instrumentos/nuevo/", views.metrologia_instrumento_form, name="metrologia_instrumento_nuevo"),
    path("metrologia/instrumentos/<int:instrumento_id>/editar/", views.metrologia_instrumento_form, name="metrologia_instrumento_editar"),
    path("metrologia/instrumentos/<int:instrumento_id>/", views.metrologia_instrumento_detalle, name="metrologia_instrumento_detalle"),
    path("metrologia/ejes/nueva/", views.metrologia_eje_nueva, name="metrologia_eje_nueva"),
    path("metrologia/plantillas/<int:plantilla_id>/configurar/", views.metrologia_plantilla_configurar, name="metrologia_plantilla_configurar"),
    path("metrologia/ejes/<int:inspeccion_id>/", views.metrologia_eje_detalle, name="metrologia_eje_detalle"),
    path("metrologia/ejes/<int:inspeccion_id>/dictamen/", views.metrologia_eje_dictamen, name="metrologia_eje_dictamen"),
    path("metrologia/ejes/<int:inspeccion_id>/reporte/", views.metrologia_eje_reporte, name="metrologia_eje_reporte"),
    path("metrologia/ejes/<int:inspeccion_id>/mecanizado/crear/", views.metrologia_mecanizado_crear, name="metrologia_mecanizado_crear"),
    path("metrologia/ejes/<int:inspeccion_id>/mecanizado/terminar/", views.metrologia_mecanizado_terminar, name="metrologia_mecanizado_terminar"),
    path("metrologia/ejes/<int:inspeccion_id>/reinspeccion/crear/", views.metrologia_reinspeccion_crear, name="metrologia_reinspeccion_crear"),

    # HORAS DE ENSAMBLE POR PAW
    path("horas/", views.dashboard_horas_taller, name="horas_dashboard"),
    path("horas/paw/<int:paw_id>/iniciar/", views.iniciar_ensamble, name="horas_iniciar"),
    path("horas/ensamble/<int:ensamble_id>/", views.detalle_ensamble, name="horas_detalle"),
    path("horas/ensamble/<int:ensamble_id>/tecnicos/", views.asignar_tecnicos, name="horas_asignar_tecnicos"),
    path("horas/ensamble/<int:ensamble_id>/jornada/nueva/", views.crear_jornada, name="horas_crear_jornada"),
    path("horas/jornada/<int:jornada_id>/editar/", views.editar_jornada, name="horas_editar_jornada"),
    path("horas/ensamble/<int:ensamble_id>/finalizar/", views.finalizar_ensamble, name="horas_finalizar"),
    path("horas/reporte/", views.reporte_horas, name="horas_reporte"),
    path("horas/reporte/empleado/", views.reporte_horas_empleado, name="horas_reporte_empleado"),
]
