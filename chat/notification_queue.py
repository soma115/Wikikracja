"""Redis Streams queue for chat notification delivery."""

from __future__ import annotations

import json
import logging
import socket
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


def enqueue_notification(*, user_id, room_id, notification, kind):
    """Enqueue one personal notification and return its stable job id."""
    job_id = f"message:{notification.get('notification_id', uuid.uuid4().hex)}:{user_id}:{kind}"
    payload = {"job_id": job_id, "user_id": str(user_id), "room_id": str(room_id), "kind": kind, "notification": json.dumps(notification, separators=(",", ":"))}
    client = ensure_consumer_group()
    client.xadd(STREAM_NAME, payload, maxlen=STREAM_MAXLEN, approximate=True)
    log.debug("Queued chat notification job %s", job_id)
    return job_id


def _decode_job(fields):
    notification = fields.get("notification", "{}")
    return {"job_id": fields["job_id"], "user_id": int(fields["user_id"]), "room_id": int(fields["room_id"]), "kind": fields["kind"], "notification": json.loads(notification)}


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
