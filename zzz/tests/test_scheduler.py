import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from zzz.scheduler import _acquire_scheduler_lock, should_start_scheduler


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
