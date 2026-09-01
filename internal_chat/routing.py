from django.urls import re_path

from . import consumers


websocket_urlpatterns = [

    # WebSocket de una conversación específica:
    # funciona igual para PRIVADA, GRUPO, PAW y OT.
    re_path(
        r"ws/chat/(?P<conversacion_id>\d+)/$",
        consumers.ChatConsumer.as_asgi()
    ),

    # WebSocket global de notificaciones del usuario.
    re_path(
        r"ws/notificaciones/$",
        consumers.NotificationConsumer.as_asgi()
    ),

]
