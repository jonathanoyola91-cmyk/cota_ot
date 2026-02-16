from django.urls import path
from .views import crear_cotizacion

urlpatterns = [
    path("crear/", crear_cotizacion, name="crear_cotizacion"),
]