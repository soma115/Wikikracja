"""Tests for glosowania views."""
import pytest
from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import Client
from unittest.mock import patch

from glosowania.models import Decyzja, Argument, ZebranePodpisy, KtoJuzGlosowal, VoteCode

User = get_user_model()


@pytest.mark.django_db
def test_details_view_retries_on_database_lock(sample_users):
    """Test that details view retries on database lock error."""
    from glosowania.views import details
    from django.test import RequestFactory
    from django.http import HttpRequest
    
    author = sample_users[0]
    decyzja = Decyzja.objects.create(
        title='Test Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.PROPOSITION
    )
    
    factory = RequestFactory()
    request = factory.get(f'/glosowania/details/{decyzja.pk}/')
    request.user = author
    
    # Mock get_object_or_404 to raise OperationalError on first call, succeed on second
    call_count = [0]
    original_get_object_or_404 = __import__('django.shortcuts', fromlist=['get_object_or_404']).get_object_or_404
    
    def mock_get_object_or_404(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise OperationalError('database is locked')
        return original_get_object_or_404(*args, **kwargs)
    
    with patch('django.shortcuts.get_object_or_404', side_effect=mock_get_object_or_404):
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
    
    decyzja = Decyzja.objects.create(
        title='Test Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.PROPOSITION
    )
    
    # Add some arguments
    Argument.objects.create(
        decyzja=decyzja,
        author=author,
        argument_type='FOR',
        content='Test argument for'
    )
    Argument.objects.create(
        decyzja=decyzja,
        author=sample_users[1],
        argument_type='AGAINST',
        content='Test argument against'
    )
    
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
    decyzja = Decyzja.objects.create(
        title='Referendum Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.REFERENDUM,
    )

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
def test_double_voting_is_still_blocked_without_writing_a_second_pending_vote(sample_users):
    """A second vote attempt must be rejected before it reaches the buffer."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(
        title='Referendum Bill',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.REFERENDUM,
    )
    KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter)

    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote') as mock_push:
        client.post(f'/glosowania/details/{decyzja.pk}/', {'nie': '1'})

    mock_push.assert_not_called()
    assert KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).count() == 1
