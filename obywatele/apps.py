from django.apps import AppConfig


class ObywateleConfig(AppConfig):
    name = 'obywatele'

    def ready(self):
        import obywatele.signals  # noqa: F401
        from home.feed_registry import register_feed_provider
        from home.models import ReadStatus
        from home.services.feed import make_read_status_markers

        from .feed import get_feed_items

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.CITIZEN)
        register_feed_provider('citizen', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
