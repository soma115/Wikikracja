from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from chat.signals import chat_message_requested
from home.services.feed import invalidate_feed_cache_on_change
from zzz.signals import important_post_published
from zzz.utils import build_site_url, get_site_domain

from .models import Post


@receiver(post_save, sender=Post)
def notify_important_chat_on_important_post(sender, instance, created, **kwargs):
    """Send notification to "Ważne" chat room when a post is important."""
    if not instance.is_important:
        return

    # Determine if this is a new important post or an update to an existing one
    post_path = reverse('board:view_post', args=[instance.pk])
    protocol = 'http' if settings.DEBUG else 'https'
    post_url = f"{protocol}://{get_site_domain()}{post_path}"

    if created:
        message = _("New important document by %(username)s: %(title)s - %(post_url)s") % {'username': instance.author.username, 'post_url': post_url, 'title': instance.title}
    else:
        message = _("Updated important document by %(username)s: %(title)s - %(post_url)s") % {'username': instance.author.username, 'post_url': post_url, 'title': instance.title}

    chat_message_requested.send(sender=Post, room_title="Ważne", message_text=message, from_user=instance.author, anonymous=False)
    important_post_published.send(sender=Post, post=instance, url=build_site_url(post_path), created=created)


@receiver(post_save, sender=Post)
@receiver(post_delete, sender=Post)
def _invalidate_feed_cache_on_post_change(sender, **kwargs):
    invalidate_feed_cache_on_change(sender, **kwargs)
