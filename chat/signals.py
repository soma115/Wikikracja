from django.db.models import F
from django.db.models.functions import Greatest
from django.db.models.signals import m2m_changed, post_delete, post_migrate, post_save
from django.dispatch import Signal, receiver

from .models import Message, Room

user_accepted = Signal()
user_deleted = Signal()


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
    from home.services.feed import invalidate_feed_cache

    invalidate_feed_cache()


@receiver(post_save, sender=Room)
@receiver(post_delete, sender=Room)
@receiver(m2m_changed, sender=Room.allowed.through)
def _invalidate_feed_cache_on_room_change(sender, **kwargs):
    from home.services.feed import invalidate_feed_cache

    invalidate_feed_cache()
