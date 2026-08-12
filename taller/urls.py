from django.urls import path

from . import views

app_name = "taller"

urlpatterns = [
    # TALLER ACTUAL
    path("", views.dashboard, name="dashboard"),
    path("cerrar-ensamble/<int:ot_id>/", views.confirmar_ensamble_ok, name="confirmar_ensamble_ok"),
    path("camaras/", views.camaras_taller, name="camaras_taller"),
    path("camaras/nueva/", views.camara_nueva, name="camara_nueva"),
    path("camaras/<int:camara_id>/editar/", views.camara_editar, name="camara_editar"),

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
