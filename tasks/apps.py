from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"

    def ready(self):
        import tasks.signals  # noqa: F401
        from home.dashboard_registry import register_dashboard_provider
        from home.feed_registry import register_feed_provider
        from home.models import ReadStatus
        from home.search_registry import register_search_provider
        from home.services.feed import make_read_status_markers

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.TASK)
        register_feed_provider('task', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('task', search=search)
        register_dashboard_provider('tasks', get_context=get_dashboard_context)
