from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from board.models import Post
from chat.models import Message, Room
from events.models import Event
from glosowania.models import Decyzja
from obywatele.models import CitizenActivity
from tasks.models import Task

# Feed cache invalidation — clear global feed cache when any feed-related model changes
_FEED_SIGNAL_SENDERS = (Post, Task, Event, Decyzja, CitizenActivity, Message)

for _sender in _FEED_SIGNAL_SENDERS:

    @receiver(post_save, sender=_sender, weak=False)
    @receiver(post_delete, sender=_sender, weak=False)
    def _invalidate_feed_cache(sender, **kwargs):
        from .views import invalidate_feed_cache
        invalidate_feed_cache()


@receiver(m2m_changed, sender=Room.allowed.through, weak=False)
def _invalidate_feed_cache_on_room_access_change(sender, **kwargs):
    from .views import invalidate_feed_cache
    invalidate_feed_cache()
