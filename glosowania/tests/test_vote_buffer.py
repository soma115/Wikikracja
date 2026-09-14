"""Tests for the Redis-backed vote buffer (glosowania.vote_buffer).

Uses a small in-memory fake instead of a real Redis server - this repo's
tests don't spin up Redis (see zzz/test_settings.py, which swaps the cache
backend to LocMemCache for the same reason).
"""

from unittest.mock import patch

import pytest
import redis

from glosowania import vote_buffer


class FakeRedis:
    """Minimal stand-in for the Redis commands used by the vote buffer."""

    def __init__(self):
        self.hashes = {}
        self.lists = {}

    def hsetnx(self, key, field, value):
        values = self.hashes.setdefault(key, {})
        if field in values:
            return 0
        values[field] = value
        return 1

    def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    def hdel(self, key, field):
        values = self.hashes.get(key, {})
        deleted = field in values
        values.pop(field, None)
        return int(deleted)

    def hlen(self, key):
        return len(self.hashes.get(key, {}))

    def llen(self, key):
        return len(self.lists.get(key, []))

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            deleted += int(key in self.hashes or key in self.lists)
            self.hashes.pop(key, None)
            self.lists.pop(key, None)
        return deleted

    def eval(self, _script, numkeys, hash_key, legacy_key, claim_key):
        assert numkeys == 3
        claim = self.hashes.setdefault(claim_key, {})
        claim.update(self.hashes.get(hash_key, {}))
        offset = len(claim)
        for index, payload in enumerate(self.lists.get(legacy_key, []), start=1):
            claim[f'legacy:{offset + index}'] = payload
        self.hashes.pop(hash_key, None)
        self.lists.pop(legacy_key, None)
        return [item for pair in claim.items() for item in pair]


def test_push_claim_and_acknowledge_round_trip():
    fake = FakeRedis()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True)
        vote_buffer.push_pending_vote(1, 'operation-b', 'bbbbb', False)

        assert vote_buffer.pending_vote_count(1) == 2
        votes = vote_buffer.claim_pending_votes(1)
        assert vote_buffer.pending_vote_count(1) == 2
        assert vote_buffer.claim_pending_votes(1) == votes
        assert vote_buffer.acknowledge_claimed_votes(1) is True
        assert vote_buffer.pending_vote_count(1) == 0

    assert set(tuple(sorted(vote.items())) for vote in votes) == {(('code', 'aaaaa'), ('vote', True)), (('code', 'bbbbb'), ('vote', False))}


def test_repeating_operation_id_does_not_duplicate_vote():
    fake = FakeRedis()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        assert vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True) is True
        assert vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True) is False
        assert vote_buffer.pending_vote_count(1) == 1


def test_reusing_operation_id_with_different_vote_is_rejected():
    fake = FakeRedis()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True)
        with pytest.raises(redis.RedisError, match='reused'):
            vote_buffer.push_pending_vote(1, 'operation-a', 'bbbbb', False)


def test_claim_merges_current_legacy_and_late_votes_until_acknowledged():
    fake = FakeRedis()
    legacy_key = vote_buffer._legacy_buffer_key(1)
    fake.lists[legacy_key] = ['{"code":"legacy","vote":true}']
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True)
        votes = vote_buffer.claim_pending_votes(1)
        vote_buffer.push_pending_vote(1, 'operation-b', 'bbbbb', False)
        votes = vote_buffer.claim_pending_votes(1)

        assert len(votes) == 3
        assert vote_buffer.pending_vote_count(1) == 3
        vote_buffer.acknowledge_claimed_votes(1)
        assert vote_buffer.pending_vote_count(1) == 0


def test_clear_pending_votes_removes_sources_and_claim():
    fake = FakeRedis()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True)
        vote_buffer.claim_pending_votes(1)
        vote_buffer.push_pending_vote(1, 'operation-b', 'bbbbb', False)

        assert vote_buffer.clear_pending_votes(1) == 2
        assert vote_buffer.pending_vote_count(1) == 0


def test_buffers_are_isolated_per_decyzja():
    fake = FakeRedis()
    with patch.object(vote_buffer, '_get_client', return_value=fake):
        vote_buffer.push_pending_vote(1, 'operation-a', 'aaaaa', True)
        vote_buffer.push_pending_vote(2, 'operation-b', 'zzzzz', False)

        assert vote_buffer.claim_pending_votes(1) == [{'code': 'aaaaa', 'vote': True}]
        assert vote_buffer.claim_pending_votes(2) == [{'code': 'zzzzz', 'vote': False}]
