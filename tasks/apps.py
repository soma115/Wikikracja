from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"

    def ready(self):
        import tasks.signals  # noqa: F401
        from chat.permissions import register_room_permission_checker
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import make_read_status_markers

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items
        from .models import Task
        from .search import search

        register_room_permission_checker(self.label, Task.can_user_post_in_chat_room)
        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.TASK)
        register_feed_provider('task', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        register_search_provider('task', search=search)
        register_dashboard_provider('tasks', get_context=get_dashboard_context)
