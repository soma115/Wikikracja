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
`glosowania.management.commands.vote` pops the whole buffer for a
referendum, shuffles it, and bulk-writes it to `VoteCode` in one go, so the
resulting row order carries no information about when/in what order votes
were cast.

This does not provide cryptographic (zero-knowledge) anonymity - someone
actively monitoring the server in real time, at the exact moment a vote is
cast, could still observe the pairing. It does eliminate the much bigger,
much easier risk of anyone with (possibly much later, offline) database
access reconstructing the vote.
"""

import json

import redis
from django.conf import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_HOST)
    return _client


def _buffer_key(decyzja_id):
    return f"glosowania:vote_buffer:{decyzja_id}"


def push_pending_vote(decyzja_id, code, vote):
    """Queue a freshly cast vote instead of writing it to VoteCode directly."""
    payload = json.dumps({'code': code, 'vote': bool(vote)})
    _get_client().rpush(_buffer_key(decyzja_id), payload)


def pop_all_pending_votes(decyzja_id):
    """Atomically fetch and clear all buffered votes for a referendum.

    Returns a list of {'code': str, 'vote': bool} dicts, in the order they
    were cast. Callers MUST shuffle this list before persisting it anywhere
    queryable (e.g. VoteCode), otherwise the original ordering - and the
    anonymity this module exists to provide - leaks right back in.

    The LRANGE + DELETE pair runs inside a single Redis MULTI/EXEC block, so
    no vote cast concurrently with the flush can be silently dropped or
    double-counted.
    """
    client = _get_client()
    key = _buffer_key(decyzja_id)
    with client.pipeline() as pipe:
        pipe.lrange(key, 0, -1)
        pipe.delete(key)
        raw_items, _deleted = pipe.execute()
    return [json.loads(item) for item in raw_items]


def pending_vote_count(decyzja_id):
    return _get_client().llen(_buffer_key(decyzja_id))
