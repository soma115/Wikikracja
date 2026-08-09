from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Survey


@receiver(post_save, sender=Survey)
@receiver(post_delete, sender=Survey)
def _invalidate_feed_cache_on_survey_change(sender, **kwargs):
    from home.services.feed import invalidate_feed_cache

    invalidate_feed_cache()
