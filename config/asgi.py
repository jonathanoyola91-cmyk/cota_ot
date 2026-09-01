import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

import internal_chat.routing

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": AuthMiddlewareStack(
        URLRouter(
            internal_chat.routing.websocket_urlpatterns
        )
    ),
})