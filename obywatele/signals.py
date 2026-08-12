from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from home.services.feed import invalidate_feed_cache_on_change

from .models import CitizenActivity, Uzytkownik


@receiver(post_save, sender=Uzytkownik)
def track_citizen_activities(sender, instance, created, **kwargs):
    """Track citizen activities when Uzytkownik is created or updated"""

    if created:
        # New candidate registered
        CitizenActivity.objects.create(uzytkownik=instance, activity_type=CitizenActivity.ActivityType.NEW_CANDIDATE, description=_('New candidate has registered'))


def track_user_blocked(uzytkownik, was_previously_active=False):
    """Track when a user is blocked - only if they were previously active"""
    if was_previously_active:
        CitizenActivity.objects.create(uzytkownik=uzytkownik, activity_type=CitizenActivity.ActivityType.USER_BLOCKED, description=_('Citizen has been blocked'))


@receiver(post_save, sender=CitizenActivity)
@receiver(post_delete, sender=CitizenActivity)
def _invalidate_feed_cache_on_citizen_activity_change(sender, **kwargs):
    invalidate_feed_cache_on_change(sender, **kwargs)
