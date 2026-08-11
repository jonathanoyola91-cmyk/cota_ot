from django.urls import path
from . import views

app_name = "taller"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path(
        "cerrar-ensamble/<int:ot_id>/",
        views.confirmar_ensamble_ok,
        name="confirmar_ensamble_ok"
    ),

    # Control de cámaras que ingresan al taller
    path(
        "camaras/",
        views.camaras_taller,
        name="camaras_taller"
    ),

    path(
        "camaras/nueva/",
        views.camara_nueva,
        name="camara_nueva"
    ),

    path(
        "camaras/<int:camara_id>/editar/",
        views.camara_editar,
        name="camara_editar"
    ),
]