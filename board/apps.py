from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'board'

    def ready(self):
        # Import signals to register them
        import board.signals  # noqa: F401
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import make_read_status_markers

        from .dashboard import get_public_context
        from .feed import get_feed_items
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.POST)
        register_feed_provider('post', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('post', search=search)
        register_dashboard_provider('board', get_public_context=get_public_context)
