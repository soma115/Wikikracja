"""Smoke tests workflow glosowania.

UWAGA: `glosowania.signals.create_or_update_chat_room_for_referendum` AUTOMATYCZNIE tworzy
chat_room przy każdym nowym Decyzja(status=PROPOSITION). Nie podawaj `chat_room=` w create() —
sygnał i tak go nadpisze.
"""

import pytest


@pytest.mark.django_db
def test_complete_voting_workflow(sample_users):
    """Pełen flow Decyzja: stworzenie → argumenty FOR/AGAINST → podpisy → głosowanie → kody → status."""
    from glosowania.models import Argument, Decyzja, KtoJuzGlosowal, VoteCode, ZebranePodpisy

    author = sample_users[0]

    decyzja = Decyzja.objects.create(title='Workflow Test Bill', tresc='Test law text', kara='Test penalty', author=author, status=Decyzja.Status.PROPOSITION)
    assert Decyzja.objects.filter(title='Workflow Test Bill').exists()

    for i in range(5):
        Argument.objects.create(decyzja=decyzja, author=sample_users[i % len(sample_users)], argument_type='FOR', content=f'Pro {i}')
    for i in range(3):
        Argument.objects.create(decyzja=decyzja, author=sample_users[i % len(sample_users)], argument_type='AGAINST', content=f'Con {i}')

    assert decyzja.arguments.count() == 8
    assert decyzja.arguments.filter(argument_type='FOR').count() == 5
    assert decyzja.arguments.filter(argument_type='AGAINST').count() == 3

    for user in sample_users:
        ZebranePodpisy.objects.create(projekt=decyzja, podpis_uzytkownika=user)
    decyzja.ile_osob_podpisalo = len(sample_users)
    decyzja.save()

    assert ZebranePodpisy.objects.filter(projekt=decyzja).count() == len(sample_users)
    assert decyzja.ile_osob_podpisalo == len(sample_users)

    for i, user in enumerate(sample_users):
        KtoJuzGlosowal.objects.create(projekt=decyzja, ktory_uzytkownik_juz_zaglosowal=user)
        if i % 2 == 0:
            decyzja.za += 1
        else:
            decyzja.przeciw += 1
    decyzja.save()

    assert KtoJuzGlosowal.objects.filter(projekt=decyzja).count() == len(sample_users)
    assert decyzja.za + decyzja.przeciw == len(sample_users)

    for i in range(5):
        VoteCode.objects.create(project=decyzja, code=f'WF{i:04d}', vote=(i % 2 == 0))
    assert VoteCode.objects.filter(project=decyzja).count() == 5

    decyzja.status = Decyzja.Status.DISCUSSION
    decyzja.save()
    decyzja.refresh_from_db()
    assert decyzja.status == Decyzja.Status.DISCUSSION


@pytest.mark.django_db
def test_signal_auto_creates_chat_room_for_new_decyzja(sample_users):
    """Każda nowa Decyzja(status=PROPOSITION) ma auto-utworzony chat_room (sygnał) z properties: public, protected, founder=author + welcome message."""
    from chat.models import Message
    from glosowania.models import Decyzja

    author = sample_users[0]
    decyzja = Decyzja.objects.create(title='Auto Room Bill', tresc='Auto law', kara='Auto penalty', author=author, status=Decyzja.Status.PROPOSITION)
    decyzja.refresh_from_db()

    # Signal stworzył pokój
    assert decyzja.chat_room is not None
    room = decyzja.chat_room

    # Properties zgodne ze specyfikacją signal'a
    assert room.public is True
    assert room.protected is True
    assert room.archived is False
    assert room.founder_id == author.id

    # Welcome message anonimowy
    welcome_messages = Message.objects.filter(room=room, anonymous=True, sender=None)
    assert welcome_messages.count() == 1
    assert f'#{decyzja.pk}' in welcome_messages.first().text

    # Zaproszeni są wszyscy aktywni userzy (signal wywołuje room.allowed.set(active_users))
    from django.contrib.auth import get_user_model

    User = get_user_model()
    active_count = User.objects.filter(is_active=True).count()
    assert room.allowed.count() == active_count

    # Możemy dodawać normalne messages do pokoju
    Message.objects.create(sender=sample_users[1], text='Discussion point', room=room, anonymous=False)
    assert Message.objects.filter(room=room, sender__isnull=False).count() == 1
