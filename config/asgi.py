import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

# IMPORTANTE:
# Primero Django debe cargar todas las aplicaciones y modelos.
django_asgi_app = get_asgi_application()

# Solo después de inicializar Django importamos Channels
# y las rutas que terminan importando consumers/models.
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

import internal_chat.routing


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,

        "websocket": AuthMiddlewareStack(
            URLRouter(
                internal_chat.routing.websocket_urlpatterns
            )
        ),
    }
)