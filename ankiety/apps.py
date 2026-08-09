from django.apps import AppConfig


class AnkietyConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ankiety"
    verbose_name = "Ankiety"

    def ready(self):
        import ankiety.signals  # noqa: F401
        from home.feed_registry import register_feed_provider

        from .feed import get_feed_items, mark_as_read, mark_as_unread

        register_feed_provider("survey", get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
