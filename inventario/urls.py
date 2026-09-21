from django.urls import path
from . import views

app_name = "inventario"

urlpatterns = [
    path("entrega-taller/<int:pk>/linea/<int:linea_pk>/transferir-bodega/", views.entrega_transferir_bodega, name="entrega_transferir_bodega"),
    path("", views.inventario_dashboard, name="dashboard"),
    path("existencias/", views.existencias_lista, name="existencias_lista"),
    path("existencias/inicial/", views.inventario_inicial, name="inventario_inicial"),
    path("existencias/inicial/plantilla/", views.inventario_inicial_plantilla, name="inventario_inicial_plantilla"),
    path("existencias/inicial/masivo/", views.inventario_inicial_masivo, name="inventario_inicial_masivo"),
    path("existencias/<int:pk>/ajustar/", views.ajustar_stock, name="ajustar_stock"),
    path("existencias/<int:pk>/kardex/", views.kardex_stock, name="kardex_stock"),
    path("transferencias/", views.transferencias_lista, name="transferencias_lista"),
    path("transferencias/nueva/", views.transferencia_nueva, name="transferencia_nueva"),
    path("transferencias/items-destino/", views.transferencia_items_destino, name="transferencia_items_destino"),
    path("reservas/transicion/", views.reserva_transicion, name="reserva_transicion"),
    path("revision-bom/<int:pk>/", views.revision_bom_detail, name="revision_bom_detail"),
    path("revision-bom/<int:pk>/generar-entrega/", views.generar_entrega, name="generar_entrega"),
    path("recepcion/<int:pk>/", views.recepcion_detail, name="recepcion_detail"),
    path(
        "recepcion/<int:pk>/linea/<int:linea_pk>/transferir-bodega/",
        views.recepcion_transferir_bodega,
        name="recepcion_transferir_bodega",
    ),
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
