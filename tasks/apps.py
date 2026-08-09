from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"

    def ready(self):
        import tasks.signals  # noqa: F401
        from home.feed_registry import register_feed_provider

        from .feed import get_feed_items, mark_as_read, mark_as_unread

        register_feed_provider('task', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
