from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.inventario_dashboard, name="dashboard"),
    path("recepcion/<int:pk>/", views.recepcion_detail, name="recepcion_detail"),
    path("entrega-taller/<int:pk>/", views.entrega_taller_detail, name="entrega_taller_detail"),
]