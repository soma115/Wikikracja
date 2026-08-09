from django.apps import AppConfig


class ObywateleConfig(AppConfig):
    name = 'obywatele'

    def ready(self):
        import obywatele.signals  # noqa: F401
        from home.feed_registry import register_feed_provider

        from .feed import get_feed_items, mark_as_read, mark_as_unread

        register_feed_provider('citizen', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
