from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'

    def ready(self):
        # Import signals to register them
        import chat.signals  # noqa: F401
        from home.feed_registry import register_feed_provider

        from .feed import get_feed_items, mark_as_read, mark_as_unread

        register_feed_provider('room_messages', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
