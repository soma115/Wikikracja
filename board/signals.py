import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from chat.signals import chat_message_requested, chat_room_requested
from core.services.feed import invalidate_feed_cache_on_change
from core.signals import important_post_published
from core.utils import build_site_url, get_site_domain
from zzz.templatetags.citizen_filters import user_display_name

from .models import Post, PostCategory

log = logging.getLogger(__name__)

User = get_user_model()


@receiver(pre_delete, sender=PostCategory)
def prevent_protected_category_delete(sender, instance, **kwargs):
    if instance.is_protected:
        raise ValidationError(_("Protected categories cannot be deleted."))


@receiver(post_save, sender=Post)
def notify_important_chat_on_important_post(sender, instance, created, **kwargs):
    """Keep a history of important-document status changes in the "Ważne" room."""
    public_visibilities = (Post.Visibility.GROUP, Post.Visibility.PUBLIC)
    previous_visibility = getattr(instance, '_previous_visibility', None)
    previous_important = getattr(instance, '_previous_is_important', None)
    visibility_changed = previous_visibility is not None and previous_visibility != instance.visibility
    important_changed = previous_important is not None and previous_important != instance.is_important
    was_important = created or previous_important is True
    is_important_context = instance.is_important or was_important

    if not is_important_context:
        return

    post_path = reverse('board:view_post', args=[instance.pk])
    protocol = 'http' if settings.DEBUG else 'https'
    post_url = f"{protocol}://{get_site_domain()}{post_path}"
    link = f"<a href='{post_url}'>{instance.title}</a>"

    actor = instance.author if created else instance.updated_by

    if created and instance.is_important and instance.visibility in public_visibilities:
        message = _("New important document by %(username)s: %(link)s") % {'username': user_display_name(actor), 'link': link}
    elif important_changed and not instance.is_important:
        message = _("Document is no longer marked as important: %(link)s") % {'link': link}
    elif visibility_changed and instance.visibility == Post.Visibility.ARCHIVE:
        message = _("Important document was archived: %(link)s") % {'link': link}
    elif visibility_changed and previous_visibility == Post.Visibility.ARCHIVE and instance.visibility in public_visibilities:
        message = _("Important document was made visible again: %(link)s") % {'link': link}
    elif instance.is_important and instance.visibility in public_visibilities:
        message = _("I've updated Important document: %(link)s") % {'link': link}
    else:
        return

    chat_message_requested.send(sender=Post, system_key='important', room_title="Ważne", message_text=message, from_user=actor, anonymous=False)
    if instance.is_important and instance.visibility in public_visibilities:
        important_post_published.send(sender=Post, post=instance, url=build_site_url(post_path), created=created)


@receiver(post_save, sender=Post)
def create_or_update_chat_room_for_post(sender, instance, created, **kwargs):
    """Create, archive, or update a document discussion room according to visibility."""
    room_title = instance.get_chat_room_title()
    post_path = reverse('board:view_post', args=[instance.pk])
    post_url = build_site_url(post_path)
    welcome_message = _("Discussion room for document: <a href='%(url)s'>%(title)s</a>") % {'title': instance.title, 'url': post_url}
    is_public = instance.visibility == Post.Visibility.PUBLIC
    is_archived = instance.visibility == Post.Visibility.ARCHIVE
    if is_public or instance.visibility == Post.Visibility.GROUP:
        allowed_users = User.objects.filter(is_active=True)
    elif instance.author_id:
        allowed_users = User.objects.filter(pk=instance.author_id)
    else:
        allowed_users = User.objects.none()

    chat_room_requested.send(
        sender=Post,
        instance=instance,
        title=room_title,
        founder=instance.author,
        allowed_users=allowed_users,
        welcome_message=welcome_message,
        welcome_message_sender=instance.author,
        welcome_message_anonymous=False,
        room_public=is_public,
        room_archived=is_archived,
        source_app='board',
        source_object_id=instance.pk,
    )

    log.info(f'Chat room "{room_title}" requested for document #{instance.pk}')


@receiver(pre_delete, sender=Post)
def delete_post_chat_room(sender, instance, **kwargs):
    """Automatically delete the associated chat room when a document is deleted."""
    if instance.system_key:
        raise ValidationError(_("System posts cannot be deleted."))
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
