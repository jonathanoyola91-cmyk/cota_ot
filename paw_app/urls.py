from django.urls import path
from . import views

urlpatterns = [
    path("", views.paw_list, name="paw_list"),
    path("<int:paw_id>/", views.paw_detail, name="paw_detail"),
    path("crear/<int:cotizacion_id>/", views.crear_paw, name="crear_paw"),
    path("<int:paw_id>/registrar-ensamble/", views.registrar_ensamble, name="registrar_ensamble"),
    path("<int:paw_id>/producto-ok/", views.marcar_producto_ok, name="marcar_producto_ok"),
    path("<int:paw_id>/iniciar-servicio-campo/", views.iniciar_servicio_campo, name="iniciar_servicio_campo"),
    path("<int:paw_id>/cambiar-tipo-operacion/", views.cambiar_tipo_operacion, name="cambiar_tipo_operacion"),
]
