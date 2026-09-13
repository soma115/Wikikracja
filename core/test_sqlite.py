from unittest.mock import patch

from django.db import OperationalError
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
