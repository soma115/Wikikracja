import copy
import multiprocessing
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import OperationalError, connections
from django.test import RequestFactory
from django.utils import timezone


def _reset_default_connection(database_config):
    connections.close_all()
    if hasattr(connections._connections, 'default'):
        delattr(connections._connections, 'default')
    connections.databases['default'] = database_config


@contextmanager
def _temporary_application_database():
    original_config = copy.deepcopy(connections.databases['default'])
    directory = tempfile.mkdtemp(prefix='wikikracja-business-concurrency-')
    database_path = str(Path(directory) / 'db.sqlite3')
    media_path = str(Path(directory) / 'media')
    Path(media_path).mkdir()
    test_config = copy.deepcopy(original_config)
    test_config['NAME'] = database_path
    test_config['TEST'] = {'NAME': database_path}
    old_media_root = settings.MEDIA_ROOT
    old_media_env = os.environ.get('WIKIKRACJA_CONCURRENCY_MEDIA_ROOT')
    settings.MEDIA_ROOT = media_path
    os.environ['WIKIKRACJA_CONCURRENCY_MEDIA_ROOT'] = media_path
    _reset_default_connection(test_config)
    try:
        call_command('migrate', verbosity=0)
        yield database_path
    finally:
        _reset_default_connection(original_config)
        settings.MEDIA_ROOT = old_media_root
        if old_media_env is None:
            os.environ.pop('WIKIKRACJA_CONCURRENCY_MEDIA_ROOT', None)
        else:
            os.environ['WIKIKRACJA_CONCURRENCY_MEDIA_ROOT'] = old_media_env
        shutil.rmtree(directory, ignore_errors=True)


def _configure_worker_database(database_path):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zzz.test_settings')
    import django

    django.setup()
    settings.MEDIA_ROOT = os.environ['WIKIKRACJA_CONCURRENCY_MEDIA_ROOT']
    worker_config = copy.deepcopy(connections.databases['default'])
    worker_config['NAME'] = database_path
    worker_config['TEST'] = {'NAME': database_path}
    _reset_default_connection(worker_config)


def _business_vote_worker(database_path, action, user_id, object_id, option_id, value, barrier, result_queue):
    _configure_worker_database(database_path)

    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore

    from ankiety.models import Survey
    from ankiety.views import _cast_vote
    from tasks.views import vote_task

    user_model = get_user_model()
    barrier.wait()
    started = time.perf_counter()
    last_error = None
    for attempt in range(5):
        try:
            user = user_model.objects.get(pk=user_id)
            request = RequestFactory().post('/', data={})
            request.user = user
            request.session = SessionStore()
            request._messages = FallbackStorage(request)
            if action == 'survey':
                survey = Survey.objects.get(pk=object_id)
                if option_id is not None:
                    request.POST = request.POST.copy()
                    request.POST['option'] = str(option_id)
                _cast_vote(request, survey)
            else:
                request = RequestFactory().post('/', data={'value': str(value)}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                request.user = user
                request.session = SessionStore()
                request._messages = FallbackStorage(request)
                vote_task(request, object_id)
            result_queue.put({'ok': True, 'elapsed': time.perf_counter() - started, 'attempts': attempt + 1})
            connections.close_all()
            return
        except OperationalError as error:
            if 'database is locked' not in str(error).lower() or attempt == 4:
                last_error = str(error)
                break
            time.sleep(0.05 * (2**attempt))
        except Exception as error:
            last_error = repr(error)
            break
    result_queue.put({'ok': False, 'error': last_error, 'elapsed': time.perf_counter() - started})
    connections.close_all()


def _run_workers(database_path, jobs):
    context = multiprocessing.get_context('spawn')
    barrier = context.Barrier(len(jobs))
    result_queue = context.Queue()
    processes = [context.Process(target=_business_vote_worker, args=(database_path, *job, barrier, result_queue)) for job in jobs]
    for process in processes:
        process.start()
    for process in processes:
        process.join(60)
        assert not process.is_alive()
        assert process.exitcode == 0
    results = [result_queue.get(timeout=5) for _ in processes]
    assert all(result['ok'] for result in results), results
    return results


def _create_survey(users, allow_multiple_choice=False):
    from ankiety.models import Survey, SurveyOption

    survey = Survey.objects.create(title='Concurrency survey', description='Concurrency test', end_date=timezone.now() + timedelta(days=36500), author=users[0], allow_multiple_choice=allow_multiple_choice)
    options = [SurveyOption.objects.create(survey=survey, text=text, order=index) for index, text in enumerate(('Yes', 'No', 'Maybe'))]
    return survey, options


@pytest.mark.django_db(transaction=True)
def test_concurrent_single_choice_changes_leave_one_vote_per_user():
    from ankiety.models import SurveyVote

    user_model = get_user_model()
    with _temporary_application_database() as database_path:
        users = [user_model.objects.create_user(username=f'survey-race-{index}') for index in range(2)]
        survey, options = _create_survey(users)
        jobs = [('survey', users[0].id, survey.id, options[0].id, None), ('survey', users[0].id, survey.id, options[1].id, None)]

        results = _run_workers(database_path, jobs)

        votes = list(SurveyVote.objects.filter(survey=survey, user=users[0]))
        assert len(votes) == 1
        assert votes[0].option_id in {options[0].id, options[1].id}
        assert all(result['attempts'] >= 1 for result in results)
        print(f'survey_single_choice_elapsed={max(result["elapsed"] for result in results):.4f}s')


@pytest.mark.django_db(transaction=True)
def test_concurrent_survey_withdrawal_and_save_never_create_duplicate_votes():
    from ankiety.models import SurveyVote

    user_model = get_user_model()
    with _temporary_application_database() as database_path:
        users = [user_model.objects.create_user(username=f'survey-withdraw-{index}') for index in range(2)]
        survey, options = _create_survey(users)
        SurveyVote.objects.create(survey=survey, user=users[0], option=options[0])
        jobs = [('survey', users[0].id, survey.id, None, None), ('survey', users[0].id, survey.id, options[1].id, None)]

        results = _run_workers(database_path, jobs)

        assert SurveyVote.objects.filter(survey=survey, user=users[0]).count() <= 1
        print(f'survey_withdraw_save_elapsed={max(result["elapsed"] for result in results):.4f}s')


@pytest.mark.django_db(transaction=True)
def test_concurrent_users_casting_same_survey_retain_one_vote_each():
    from ankiety.models import SurveyVote

    user_model = get_user_model()
    with _temporary_application_database() as database_path:
        users = [user_model.objects.create_user(username=f'survey-many-{index}') for index in range(4)]
        survey, options = _create_survey(users)
        jobs = [('survey', user.id, survey.id, options[index % 2].id, None) for index, user in enumerate(users)]

        results = _run_workers(database_path, jobs)

        assert SurveyVote.objects.filter(survey=survey).count() == len(users)
        assert SurveyVote.objects.filter(survey=survey).values('user_id').distinct().count() == len(users)
        print(f'survey_many_users_elapsed={max(result["elapsed"] for result in results):.4f}s')


@pytest.mark.django_db(transaction=True)
def test_concurrent_task_votes_have_deterministic_rejection_status():
    from django.contrib.auth import get_user_model

    from tasks.models import Task, TaskVote

    user_model = get_user_model()
    with _temporary_application_database() as database_path:
        users = [user_model.objects.create_user(username=f'task-race-{index}') for index in range(2)]
        task = Task.objects.create(title='Concurrency task', description='Concurrency test', created_by=users[0])
        jobs = [('task', users[0].id, task.id, None, int(TaskVote.Value.DOWN)), ('task', users[1].id, task.id, None, int(TaskVote.Value.DOWN))]

        results = _run_workers(database_path, jobs)

        task.refresh_from_db()
        assert TaskVote.objects.filter(task=task).count() == 2
        assert sum(TaskVote.objects.filter(task=task).values_list('value', flat=True)) == -2
        assert task.status == Task.Status.REJECTED
        print(f'task_votes_elapsed={max(result["elapsed"] for result in results):.4f}s')
