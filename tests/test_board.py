"""Testy modułu board — dokumenty i powiązany z nimi czat.

Weryfikują że tworzenie/aktualizacja/usuwanie dokumentu prowadzi
do odpowiedniego utworzenia/aktualizacji/usunięcia pokoju czatu,
na tej samej zasadzie co tasks i glosowania.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils.translation import gettext, override

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
    assert room.messages.count() == 1
    assert f'/board/view/{post.pk}/' in room.messages.get().text


@pytest.mark.django_db
@override_settings(LANGUAGE_CODE='pl')
def test_document_chat_welcome_uses_instance_language():
    with override('en'):
        post = PostFactory(title='Translated document')

    welcome_message = post.chat_room.messages.get().text
    assert welcome_message.startswith('Pokój dyskusji do dokumentu:')


@pytest.mark.django_db
def test_group_document_room_uses_document_title_for_display():
    post = PostFactory(title='Group document', visibility=Post.Visibility.GROUP)

    assert post.chat_room.public is False
    assert post.chat_room.displayed_name(post.author) == 'Group document'


@pytest.mark.django_db
def test_empty_document_chat_gets_welcome_message_on_update():
    post = PostFactory(title='Document without welcome')
    room = post.chat_room
    room.messages.all().delete()

    post.title = 'Document with restored welcome'
    post.save()

    assert room.messages.count() == 1
    assert f'/board/view/{post.pk}/' in room.messages.get().text


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
    post = PostFactory(visibility='public')

    res = client.get(reverse('board:view_post', args=[post.pk]))

    assert res.status_code == 200
    assert 'tw-ec-section' in res.content.decode()
    assert f'data-room-id="{post.chat_room_id}"' in res.content.decode()


@pytest.mark.django_db
def test_board_list_renders_chat_link(authenticated_client):
    """Widok listy dokumentów pokazuje guzik czatu obok tytułu w obu układach."""
    client, _ = authenticated_client
    post = PostFactory(visibility='public')

    res = client.get(reverse('board:start'))

    assert res.status_code == 200
    content = res.content.decode()
    assert post.chat_room_url in content
    assert 'tw-chat-link' in content


@pytest.mark.django_db
def test_board_list_chat_pulse_for_unread_message(authenticated_client):
    """Guzik czatu pulsuje i liczy tylko wiadomości bez MessageReadBy."""
    client, user = authenticated_client
    post = PostFactory(visibility='public')
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
def test_create_post_saves_author_and_multiple_attachments(authenticated_client):
    """POST create tworzy dokument z autorem i zapisuje wiele załączników."""
    client, user = authenticated_client
    uploads = [SimpleUploadedFile('notatka.txt', b'zawartosc'), SimpleUploadedFile('plan.pdf', b'plan')]

    res = client.post(reverse('board:create_post'), {'title': 'Nowy dokument', 'text': 'Treść', 'attachments': uploads})

    post = Post.objects.get(title='Nowy dokument')
    assert res.status_code == 302
    assert res.url == reverse('board:view_post', args=[post.pk])
    assert post.author == user
    assert post.updated_by == user
    assert post.chat_room_id is not None
    assert set(post.attachments.values_list('filename', flat=True)) == {'notatka.txt', 'plan.pdf'}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('tab', 'visibility', 'is_important'),
    [('group', Post.Visibility.GROUP, False), ('public', Post.Visibility.PUBLIC, True), ('important', Post.Visibility.GROUP, True), ('archive', Post.Visibility.ARCHIVE, False)],
)
def test_create_form_prefills_settings_from_board_tab(authenticated_client, tab, visibility, is_important):
    """Formularz nowego dokumentu dziedziczy ustawienia aktywnej zakładki."""
    client, _ = authenticated_client

    response = client.get(reverse('board:create_post'), {'tab': tab})

    assert response.status_code == 200
    assert response.context['form'].initial['visibility'] == visibility
    assert response.context['form'].initial.get('is_important', False) is is_important


@pytest.mark.django_db
@pytest.mark.parametrize('tab', ['group', 'public', 'important', 'archive'])
def test_board_create_links_preserve_active_tab(authenticated_client, tab):
    """Guziki tworzenia dokumentu przekazują aktywną zakładkę do formularza."""
    client, _ = authenticated_client

    response = client.get(reverse('board:start'), {'tab': tab})

    assert response.status_code == 200
    assert f'href="/board/create/?tab={tab}"' in response.content.decode()


@pytest.mark.django_db
def test_archived_post_can_be_opened_from_a_direct_link(authenticated_client):
    client, user = authenticated_client
    post = PostFactory(title='Archived document', visibility=Post.Visibility.ARCHIVE, author=user)

    response = client.get(reverse('board:view_post', args=[post.pk]))

    assert response.status_code == 200
    assert post.title in response.content.decode()


@pytest.mark.django_db
def test_message_in_archived_document_chat_restores_document(authenticated_client):
    _, user = authenticated_client
    other = UserFactory(username='archive-chat-writer', email='archive-chat-writer@example.com')
    post = PostFactory(title='Archived discussion', visibility=Post.Visibility.GROUP, author=user)
    post.visibility = Post.Visibility.ARCHIVE
    post.save(update_fields=['visibility', 'updated'])
    room = post.chat_room

    assert room.archived is True
    assert room.allowed.filter(pk=other.pk).exists()

    Message.objects.create(room=room, sender=other, text='Restore this document')

    post.refresh_from_db()
    room.refresh_from_db()
    assert post.visibility == Post.Visibility.GROUP
    assert post.updated_by == other
    assert room.archived is False


@pytest.mark.django_db
def test_create_archived_post_redirects_to_visible_detail(authenticated_client):
    """Nowy dokument archiwalny pozostaje dostępny po zapisie."""
    client, user = authenticated_client

    res = client.post(reverse('board:create_post'), {'title': 'Dokument archiwalny', 'text': 'Treść', 'visibility': Post.Visibility.ARCHIVE})

    post = Post.objects.get(title='Dokument archiwalny')
    detail_url = f'{reverse("board:view_post", args=[post.pk])}?tab=archive'
    assert res.status_code == 302
    assert res.url == detail_url
    assert post.author == user
    assert post.visibility == Post.Visibility.ARCHIVE
    assert client.get(res.url).status_code == 200


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
def test_post_form_uses_shared_uploaders_and_places_attachments_at_bottom(authenticated_client):
    client, _ = authenticated_client
    response = client.get(reverse('board:create_post'))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-file-upload-single' in content
    assert 'accept="image/*"' in content
    assert 'tw-file-upload' in content
    assert content.index('name="attachments"') > content.index('name="text"')
    assert content.index('form="post-form"') < content.index('name="attachments"')


@pytest.mark.django_db
def test_delete_featured_image_is_immediate_and_requires_post(authenticated_client):
    client, user = authenticated_client
    post = PostFactory(author=user)
    post.featured_image = SimpleUploadedFile('cover.jpg', b'image data', content_type='image/jpeg')
    post.save(update_fields=('featured_image',))

    response = client.post(reverse('board:delete_featured_image', args=[post.pk]))

    assert response.status_code == 302
    assert response.url == reverse('board:edit_post', args=[post.pk])
    post.refresh_from_db()
    assert not post.featured_image


@pytest.mark.django_db
@override_settings(UPLOAD_ATTACHMENT_MAX_SIZE_MB=1)
def test_invalid_attachment_uses_tw_error_class(authenticated_client):
    client, _ = authenticated_client
    post = PostFactory()
    oversized = SimpleUploadedFile('large.txt', b'x' * 1_000_001)

    response = client.post(reverse('board:edit_post', args=[post.pk]), {'title': post.title, 'text': post.text, 'attachments': oversized})

    assert response.status_code == 200
    content = response.content.decode()
    assert 'is-invalid' not in content
    assert 'tw-invalid-feedback' in content


@pytest.mark.django_db
def test_create_and_edit_post_require_login(client):
    post = PostFactory()

    assert client.get(reverse('board:create_post')).status_code == 302
    assert client.get(reverse('board:edit_post', args=[post.pk])).status_code == 302


@pytest.mark.django_db
def test_view_post_detail_has_no_chat_link_next_to_title(authenticated_client):
    """Widok szczegółów dokumentu nie pokazuje guzika czatu obok tytułu."""
    client, _ = authenticated_client
    post = PostFactory(visibility='public')

    res = client.get(reverse('board:view_post', args=[post.pk]))

    assert res.status_code == 200
    content = res.content.decode()
    assert 'tw-ec-section' in content
    assert f'data-room-id="{post.chat_room_id}"' in content
    assert 'tw-chat-link' not in content


@pytest.mark.django_db
def test_non_private_post_is_visible_to_other_authenticated_users(authenticated_client):
    """Zwykły dokument jest widoczny dla każdego zalogowanego użytkownika."""
    client, _ = authenticated_client
    author = UserFactory(username='document-author', email='document-author@example.com')
    post = PostFactory(title='Zwykły dokument', visibility='group', author=author)

    response = client.get(reverse('board:start'), {'tab': 'group'})

    assert response.status_code == 200
    assert post.title in response.content.decode()


@pytest.mark.django_db
def test_system_post_visible_to_authenticated_users_regardless_of_author_or_private_flag(authenticated_client):
    """System posts are visible to logged-in users even when marked as private."""
    client, user = authenticated_client
    other = UserFactory(username='system-owner', email='system-owner@example.com')
    system_post = PostFactory(system_key='system-visible', author=other, visibility='public', is_important=True)

    response = client.get(reverse('board:view_post', args=[system_post.pk]))

    assert response.status_code == 200
    assert system_post.title in response.content.decode()
    system_post.refresh_from_db()
    assert system_post.category.name == 'System'

    listing_response = client.get(reverse('board:start'))
    system_group = next(group for group in listing_response.context['category_groups'] if group['category'] and group['category'].name == 'System')
    assert system_post in system_group['posts']
    assert not any(system_post in group['posts'] for group in listing_response.context['category_groups'] if group['category'] is None)
    assert system_post in Post.objects.filter(Post.visibility_filter_for_user(user))

    client.logout()
    assert client.get(reverse('board:start')).status_code == 200
    assert system_post.title not in client.get(reverse('board:start')).content.decode()
    assert client.get(reverse('board:view_post', args=[system_post.pk])).status_code == 404


@pytest.mark.django_db
def test_system_posts_use_protected_system_category(authenticated_client):
    client, _ = authenticated_client

    from board.models import PostCategory

    system_category = PostCategory.get_system_category()
    duplicate_category = PostCategoryFactory(name='System')
    existing_system_posts = PostFactory.create_batch(5, category=duplicate_category)
    for post in existing_system_posts:
        Post.objects.filter(pk=post.pk).update(system_key=f'existing-system-{post.pk}')

    assert system_category.is_protected is True
    assert PostCategory.get_system_category().pk == system_category.pk
    edited_system_post = PostFactory(system_key='edited-system-post', category=duplicate_category)
    edited_system_post.refresh_from_db()

    assert edited_system_post.category_id == system_category.pk
    response = client.get(reverse('board:start'))
    system_group = next(group for group in response.context['category_groups'] if group['category'] and group['category'].pk == system_category.pk)
    assert {post.pk for post in existing_system_posts} | {edited_system_post.pk} <= {post.pk for post in system_group['posts']}


@pytest.mark.django_db
def test_public_post_visible_to_everyone(client, authenticated_client):
    """Publiczny dokument jest widoczny dla anonimowego i zalogowanego użytkownika."""
    _, user = authenticated_client
    public = PostFactory(title='Publiczny dokument', visibility='public', author=user)

    res = client.get(reverse('board:start'))
    assert res.status_code == 200
    content = res.content.decode()
    assert public.title in content
    assert 'tw-board-stepper' not in content
    assert 'tw-toolbar' in content
    assert 'id="catFilter"' not in content
    assert 'name="q"' not in content
    assert 'data-sort-state' not in content
    assert 'data-view="grid"' in content
    assert 'data-view="list"' in content
    assert 'data-default-view="grid"' in content
    assert 'tw-chat-link' not in content

    client_auth, _ = authenticated_client
    res = client_auth.get(reverse('board:start'))
    assert res.status_code == 200
    assert public.title in res.content.decode()

    res = client.get(reverse('board:view_post', args=[public.pk]))
    assert res.status_code == 200
    content = res.content.decode()
    assert public.title in content
    assert 'tw-board-stepper' not in content
    assert 'tw-ec-section' not in content


@pytest.mark.django_db
def test_public_blog_lists_only_regular_public_posts(client, authenticated_client):
    """Publiczny blog pokazuje wyłącznie zwykłe wpisy publiczne."""
    _, user = authenticated_client
    public = PostFactory(title='Publiczny wpis', visibility=Post.Visibility.PUBLIC, author=user)
    PostFactory(title='Wewnętrzny wpis', visibility=Post.Visibility.GROUP, author=user)
    PostFactory(title='Systemowy wpis', visibility=Post.Visibility.PUBLIC, author=user, system_key='public-blog-system')

    response = client.get(reverse('board:public_start'))

    assert response.status_code == 200
    assert [post.pk for post in response.context['posts']] == [public.pk]
    content = response.content.decode()
    assert 'Publiczny wpis' in content
    assert 'Wewnętrzny wpis' not in content
    assert 'Systemowy wpis' not in content
    assert 'tw-board-stepper' not in content
    assert 'tw-ec-section' not in content


@pytest.mark.django_db
def test_public_blog_decodes_entities_in_article_excerpt(client, authenticated_client):
    _, user = authenticated_client
    public = PostFactory(title='Oferta usług', text='<p>Usługi z &oacute; polskimi znakami&nbsp;dla grupy.</p>', visibility=Post.Visibility.PUBLIC, author=user)

    response = client.get(reverse('board:public_start'))

    content = response.content.decode()
    assert 'Usługi z ó polskimi znakami dla grupy.' in content
    assert '&oacute;' not in content
    assert '&nbsp;' not in content
    assert public.title in content


@pytest.mark.django_db
def test_public_blog_detail_has_no_internal_controls_or_chat(client, authenticated_client):
    """Publiczny detail jest minimalistycznym artykułem bez elementów wewnętrznych."""
    _, user = authenticated_client
    post = PostFactory(title='Artykuł publiczny', visibility=Post.Visibility.PUBLIC, author=user, subtitle='Lead')

    response = client.get(reverse('board:public_view_post', args=[post.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert post.title in content
    assert post.subtitle in content
    assert 'tw-ec-section' not in content
    assert 'tw-detail-nav' not in content
    assert 'tw-post-content' in content


@pytest.mark.django_db
def test_public_blog_detail_normalizes_relative_image_urls(client, authenticated_client):
    _, user = authenticated_client
    post = PostFactory(title='Artykuł z obrazkiem', text='<p><img src="media/uploads/article.webp" alt="Article image"></p>', visibility=Post.Visibility.PUBLIC, author=user)

    response = client.get(reverse('board:public_view_post', args=[post.pk]))

    assert response.status_code == 200
    assert '<img src="/media/uploads/article.webp" alt="Article image">' in response.content.decode()


@pytest.mark.django_db
def test_public_blog_slug_detail(client, authenticated_client):
    _, user = authenticated_client
    post = PostFactory(title='Slug article', visibility=Post.Visibility.PUBLIC, author=user, slug='slug-article')

    response = client.get(reverse('board:public_view_post_by_slug', kwargs={'slug': post.slug}))

    assert response.status_code == 200
    assert post.title in response.content.decode()


@pytest.mark.django_db
def test_system_post_titles_are_localized_and_system_assigned():
    post = Post.objects.get(system_key='start')
    post.title = 'Dowolny tytuł'
    post.save()
    post.refresh_from_db()

    assert post.title == 'Start page'
    with override('pl'):
        assert post.get_display_title() == 'Strona startowa'
    with override('en'):
        assert post.get_display_title() == 'Start page'


@pytest.mark.django_db
def test_edit_system_post_can_change_content_but_not_title_category_or_other_flags(authenticated_client):
    """Dokument systemowy nie pozwala zmienić tytułu ani pól zabezpieczających."""
    client, user = authenticated_client
    original_category = PostCategoryFactory(name='System category')
    new_category = PostCategoryFactory(name='Other category')
    post = PostFactory(title='Stały tytuł', system_key='protected-system-post', category=original_category, visibility='public', is_important=True)

    response = client.post(reverse('board:edit_post', args=[post.pk]), {'title': 'Zmieniony tytuł', 'text': 'Nowa treść', 'category': new_category.pk, 'is_private': 'on', 'is_important': 'on'})

    assert response.status_code == 302
    post.refresh_from_db()
    assert post.title == 'Stały tytuł'
    assert post.category.name == 'System'
    assert post.category != new_category
    assert post.visibility == Post.Visibility.PUBLIC
    assert post.is_important is True
    assert post.updated_by == user


@pytest.mark.django_db
def test_system_post_cannot_be_deleted_or_have_protected_fields_changed(authenticated_client):
    client, _ = authenticated_client
    original_category = PostCategoryFactory(name='System')
    new_category = PostCategoryFactory(name='Other')
    post = PostFactory(system_key='immutable-system-post', category=original_category, visibility='public', is_important=True)

    detail_response = client.get(reverse('board:view_post', args=[post.pk]))
    assert detail_response.status_code == 200
    assert 'deletePostModal' not in detail_response.content.decode()
    assert reverse('board:delete_post', args=[post.pk]) not in detail_response.content.decode()

    response = client.post(reverse('board:delete_post', args=[post.pk]))
    assert response.status_code == 404
    post.refresh_from_db()
    assert post.visibility == Post.Visibility.PUBLIC

    post.category = new_category
    post.visibility = Post.Visibility.ARCHIVE
    post.is_important = False
    post.system_key = None
    post.save()
    post.refresh_from_db()

    assert post.system_key == 'immutable-system-post'
    assert post.category.name == 'System'
    assert post.category != new_category
    assert post.visibility == Post.Visibility.PUBLIC
    assert post.is_important is True


@pytest.mark.django_db
def test_delete_post_is_available_to_other_users(authenticated_client):
    """Zalogowany użytkownik może przenieść cudzy dokument do kosza."""
    client, _ = authenticated_client
    other = UserFactory(username='other4', email='other4@example.com')
    private = PostFactory(title='Do usunięcia', visibility='group', author=other)

    res = client.post(reverse('board:delete_post', args=[private.pk]))

    assert res.status_code == 302
    private.refresh_from_db()
    assert private.visibility == Post.Visibility.ARCHIVE


@pytest.mark.django_db
def test_important_post_update_message_uses_modifier_as_sender(authenticated_client):
    _, author = authenticated_client
    editor = UserFactory(username='document-editor', email='document-editor@example.com')
    important_room = Room.objects.get(system_key='important')
    important_room.messages.all().delete()
    post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC, is_important=True)

    post.title = 'Zmieniony ważny dokument'
    post.updated_by = editor
    post.save(update_fields=['title', 'updated_by'])

    message = important_room.messages.order_by('-id').first()
    assert message.sender_id == editor.pk


@pytest.mark.django_db
def test_disabling_important_marker_adds_status_message(authenticated_client):
    _, user = authenticated_client
    important_room = Room.objects.get(system_key='important')
    important_room.messages.all().delete()
    post = PostFactory(author=user, visibility=Post.Visibility.PUBLIC, is_important=True)

    post.is_important = False
    post.save(update_fields=['is_important'])

    assert important_room.messages.count() == 2
    assert gettext('Document is no longer marked as important: %(link)s') % {'link': ''} in important_room.messages.order_by('-id').first().text


@pytest.mark.django_db
def test_tinymce_list_configuration_and_markup_survive_post_save(authenticated_client):
    client, _ = authenticated_client
    form_response = client.get(reverse('board:create_post'))
    config = form_response.context['form'].fields['text'].widget.get_mce_config({'id': 'id_text'})
    assert 'list-style-type: disc' in config['content_style']
    assert 'list-style-type: decimal' in config['content_style']
    response = client.post(reverse('board:create_post'), {'title': 'Dokument z listą', 'text': '<ul><li>Pierwszy punkt</li><li>Drugi punkt</li></ul>', 'visibility': Post.Visibility.GROUP})

    assert response.status_code == 302
    post = Post.objects.get(title='Dokument z listą')
    assert '<ul><li>Pierwszy punkt</li><li>Drugi punkt</li></ul>' in post.text


@pytest.mark.django_db
def test_important_post_update_without_modifier_uses_system_sender(authenticated_client):
    _, author = authenticated_client
    important_room = Room.objects.get(system_key='important')
    important_room.messages.all().delete()
    post = PostFactory(author=author, visibility=Post.Visibility.PUBLIC, is_important=True)

    post.title = 'Zmiana bez znanego modyfikatora'
    post.updated_by = None
    post.save(update_fields=['title', 'updated_by'])

    assert important_room.messages.order_by('-id').first().sender_id is None


@pytest.mark.django_db
def test_archived_important_post_keeps_history_and_notifies_when_restored(authenticated_client):
    _, user = authenticated_client
    important_room = Room.objects.get(system_key='important')
    important_room.messages.all().delete()
    post = PostFactory(author=user, visibility=Post.Visibility.PUBLIC, is_important=True)

    post.visibility = Post.Visibility.ARCHIVE
    post.save(update_fields=['visibility'])
    post.visibility = Post.Visibility.GROUP
    post.save(update_fields=['visibility'])

    messages = list(important_room.messages.order_by('id').values_list('text', flat=True))
    assert len(messages) == 3
    assert gettext('Important document was archived: %(link)s') % {'link': ''} in messages[1]
    assert gettext('Important document was made visible again: %(link)s') % {'link': ''} in messages[2]
