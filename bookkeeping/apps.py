from django.apps import AppConfig


class BookkeepingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookkeeping'

    def ready(self):
        from core.dashboard_registry import register_dashboard_provider

        from .dashboard import get_context as get_dashboard_context

        register_dashboard_provider('bookkeeping', get_context=get_dashboard_context)
