"""Testy modułu board — dokumenty i powiązany z nimi czat.

Weryfikują że tworzenie/aktualizacja/usuwanie dokumentu prowadzi
do odpowiedniego utworzenia/aktualizacji/usunięcia pokoju czatu,
na tej samej zasadzie co tasks i glosowania.
"""

import pytest
from django.urls import reverse

from board.models import Post
from chat.models import Room
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
