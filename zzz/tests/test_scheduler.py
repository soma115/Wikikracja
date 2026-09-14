import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from zzz.scheduler import _acquire_scheduler_lock, _run_command, should_start_scheduler


class SchedulerStartGuardTest(TestCase):
    def test_management_commands_do_not_start_scheduler(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'true', 'RUN_MAIN': 'false'}), patch('zzz.scheduler.sys.argv', ['manage.py', 'migrate']):
            self.assertFalse(should_start_scheduler())

    def test_dedicated_command_starts_scheduler(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'true', 'RUN_MAIN': 'false'}), patch('zzz.scheduler.sys.argv', ['manage.py', 'run_scheduler']):
            self.assertTrue(should_start_scheduler())

    def test_help_command_does_not_start_scheduler(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'true', 'RUN_MAIN': 'false'}), patch('zzz.scheduler.sys.argv', ['manage.py', 'help', 'run_scheduler']):
            self.assertFalse(should_start_scheduler())

    def test_http_process_stays_disabled(self):
        with patch.dict(os.environ, {'SCHEDULER_ENABLED': 'false', 'RUN_MAIN': 'false'}), patch('zzz.scheduler.sys.argv', ['daphne', 'zzz.routing:application']):
            self.assertFalse(should_start_scheduler())


class SchedulerCommandMonitoringTest(TestCase):
    def test_command_logs_duration_and_wal_size(self):
        with (
            patch('zzz.scheduler.call_command'),
            patch('zzz.scheduler.wal_size', return_value=4096),
            patch('zzz.scheduler.time.monotonic', side_effect=[10.0, 10.25]),
            self.assertLogs('zzz.scheduler', level='INFO') as logs,
        ):
            _run_command('count_citizens')

        self.assertTrue(any('Scheduler command finished command=count_citizens duration=0.250s wal_size=4096' in message for message in logs.output))

    def test_command_logs_failure_and_still_reports_duration(self):
        with (
            patch('zzz.scheduler.call_command', side_effect=RuntimeError('forced failure')),
            patch('zzz.scheduler.wal_size', return_value=None),
            patch('zzz.scheduler.time.monotonic', side_effect=[20.0, 20.5]),
            self.assertLogs('zzz.scheduler', level='INFO') as logs,
        ):
            _run_command('vote')

        self.assertTrue(any('Scheduler command failed command=vote' in message for message in logs.output))
        self.assertTrue(any('Scheduler command finished command=vote duration=0.500s wal_size=None' in message for message in logs.output))


class SchedulerLockTest(TestCase):
    def test_acquires_lock_file_and_keeps_it_available(self):
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / 'scheduler.lock'
            lock_fd = _acquire_scheduler_lock(str(lock_path))
            self.assertIsNotNone(lock_fd)
            self.assertTrue(lock_path.exists())
            lock_fd.close()

    def test_returns_none_for_unavailable_lock_path(self):
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / 'missing' / 'scheduler.lock'
            self.assertIsNone(_acquire_scheduler_lock(str(lock_path)))
