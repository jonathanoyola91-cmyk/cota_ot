from django.urls import path
from .views import purchase_request_pdf, purchase_request_excel
from . import views

app_name = "compras_oil"

urlpatterns = [
    path("purchase-request/<int:pk>/pdf/", purchase_request_pdf, name="purchase_request_pdf"),
    path("purchase-request/<int:pk>/excel/", purchase_request_excel, name="purchase_request_excel"),
    path("", views.dashboard, name="dashboard"),
    path("historial/", views.historial_compras, name="historial"),
    path("paw/<int:pk>/", views.paw_detail, name="paw_detail"),
    path("linea/<int:linea_id>/enviar-finanzas/", views.enviar_linea_finanzas, name="enviar_linea_finanzas"),
    path("linea/<int:linea_id>/enviar-gerencia/", views.enviar_linea_gerencia, name="enviar_linea_gerencia"),
    path("linea/<int:linea_id>/enviar-inventario/", views.enviar_linea_inventario, name="enviar_linea_inventario"),
    path("paw/<int:pk>/enviar-finanzas/", views.enviar_finanzas, name="enviar_finanzas"),
    path("paw/<int:pk>/enviar-aprobacion/", views.enviar_aprobacion, name="enviar_aprobacion"),
    path("paw/<int:pk>/enviar-inventario/", views.enviar_inventario, name="enviar_inventario"),
    path("paw/<int:pk>/generar-entrega/", views.generar_entrega, name="generar_entrega"),
    path("paw/<int:pk>/generar-entrega-taller/", views.generar_entrega_taller, name="generar_entrega_taller"),
    path("proveedores/nuevo/", views.supplier_create, name="supplier_create"),
    path("proveedores/<int:pk>/", views.supplier_detail, name="supplier_detail"),
    path("cerrar/<int:pk>/", views.cerrar_solicitud, name="cerrar_solicitud"),
    path("proveedores/", views.supplier_list, name="supplier_list"),
    path("paw/<int:pk>/aprobar-gerencia/",views.aprobar_gerencia_compra,name="aprobar_gerencia_compra"),
]