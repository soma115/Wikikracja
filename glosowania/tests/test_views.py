"""Tests for glosowania views."""

from unittest.mock import patch

import pytest
import redis
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import OperationalError
from django.test import Client

from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

User = get_user_model()


@pytest.mark.django_db
def test_details_view_retries_on_database_lock(sample_users):
    """Test that details view retries on database lock error."""
    from django.test import RequestFactory

    from glosowania.views import details
    from glosowania.views import get_object_or_404 as original_get_object_or_404

    author = sample_users[0]
    decyzja = Decyzja.objects.create(title='Test Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.PROPOSITION)

    factory = RequestFactory()
    request = factory.get(f'/glosowania/details/{decyzja.pk}/')
    request.user = author

    # Mock get_object_or_404 to raise OperationalError on first call, succeed on second
    call_count = [0]

    def mock_get_object_or_404(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise OperationalError('database is locked')
        return original_get_object_or_404(*args, **kwargs)

    with patch('glosowania.views.get_object_or_404', side_effect=mock_get_object_or_404):
        response = details(request, decyzja.pk)

    # Should have retried and succeeded
    assert response.status_code == 200
    assert call_count[0] == 2  # First call failed, second succeeded


@pytest.mark.django_db
def test_details_view_with_chat_room(sample_users):
    """Test that details view loads correctly with chat room."""
    from django.test import Client

    author = sample_users[0]
    client = Client()
    client.force_login(author)

    decyzja = Decyzja.objects.create(title='Test Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.PROPOSITION)

    # Add some arguments
    Argument.objects.create(decyzja=decyzja, author=author, argument_type='FOR', content='Test argument for')
    Argument.objects.create(decyzja=decyzja, author=sample_users[1], argument_type='AGAINST', content='Test argument against')

    response = client.get(f'/glosowania/details/{decyzja.pk}/')

    assert response.status_code == 200
    assert b'Test Bill' in response.content


@pytest.mark.django_db
def test_voting_does_not_write_vote_code_directly(sample_users):
    """Casting a vote must not create a VoteCode row (or bump za/przeciw) right
    away - doing so in the same request/transaction as the KtoJuzGlosowal row
    is exactly the correlation that lets anyone with DB access deanonymize
    votes. The vote content should only be queued (glosowania.vote_buffer),
    to be revealed later, shuffled, once the referendum closes."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Referendum Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)

    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote') as mock_push:
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'tak': '1'})

    assert response.status_code == 302
    assert KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).exists()
    assert VoteCode.objects.filter(project=decyzja).count() == 0

    mock_push.assert_called_once()
    called_decyzja_id, called_code, called_vote = mock_push.call_args[0]
    assert called_decyzja_id == decyzja.id
    assert called_vote is True

    decyzja.refresh_from_db()
    assert decyzja.za == 0
    assert decyzja.przeciw == 0


@pytest.mark.django_db
def test_voting_when_vote_storage_is_down_does_not_mark_user_as_voted(sample_users):
    """If vote storage (Redis) is unreachable while casting a vote, the whole
    transaction - including the KtoJuzGlosowal row - must roll back, so the
    user isn't marked as having voted for a vote that was never recorded.
    They should see a friendly error instead of a 500."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Referendum Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)

    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote', side_effect=redis.RedisError('boom')):
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'tak': '1'})

    assert response.status_code == 302
    assert not KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).exists()


@pytest.mark.django_db
def test_double_voting_is_still_blocked_without_writing_a_second_pending_vote(sample_users):
    """A second vote attempt must be rejected before it reaches the buffer."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Referendum Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)
    KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter)

    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote') as mock_push:
        client.post(f'/glosowania/details/{decyzja.pk}/', {'nie': '1'})

    mock_push.assert_not_called()
    assert KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).count() == 1


@pytest.mark.django_db
def test_signing_rejected_when_not_proposition(sample_users):
    """Signing a motion must be rejected once it has left the PROPOSITION status."""
    author = sample_users[0]
    signer = sample_users[1]
    decyzja = Decyzja.objects.create(title='Ref Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)

    client = Client()
    client.force_login(signer)
    response = client.post(f'/glosowania/details/{decyzja.pk}/', {'sign': '1'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decyzja.pk}/'
    assert not ZebranePodpisy.objects.filter(projekt=decyzja, podpis_uzytkownika=signer).exists()


@pytest.mark.django_db
def test_withdrawing_rejected_when_not_proposition(sample_users):
    """Withdrawing a signature must be rejected once the motion has left the PROPOSITION status."""
    author = sample_users[0]
    signer = sample_users[1]
    decyzja = Decyzja.objects.create(title='Ref Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.PROPOSITION)
    ZebranePodpisy.objects.create(projekt=decyzja, podpis_uzytkownika=signer)
    decyzja.status = Decyzja.Status.DISCUSSION
    decyzja.save()

    client = Client()
    client.force_login(signer)
    response = client.post(f'/glosowania/details/{decyzja.pk}/', {'withdraw': '1'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decyzja.pk}/'
    assert ZebranePodpisy.objects.filter(projekt=decyzja, podpis_uzytkownika=signer).count() == 1


@pytest.mark.django_db
def test_voting_yes_rejected_when_not_referendum(sample_users):
    """Casting a Yes vote must be rejected when the motion is not in REFERENDUM status."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Prop Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.PROPOSITION)

    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote') as mock_push:
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'tak': '1'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decyzja.pk}/'
    assert not KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).exists()
    mock_push.assert_not_called()


@pytest.mark.django_db
def test_voting_no_rejected_when_not_referendum(sample_users):
    """Casting a No vote must be rejected when the motion is not in REFERENDUM status."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Prop Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.DISCUSSION)

    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote') as mock_push:
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'nie': '1'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decyzja.pk}/'
    assert not KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).exists()
    mock_push.assert_not_called()


@pytest.mark.django_db
def test_add_proposal_creates_decyzja(sample_users):
    """Submitting the add form must create a new PROPOSITION and redirect."""
    author = sample_users[0]
    client = Client()
    client.force_login(author)

    response = client.post('/glosowania/nowy/', {
        'title': 'New proposal',
        'tresc': 'Proposal law text',
        'uzasadnienie': 'It is needed',
        'kara': '',
        'znosi': '',
    })

    assert response.status_code == 302
    assert response.url == '/glosowania/proposition/'

    decyzja = Decyzja.objects.latest('id')
    assert decyzja.title == 'New proposal'
    assert decyzja.tresc == 'Proposal law text'
    assert decyzja.status == Decyzja.Status.PROPOSITION
    assert decyzja.author == author
    assert decyzja.ile_osob_podpisalo == 0


@pytest.mark.django_db
def test_add_proposal_invalid_form_shows_error_message(sample_users):
    """An invalid add form must re-render with an error message."""
    author = sample_users[0]
    client = Client()
    client.force_login(author)

    response = client.post('/glosowania/nowy/', {
        'title': '',
        'tresc': '',
        'uzasadnienie': '',
    })

    assert response.status_code == 200
    assert 'form' in response.context
    assert response.context['form'].errors
    assert Decyzja.objects.count() == 0

    messages_list = list(get_messages(response.wsgi_request))
    assert any('Please correct the errors below' in str(m) for m in messages_list)


@pytest.mark.django_db
def test_add_proposal_saves_even_when_notification_handler_fails(sample_users):
    """A failing vote_state_changed handler must not break the save/redirect."""
    author = sample_users[0]
    client = Client()
    client.force_login(author)

    with patch('glosowania.views.vote_state_changed.send', side_effect=RuntimeError('notification handler failed')):
        response = client.post('/glosowania/nowy/', {
            'title': 'Resilient proposal',
            'tresc': 'Proposal law text',
            'uzasadnienie': 'It is needed',
        })

    assert response.status_code == 302
    assert response.url == '/glosowania/proposition/'
    assert Decyzja.objects.filter(title='Resilient proposal').exists()
