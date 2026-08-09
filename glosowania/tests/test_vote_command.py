"""Tests for the referendum-closing behaviour of `python manage.py vote`.

Focused on the anonymization fix: votes buffered outside the DB while the
referendum is open must only be written to VoteCode - shuffled, and tallied
into za/przeciw - once the referendum closes.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from glosowania.models import Decyzja, KtoJuzGlosowal, VoteCode


@pytest.mark.django_db
def test_closing_referendum_reveals_shuffled_votes_and_tallies_them(sample_users):
    author = sample_users[0]
    today = timezone.now().date()

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
        patch('glosowania.management.commands.vote.pop_all_pending_votes', return_value=list(pending_votes)) as mock_pop,
        patch('glosowania.management.commands.vote.send_notification_email_to_active_users'),
        patch('glosowania.management.commands.vote.send_notification_to_all_sync'),
        patch('glosowania.management.commands.vote.Room.create_all_one2one_rooms'),
    ):
        call_command('vote')

    mock_pop.assert_called_once_with(decyzja.id)

    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.APPROVED
    assert decyzja.za == 2
    assert decyzja.przeciw == 1

    codes = set(VoteCode.objects.filter(project=decyzja).values_list('code', flat=True))
    assert codes == {'aaaaa', 'bbbbb', 'ccccc'}


@pytest.mark.django_db
def test_closing_referendum_rejects_when_no_votes_cast(sample_users):
    author = sample_users[0]
    today = timezone.now().date()

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
        patch('glosowania.management.commands.vote.pop_all_pending_votes', return_value=[]),
        patch('glosowania.management.commands.vote.send_notification_email_to_active_users'),
        patch('glosowania.management.commands.vote.send_notification_to_all_sync'),
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
    today = timezone.now().date()

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
        patch('glosowania.management.commands.vote.pop_all_pending_votes', return_value=[{'code': 'aaaaa', 'vote': True}]),
        patch('glosowania.management.commands.vote.send_notification_email_to_active_users'),
        patch('glosowania.management.commands.vote.send_notification_to_all_sync'),
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
