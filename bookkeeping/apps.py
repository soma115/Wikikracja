from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save


class BookkeepingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookkeeping'

    def ready(self):
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.services.feed import invalidate_feed_cache_on_change, make_read_status_markers

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items
        from .models import Transaction

        register_dashboard_provider('bookkeeping', get_context=get_dashboard_context)
        mark_as_read, mark_as_unread = make_read_status_markers('transaction')
        register_feed_provider('transaction', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        post_save.connect(invalidate_feed_cache_on_change, sender=Transaction)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Transaction)
