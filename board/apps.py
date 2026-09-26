from django.apps import AppConfig


class BoardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'board'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        # Import signals to register them
        import board.signals  # noqa: F401
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import invalidate_feed_cache_on_change, make_read_status_markers

        from .dashboard import get_context, get_public_context
        from .feed import get_feed_items, prepare_digest_items, prepare_items
        from .models import Post
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.POST)
        register_feed_provider('post', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread, prepare_items=prepare_items, prepare_digest_items=prepare_digest_items)
        register_search_provider('post', search=search)
        register_dashboard_provider('board', get_context=get_context, get_public_context=get_public_context)

        post_save.connect(invalidate_feed_cache_on_change, sender=Post)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Post)
