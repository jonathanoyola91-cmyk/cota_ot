from django.urls import path
from . import views

urlpatterns = [
    path("", views.paw_list, name="paw_list"),
    path("seguimiento/<uuid:token>/",views.seguimiento_publico,name="seguimiento_publico",),
    path("<int:paw_id>/activar-seguimiento/",views.activar_seguimiento_publico,name="activar_seguimiento_publico",),
    path("<int:paw_id>/desactivar-seguimiento/",views.desactivar_seguimiento_publico,name="desactivar_seguimiento_publico",),
    path("<int:paw_id>/", views.paw_detail, name="paw_detail"),
    path("<int:paw_id>/chat/", views.abrir_chat_paw, name="abrir_chat_paw"),
    path("crear/<int:cotizacion_id>/", views.crear_paw, name="crear_paw"),
    path("<int:paw_id>/registrar-ensamble/", views.registrar_ensamble, name="registrar_ensamble"),
    path("<int:paw_id>/producto-ok/", views.marcar_producto_ok, name="marcar_producto_ok"),
    path("<int:paw_id>/iniciar-servicio-campo/", views.iniciar_servicio_campo, name="iniciar_servicio_campo"),
    path("<int:paw_id>/cambiar-tipo-operacion/", views.cambiar_tipo_operacion, name="cambiar_tipo_operacion"),
    path("<int:paw_id>/actualizar-alcance/", views.actualizar_alcance_paw, name="actualizar_alcance_paw"),
    path("eliminar/<int:paw_id>/", views.eliminar_paw, name="eliminar_paw"),
    path("<int:paw_id>/actualizar-gestion/", views.actualizar_gestion_paw, name="actualizar_gestion_paw"),
    path("historial/", views.paw_historial, name="paw_historial"),
    path("<int:paw_id>/cerrar-antiguo/", views.cerrar_paw_antiguo, name="cerrar_paw_antiguo"),
]
