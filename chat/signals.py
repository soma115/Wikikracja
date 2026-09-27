import logging

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import m2m_changed, post_delete, post_migrate, post_save
from django.dispatch import Signal, receiver

from core.signals import citizen_accepted, citizen_deleted

from .models import Message, Room
from .services import ensure_system_rooms, send_message

log = logging.getLogger(__name__)

chat_room_requested = Signal()
chat_message_requested = Signal()


def request_discussion_room(instance, *, founder, allowed_users=None, welcome_message='', welcome_message_sender=None, welcome_message_anonymous=True, public=True, archived=False):
    """Ask chat to create or update the discussion room linked to a ChatRoomModel instance.

    Title and source coordinates are derived from the instance, so each app
    supplies only what actually differs.
    """
    room_title = instance.get_chat_room_title()
    chat_room_requested.send(
        sender=type(instance),
        instance=instance,
        title=room_title,
        founder=founder,
        allowed_users=allowed_users,
        welcome_message=welcome_message,
        welcome_message_sender=welcome_message_sender,
        welcome_message_anonymous=welcome_message_anonymous,
        room_public=public,
        room_archived=archived,
        source_app=instance._meta.app_label,
        source_object_id=instance.pk,
    )
    log.info("Discussion room '%s' requested for %s #%s", room_title, instance._meta.label, instance.pk)


def ensure_discussion_room_for_instance(instance):
    """Create a missing room for a ChatRoomModel instance without a welcome message."""
    from django.contrib.auth import get_user_model

    if instance.chat_room_id:
        return instance.chat_room

    users = get_user_model().objects.filter(is_active=True)
    app_label = instance._meta.app_label
    public = True
    archived = False
    if app_label == 'board':
        from board.models import Post

        public = instance.visibility == Post.Visibility.PUBLIC
        archived = instance.visibility == Post.Visibility.ARCHIVE

    request_discussion_room(instance, founder=getattr(instance, 'author', None) or getattr(instance, 'created_by', None), allowed_users=users, public=public, archived=archived)
    return instance.chat_room


def delete_linked_chat_room(sender, instance, **kwargs):
    """pre_delete receiver: delete the discussion room linked to the instance."""
    room = instance.chat_room
    if room:
        room.delete()
        log.info("Deleted chat room '%s' linked to %s #%s", room.title, instance._meta.label, instance.pk)


@receiver(post_migrate)
def ensure_system_chat_rooms(sender, **kwargs):
    """Create the application-managed chat rooms when the app is initialized."""
    if sender.name != 'chat':
        return
    ensure_system_rooms()


@receiver(post_save, sender=Message)
def _sync_room_last_message(sender, instance, created, **kwargs):
    # Denormalizujemy ostatnią wiadomość do Room, żeby sidebar mógł renderować podgląd bez JOIN-a.
    # last_activity przez Greatest() — nigdy nie cofamy czasu (room mógł być bumpowany później przez inną akcję).
    if created:
        room = Room.objects.filter(id=instance.room_id).first()
        was_archived = room is not None and room.archived
        Room.objects.filter(id=instance.room_id).update(
            last_message_text=instance.text[:200],
            last_message_sender_id=instance.sender_id,
            last_message_at=instance.time,
            last_message_anonymous=instance.anonymous,
            last_activity=Greatest(F('last_activity'), instance.time),
            archived=False,
        )
        if was_archived and room.source_app == 'board':
            from board.models import Post

            post = Post.objects.filter(pk=room.source_object_id, visibility=Post.Visibility.ARCHIVE).first()
            if post is not None:
                post.visibility = Post.Visibility.GROUP
                post.updated_by = instance.sender
                post.save(update_fields=['visibility', 'updated_by', 'updated'])
    else:
        # Na edycji: interesuje nas tylko zmiana tekstu.
        uf = kwargs.get('update_fields')
        if uf is not None and 'text' not in uf:
            return
        # Aktualizuj last_message_text tylko jeśli to ostatnia wiadomość w pokoju.
        # Sprawdzamy po pk (auto-increment) — wyższy pk = nowsza wiadomość, niezależnie od
        # auto_now na polu time, które zmienia się przy każdym save().
        is_last = not Message.objects.filter(room_id=instance.room_id, pk__gt=instance.pk).exists()
        if is_last:
            Room.objects.filter(id=instance.room_id).update(last_message_text=instance.text[:200])


@receiver(post_save, sender=Message)
@receiver(post_delete, sender=Message)
def _invalidate_feed_cache_on_message_change(sender, **kwargs):
    from core.services.feed import invalidate_feed_cache

    invalidate_feed_cache()


@receiver(post_save, sender=Room)
@receiver(post_delete, sender=Room)
@receiver(m2m_changed, sender=Room.allowed.through)
def _invalidate_feed_cache_on_room_change(sender, **kwargs):
    from core.services.feed import invalidate_feed_cache

    invalidate_feed_cache()


def _create_discussion_room(title, *, public, archived, founder, source_app, source_object_id):
    """Create a room with a display-only collision suffix; lookup remains ID-based."""
    for attempt in range(10):
        suffix = '' if attempt == 0 else f' [{source_app}#{source_object_id}-{attempt}]'
        candidate = f'{title[: 255 - len(suffix)]}{suffix}'
        try:
            with transaction.atomic():
                return Room.objects.create(title=candidate, public=public, archived=archived, protected=True, founder=founder, source_app=source_app, source_object_id=source_object_id)
        except IntegrityError:
            existing = Room.objects.filter(source_app=source_app, source_object_id=source_object_id).first()
            if existing is not None:
                return existing
    raise IntegrityError(f'Could not create a unique title for {source_app} #{source_object_id}')


@receiver(chat_room_requested)
def on_chat_room_requested(sender, instance, title, founder, allowed_users, welcome_message, source_app, source_object_id, room_public=True, room_archived=False, **kwargs):
    """Create or update a chat room using the source object's stable ID only."""
    with transaction.atomic():
        room = None
        if getattr(instance, 'chat_room_id', None):
            room = Room.objects.filter(pk=instance.chat_room_id, source_app=source_app, source_object_id=source_object_id).first()
        if room is None:
            room = Room.objects.filter(source_app=source_app, source_object_id=source_object_id).first()

        if room is None:
            room = _create_discussion_room(title, public=room_public, archived=room_archived, founder=founder, source_app=source_app, source_object_id=source_object_id)
        else:
            changed_fields = []
            if room.title != title:
                if Room.objects.filter(title=title).exclude(pk=room.pk).exists():
                    suffix = f' [{source_app}#{source_object_id}]'
                    title = f'{title[: 255 - len(suffix)]}{suffix}'
                room.title = title
                changed_fields.append('title')
            if room.public != room_public:
                room.public = room_public
                changed_fields.append('public')
            if room.archived != room_archived:
                room.archived = room_archived
                changed_fields.append('archived')
            if changed_fields:
                room.save(update_fields=changed_fields)

        # Link the source instance without re-firing post_save.
        if hasattr(instance, 'chat_room_id') and instance.chat_room_id != room.id:
            type(instance).objects.filter(pk=instance.pk).update(chat_room=room)
        if hasattr(instance, 'chat_room_id'):
            instance.chat_room = room

        if welcome_message and not room.messages.exists():
            message_sender = kwargs.get('welcome_message_sender')
            message_anonymous = kwargs.get('welcome_message_anonymous', True)
            Message.objects.create(room=room, text=welcome_message, sender=message_sender, anonymous=message_anonymous)

        if allowed_users is not None:
            room.allowed.set(allowed_users)

    return room


@receiver(chat_message_requested)
def on_chat_message_requested(sender, message_text='', from_user=None, anonymous=True, guest_email='', guest_name='', system_key='', room_id=None, **kwargs):
    """Deliver a message to a chat room on behalf of another app."""
    room = Room.objects.filter(pk=room_id).first() if room_id else None
    if room is None and system_key:
        room = Room.objects.filter(system_key=system_key).first()
    if room is None:
        log.error("Chat room '%s' does not exist", room_id or system_key)
        return

    async_to_sync(send_message)(room, message_text, sender=from_user, anonymous=anonymous, guest_email=guest_email, guest_name=guest_name, linkify=False)


@receiver(citizen_accepted)
def create_one2one_rooms(sender, **kwargs):
    """Create all one-to-one rooms when a citizen is accepted."""
    Room.create_all_one2one_rooms()


@receiver(citizen_accepted)
def add_citizen_to_public_rooms(sender, user, **kwargs):
    """Grant a newly accepted citizen access to existing public rooms."""
    room_ids = Room.objects.filter(public=True).values_list('id', flat=True)
    membership_model = Room.allowed.through
    user_id = getattr(user, 'pk', getattr(user, 'id', None))
    if not user_id or not get_user_model().objects.filter(pk=user_id).exists():
        return
    membership_model.objects.bulk_create([membership_model(room_id=room_id, user_id=user_id) for room_id in room_ids], ignore_conflicts=True)


@receiver(citizen_deleted)
def cleanup_user_chat_rooms(sender, user, **kwargs):
    """Clean up chat rooms after a citizen is deleted.

    Deletes private one-to-one rooms and removes the user from all remaining
    room memberships (allowed, muted, seen).
    """
    private_rooms = Room.objects.filter(public=False, allowed=user)
    for room in private_rooms:
        log.info(f'Room {room} deleted.')
    private_rooms.delete()

    user.rooms.clear()
    user.muted_rooms.clear()
    user.seen_rooms.clear()
