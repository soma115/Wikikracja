from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'board'

    def ready(self):
        # Import signals to register them
        import board.signals  # noqa: F401
        from home.feed_registry import register_feed_provider

        from .feed import get_feed_items, mark_as_read, mark_as_unread
        register_feed_provider(
            'post',
            get_items=get_feed_items,
            mark_as_read=mark_as_read,
            mark_as_unread=mark_as_unread,
        )
