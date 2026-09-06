"""Testy modułu board — dokumenty i powiązany z nimi czat.

Weryfikują że tworzenie/aktualizacja/usuwanie dokumentu prowadzi
do odpowiedniego utworzenia/aktualizacji/usunięcia pokoju czatu,
na tej samej zasadzie co tasks i glosowania.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from board.models import Post
from chat.models import Message, Room
from tests.factories import PostFactory


@pytest.mark.django_db
def test_post_creation_creates_chat_room():
    """Utworzenie dokumentu tworzy chroniony pokój czatu z poprawnym tytułem i allowed."""
    post = PostFactory(title='Important doc')

    assert post.chat_room_id is not None
    room = post.chat_room
    assert room is not None
    assert room.title == f'Document #{post.pk}: Important doc'
    assert room.source_app == 'board'
    assert room.source_object_id == post.pk
    assert room.protected is True
    assert room.public is True
    # Pokój jest dostępny dla wszystkich aktywnych użytkowników
    assert room.allowed.filter(pk=post.author.pk).exists()

    # Tytuł jest prawidłowo czyszczony przy wyświetlaniu
    assert room.clean_title() == 'Important doc'


@pytest.mark.django_db
def test_post_update_updates_chat_room_title():
    """Zmiana tytułu dokumentu aktualizuje tytuł pokoju czatu."""
    post = PostFactory(title='Old title')
    room_id = post.chat_room_id

    post.title = 'New title'
    post.save()
    post.refresh_from_db()

    assert post.chat_room_id == room_id
    assert post.chat_room.title == f'Document #{post.pk}: New title'


@pytest.mark.django_db
def test_post_delete_deletes_chat_room():
    """Usunięcie dokumentu usuwa powiązany pokój czatu."""
    post = PostFactory()
    room_id = post.chat_room_id
    assert room_id is not None

    post.delete()

    assert not Post.objects.filter(pk=post.pk).exists()
    assert not Room.objects.filter(pk=room_id).exists()


@pytest.mark.django_db
def test_view_post_renders_embedded_chat(authenticated_client):
    """Widok dokumentu zawiera osadzony czat dla zalogowanego użytkownika."""
    client, _ = authenticated_client
    post = PostFactory(is_public=True)

    res = client.get(reverse('board:view_post', args=[post.pk]))

    assert res.status_code == 200
    assert 'ec-section' in res.content.decode()
    assert f'data-room-id="{post.chat_room_id}"' in res.content.decode()


@pytest.mark.django_db
def test_board_list_renders_chat_link(authenticated_client):
    """Widok listy dokumentów pokazuje guzik czatu obok tytułu w obu układach."""
    client, _ = authenticated_client
    post = PostFactory(is_public=True)

    res = client.get(reverse('board:start'))

    assert res.status_code == 200
    content = res.content.decode()
    assert post.chat_room_url in content
    assert 'chat-link' in content


@pytest.mark.django_db
def test_board_list_chat_pulse_for_unread_message(authenticated_client):
    """Guzik czatu pulsuje, gdy są nieprzeczytane wiadomości w pokoju dokumentu."""
    client, user = authenticated_client
    post = PostFactory(is_public=True)
    Message.objects.create(room=post.chat_room, text='Hello', sender=user)

    res = client.get(reverse('board:start'))

    assert res.status_code == 200
    assert 'chat-room-pulse' in res.content.decode()


@pytest.mark.django_db
def test_create_post_saves_author_and_attachments(authenticated_client):
    """POST create tworzy dokument z autorem z request.user i zapisuje załączniki."""
    client, user = authenticated_client
    upload = SimpleUploadedFile('notatka.txt', b'zawartosc')

    res = client.post(reverse('board:create_post'), {'title': 'Nowy dokument', 'text': 'Treść', 'attachments': upload})

    post = Post.objects.get(title='Nowy dokument')
    assert res.status_code == 302
    assert res.url == reverse('board:view_post', args=[post.pk])
    assert post.author == user
    assert post.chat_room_id is not None
    attachment = post.attachments.get()
    assert attachment.filename == 'notatka.txt'


@pytest.mark.django_db
def test_edit_post_updates_fields_and_adds_attachments(authenticated_client):
    """POST edit aktualizuje pola i dopisuje nowe załączniki do istniejącego dokumentu."""
    client, user = authenticated_client
    post = PostFactory(title='Stary tytuł')
    upload = SimpleUploadedFile('zalacznik.txt', b'x')

    res = client.post(reverse('board:edit_post', args=[post.pk]), {'title': 'Zmieniony tytuł', 'text': 'Nowa treść', 'attachments': upload})

    assert res.status_code == 302
    assert res.url == reverse('board:view_post', args=[post.pk])
    post.refresh_from_db()
    assert post.title == 'Zmieniony tytuł'
    # Zachowane dotychczasowe zachowanie: edytujący staje się autorem dokumentu.
    assert post.author == user
    assert post.attachments.get().filename == 'zalacznik.txt'


@pytest.mark.django_db
def test_create_and_edit_post_require_login(client):
    post = PostFactory()

    assert client.get(reverse('board:create_post')).status_code == 302
    assert client.get(reverse('board:edit_post', args=[post.pk])).status_code == 302


@pytest.mark.django_db
def test_view_post_detail_has_no_chat_link_next_to_title(authenticated_client):
    """Widok szczegółów dokumentu nie pokazuje guzika czatu obok tytułu."""
    client, _ = authenticated_client
    post = PostFactory(is_public=True)

    res = client.get(reverse('board:view_post', args=[post.pk]))

    assert res.status_code == 200
    content = res.content.decode()
    assert 'ec-section' in content
    assert f'data-room-id="{post.chat_room_id}"' in content
    assert 'chat-link' not in content
