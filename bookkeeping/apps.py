from django.apps import AppConfig
from django.db.models.signals import post_delete, post_save, pre_delete


def delete_legacy_member_resources_on_profile_delete(sender, instance, using, **kwargs):
    from resources.models import LEGACY_RESOURCE_LISTING_SOURCE, Entity

    Entity.objects.using(using).filter(entity_type=Entity.Type.RESOURCE, is_community_owned=False, assigned_member_id=instance.pk, legacy_references__source_model=LEGACY_RESOURCE_LISTING_SOURCE).delete()


class BookkeepingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bookkeeping'

    def ready(self):
        from core.dashboard_registry import register_dashboard_provider
        from core.feed_registry import register_feed_provider
        from core.services.feed import invalidate_feed_cache_on_change, make_read_status_markers
        from obywatele.models import Uzytkownik

        from .dashboard import get_context as get_dashboard_context
        from .feed import get_feed_items
        from .models import Transaction

        register_dashboard_provider('bookkeeping', get_context=get_dashboard_context)
        mark_as_read, mark_as_unread = make_read_status_markers('transaction')
        register_feed_provider('transaction', get_items=get_feed_items, mark_as_read=mark_as_read, mark_as_unread=mark_as_unread)
        post_save.connect(invalidate_feed_cache_on_change, sender=Transaction)
        post_delete.connect(invalidate_feed_cache_on_change, sender=Transaction)
        pre_delete.connect(delete_legacy_member_resources_on_profile_delete, sender=Uzytkownik, dispatch_uid='bookkeeping.legacy_member_resources_delete', weak=False)
