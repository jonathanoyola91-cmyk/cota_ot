from django.urls import path
from . import views

app_name = "hse"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("entregas/", views.entregas_pendientes, name="entregas_pendientes"),
    path("historial/", views.historial_entregas, name="historial_entregas"),
    path("solicitar/<str:tipo>/", views.solicitar, name="solicitar"),
    path("reponer-bodega/", views.reponer_bodega, name="reponer_bodega"),
    path("stock/<int:pk>/editar/", views.editar_solicitud_stock, name="editar_stock"),
    path("carga-inicial/", views.carga_inicial, name="carga_inicial"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/editar/", views.editar_solicitud, name="editar"),
    path("<int:pk>/procesar/", views.procesar_inventario, name="procesar"),
    path("<int:pk>/entregar/", views.entregar, name="entregar"),
    path("<int:pk>/pdf/", views.comprobante_pdf, name="pdf"),
    path("api/items/", views.buscar_items, name="buscar_items"),
]
