"""Tests for glosowania views."""

import io
from datetime import date, timedelta
from unittest.mock import call, patch

import pytest
import redis
from django import forms
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.test import Client
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override
from PIL import Image

from glosowania.forms import ParametersProposalForm
from glosowania.models import Argument, Decyzja, DecyzjaWersja, KtoJuzGlosowal, VoteCode, ZebranePodpisy
from site_settings.models import SiteParameters

User = get_user_model()


def _image_upload(name, image_format):
    output = io.BytesIO()
    mode = 'RGB' if image_format == 'JPEG' else 'RGBA'
    Image.new(mode, (64, 64), (0, 0, 0) if mode == 'RGB' else (0, 0, 0, 0)).save(output, format=image_format)
    return SimpleUploadedFile(name, output.getvalue(), content_type=f'image/{image_format.lower()}')


@pytest.mark.django_db
def test_parameters_proposal_accepts_only_png_logo():
    form = ParametersProposalForm()
    assert form.fields['brand_mark'].widget.attrs['accept'] == 'image/png'
    with override('en'):
        assert 'transparent background' in str(form.fields['brand_mark'].help_text)

    jpeg = form.fields['brand_mark'].clean(_image_upload('logo.jpg', 'JPEG'))
    form.cleaned_data = {'brand_mark': jpeg}
    with pytest.raises(forms.ValidationError, match='PNG'):
        form.clean_brand_mark()


@pytest.mark.django_db
def test_parameters_proposal_accepts_png_logo():
    form = ParametersProposalForm()
    png = form.fields['brand_mark'].clean(_image_upload('logo.png', 'PNG'))
    form.cleaned_data = {'brand_mark': png}

    normalized = form.clean_brand_mark()

    assert normalized.name == 'brand_mark.png'


@pytest.mark.django_db
def test_details_does_not_show_edit_action_for_orphaned_proposition(sample_users):
    client = Client()
    client.force_login(sample_users[0])
    decyzja = Decyzja.objects.create(title='Orphaned proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=None)

    response = client.get(f'/glosowania/details/{decyzja.pk}/')

    assert response.status_code == 200
    assert f'/glosowania/edit/{decyzja.pk}/' not in response.content.decode()


@pytest.mark.django_db
def test_author_sees_delete_action_for_proposition(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Deletable proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(author)

    response = client.get(f'/glosowania/details/{decision.pk}/')

    content = response.content.decode()
    assert response.status_code == 200
    assert 'data-tw-target="#deleteProposalModal"' in content
    assert f'action="/glosowania/delete/{decision.pk}/"' in content


@pytest.mark.django_db
def test_author_can_delete_proposition(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Deletable proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(author)

    response = client.post(f'/glosowania/delete/{decision.pk}/')

    assert response.status_code == 302
    assert response.url == '/glosowania/proposition/'
    assert not Decyzja.objects.filter(pk=decision.pk).exists()


@pytest.mark.django_db
def test_other_user_cannot_delete_proposition(sample_users):
    author, other = sample_users[:2]
    decision = Decyzja.objects.create(title='Protected proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(other)

    response = client.post(f'/glosowania/delete/{decision.pk}/')

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decision.pk}/'
    assert Decyzja.objects.filter(pk=decision.pk).exists()


@pytest.mark.django_db
def test_edit_proposal_uses_shared_form_layout(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Editable proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(author)

    response = client.get(f'/glosowania/edit/{decision.pk}/')

    assert response.status_code == 200
    assert 'tw-section-heading tw-mb-0' in response.content.decode()
    assert 'tw-alert tw-alert-danger' not in response.content.decode()
    assert 'tw-flex tw-flex-wrap tw-gap-2' in response.content.decode()


@pytest.mark.django_db
def test_edit_proposal_updates_fields_and_creates_version(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Editable proposal', tresc='Old text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(author)

    with patch('glosowania.views._safe_send_vote_state_changed'):
        response = client.post(f'/glosowania/edit/{decision.pk}/', {'title': 'Updated proposal', 'tresc': 'New text', 'uzasadnienie': 'Reason', 'kara': '', 'znosi': ''})

    assert response.status_code == 302
    assert response.url == '/glosowania/proposition/'
    decision.refresh_from_db()
    assert decision.title == 'Updated proposal'
    assert decision.tresc == 'New text'
    assert DecyzjaWersja.objects.filter(decyzja=decision, version_number=1).exists()


@pytest.mark.django_db
def test_edit_proposal_invalid_post_rerenders_errors(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Editable proposal', tresc='Old text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(author)

    response = client.post(f'/glosowania/edit/{decision.pk}/', {'title': '', 'tresc': '', 'uzasadnienie': '', 'kara': '', 'znosi': ''})

    assert response.status_code == 200
    assert response.context['form'].errors
    decision.refresh_from_db()
    assert decision.title == 'Editable proposal'


@pytest.mark.django_db
def test_edit_parameters_updates_fields_and_creates_version(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Parameter proposal', tresc='Old parameters', uzasadnienie='Old reason', status=Decyzja.Status.PROPOSITION, author=author, proposed_parameters={'acceptance': 10})
    form = ParametersProposalForm(decyzja=decision)
    data = {}
    for name, field in form.fields.items():
        value = field.initial
        if isinstance(field, forms.BooleanField):
            if value:
                data[name] = 'on'
        elif value is not None:
            data[name] = str(value)
    data['uzasadnienie'] = 'Updated reason'
    data['acceptance'] = '11'

    client = Client()
    client.force_login(author)
    response = client.post(f'/glosowania/parameters/propose/{decision.pk}/', data)

    assert response.status_code == 302
    assert response.url == '/glosowania/proposition/'
    decision.refresh_from_db()
    assert decision.proposed_parameters['acceptance'] == 11
    assert DecyzjaWersja.objects.filter(decyzja=decision, version_number=1).exists()


@pytest.mark.django_db
def test_edit_parameters_invalid_post_rerenders_errors(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Parameter proposal', status=Decyzja.Status.PROPOSITION, author=author, proposed_parameters={'acceptance': 10})
    client = Client()
    client.force_login(author)

    response = client.post(f'/glosowania/parameters/propose/{decision.pk}/', {})

    assert response.status_code == 200
    assert response.context['form'].errors
    assert not DecyzjaWersja.objects.filter(decyzja=decision).exists()


@pytest.mark.django_db
def test_edit_parameters_form_uses_responsive_actions(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Parameter proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author, proposed_parameters={'acceptance': 10})
    client = Client()
    client.force_login(author)

    response = client.get(f'/glosowania/parameters/propose/{decision.pk}/')

    assert response.status_code == 200
    content = response.content.decode()
    assert 'tw-flex tw-flex-wrap tw-gap-2' in content
    assert 'tw-btn tw-btn-primary tw-btn-sm' not in content
    assert '/glosowania/parameters/' in content


@pytest.mark.django_db
def test_edit_argument_uses_responsive_actions(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Argument proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    argument = Argument.objects.create(decyzja=decision, author=author, argument_type='FOR', content='Argument text')
    client = Client()
    client.force_login(author)

    response = client.get(f'/glosowania/details/{decision.pk}/', follow=True)

    assert response.status_code == 200
    content = response.content.decode()
    assert f'id="editArgumentForm{argument.pk}"' in content
    assert f'data-tw-toggle="collapse" data-tw-target="#editArgumentForm{argument.pk}"' in content
    assert f'action="/glosowania/argument/{argument.pk}/edit/"' in content
    assert f'name="argument_type" value="{argument.argument_type}"' in content
    assert f'id="argumentType{argument.pk}"' not in content
    assert f'data-tw-target="#deleteArgumentModal{argument.pk}"' in content
    assert 'Argument text' in content

    card_content_start = content.index('class="tw-arg-card-content"')
    display_start = content.index('class="tw-arg-content-display"', card_content_start)
    form_start = content.index(f'id="editArgumentForm{argument.pk}"', display_start)
    footer_start = content.index('class="tw-arg-card-footer"', form_start)
    assert card_content_start < display_start < form_start < footer_start


@pytest.mark.django_db
def test_add_argument_notifies_referendum_chat_once(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Argument proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    client = Client()
    client.force_login(author)

    with patch('glosowania.views.chat_message_requested.send') as send_message:
        response = client.post(f'/glosowania/details/{decision.pk}/add-argument/', {'argument_type': 'FOR', 'content': 'Argument text'})

    assert response.status_code == 302
    assert Argument.objects.filter(decyzja=decision, content='Argument text').exists()
    send_message.assert_called_once()
    call_kwargs = send_message.call_args.kwargs
    assert call_kwargs['sender'] is Argument
    assert call_kwargs['room_title'] == decision.chat_room.title
    assert call_kwargs['from_user'] is None
    assert call_kwargs['anonymous'] is False
    assert call_kwargs['message_text'].startswith(f"{_('A new argument was added to this referendum:')} <a href='")
    assert call_kwargs['message_text'].endswith('>Referendum</a>')


@pytest.mark.django_db
def test_edit_argument_does_not_notify_referendum_chat(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Argument proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    argument = Argument.objects.create(decyzja=decision, author=author, argument_type='FOR', content='Old argument')
    client = Client()
    client.force_login(author)

    with patch('glosowania.views.chat_message_requested.send') as send_message:
        response = client.post(f'/glosowania/argument/{argument.pk}/edit/', {'argument_type': 'AGAINST', 'content': 'Updated argument'})

    assert response.status_code == 302
    send_message.assert_not_called()


@pytest.mark.django_db
def test_edit_argument_updates_content(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Argument proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    argument = Argument.objects.create(decyzja=decision, author=author, argument_type='FOR', content='Old argument')
    client = Client()
    client.force_login(author)

    response = client.post(f'/glosowania/argument/{argument.pk}/edit/', {'argument_type': 'AGAINST', 'content': 'Updated argument'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decision.pk}/'
    argument.refresh_from_db()
    assert argument.content == 'Updated argument'
    assert argument.argument_type == 'AGAINST'


@pytest.mark.django_db
def test_edit_argument_invalid_post_redirects_with_error_message(sample_users):
    author = sample_users[0]
    decision = Decyzja.objects.create(title='Argument proposal', tresc='Text', status=Decyzja.Status.PROPOSITION, author=author)
    argument = Argument.objects.create(decyzja=decision, author=author, argument_type='FOR', content='Old argument')
    client = Client()
    client.force_login(author)

    with patch('glosowania.views.ArgumentForm.is_valid', return_value=False), patch('glosowania.views.messages.error') as error_message:
        response = client.post(f'/glosowania/argument/{argument.pk}/edit/', {'argument_type': 'FOR', 'content': 'Updated argument'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decision.pk}/'
    error_message.assert_called_once()
    argument.refresh_from_db()
    assert argument.content == 'Old argument'


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
def test_voting_retries_when_database_is_locked(sample_users):
    """A transient SQLite lock must not turn a valid vote into a 500."""
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Referendum Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)
    client = Client()
    client.force_login(voter)

    original_save = KtoJuzGlosowal.save
    save_calls = [0]

    def save_with_transient_lock(instance, *args, **kwargs):
        save_calls[0] += 1
        if save_calls[0] == 1:
            raise OperationalError('database is locked')
        return original_save(instance, *args, **kwargs)

    with patch.object(KtoJuzGlosowal, 'save', save_with_transient_lock), patch('glosowania.views.push_pending_vote') as mock_push:
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'tak': '1'})

    assert response.status_code == 302
    assert save_calls[0] == 2
    assert KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).count() == 1
    mock_push.assert_called_once()


@pytest.mark.django_db
def test_voting_retries_with_exponential_delays(sample_users):
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Referendum Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)
    client = Client()
    client.force_login(voter)
    original_save = KtoJuzGlosowal.save
    save_calls = [0]

    def save_with_two_locks(instance, *args, **kwargs):
        save_calls[0] += 1
        if save_calls[0] < 3:
            raise OperationalError('database is locked')
        return original_save(instance, *args, **kwargs)

    with patch.object(KtoJuzGlosowal, 'save', save_with_two_locks), patch('glosowania.views.time.sleep') as sleep, patch('glosowania.views.push_pending_vote'):
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'tak': '1'})

    assert response.status_code == 302
    assert sleep.call_args_list == [call(0.9), call(1.8)]
    assert save_calls[0] == 3


@pytest.mark.django_db
def test_voting_lock_timeout_redirects_without_marking_user(sample_users):
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(title='Referendum Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.REFERENDUM)
    client = Client()
    client.force_login(voter)

    with patch.object(KtoJuzGlosowal, 'save', side_effect=OperationalError('database is locked')), patch('glosowania.views.time.sleep'), patch('glosowania.views.push_pending_vote') as mock_push:
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'nie': '1'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decyzja.pk}/'
    assert not KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).exists()
    mock_push.assert_not_called()


@pytest.mark.django_db
def test_voting_is_rejected_after_referendum_deadline(sample_users):
    author = sample_users[0]
    voter = sample_users[1]
    decyzja = Decyzja.objects.create(
        title='Expired referendum',
        tresc='Test law text',
        kara='Test penalty',
        author=author,
        status=Decyzja.Status.REFERENDUM,
        data_referendum_start=timezone.localdate() - timedelta(days=4),
        data_referendum_stop=timezone.localdate() - timedelta(days=1),
    )
    client = Client()
    client.force_login(voter)

    with patch('glosowania.views.push_pending_vote') as push_vote:
        response = client.post(f'/glosowania/details/{decyzja.pk}/', {'tak': '1'})

    assert response.status_code == 302
    assert response.url == f'/glosowania/details/{decyzja.pk}/'
    assert not KtoJuzGlosowal.objects.filter(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=voter).exists()
    push_vote.assert_not_called()


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
    called_decyzja_id, operation_id, called_code, called_vote = mock_push.call_args[0]
    assert called_decyzja_id == decyzja.id
    assert len(operation_id) == 32
    assert called_code
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

    response = client.post('/glosowania/nowy/', {'title': 'New proposal', 'tresc': 'Proposal law text', 'uzasadnienie': 'It is needed', 'kara': '', 'znosi': ''})

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

    response = client.post('/glosowania/nowy/', {'title': '', 'tresc': '', 'uzasadnienie': ''})

    assert response.status_code == 200
    assert 'form' in response.context
    assert response.context['form'].errors
    assert Decyzja.objects.count() == 0

    content = response.content.decode()
    assert _('Please correct the errors below.') in content


@pytest.mark.django_db
def test_add_proposal_saves_even_when_notification_handler_fails(sample_users):
    """A failing vote_state_changed handler must not break the save/redirect."""
    author = sample_users[0]
    client = Client()
    client.force_login(author)

    with patch('glosowania.views.vote_state_changed.send', side_effect=RuntimeError('notification handler failed')):
        response = client.post('/glosowania/nowy/', {'title': 'Resilient proposal', 'tresc': 'Proposal law text', 'uzasadnienie': 'It is needed'})

    assert response.status_code == 302
    assert response.url == '/glosowania/proposition/'
    assert Decyzja.objects.filter(title='Resilient proposal').exists()


@pytest.mark.django_db
def test_status_lists_return_200_and_filter_by_status(sample_users):
    """Each status list returns only decyzjas with its own status."""
    author = sample_users[0]
    urls = {
        Decyzja.Status.PROPOSITION: '/glosowania/proposition/',
        Decyzja.Status.DISCUSSION: '/glosowania/discussion/',
        Decyzja.Status.REFERENDUM: '/glosowania/referendum/',
        Decyzja.Status.REJECTED: '/glosowania/rejected/',
        Decyzja.Status.APPROVED: '/glosowania/approved/',
    }
    for status in urls:
        d = Decyzja.objects.create(title=f'D{status}', tresc='x', author=author, status=status)
        ZebranePodpisy.objects.create(projekt=d, podpis_uzytkownika=author)

    client = Client()
    client.force_login(author)
    for status, url in urls.items():
        response = client.get(url)
        assert response.status_code == 200
        assert [v.status for v in response.context['votings']] == [status]


@pytest.mark.django_db
def test_status_lists_require_login():
    client = Client()
    for url in ('/glosowania/proposition/', '/glosowania/discussion/', '/glosowania/referendum/', '/glosowania/rejected/', '/glosowania/approved/'):
        assert client.get(url).status_code == 302


@pytest.mark.django_db
def test_discussion_and_referendum_require_author_signature(sample_users):
    """Discussion/referendum lists exclude proposals not signed by their author."""
    author, other = sample_users[0], sample_users[1]
    for status in (Decyzja.Status.DISCUSSION, Decyzja.Status.REFERENDUM):
        signed = Decyzja.objects.create(title=f'signed{status}', tresc='x', author=author, status=status)
        ZebranePodpisy.objects.create(projekt=signed, podpis_uzytkownika=author)
        unsigned = Decyzja.objects.create(title=f'unsigned{status}', tresc='x', author=author, status=status)
        ZebranePodpisy.objects.create(projekt=unsigned, podpis_uzytkownika=other)  # signed, but not by author

    client = Client()
    client.force_login(author)
    for url in ('/glosowania/discussion/', '/glosowania/referendum/'):
        titles = {v.title for v in client.get(url).context['votings']}
        assert len(titles) == 1
        assert next(iter(titles)).startswith('signed')


@pytest.mark.django_db
def test_rejected_and_approved_ignore_author_signature(sample_users):
    """rejected/approved lists show proposals regardless of author signature."""
    author, other = sample_users[0], sample_users[1]
    for status in (Decyzja.Status.REJECTED, Decyzja.Status.APPROVED):
        unsigned = Decyzja.objects.create(title=f'unsigned{status}', tresc='x', author=author, status=status)
        ZebranePodpisy.objects.create(projekt=unsigned, podpis_uzytkownika=other)

    client = Client()
    client.force_login(author)
    for url in ('/glosowania/rejected/', '/glosowania/approved/'):
        assert len(client.get(url).context['votings']) == 1


@pytest.mark.django_db
def test_status_lists_show_stage_countdowns_and_completion_date(sample_users):
    author = sample_users[0]
    proposition = Decyzja.objects.create(title='Proposition date', tresc='x', author=author, status=Decyzja.Status.PROPOSITION)
    discussion = Decyzja.objects.create(title='Discussion date', tresc='x', author=author, status=Decyzja.Status.DISCUSSION, data_zebrania_podpisow=date(2026, 2, 2), data_referendum_start=date(2026, 2, 3))
    referendum = Decyzja.objects.create(title='Referendum dates', tresc='x', author=author, status=Decyzja.Status.REFERENDUM, data_referendum_start=date(2026, 2, 3), data_referendum_stop=date(2026, 2, 4))
    approved = Decyzja.objects.create(title='Approved date', tresc='x', author=author, status=Decyzja.Status.APPROVED)
    for decision in (discussion, referendum):
        ZebranePodpisy.objects.create(projekt=decision, podpis_uzytkownika=author)

    client = Client()
    client.force_login(author)
    proposition_response = client.get('/glosowania/proposition/')
    discussion_response = client.get('/glosowania/discussion/')
    referendum_response = client.get('/glosowania/referendum/')
    approved_response = client.get('/glosowania/approved/')

    assert proposition_response.context['votings'][0] == proposition
    assert proposition_response.context['votings'][0].countdown_end.date() == proposition.data_powstania + timedelta(days=SiteParameters.get().czas_na_zebranie_podpisow + 1)
    assert 'data-countdown' in proposition_response.content.decode()
    assert 'data-countdown-minutes' in discussion_response.content.decode()
    assert 'Starts in' not in discussion_response.content.decode()
    assert discussion_response.context['votings'][0].countdown_end.date() == date(2026, 2, 3)
    assert 'data-countdown-minutes' in referendum_response.content.decode()
    assert 'Ends in' not in referendum_response.content.decode()
    assert referendum_response.context['votings'][0].countdown_end.date() == date(2026, 2, 5)
    approved_date = timezone.localtime(approved.data_ostatniej_modyfikacji).strftime('%d.%m.%Y')
    assert approved_date in approved_response.content.decode()
    assert 'data-countdown' not in approved_response.content.decode()
