from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from home.feed_registry import register_feed_provider
        from home.models import ReadStatus
        from home.services.feed import invalidate_feed_cache_on_change, make_read_status_markers

        from .feed import get_feed_items
        from .models import Event

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.EVENT)
        register_feed_provider('event', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)

        post_save.connect(invalidate_feed_cache_on_change, sender=Event)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Event)
