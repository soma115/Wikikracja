from django.apps import AppConfig


class AnkietyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ankiety"
    verbose_name = "Ankiety"

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import invalidate_feed_cache_on_change, make_read_status_markers

        from .feed import get_feed_items
        from .models import Survey
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.SURVEY)
        register_feed_provider("survey", get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('survey', search=search)

        post_save.connect(invalidate_feed_cache_on_change, sender=Survey)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Survey)
