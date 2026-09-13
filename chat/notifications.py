"""Chat-specific notification orchestration and Redis delivery jobs."""

from __future__ import annotations

import logging
import uuid

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils.translation import gettext as _

from core import notifications as core_notifications
from core.notifications import NOTIF_LOG_TAG
from core.utils import get_site_domain
from zzz.templatetags.citizen_filters import user_display_name

from .models import MessageReadBy, Room
from .notification_queue import enqueue_notification
from .services import CHAT_UNREAD_CACHE_KEY

log = logging.getLogger(__name__)


class ChatNotificationService:
    """Coordinate unread state and enqueue personal chat notifications."""

    def __init__(self, channel_layer, online_registry):
        self.channel_layer = channel_layer
        self.online_registry = online_registry

    async def dispatch_message(self, room, message, sender, mentioned_users):
        mentioned_user_ids = {user.id for user in mentioned_users}
        room_members = await database_sync_to_async(lambda: list(room.allowed.all()))()
        other_members = [member for member in room_members if member.id != (sender.id if sender else None)]
        if not other_members:
            return

        other_member_ids = [member.id for member in other_members]
        online_ids = set(self.online_registry.get_online())
        offline_ids = [user_id for user_id in other_member_ids if user_id not in online_ids]
        if offline_ids:
            await database_sync_to_async(self._clear_unread_state)(room.id, offline_ids)
        await database_sync_to_async(self._clear_unread_caches)(other_member_ids)

        membership_prefs = await database_sync_to_async(Room.get_membership_preferences_bulk)(room.id, other_member_ids)
        author = "Anonymous" if message.anonymous else (user_display_name(sender) if sender else "System")
        room_name = self._room_notification_name(room, sender)
        notification = await self._build_notification(author, room.id, room_name)

        for member in other_members:
            prefs = membership_prefs.get(member.id, {'seen': False, 'muted': True})
            consumer = self.online_registry.get_consumer(member)
            is_present = bool(consumer) and consumer.rooms.present(room)
            is_mentioned = member.id in mentioned_user_ids

            await self.channel_layer.group_send(f"user_{member.id}", {"type": "chat.room_unread", "room_id": room.id, "delta": 1})

            if not prefs['muted'] and not is_mentioned:
                await self._enqueue_delivery(member.id, room.id, notification, 'notification')

            if consumer and not is_present and prefs['seen']:
                await consumer.repo.unsee_room(room)
                await consumer.push_unread_count()
                await consumer.send_json({"unsee_room": room.id})

        for user in mentioned_users:
            if user.id != (sender.id if sender else None):
                await self._enqueue_delivery(user.id, room.id, notification, 'mention')

    async def _enqueue_delivery(self, user_id, room_id, notification, kind):
        try:
            await sync_to_async(enqueue_notification, thread_sensitive=False)(user_id=user_id, room_id=room_id, notification={**notification, "room_id": room_id}, kind=kind)
        except Exception:
            log.error("%s Failed to queue %s notification for user %s in room %s", NOTIF_LOG_TAG, kind, user_id, room_id, exc_info=True)

    @staticmethod
    def _clear_unread_state(room_id, user_ids):
        MessageReadBy.objects.filter(message__room_id=room_id, user_id__in=user_ids).delete()
        Room.seen_by.through.objects.filter(room_id=room_id, user_id__in=user_ids).delete()

    @staticmethod
    def _clear_unread_caches(user_ids):
        cache.delete_many([CHAT_UNREAD_CACHE_KEY.format(user_id=user_id) for user_id in user_ids])

    @staticmethod
    def _room_notification_name(room, sender):
        return room.clean_title() if room.public else (user_display_name(sender) if sender else "System")

    @staticmethod
    async def _build_notification(author, room_id, room_name):
        site_url = f"https://{await database_sync_to_async(get_site_domain)()}"
        notification_id = uuid.uuid4().hex
        log.debug("%s Built chat notification %s for room %s", NOTIF_LOG_TAG, notification_id, room_id)
        return {
            'notification_id': notification_id,
            'title': _("Room: %(room)s") % {'room': room_name} if room_name else _("Chat"),
            'body': _("Sender: %(author)s") % {'author': author},
            'icon': f"{site_url}/favicon.ico",
            'click_action': f"{site_url}/chat#room_id={room_id}",
            'tag': f'chat-{room_id}',
            'room_name': room_name,
        }


def deliver_notification_job(job):
    """Deliver one queued job. Exceptions intentionally propagate for retry."""
    user = get_user_model().objects.get(pk=job['user_id'], is_active=True)
    notification = {**job['notification'], 'room_id': job['room_id']}
    ws_type = 'chat.mention' if job['kind'] == 'mention' else 'chat.notification'
    core_notifications.send_websocket_to_user_sync(user.id, notification, ws_type=ws_type)
    core_notifications.send_fcm_to_user_sync(user, notification, notification_type='chat')
    log.info("%s Delivered chat notification job %s to user %s", NOTIF_LOG_TAG, job['job_id'], user.id)
