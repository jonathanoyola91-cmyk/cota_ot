from django.urls import path

from . import views


app_name = "internal_chat"


urlpatterns = [
    path(
        "",
        views.bandeja,
        name="bandeja",
    ),
    path(
        "privado/<int:user_id>/",
        views.abrir_chat_privado,
        name="abrir_chat_privado",
    ),
    path(
        "grupo/crear/",
        views.crear_grupo,
        name="crear_grupo",
    ),
    path(
        "<int:conversacion_id>/",
        views.conversacion,
        name="conversacion",
    ),
    path(
        "<int:conversacion_id>/adjuntar/",
        views.subir_adjunto,
        name="subir_adjunto",
    ),
    path(
        "adjunto/<int:adjunto_id>/",
        views.ver_adjunto,
        name="ver_adjunto",
    ),
]
