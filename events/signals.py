from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Event


@receiver(post_save, sender=Event)
@receiver(post_delete, sender=Event)
def _invalidate_feed_cache_on_event_change(sender, **kwargs):
    from home.services.feed import invalidate_feed_cache

    invalidate_feed_cache()
