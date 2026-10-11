from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils.translation import gettext as _

from chat.models import Room
from chat.signals import chat_message_created, chat_message_requested, delete_linked_chat_room, request_discussion_room
from core.signals import citizen_accepted, document_created, important_post_published
from core.utils import build_site_url
from zzz.templatetags.citizen_filters import user_display_name

from .models import Post, PostCategory

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

    post_url = build_site_url(reverse('board:view_post', args=[instance.pk]))
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

    transaction.on_commit(lambda: chat_message_requested.send(sender=Post, system_key='important', room_title="Ważne", message_text=message, from_user=actor, anonymous=False), using=kwargs.get('using'))
    if instance.is_important and instance.visibility in public_visibilities:
        important_post_published.send(sender=Post, post=instance, url=post_url, created=created)


@receiver(post_save, sender=Post)
def notify_new_visible_document(sender, instance, created, **kwargs):
    if not created or instance.visibility not in (Post.Visibility.GROUP, Post.Visibility.PUBLIC):
        return

    post_url = build_site_url(reverse('board:view_post', args=[instance.pk]))
    transaction.on_commit(lambda: document_created.send(sender=Post, post=instance, url=post_url))


@receiver(post_save, sender=Post)
def create_or_update_chat_room_for_post(sender, instance, created, **kwargs):
    """Create, archive, or update a document discussion room according to visibility."""
    is_public = instance.chat_room_public
    is_archived = instance.chat_room_archived
    if is_public or instance.visibility in (Post.Visibility.GROUP, Post.Visibility.ARCHIVE):
        allowed_users = User.objects.filter(is_active=True)
    elif instance.author_id:
        allowed_users = User.objects.filter(pk=instance.author_id)
    else:
        allowed_users = User.objects.none()

    request_discussion_room(instance, founder=instance.author, allowed_users=allowed_users, public=is_public, archived=is_archived)


@receiver(chat_message_created)
def restore_archived_post_after_discussion_message(sender, message, room_was_archived, **kwargs):
    if not room_was_archived:
        return

    room = Room.objects.filter(pk=message.room_id, source_app=Post._meta.app_label).first()
    if room is None:
        return

    post = Post.objects.filter(pk=room.source_object_id, visibility=Post.Visibility.ARCHIVE).first()
    if post is not None:
        post.visibility = Post.Visibility.GROUP
        post.updated_by = message.sender
        post.save(update_fields=['visibility', 'updated_by', 'updated'])


@receiver(citizen_accepted)
def add_new_citizen_to_document_rooms(sender, user, **kwargs):
    user_id = getattr(user, 'pk', getattr(user, 'id', None))
    if not user_id or not User.objects.filter(pk=user_id).exists():
        return

    visible_document_ids = Post.objects.filter(visibility__in=(Post.Visibility.GROUP, Post.Visibility.ARCHIVE)).values_list('pk', flat=True)
    room_ids = list(Room.objects.filter(source_app=Post._meta.app_label, source_object_id__in=visible_document_ids).values_list('id', flat=True))
    if not room_ids:
        return

    membership_model = Room.allowed.through
    membership_model.objects.bulk_create([membership_model(room_id=room_id, user_id=user_id) for room_id in room_ids], ignore_conflicts=True)
    Room.apply_default_notification_preferences(room_ids, [user_id])


@receiver(pre_delete, sender=Post)
def delete_post_chat_room(sender, instance, **kwargs):
    """Block deletion of system posts; delete the associated chat room otherwise."""
    if instance.system_key:
        raise ValidationError(_("System posts cannot be deleted."))
    delete_linked_chat_room(sender, instance, **kwargs)
