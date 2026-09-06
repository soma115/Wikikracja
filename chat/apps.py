from django.apps import AppConfig


class ChatConfig(AppConfig):
    name = 'chat'

    def ready(self):
        # Import signals to register them
        import chat.signals  # noqa: F401
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.search_registry import register_search_provider

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items, mark_as_read, mark_as_unread, prepare_digest_items, prepare_items
        from .search import search

        register_feed_provider('room_messages', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread, prepare_items=prepare_items, prepare_digest_items=prepare_digest_items)
        register_search_provider('chat', search=search)
        register_dashboard_provider('chat', get_context=get_dashboard_context)
