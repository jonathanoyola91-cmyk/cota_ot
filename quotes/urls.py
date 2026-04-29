from django.urls import path
from . import views

urlpatterns = [
    path("", views.lista_cotizaciones, name="lista_cotizaciones"),
    path("crear/", views.crear_cotizacion, name="crear_cotizacion"),
    path("<int:pk>/", views.detalle_cotizacion, name="detalle_cotizacion"),
    path("<int:pk>/editar/", views.editar_cotizacion, name="editar_cotizacion"),

    path("clientes/", views.lista_clientes, name="lista_clientes"),
    path("clientes/crear/", views.crear_cliente, name="crear_cliente"),
    path("clientes/<int:pk>/editar/", views.editar_cliente, name="editar_cliente"),
]