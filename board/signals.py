import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from chat.signals import chat_message_requested, chat_room_requested
from home.services.feed import invalidate_feed_cache_on_change
from zzz.signals import important_post_published
from zzz.utils import build_site_url, get_site_domain

from .models import Post

log = logging.getLogger(__name__)

User = get_user_model()


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
def create_or_update_chat_room_for_post(sender, instance, created, **kwargs):
    """Ask the chat app to create or update a discussion room for this document."""
    if created:
        room_title = instance.get_chat_room_title()

        post_path = reverse('board:view_post', args=[instance.pk])
        post_url = build_site_url(post_path)
        welcome_message = _('Discussion room for document "%(title)s": %(url)s') % {'title': instance.title, 'url': post_url}

        chat_room_requested.send(
            sender=Post,
            instance=instance,
            title=room_title,
            founder=instance.author,
            allowed_users=User.objects.filter(is_active=True),
            welcome_message=welcome_message,
            welcome_message_sender=instance.author,
            welcome_message_anonymous=False,
            source_app='board',
            source_object_id=instance.pk,
        )

        log.info(f'Chat room "{room_title}" requested for document #{instance.pk}')
    elif instance.chat_room_id:
        # Request a title update if the document title changed.
        chat_room_requested.send(
            sender=Post, instance=instance, title=instance.get_chat_room_title(), founder=instance.author, allowed_users=None, welcome_message='', source_app='board', source_object_id=instance.pk
        )


@receiver(pre_delete, sender=Post)
def delete_post_chat_room(sender, instance, **kwargs):
    """Automatically delete the associated chat room when a document is deleted."""
    if instance.system_key:
        return
    room = instance.chat_room
    if room:
        room.delete()
        log.info(f"Deleted chat room '{room.title}' for document #{instance.pk}")
    else:
        log.info(f"No chat room linked to document #{instance.pk}, nothing to delete")


@receiver(post_save, sender=Post)
@receiver(post_delete, sender=Post)
def _invalidate_feed_cache_on_post_change(sender, **kwargs):
    invalidate_feed_cache_on_change(sender, **kwargs)
