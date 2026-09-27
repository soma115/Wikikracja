from django.apps import AppConfig


class BookkeepingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookkeeping'

    def ready(self):
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items

        register_dashboard_provider('bookkeeping', get_context=get_dashboard_context)
        register_feed_provider('transaction', get_items=get_feed_items)
