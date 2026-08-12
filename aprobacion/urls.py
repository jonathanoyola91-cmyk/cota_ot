from django.urls import path
from . import views

app_name = "aprobacion"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("linea/<int:linea_id>/aprobar/", views.aprobar_linea, name="aprobar_linea"),
    path("linea/<int:linea_id>/rechazar/", views.rechazar_linea, name="rechazar_linea"),
]