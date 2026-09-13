"""Small, bounded helpers for handling transient SQLite write locks."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from typing import TypeVar

from django.db import OperationalError, connection

log = logging.getLogger(__name__)

T = TypeVar('T')


def is_locked(error: OperationalError) -> bool:
    """Return whether an OperationalError is the transient SQLite lock error."""
    return 'database is locked' in str(error).lower()


def wal_size() -> int | None:
    """Return the current WAL size without failing the caller."""
    database_name = connection.settings_dict.get('NAME')
    if not database_name or database_name == ':memory:':
        return None
    try:
        return os.path.getsize(f'{database_name}-wal')
    except OSError:
        return None


def run_with_lock_retry(operation: str, function: Callable[[], T], *, max_attempts: int = 2, delays: tuple[float, ...] = (0.1,)) -> T:
    """Run a complete idempotent operation with a short bounded lock retry.

    Only the exact transient SQLite lock error is retried. The callable must contain
    the complete operation so a retry cannot resume half-way through a transaction.
    """
    if max_attempts < 1:
        raise ValueError('max_attempts must be positive')
    if len(delays) < max_attempts - 1:
        raise ValueError('delays must cover every retry')

    started_at = time.monotonic()
    for attempt in range(max_attempts):
        try:
            return function()
        except OperationalError as error:
            if not is_locked(error) or attempt == max_attempts - 1:
                raise
            delay = delays[attempt]
            log.warning('SQLite lock during operation=%s attempt=%s wait=%.3fs transaction_time=%.3fs wal_size=%s', operation, attempt + 1, delay, time.monotonic() - started_at, wal_size())
            time.sleep(delay)

    raise AssertionError('unreachable')
