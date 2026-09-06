import logging

from asgiref.sync import async_to_sync
from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import m2m_changed, post_delete, post_migrate, post_save
from django.dispatch import Signal, receiver

from core.signals import citizen_accepted, citizen_deleted

from .models import Message, Room
from .services import send_message

log = logging.getLogger(__name__)

chat_room_requested = Signal()
chat_message_requested = Signal()


@receiver(post_migrate)
def create_inbox_room(sender, **kwargs):
    """Create the guest-facing Inbox room when the app is initialized."""
    if sender.name != 'chat':
        return
    Room.create_inbox()


@receiver(post_save, sender=Message)
def _sync_room_last_message(sender, instance, created, **kwargs):
    # Denormalizujemy ostatnią wiadomość do Room, żeby sidebar mógł renderować podgląd bez JOIN-a.
    # last_activity przez Greatest() — nigdy nie cofamy czasu (room mógł być bumpowany później przez inną akcję).
    if created:
        Room.objects.filter(id=instance.room_id).update(
            last_message_text=instance.text[:200],
            last_message_sender_id=instance.sender_id,
            last_message_at=instance.time,
            last_message_anonymous=instance.anonymous,
            last_activity=Greatest(F('last_activity'), instance.time),
            archived=False,
        )
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


@receiver(chat_room_requested)
def on_chat_room_requested(sender, instance, title, founder, allowed_users, welcome_message, source_app, source_object_id, **kwargs):
    """Create or update a chat room on behalf of another app."""
    room = getattr(instance, 'chat_room', None)
    if room is None:
        room = Room.objects.filter(source_app=source_app, source_object_id=source_object_id).first()
    if room is None:
        room = Room.objects.filter(title=title).first()

    created = False
    if room is None:
        room = Room.objects.create(title=title, public=True, archived=False, protected=True, founder=founder, source_app=source_app, source_object_id=source_object_id)
        created = True
    else:
        if room.title != title:
            room.title = title
            room.save(update_fields=['title'])

    if room.source_app != source_app or room.source_object_id != source_object_id:
        room.source_app = source_app
        room.source_object_id = source_object_id
        room.save(update_fields=['source_app', 'source_object_id'])

    # Link the source instance without re-firing post_save.
    if hasattr(instance, 'chat_room_id') and instance.chat_room_id != room.id:
        type(instance).objects.filter(pk=instance.pk).update(chat_room=room)
        instance.chat_room = room

    if created and welcome_message:
        message_sender = kwargs.get('welcome_message_sender')
        message_anonymous = kwargs.get('welcome_message_anonymous', True)
        Message.objects.create(room=room, text=welcome_message, sender=message_sender, anonymous=message_anonymous)

    if created and allowed_users is not None:
        room.allowed.set(allowed_users)


@receiver(chat_message_requested)
def on_chat_message_requested(sender, room_title, message_text, from_user=None, anonymous=True, guest_email='', guest_name='', **kwargs):
    """Deliver a message to a chat room on behalf of another app."""
    try:
        room = Room.objects.get(title=room_title)
    except Room.DoesNotExist:
        log.error(f"Room '{room_title}' does not exist")
        return

    async_to_sync(send_message)(room, message_text, sender=from_user, anonymous=anonymous, guest_email=guest_email, guest_name=guest_name, linkify=False)


@receiver(citizen_accepted)
def create_one2one_rooms(sender, **kwargs):
    """Create all one-to-one rooms when a citizen is accepted."""
    Room.create_all_one2one_rooms()


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
