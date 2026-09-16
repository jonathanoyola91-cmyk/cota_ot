from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    path("", views.inventario_dashboard, name="dashboard"),
    path("revision-bom/<int:pk>/", views.revision_bom_detail, name="revision_bom_detail"),
    path("revision-bom/<int:pk>/generar-entrega/", views.generar_entrega, name="generar_entrega"),
    path("recepcion/<int:pk>/", views.recepcion_detail, name="recepcion_detail"),
    path("entrega-taller/<int:pk>/", views.entrega_taller_detail, name="entrega_taller_detail"),
    path("entrega-taller/<int:pk>/pdf/", views.entrega_taller_pdf, name="entrega_taller_pdf"),

    # Salidas sin PAW
    path("salidas/", views.salidas_lista, name="salidas_lista"),
    path("salidas/nueva/", views.salida_nueva, name="salida_nueva"),
    path("salidas/<int:pk>/", views.salida_detail, name="salida_detail"),
    path("salidas/<int:pk>/pdf/", views.salida_pdf, name="salida_pdf"),

    # Remisiones de salida
    path("remisiones/", views.remisiones_lista, name="remisiones_lista"),
    path("remisiones/nueva/", views.remision_nueva, name="remision_nueva"),
    path("remisiones/<int:pk>/", views.remision_detail, name="remision_detail"),
    path("remisiones/<int:pk>/anular/", views.remision_anular, name="remision_anular"),
    path("remisiones/<int:pk>/pdf/", views.remision_pdf, name="remision_pdf"),

    # Autocomplete del catálogo
    path("api/items/", views.buscar_items_inventario, name="buscar_items_inventario"),
]
