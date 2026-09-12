"""Testy modułu board — dokumenty i powiązany z nimi czat.

Weryfikują że tworzenie/aktualizacja/usuwanie dokumentu prowadzi
do odpowiedniego utworzenia/aktualizacji/usunięcia pokoju czatu,
na tej samej zasadzie co tasks i glosowania.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from board.models import Post
from chat.models import Message, MessageReadBy, Room
from tests.factories import PostCategoryFactory, PostFactory, UserFactory


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
    assert 'tw-ec-section' in res.content.decode()
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
    assert 'tw-chat-link' in content


@pytest.mark.django_db
def test_board_list_chat_pulse_for_unread_message(authenticated_client):
    """Guzik czatu pulsuje i liczy tylko wiadomości bez MessageReadBy."""
    client, user = authenticated_client
    post = PostFactory(is_public=True)
    other = UserFactory()
    Message.objects.create(room=post.chat_room, text='Read', sender=other)
    MessageReadBy.objects.bulk_create([MessageReadBy(message=message, user=user) for message in post.chat_room.messages.all()])
    Message.objects.create(room=post.chat_room, text='Unread', sender=other)

    res = client.get(reverse('board:start'))

    assert res.status_code == 200
    rendered_post = next(item for group in res.context['category_groups'] for item in group['posts'] if item.pk == post.pk)
    assert rendered_post.chat_room_unread_count == 1
    assert 'tw-chat-room-pulse' in res.content.decode()


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
    assert post.updated_by == user
    assert post.chat_room_id is not None
    attachment = post.attachments.get()
    assert attachment.filename == 'notatka.txt'


@pytest.mark.django_db
def test_create_private_post(authenticated_client):
    """Tworzenie dokumentu z zaznaczonym checkboxem 'Prywatne' zapisuje is_private=True."""
    client, user = authenticated_client
    upload = SimpleUploadedFile('notatka.txt', b'zawartosc')

    res = client.post(reverse('board:create_post'), {'title': 'Dokument prywatny', 'text': 'Treść', 'is_private': 'on', 'attachments': upload})

    post = Post.objects.get(title='Dokument prywatny')
    assert res.status_code == 302
    assert post.author == user
    assert post.is_private is True
    assert post.is_public is False


@pytest.mark.django_db
def test_edit_post_updates_fields_and_adds_attachments(authenticated_client):
    """POST edit aktualizuje pola i dopisuje nowe załączniki do istniejącego dokumentu."""
    client, user = authenticated_client
    post = PostFactory(title='Stary tytuł', author=user)
    upload = SimpleUploadedFile('zalacznik.txt', b'x')

    res = client.post(reverse('board:edit_post', args=[post.pk]), {'title': 'Zmieniony tytuł', 'text': 'Nowa treść', 'attachments': upload})

    assert res.status_code == 302
    assert res.url == reverse('board:view_post', args=[post.pk])
    post.refresh_from_db()
    assert post.title == 'Zmieniony tytuł'
    assert post.author == user
    assert post.updated_by == user
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
    assert 'tw-ec-section' in content
    assert f'data-room-id="{post.chat_room_id}"' in content
    assert 'tw-chat-link' not in content


@pytest.mark.django_db
def test_private_post_visible_only_to_author_on_list(authenticated_client):
    """Prywatny dokument na liście jest widoczny tylko dla autora."""
    client, user = authenticated_client
    other = UserFactory(username='other', email='other@example.com')
    private = PostFactory(title='Prywatny', is_private=True, author=other)

    res = client.get(reverse('board:start'))
    assert res.status_code == 200
    assert private.title not in res.content.decode()

    # Dla autora dokument jest widoczny
    client.force_login(other)
    res = client.get(reverse('board:start'))
    assert res.status_code == 200
    assert private.title in res.content.decode()


@pytest.mark.django_db
def test_non_private_post_is_visible_to_other_authenticated_users(authenticated_client):
    """Zwykły dokument jest widoczny dla każdego zalogowanego użytkownika."""
    client, _ = authenticated_client
    author = UserFactory(username='document-author', email='document-author@example.com')
    post = PostFactory(title='Zwykły dokument', is_public=False, is_private=False, author=author)

    response = client.get(reverse('board:start'))

    assert response.status_code == 200
    assert post.title in response.content.decode()


@pytest.mark.django_db
def test_system_post_visible_to_authenticated_users_regardless_of_author_or_private_flag(authenticated_client):
    """System posts are visible to logged-in users even when marked as private."""
    client, user = authenticated_client
    other = UserFactory(username='system-owner', email='system-owner@example.com')
    system_post = PostFactory(system_key='system-visible', author=other, is_public=False, is_private=True)

    response = client.get(reverse('board:view_post', args=[system_post.pk]))

    assert response.status_code == 200
    assert system_post.title in response.content.decode()
    assert system_post in Post.objects.filter(Post.visibility_filter_for_user(user))

    client.logout()
    assert client.get(reverse('board:view_post', args=[system_post.pk])).status_code == 404


@pytest.mark.django_db
def test_private_post_detail_visible_only_to_author(authenticated_client):
    """Szczegóły prywatnego dokumentu dostępne są tylko dla autora."""
    client, user = authenticated_client
    other = UserFactory(username='other2', email='other2@example.com')
    private = PostFactory(title='Prywatny szczegóły', is_private=True, author=other)

    # Nie-autor dostaje 404
    res = client.get(reverse('board:view_post', args=[private.pk]))
    assert res.status_code == 404

    # Autor widzi dokument
    client.force_login(other)
    res = client.get(reverse('board:view_post', args=[private.pk]))
    assert res.status_code == 200
    assert private.title in res.content.decode()


@pytest.mark.django_db
def test_public_post_visible_to_everyone(client, authenticated_client):
    """Publiczny dokument jest widoczny dla anonimowego i zalogowanego użytkownika."""
    _, user = authenticated_client
    public = PostFactory(title='Publiczny dokument', is_public=True, author=user)

    res = client.get(reverse('board:start'))
    assert res.status_code == 200
    assert public.title in res.content.decode()

    client_auth, _ = authenticated_client
    res = client_auth.get(reverse('board:start'))
    assert res.status_code == 200
    assert public.title in res.content.decode()

    res = client.get(reverse('board:view_post', args=[public.pk]))
    assert res.status_code == 200
    assert public.title in res.content.decode()


@pytest.mark.django_db
def test_private_flag_overrides_public(authenticated_client):
    """Prywatne ma pierwszeństwo nad publicznym — dokument widoczny tylko dla autora."""
    client, user = authenticated_client
    other = UserFactory(username='other5', email='other5@example.com')
    private = PostFactory(title='Niby publiczny, ale prywatny', is_public=True, is_private=True, author=other)

    res = client.get(reverse('board:start'))
    assert res.status_code == 200
    assert private.title not in res.content.decode()

    res = client.get(reverse('board:view_post', args=[private.pk]))
    assert res.status_code == 404

    client.force_login(other)
    res = client.get(reverse('board:view_post', args=[private.pk]))
    assert res.status_code == 200
    assert private.title in res.content.decode()


@pytest.mark.django_db
def test_edit_post_allows_other_user(authenticated_client):
    """Każdy zalogowany użytkownik może edytować dokument."""
    client, user = authenticated_client
    other = UserFactory(username='other3', email='other3@example.com')
    post = PostFactory(title='Do edycji', is_private=True, author=other)

    res = client.get(reverse('board:edit_post', args=[post.pk]))
    assert res.status_code == 200
    assert 'Do edycji' in res.content.decode()

    res = client.post(reverse('board:edit_post', args=[post.pk]), {'title': 'Zmieniony przez innego', 'text': 'Nowa treść'})
    assert res.status_code == 302
    post.refresh_from_db()
    assert post.title == 'Zmieniony przez innego'
    # Autor pozostaje twórcą, a użytkownik edytujący jest zapisywany osobno.
    assert post.author == other
    assert post.updated_by == user


@pytest.mark.django_db
def test_edit_system_post_can_change_public_but_not_category_or_other_flags(authenticated_client):
    """Dokument systemowy pozwala zmienić publiczność, ale blokuje pozostałe pola chronione."""
    client, user = authenticated_client
    original_category = PostCategoryFactory(name='System category')
    new_category = PostCategoryFactory(name='Other category')
    post = PostFactory(system_key='protected-system-post', category=original_category, is_public=True, is_private=False, is_important=False)

    response = client.post(reverse('board:edit_post', args=[post.pk]), {'title': 'Zmieniony tytuł', 'text': 'Nowa treść', 'category': new_category.pk, 'is_private': 'on', 'is_important': 'on'})

    assert response.status_code == 302
    post.refresh_from_db()
    assert post.title == 'Zmieniony tytuł'
    assert post.category == original_category
    assert post.is_public is False
    assert post.is_private is False
    assert post.is_important is False
    assert post.updated_by == user


@pytest.mark.django_db
def test_delete_post_restricted_to_author(authenticated_client):
    """Usuwanie dokumentu dostępne jest tylko dla autora."""
    client, user = authenticated_client
    other = UserFactory(username='other4', email='other4@example.com')
    private = PostFactory(title='Do usunięcia', is_private=True, author=other)

    # Nie-autor nie może usunąć
    res = client.get(reverse('board:delete_post', args=[private.pk]))
    assert res.status_code == 404

    # Autor może usunąć
    client.force_login(other)
    res = client.post(reverse('board:delete_post', args=[private.pk]))
    assert res.status_code == 302
    assert not Post.objects.filter(pk=private.pk).exists()
