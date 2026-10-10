from django.apps import AppConfig


class VotingConfig(AppConfig):
    name = 'glosowania'

    def ready(self):
        from django.db.models.signals import post_delete, post_save, pre_delete

        import glosowania.signals  # noqa
        from chat.signals import delete_linked_chat_room
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.models import ReadStatus
        from core.search_registry import register_search_provider
        from core.services.feed import invalidate_feed_cache_on_change, make_read_status_markers

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items, get_items_by_ids
        from .models import Argument, Decyzja
        from .search import search

        mark_as_read, mark_as_unread = make_read_status_markers(ReadStatus.ContentType.DECISION)
        register_feed_provider('decision', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread, get_items_by_ids=get_items_by_ids)
        register_search_provider('decision', search=search)
        register_dashboard_provider('glosowania', get_context=get_dashboard_context)

        post_save.connect(invalidate_feed_cache_on_change, sender=Decyzja)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Decyzja)
        post_save.connect(invalidate_feed_cache_on_change, sender=Argument)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Argument)
        pre_delete.connect(delete_linked_chat_room, sender=Decyzja)
