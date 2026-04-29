from django.urls import path
from . import views

urlpatterns = [
    path("crear-desde-ot/<int:ot_numero>/", views.crear_bom_desde_ot, name="crear_bom_desde_ot"),
    path("<int:bom_id>/", views.bom_detail, name="bom_detail"),
    path("<int:bom_id>/agregar-item/", views.agregar_item_bom, name="agregar_item_bom"),
    path("item/<int:item_id>/editar/", views.editar_item_bom, name="editar_item_bom"),
    path("item/<int:item_id>/eliminar/", views.eliminar_item_bom, name="eliminar_item_bom"),
    path("<int:bom_id>/enviar-compras/", views.enviar_bom_compras, name="enviar_bom_compras"),
    
]