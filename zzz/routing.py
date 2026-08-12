import asyncio
import logging
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "zzz.settings")

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
from django.urls import path

log = logging.getLogger(__name__)


class CancelledErrorMiddleware:
    """
    Suppress asyncio.CancelledError logs from Django ASGI middleware.
    CancelledError is normal when clients disconnect mid-request and should not be logged as ERROR.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            return await self.app(scope, receive, send)
        except (asyncio.CancelledError):
            log.debug("ASGI request cancelled by client (normal disconnect)")
            raise


django_asgi_app = get_asgi_application()
django_asgi_app = CancelledErrorMiddleware(django_asgi_app)

from chat.consumers import ChatConsumer  # noqa: E402

# from channels.http import AsgiHandler
# from chat.consumers import Consumer

# The channel routing defines what connections get handled by what consumers,
# selecting on either the connection type (ProtocolTypeRouter) or properties
# of the connection's scope (like URLRouter, which looks at scope["path"])
# For more, see http://channels.readthedocs.io/en/latest/topics/routing.html
application = ProtocolTypeRouter(
    {
        # Channels will do this for you automatically. It's included here as
        # an example.
        # "http": AsgiHandler,
        "http": django_asgi_app,
        # Route all WebSocket requests to our custom chat handler.
        # We actually don't need the URLRouter here, but we've put it in for
        # illustration. Also note the inclusion of the AuthMiddlewareStack to
        # add users and sessions
        # see http://channels.readthedocs.io/en/latest/topics/authentication.html
        "websocket": AuthMiddlewareStack(
            URLRouter(
                [
                    # URLRouter just takes standard Django path() or url() entries.
                    path("chat/stream/", ChatConsumer.as_asgi())
                ]
            )
        ),
    }
)
