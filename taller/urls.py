from django.urls import path
from . import views

app_name = "taller"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cerrar-ensamble/<int:ot_id>/", views.confirmar_ensamble_ok, name="confirmar_ensamble_ok"),   
]