from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from core.signals import citizen_blocked

from .models import CitizenActivity, Uzytkownik


def _lowercase_email(value):
    return value.lower() if value else value


@receiver(pre_save, sender=User)
def normalize_user_email(sender, instance, **kwargs):
    instance.email = _lowercase_email(instance.email)


@receiver(pre_save, sender=EmailAddress)
def normalize_email_address(sender, instance, **kwargs):
    instance.email = _lowercase_email(instance.email)


@receiver(post_save, sender=Uzytkownik)
def track_citizen_activities(sender, instance, created, **kwargs):
    """Track citizen activities when Uzytkownik is created or updated"""

    if created:
        # New candidate registered
        CitizenActivity.objects.create(uzytkownik=instance, activity_type=CitizenActivity.ActivityType.NEW_CANDIDATE, description=_('New candidate has registered'))


@receiver(post_delete, sender=Uzytkownik)
def delete_profile_avatar(sender, instance, using, **kwargs):
    if not instance.avatar:
        return

    storage = instance.avatar.storage
    name = instance.avatar.name
    transaction.on_commit(lambda: storage.delete(name), using=using)


@receiver(citizen_blocked)
def track_user_blocked(sender, user, was_previously_active=False, **kwargs):
    """Track when a citizen is blocked - only if they were previously active."""
    if not was_previously_active:
        return
    try:
        uzytkownik = user.uzytkownik
    except (AttributeError, Uzytkownik.DoesNotExist):
        return
    CitizenActivity.objects.create(uzytkownik=uzytkownik, activity_type=CitizenActivity.ActivityType.USER_BLOCKED, description=_('Citizen has been blocked'))
