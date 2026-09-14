"""Temporary, out-of-database storage for cast referendum votes.

Why this exists
----------------
Historically, casting a vote wrote a `KtoJuzGlosowal` row (who voted) and a
`VoteCode` row (what they voted) in the very same transaction/request. Both
rows land in the SQL database at the same instant, in the same insertion
order, so anyone with read access to the database (an admin, a backup, a
leaked dump) could trivially pair them up by timing/order and deanonymize
every vote — despite `VoteCode` having no foreign key to the voter.

To break that correlation, the vote's content (code + choice) is buffered
here, in Redis, instead of being written straight to `VoteCode`. It never
touches the relational database - and therefore never appears in a SQL
backup/dump - until the referendum closes. At that point
`glosowania.management.commands.vote` claims the whole buffer for a
referendum, shuffles it, and bulk-writes it to `VoteCode` in one go, so the
resulting row order carries no information about when/in what order votes
were cast. The claim is acknowledged only after SQLite commits.

This does not provide cryptographic (zero-knowledge) anonymity - someone
actively monitoring the server in real time, at the exact moment a vote is
cast, could still observe the pairing. It does eliminate the much bigger,
much easier risk of anyone with (possibly much later, offline) database
access reconstructing the vote.
"""

from __future__ import annotations

import json

import redis
from django.conf import settings

_client = None
_BUFFER_VERSION = 'v2'


def _get_client():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_HOST)
    return _client


def _buffer_key(decyzja_id):
    return f'glosowania:vote_buffer:{_BUFFER_VERSION}:{decyzja_id}'


def _legacy_buffer_key(decyzja_id):
    """Return the pre-idempotency list key for a controlled migration."""
    return f'glosowania:vote_buffer:{decyzja_id}'


def push_pending_vote(decyzja_id, operation_id, code, vote):
    """Queue a vote once, even when the surrounding SQL transaction retries.

    ``operation_id`` is generated once per HTTP request and reused for every
    retry. Redis HSETNX makes the enqueue idempotent without storing the
    operation id in SQLite or exposing a voter identity in the buffer.
    """
    payload = json.dumps({'code': code, 'vote': bool(vote)}, separators=(',', ':'))
    client = _get_client()
    created = client.hsetnx(_buffer_key(decyzja_id), operation_id, payload)
    if created:
        return True

    existing = client.hget(_buffer_key(decyzja_id), operation_id)
    if existing is None:
        raise redis.RedisError('Vote buffer entry disappeared during idempotent enqueue')
    if isinstance(existing, bytes):
        existing = existing.decode()
    if existing != payload:
        raise redis.RedisError('Vote buffer operation id was reused with different data')
    return False


def discard_pending_vote(decyzja_id, operation_id):
    """Remove an idempotent entry when its SQL insert is known to have failed."""
    return bool(_get_client().hdel(_buffer_key(decyzja_id), operation_id))


def _claim_key(decyzja_id):
    return f'glosowania:vote_buffer:claim:v1:{decyzja_id}'


_CLAIM_PENDING_VOTES_SCRIPT = """
local current = redis.call('HGETALL', KEYS[1])
local legacy = redis.call('LRANGE', KEYS[2], 0, -1)
for index = 1, #current, 2 do
    redis.call('HSET', KEYS[3], current[index], current[index + 1])
end
local offset = redis.call('HLEN', KEYS[3])
for index = 1, #legacy do
    redis.call('HSET', KEYS[3], 'legacy:' .. (offset + index), legacy[index])
end
redis.call('DEL', KEYS[1], KEYS[2])
return redis.call('HGETALL', KEYS[3])
"""


def claim_pending_votes(decyzja_id):
    """Atomically move current and legacy votes into a retryable claim."""
    raw_hash = _get_client().eval(_CLAIM_PENDING_VOTES_SCRIPT, 3, _buffer_key(decyzja_id), _legacy_buffer_key(decyzja_id), _claim_key(decyzja_id))
    votes = []
    for index in range(1, len(raw_hash), 2):
        payload = raw_hash[index]
        if isinstance(payload, bytes):
            payload = payload.decode()
        votes.append(json.loads(payload))
    return votes


def acknowledge_claimed_votes(decyzja_id):
    """Delete a claimed snapshot after its SQLite result commits."""
    return bool(_get_client().delete(_claim_key(decyzja_id)))


def clear_pending_votes(decyzja_id):
    """Clear every buffer generation when a referendum must restart."""
    return _get_client().delete(_buffer_key(decyzja_id), _legacy_buffer_key(decyzja_id), _claim_key(decyzja_id))


def pending_vote_count(decyzja_id):
    client = _get_client()
    return client.hlen(_buffer_key(decyzja_id)) + client.llen(_legacy_buffer_key(decyzja_id)) + client.hlen(_claim_key(decyzja_id))
