from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.db.utils import ConnectionHandler
from django.test import SimpleTestCase

from core.sqlite import run_with_lock_retry


class SQLiteRetryTest(SimpleTestCase):
    def test_retries_only_a_transient_lock(self):
        operation = MockOperation([OperationalError('database is locked'), 'ok'])

        with patch('core.sqlite.time.sleep') as sleep:
            result = run_with_lock_retry('test.operation', operation, delays=(0.1,))

        self.assertEqual(result, 'ok')
        self.assertEqual(operation.calls, 2)
        sleep.assert_called_once_with(0.1)

    def test_does_not_retry_other_operational_errors(self):
        operation = MockOperation([OperationalError('disk I/O error'), 'unexpected'])

        with patch('core.sqlite.time.sleep') as sleep:
            with self.assertRaisesMessage(OperationalError, 'disk I/O error'):
                run_with_lock_retry('test.operation', operation, delays=(0.1,))

        self.assertEqual(operation.calls, 1)
        sleep.assert_not_called()

    def test_logs_when_lock_retries_are_exhausted(self):
        operation = MockOperation([OperationalError('database is locked'), OperationalError('database is locked')])

        with patch('core.sqlite.time.sleep'), self.assertLogs('core.sqlite', level='ERROR') as logs:
            with self.assertRaisesMessage(OperationalError, 'database is locked'):
                run_with_lock_retry('test.operation', operation, delays=(0.1,))

        self.assertTrue(any('SQLite database is locked; retry exhausted operation=test.operation' in message for message in logs.output))


@pytest.mark.django_db
def test_new_sqlite_connection_configures_required_pragmas(tmp_path):
    connections = ConnectionHandler({'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': tmp_path / 'pragmas.sqlite3', 'OPTIONS': {'timeout': 0.25}}})
    connection = connections['default']
    try:
        with connection.cursor() as cursor:
            journal_mode = cursor.execute('PRAGMA journal_mode').fetchone()[0]
            foreign_keys = cursor.execute('PRAGMA foreign_keys').fetchone()[0]
            busy_timeout = cursor.execute('PRAGMA busy_timeout').fetchone()[0]
    finally:
        connection.close()

    assert journal_mode == 'wal'
    assert foreign_keys == 1
    assert busy_timeout == 250


class MockOperation:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result
