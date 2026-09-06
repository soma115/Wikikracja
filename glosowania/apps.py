from django.apps import AppConfig


class VotingConfig(AppConfig):
    name = 'glosowania'

    def ready(self):
        import glosowania.signals  # noqa
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import make_read_status_markers

        from .dashboard import get_context as get_dashboard_context, get_site_admin_context
        from .feed import get_feed_items
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.DECISION)
        register_feed_provider('decision', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('decision', search=search)
        register_dashboard_provider('glosowania', get_context=get_dashboard_context, get_site_admin_context=get_site_admin_context)
