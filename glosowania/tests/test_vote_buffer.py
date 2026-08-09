"""Tests for the Redis-backed vote buffer (glosowania.vote_buffer).

Uses a small in-memory fake instead of a real Redis server - this repo's
tests don't spin up Redis (see zzz/test_settings.py, which swaps the cache
backend to LocMemCache for the same reason).
"""

from unittest.mock import patch

from glosowania import vote_buffer


class FakeRedisList:
    """Minimal stand-in for the handful of redis-py calls we use."""

    def __init__(self):
        self.store = {}

    def rpush(self, key, value):
        self.store.setdefault(key, []).append(value)

    def llen(self, key):
        return len(self.store.get(key, []))

    def pipeline(self):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.ops = []

    def lrange(self, key, start, end):
        self.ops.append(('lrange', key))
        return self

    def delete(self, key):
        self.ops.append(('delete', key))
        return self

    def execute(self):
        results = []
        for op, key in self.ops:
            if op == 'lrange':
                results.append(list(self.client.store.get(key, [])))
            elif op == 'delete':
                results.append(self.client.store.pop(key, None) is not None)
        return results

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_push_and_pop_round_trip():
    fake = FakeRedisList()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'aaaaa', True)
        vote_buffer.push_pending_vote(1, 'bbbbb', False)

        assert vote_buffer.pending_vote_count(1) == 2

        votes = vote_buffer.pop_all_pending_votes(1)

    assert votes == [{'code': 'aaaaa', 'vote': True}, {'code': 'bbbbb', 'vote': False}]


def test_pop_clears_the_buffer():
    fake = FakeRedisList()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'aaaaa', True)
        vote_buffer.pop_all_pending_votes(1)

        assert vote_buffer.pop_all_pending_votes(1) == []
        assert vote_buffer.pending_vote_count(1) == 0


def test_buffers_are_isolated_per_decyzja():
    fake = FakeRedisList()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'aaaaa', True)
        vote_buffer.push_pending_vote(2, 'zzzzz', False)

        assert vote_buffer.pop_all_pending_votes(1) == [{'code': 'aaaaa', 'vote': True}]
        assert vote_buffer.pop_all_pending_votes(2) == [{'code': 'zzzzz', 'vote': False}]
