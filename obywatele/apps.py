from django.apps import AppConfig


class ObywateleConfig(AppConfig):
    name = 'obywatele'

    def ready(self):
        import obywatele.signals  # noqa: F401
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import make_read_status_markers

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.CITIZEN)
        register_feed_provider('citizen', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('citizen', search=search)
        register_dashboard_provider('obywatele', get_context=get_dashboard_context)
