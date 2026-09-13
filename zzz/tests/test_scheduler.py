from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from zzz.scheduler import _acquire_scheduler_lock


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
