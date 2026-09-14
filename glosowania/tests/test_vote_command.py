"""Tests for the referendum-closing behaviour of `python manage.py vote`.

Focused on the anonymization fix: votes buffered outside the DB while the
referendum is open must only be written to VoteCode - shuffled, and tallied
into za/przeciw - once the referendum closes.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.db import OperationalError
from django.utils import timezone

from glosowania.models import Decyzja, KtoJuzGlosowal, ReferendumEffect, VoteCode


@pytest.fixture(autouse=True)
def vote_buffer_effects():
    with patch('glosowania.management.commands.vote.acknowledge_claimed_votes', return_value=True), patch('glosowania.management.commands.vote.clear_pending_votes', return_value=1):
        yield


@pytest.mark.django_db
def test_closing_referendum_reveals_shuffled_votes_and_tallies_them(sample_users, settings):
    settings.SITE_PROTOCOL = 'https'
    author = sample_users[0]
    today = timezone.localdate()

    decyzja = Decyzja.objects.create(
        title='Referendum Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.REFERENDUM,
        path='Proposition',
        data_referendum_start=today - timedelta(days=4),
        data_referendum_stop=today - timedelta(days=1),
    )

    for voter in sample_users[:3]:
        KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter)

    pending_votes = [{'code': 'aaaaa', 'vote': True}, {'code': 'bbbbb', 'vote': True}, {'code': 'ccccc', 'vote': False}]

    # Nothing revealed yet while the referendum was open.
    assert VoteCode.objects.filter(project=decyzja).count() == 0
    assert decyzja.za == 0
    assert decyzja.przeciw == 0

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=list(pending_votes)) as mock_claim,
        patch('core.notifications.send_notification_to_all_sync') as send_notification,
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

    mock_claim.assert_called_once_with(decyzja.id)
    notification = send_notification.call_args.args[0]
    assert notification['click_action'].startswith('https://')

    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.APPROVED
    assert decyzja.za == 2
    assert decyzja.przeciw == 1

    codes = set(VoteCode.objects.filter(project=decyzja).values_list('code', flat=True))
    assert codes == {'aaaaa', 'bbbbb', 'ccccc'}


@pytest.mark.django_db
def test_closing_referendum_rejects_when_no_votes_cast(sample_users):
    author = sample_users[0]
    today = timezone.localdate()

    decyzja = Decyzja.objects.create(
        title='Unpopular Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.REFERENDUM,
        path='Proposition',
        data_referendum_start=today - timedelta(days=4),
        data_referendum_stop=today - timedelta(days=1),
    )

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=[]),
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.REJECTED
    assert decyzja.za == 0
    assert decyzja.przeciw == 0
    assert VoteCode.objects.filter(project=decyzja).count() == 0


@pytest.mark.django_db
def test_closing_referendum_restarts_on_buffer_mismatch(sample_users, caplog):
    """If fewer (or more) votes come back from the buffer than KtoJuzGlosowal
    recorded voters, some votes were lost (e.g. the vote storage service
    restarted). Instead of tallying a wrong/partial result, the referendum
    must restart from scratch: no result is recorded, everyone is cleared
    from the who-voted list so they can vote again, and the voting window
    is reset to a full new period."""
    author = sample_users[0]
    today = timezone.localdate()

    decyzja = Decyzja.objects.create(
        title='Referendum Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.REFERENDUM,
        path='Proposition',
        data_referendum_start=today - timedelta(days=4),
        data_referendum_stop=today - timedelta(days=1),
    )
    for voter in sample_users[:2]:
        KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter)

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=[{'code': 'aaaaa', 'vote': True}]),
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
        caplog.at_level('WARNING'),
    ):
        call_command('vote')

    assert any('vote buffer' in message.lower() for message in caplog.messages)

    decyzja.refresh_from_db()
    # No result was ever tallied or revealed.
    assert decyzja.status == Decyzja.Status.REFERENDUM
    assert decyzja.za == 0
    assert decyzja.przeciw == 0
    assert VoteCode.objects.filter(project=decyzja).count() == 0
    # Nobody is marked as having voted anymore - everyone can vote again.
    assert KtoJuzGlosowal.objects.filter(projekt=decyzja).count() == 0
    # The voting window restarts from today for a full new period.
    assert decyzja.data_referendum_start == today
    assert decyzja.data_referendum_stop > today
    assert decyzja.referendum_restart_count == 1


def _create_expired_referendum(author, **overrides):
    today = timezone.localdate()
    values = {
        'title': 'P1a referendum',
        'tresc': 'Test law text',
        'kara': 'Test penalty',
        'author': author,
        'status': Decyzja.Status.REFERENDUM,
        'path': 'Proposition',
        'data_referendum_start': today - timedelta(days=4),
        'data_referendum_stop': today - timedelta(days=1),
    }
    values.update(overrides)
    return Decyzja.objects.create(**values)


def _record_voters(decyzja, users):
    for user in users:
        KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=user)


@pytest.mark.django_db
def test_sql_failure_after_vote_buffer_claim_preserves_buffer(sample_users):
    decyzja = _create_expired_referendum(sample_users[0])
    _record_voters(decyzja, sample_users[:2])
    buffered_votes = [{'code': 'aaaaa', 'vote': True}, {'code': 'bbbbb', 'vote': False}]

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=buffered_votes),
        patch('glosowania.management.commands.vote.acknowledge_claimed_votes') as acknowledge,
        patch.object(VoteCode.objects, 'bulk_create', side_effect=OperationalError('forced SQLite failure')),
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.REFERENDUM
    assert VoteCode.objects.filter(project=decyzja).count() == 0
    assert ReferendumEffect.objects.filter(decision=decyzja).count() == 0
    acknowledge.assert_not_called()


@pytest.mark.django_db
def test_bulk_create_failure_rolls_back_partial_referendum_result(sample_users):
    decyzja = _create_expired_referendum(sample_users[0])
    _record_voters(decyzja, sample_users[:2])
    pending_votes = [{'code': 'aaaaa', 'vote': True}, {'code': 'bbbbb', 'vote': False}]
    original_bulk_create = VoteCode.objects.bulk_create

    def create_then_fail(objects, *args, **kwargs):
        original_bulk_create(objects, *args, **kwargs)
        raise OperationalError('forced failure after insert')

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=pending_votes),
        patch.object(VoteCode.objects, 'bulk_create', side_effect=create_then_fail),
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.REFERENDUM
    assert decyzja.za == 0
    assert decyzja.przeciw == 0
    assert VoteCode.objects.filter(project=decyzja).count() == 0
    assert KtoJuzGlosowal.objects.filter(projekt=decyzja).count() == 2


@pytest.mark.django_db
def test_repeating_referendum_closure_does_not_duplicate_vote_codes(sample_users):
    decyzja = _create_expired_referendum(sample_users[0])
    _record_voters(decyzja, sample_users[:2])
    pending_votes = [{'code': 'aaaaa', 'vote': True}, {'code': 'bbbbb', 'vote': True}]

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=pending_votes) as claim_votes,
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')
        call_command('vote')

    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.APPROVED
    assert VoteCode.objects.filter(project=decyzja).count() == 2
    assert set(VoteCode.objects.filter(project=decyzja).values_list('code', flat=True)) == {'aaaaa', 'bbbbb'}
    claim_votes.assert_called_once_with(decyzja.id)


@pytest.mark.django_db
def test_failed_buffer_acknowledgement_is_recorded_and_retried(sample_users):
    decyzja = _create_expired_referendum(sample_users[0])
    _record_voters(decyzja, sample_users[:1])

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=[{'code': 'aaaaa', 'vote': True}]),
        patch('glosowania.management.commands.vote.acknowledge_claimed_votes', side_effect=[RuntimeError('forced acknowledgement failure'), True]) as acknowledge,
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

        effect = ReferendumEffect.objects.get(decision=decyzja, kind=ReferendumEffect.Kind.BUFFER_ACK)
        assert effect.applied_at is None
        assert effect.attempts == 1
        assert 'forced acknowledgement failure' in effect.last_error

        call_command('vote')

    effect.refresh_from_db()
    assert effect.applied_at is not None
    assert effect.attempts == 2
    assert effect.last_error == ''
    assert acknowledge.call_count == 2


@pytest.mark.parametrize(
    ('field_name', 'field_value', 'effect_target', 'effect_kind'),
    [
        ('proposed_parameters', {'LANGUAGE_CODE': 'pl'}, 'glosowania.management.commands.vote.apply_parameters', ReferendumEffect.Kind.PARAMETERS),
        ('proposed_brand_mark', 'site_branding/proposed/test.png', 'glosowania.management.commands.vote.apply_brand_mark', ReferendumEffect.Kind.BRAND_MARK),
    ],
)
@pytest.mark.django_db
def test_external_effect_failure_is_recorded_and_retried(sample_users, field_name, field_value, effect_target, effect_kind):
    decyzja = _create_expired_referendum(sample_users[0], **{field_name: field_value})
    _record_voters(decyzja, sample_users[:1])

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', return_value=[{'code': 'aaaaa', 'vote': True}]),
        patch(effect_target, side_effect=[RuntimeError('forced external effect failure'), None]) as apply_effect,
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

        decyzja.refresh_from_db()
        effect = ReferendumEffect.objects.get(decision=decyzja, kind=effect_kind)
        assert decyzja.status == Decyzja.Status.APPROVED
        assert decyzja.za == 1
        assert VoteCode.objects.filter(project=decyzja).count() == 1
        assert effect.applied_at is None
        assert effect.attempts == 1
        assert 'forced external effect failure' in effect.last_error

        call_command('vote')

    effect.refresh_from_db()
    assert effect.applied_at is not None
    assert effect.attempts == 2
    assert effect.last_error == ''
    assert apply_effect.call_count == 2


@pytest.mark.django_db
def test_failure_processing_one_decision_does_not_rollback_another(sample_users):
    broken = _create_expired_referendum(sample_users[0], title='Broken referendum')
    healthy = _create_expired_referendum(sample_users[1], title='Healthy referendum')
    _record_voters(broken, sample_users[:1])
    _record_voters(healthy, sample_users[1:2])
    pending_votes = {broken.id: [{'code': 'aaaaa', 'vote': True}], healthy.id: [{'code': 'bbbbb', 'vote': True}]}
    original_bulk_create = VoteCode.objects.bulk_create

    def fail_for_one_decision(objects, *args, **kwargs):
        objects = list(objects)
        if objects[0].project_id == broken.id:
            raise OperationalError('forced failure for one decision')
        return original_bulk_create(objects, *args, **kwargs)

    with (
        patch('glosowania.management.commands.vote.claim_pending_votes', side_effect=lambda decyzja_id: pending_votes[decyzja_id]),
        patch.object(VoteCode.objects, 'bulk_create', side_effect=fail_for_one_decision),
        patch('core.notifications.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

    broken.refresh_from_db()
    healthy.refresh_from_db()
    assert broken.status == Decyzja.Status.REFERENDUM
    assert VoteCode.objects.filter(project=broken).count() == 0
    assert healthy.status == Decyzja.Status.APPROVED
    assert healthy.za == 1
    assert healthy.przeciw == 0
    assert list(VoteCode.objects.filter(project=healthy).values_list('code', flat=True)) == ['bbbbb']
