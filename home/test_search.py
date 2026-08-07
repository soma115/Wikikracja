import pytest
from django.utils import timezone

from chat.models import Message, Room
from events.models import Event
from glosowania.models import Argument, Decyzja
from home.services.search import run_global_search
from home.views import ALL_SEARCH_CATS
from tasks.models import Task
from tests.factories import PostCategoryFactory, PostFactory, UserFactory

# NOTE: run_global_search expects a category set, but the view builds active_cats.
# The service module re-exports ALL_SEARCH_CATS for convenience.


@pytest.fixture
def searcher(db):
    return UserFactory(username='searcher', email='searcher@example.com')


@pytest.fixture
def other_user(db):
    return UserFactory(username='other', email='other@example.com')


@pytest.mark.django_db
def test_search_post_category(searcher):
    category = PostCategoryFactory()
    PostFactory(author=searcher, category=category, title='Findable post', text='<p>unique keyword xyz</p>')

    results = run_global_search('xyz', {'post'}, searcher)
    assert any(r['cat'] == 'post' for r in results)


@pytest.mark.django_db
def test_search_task_category(searcher, other_user):
    Task.objects.create(
        title='Task with xyz',
        description='description',
        created_by=searcher,
        assigned_to=other_user,
        status=Task.Status.ACTIVE,
    )

    results = run_global_search('xyz', {'task'}, searcher)
    assert any(r['cat'] == 'task' for r in results)


@pytest.mark.django_db
def test_search_decision_category(searcher):
    decision = Decyzja.objects.create(
        title='Decision with xyz',
        tresc='Some content',
        author=searcher,
        status=Decyzja.Status.PROPOSITION,
    )

    results = run_global_search('xyz', {'decision'}, searcher)
    assert any(r['cat'] == 'decision' and r['title'] == decision.title for r in results)


@pytest.mark.django_db
def test_search_decision_argument(searcher):
    decision = Decyzja.objects.create(
        title='Decision title',
        tresc='Content',
        author=searcher,
        status=Decyzja.Status.PROPOSITION,
    )
    Argument.objects.create(
        decyzja=decision,
        author=searcher,
        argument_type='FOR',
        content='argument xyz',
    )

    results = run_global_search('xyz', {'decision'}, searcher)
    assert any(r['cat'] == 'decision' for r in results)


@pytest.mark.django_db
def test_search_event_category(searcher):
    Event.objects.create(
        title='Event xyz',
        description='desc',
        start_date=timezone.now() + timezone.timedelta(days=1),
        frequency='once',
        is_active=True,
    )

    results = run_global_search('xyz', {'event'}, searcher)
    assert any(r['cat'] == 'event' for r in results)


@pytest.mark.django_db
def test_search_citizen_category(searcher):
    other = UserFactory(username='xyz_citizen', first_name='Xyz', last_name='Test')

    results = run_global_search('xyz', {'citizen'}, searcher)
    assert any(r['cat'] == 'citizen' and r['description'] == f'@{other.username}' for r in results)


@pytest.mark.django_db
def test_search_chat_category(searcher, other_user):
    room = Room.objects.create(title='Room xyz', public=False)
    room.allowed.add(searcher)
    Message.objects.create(room=room, sender=other_user, text='hello')

    results = run_global_search('xyz', {'chat'}, searcher)
    assert any(r['cat'] == 'chat' for r in results)


@pytest.mark.django_db
def test_search_active_cats_filtering(searcher):
    category = PostCategoryFactory()
    PostFactory(author=searcher, category=category, title='Post xyz', text='<p>xyz</p>')
    Task.objects.create(
        title='Task xyz',
        description='desc',
        created_by=searcher,
        assigned_to=searcher,
        status=Task.Status.ACTIVE,
    )

    post_results = run_global_search('xyz', {'post'}, searcher)
    assert all(r['cat'] == 'post' for r in post_results)

    task_results = run_global_search('xyz', {'task'}, searcher)
    assert all(r['cat'] == 'task' for r in task_results)


@pytest.mark.django_db
def test_search_returns_nothing_for_empty_query(searcher):
    results = run_global_search('', ALL_SEARCH_CATS, searcher)
    assert results == []
