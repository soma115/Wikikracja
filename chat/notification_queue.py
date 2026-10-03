"""Redis Streams queue for chat notification delivery."""

from __future__ import annotations

import json
import logging
import socket
import time
import uuid

import redis
from django.conf import settings

log = logging.getLogger(__name__)

STREAM_NAME = "wikikracja:chat:notifications"
CONSUMER_GROUP = "chat-notification-workers"
STREAM_MAXLEN = 10_000
CLAIM_IDLE_MS = 60_000


def _redis_client():
    return redis.Redis.from_url(settings.REDIS_HOST, decode_responses=True)


def ensure_consumer_group(client=None):
    client = client or _redis_client()
    try:
        client.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise
    return client


def enqueue_notification(*, user_id, room_id, notification, kind, push_event=None):
    """Enqueue one personal notification and return its stable job id."""
    job_id = f"message:{notification.get('notification_id', uuid.uuid4().hex)}:{user_id}:{kind}"
    payload = {"job_id": job_id, "user_id": str(user_id), "room_id": str(room_id), "kind": kind, "notification": json.dumps(notification, separators=(",", ":"))}
    if push_event:
        payload['push_event'] = push_event
    client = ensure_consumer_group()
    client.xadd(STREAM_NAME, payload, maxlen=STREAM_MAXLEN, approximate=True)
    log.debug("Queued chat notification job %s", job_id)
    return job_id


def _decode_job(fields):
    notification = fields.get("notification", "{}")
    job = {"job_id": fields["job_id"], "user_id": int(fields["user_id"]), "room_id": int(fields["room_id"]), "kind": fields["kind"], "notification": json.loads(notification)}
    push_event = fields.get('push_event')
    if push_event:
        job['push_event'] = push_event.decode() if isinstance(push_event, bytes) else push_event
    return job


def read_notifications(client, consumer_name=None, *, count=10, block_ms=5_000):
    """Read new jobs for a worker using the consumer group."""
    consumer_name = consumer_name or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    ensure_consumer_group(client)
    result = client.xreadgroup(CONSUMER_GROUP, consumer_name, {STREAM_NAME: ">"}, count=count, block=block_ms)
    if not result:
        return []
    return [(stream_id, _decode_job(fields)) for _stream, entries in result for stream_id, fields in entries]


def claim_notifications(client, consumer_name, *, count=10, min_idle_ms=CLAIM_IDLE_MS):
    """Claim jobs abandoned by a worker that died before acknowledging them."""
    ensure_consumer_group(client)
    _next_id, entries, _deleted = client.xautoclaim(STREAM_NAME, CONSUMER_GROUP, consumer_name, min_idle_ms, start_id="0-0", count=count)
    return [(stream_id, _decode_job(fields)) for stream_id, fields in entries]


def acknowledge_notification(client, stream_id):
    return client.xack(STREAM_NAME, CONSUMER_GROUP, stream_id)


CHAT_PUSH_COOLDOWN_SECONDS = 60 * 60
CHAT_PUSH_DELAYED_KEY = 'wikikracja:chat:notifications:delayed'
CHAT_PUSH_LOCK_SECONDS = 120


def _room_notification_state_keys(user_id, room_id):
    member = f'{user_id}:{room_id}'
    prefix = f'wikikracja:chat:notification:{member}'
    return member, f'{prefix}:lock', f'{prefix}:cooldown', f'{prefix}:pending'


def _redis_timestamp(value):
    if isinstance(value, bytes):
        value = value.decode()
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _release_lock(lock):
    try:
        lock.release()
    except redis.exceptions.LockError:
        pass


def dispatch_or_defer_chat_notification(client, job, deliver, *, now=None):
    """Deliver immediately or replace the pending job for this user-room pair."""
    now = time.time() if now is None else now
    member, lock_key, cooldown_key, pending_key = _room_notification_state_keys(job['user_id'], job['room_id'])
    lock = client.lock(lock_key, timeout=CHAT_PUSH_LOCK_SECONDS)
    if not lock.acquire(blocking=False):
        return None

    try:
        deadline = _redis_timestamp(client.get(cooldown_key))
        if deadline and deadline > now:
            client.set(pending_key, json.dumps(job, separators=(',', ':')), ex=CHAT_PUSH_COOLDOWN_SECONDS * 2)
            client.zadd(CHAT_PUSH_DELAYED_KEY, {member: deadline})
            return 'deferred'

        client.delete(pending_key)
        client.zrem(CHAT_PUSH_DELAYED_KEY, member)
        deliver(job)
        client.set(cooldown_key, str(now + CHAT_PUSH_COOLDOWN_SECONDS), ex=CHAT_PUSH_COOLDOWN_SECONDS + 5)
        return 'delivered'
    finally:
        _release_lock(lock)


def deliver_due_chat_notifications(client, deliver, *, now=None, limit=50):
    """Deliver the latest coalesced job when its user-room cooldown expires."""
    now = time.time() if now is None else now
    members = client.zrangebyscore(CHAT_PUSH_DELAYED_KEY, '-inf', now, start=0, num=limit)
    delivered = 0

    for raw_member in members:
        member = raw_member.decode() if isinstance(raw_member, bytes) else raw_member
        try:
            user_id, room_id = (int(value) for value in member.split(':', 1))
        except (TypeError, ValueError):
            client.zrem(CHAT_PUSH_DELAYED_KEY, member)
            continue

        _member, lock_key, cooldown_key, pending_key = _room_notification_state_keys(user_id, room_id)
        lock = client.lock(lock_key, timeout=CHAT_PUSH_LOCK_SECONDS)
        if not lock.acquire(blocking=False):
            continue

        try:
            pending = client.get(pending_key)
            if not pending:
                client.zrem(CHAT_PUSH_DELAYED_KEY, member)
                continue

            deadline = _redis_timestamp(client.get(cooldown_key))
            if deadline and deadline > now:
                client.zadd(CHAT_PUSH_DELAYED_KEY, {member: deadline})
                continue

            if isinstance(pending, bytes):
                pending = pending.decode()
            job = json.loads(pending)
            delivered_key = f"wikikracja:chat:notification-delivered:{job['job_id']}"
            if client.exists(delivered_key):
                client.delete(pending_key, cooldown_key)
                client.zrem(CHAT_PUSH_DELAYED_KEY, member)
                continue
            try:
                deliver(job)
            except Exception:
                log.exception('Failed to deliver delayed chat notification for %s', member)
                client.zadd(CHAT_PUSH_DELAYED_KEY, {member: now + 15})
                continue

            client.set(delivered_key, '1', ex=7 * 24 * 60 * 60)
            client.set(cooldown_key, str(now + CHAT_PUSH_COOLDOWN_SECONDS), ex=CHAT_PUSH_COOLDOWN_SECONDS + 5)
            client.delete(pending_key)
            client.zrem(CHAT_PUSH_DELAYED_KEY, member)
            delivered += 1
        finally:
            _release_lock(lock)

    return delivered


def clear_room_notification_state(user_id, room_id, client=None):
    """Clear cooldown and coalesced chat push after the user opens the room."""
    try:
        client = client or _redis_client()
        member, lock_key, cooldown_key, pending_key = _room_notification_state_keys(user_id, room_id)
        lock = client.lock(lock_key, timeout=CHAT_PUSH_LOCK_SECONDS)
        if not lock.acquire(blocking=True, blocking_timeout=1):
            return False
        try:
            client.delete(cooldown_key, pending_key)
            client.zrem(CHAT_PUSH_DELAYED_KEY, member)
            return True
        finally:
            _release_lock(lock)
    except Exception:
        log.warning('Could not reset chat notification state for user %s in room %s', user_id, room_id, exc_info=True)
        return False
