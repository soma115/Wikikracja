from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import invalidate_feed_cache_on_change, make_read_status_markers

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items
        from .models import Event
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.EVENT)
        register_feed_provider('event', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('event', search=search)
        register_dashboard_provider('events', get_context=get_dashboard_context)

        post_save.connect(invalidate_feed_cache_on_change, sender=Event)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Event)
