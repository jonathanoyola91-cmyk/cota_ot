from django.urls import path
from . import views

app_name = "facturacion"

urlpatterns = [
    path("", views.dashboard_facturacion, name="dashboard"),
    path("<int:pk>/", views.detalle_factura, name="detalle"),
    path("crear/<int:paw_id>/", views.crear_desde_paw, name="crear_desde_paw"),
    path("radicar/<int:pk>/", views.radicar_factura, name="radicar"),
]