"""Measure SQLite write contention without modifying the application database.

By default the test creates a temporary SQLite database. When ``--database`` is
provided, the source database is copied to a temporary working database first;
the source is never modified. The test starts multiple writer processes and
optionally runs SQLite Backup API and VACUUM operations while they write. It
reports lock counts, elapsed times, write throughput, backup duration, and WAL/
SHM sidecar sizes.

Examples (run from the project root):

    # Basic write-contention test on a temporary database.
    python scripts/sqlite_contention_test.py

    # More writers and operations, including backup and VACUUM contention.
    python scripts/sqlite_contention_test.py --writers 4 --operations 500 --backup --vacuum

    # Use the application database as a read-only source for the test copy.
    python scripts/sqlite_contention_test.py --database db/db.sqlite3 --writers 4 --backup
"""

import argparse
import multiprocessing
import sqlite3
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS contention_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@dataclass
class WorkerResult:
    worker_id: int
    succeeded: int
    locked: int
    failed: int
    elapsed_seconds: float


def configure_connection(connection, timeout):
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('PRAGMA synchronous=NORMAL')
    connection.execute(f'PRAGMA busy_timeout={int(timeout * 1000)}')


def initialize_database(database, source=None, timeout=5.0):
    if source is not None:
        source_connection = sqlite3.connect(source, timeout=timeout)
        target_connection = sqlite3.connect(database, timeout=timeout)
        try:
            source_connection.backup(target_connection, pages=100, sleep=0.1)
        finally:
            target_connection.close()
            source_connection.close()

    connection = sqlite3.connect(database, timeout=timeout)
    try:
        configure_connection(connection, timeout)
        connection.execute(TABLE_SQL)
        connection.commit()
    finally:
        connection.close()


def is_locked(error):
    return 'database is locked' in str(error).lower()


def writer_process(database, worker_id, operations, timeout, result_queue):
    started_at = time.monotonic()
    succeeded = locked = failed = 0
    connection = sqlite3.connect(database, timeout=timeout)
    try:
        configure_connection(connection, timeout)
        for sequence in range(operations):
            try:
                with connection:
                    connection.execute('INSERT INTO contention_events(worker_id, sequence, payload) VALUES (?, ?, ?)', (worker_id, sequence, f'worker-{worker_id}-{sequence}'))
                    connection.execute('UPDATE contention_events SET updated_at=CURRENT_TIMESTAMP WHERE worker_id=? AND sequence=?', (worker_id, sequence))
                succeeded += 1
            except sqlite3.OperationalError as error:
                if is_locked(error):
                    locked += 1
                else:
                    failed += 1
            except sqlite3.Error:
                failed += 1
    finally:
        connection.close()
        result_queue.put(WorkerResult(worker_id, succeeded, locked, failed, time.monotonic() - started_at))


def run_backup(database, destination, timeout):
    started_at = time.monotonic()
    source_connection = sqlite3.connect(database, timeout=timeout)
    target_connection = sqlite3.connect(destination, timeout=timeout)
    try:
        source_connection.backup(target_connection, pages=100, sleep=0.1)
    finally:
        target_connection.close()
        source_connection.close()
    return time.monotonic() - started_at


def run_vacuum(database, timeout):
    connection = sqlite3.connect(database, timeout=timeout)
    try:
        connection.execute('VACUUM')
    finally:
        connection.close()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, help='Read-only source database; it is copied to a temporary working database.')
    parser.add_argument('--writers', type=int, default=4)
    parser.add_argument('--operations', type=int, default=250)
    parser.add_argument('--timeout', type=float, default=1.0, help='SQLite busy timeout per connection, in seconds.')
    parser.add_argument('--backup', action='store_true', help='Run one SQLite Backup API copy while writers are active.')
    parser.add_argument('--vacuum', action='store_true', help='Run VACUUM while writers are active to measure contention.')
    parser.add_argument('--keep-artifacts', action='store_true', help='Keep the temporary working database and backup files.')
    return parser.parse_args()


def validate_args(args):
    if args.writers < 1:
        raise SystemExit('--writers must be at least 1')
    if args.operations < 1:
        raise SystemExit('--operations must be at least 1')
    if args.timeout <= 0:
        raise SystemExit('--timeout must be greater than 0')
    if args.database and not args.database.exists():
        raise SystemExit(f'Source database does not exist: {args.database}')


def sqlite_sidecar_size(database, suffix):
    sidecar = Path(f'{database}{suffix}')
    return sidecar.stat().st_size if sidecar.exists() else 0


def monitor_sidecars(database, stop_event, samples):
    while not stop_event.wait(0.05):
        samples.append((sqlite_sidecar_size(database, '-wal'), sqlite_sidecar_size(database, '-shm')))


def main():
    args = parse_args()
    validate_args(args)
    test_started_at = time.monotonic()
    temp_directory = None
    if args.keep_artifacts:
        work_directory = Path.cwd() / 'sqlite-contention-artifacts'
        work_directory.mkdir(exist_ok=True)
    else:
        temp_directory = tempfile.TemporaryDirectory(prefix='wikikracja-sqlite-')
        work_directory = Path(temp_directory.name)

    database = work_directory / 'working.sqlite3'
    source = args.database.resolve() if args.database else None
    initialize_database(database, source=source, timeout=args.timeout)
    backup_path = work_directory / 'during-writes-backup.sqlite3'

    context = multiprocessing.get_context('spawn')
    result_queue = context.Queue()
    processes = [context.Process(target=writer_process, args=(str(database), worker_id, args.operations, args.timeout, result_queue)) for worker_id in range(args.writers)]
    for process in processes:
        process.start()

    sidecar_stop = threading.Event()
    sidecar_samples = []
    sidecar_thread = threading.Thread(target=monitor_sidecars, args=(database, sidecar_stop, sidecar_samples), daemon=True)
    sidecar_thread.start()

    backup_error = None
    backup_elapsed = None
    vacuum_error = None
    time.sleep(0.1)
    if args.backup:
        try:
            backup_elapsed = run_backup(database, backup_path, args.timeout)
        except sqlite3.Error as error:
            backup_error = str(error)
    if args.vacuum:
        try:
            run_vacuum(database, args.timeout)
        except sqlite3.Error as error:
            vacuum_error = str(error)

    for process in processes:
        process.join()
    sidecar_stop.set()
    sidecar_thread.join()

    results = [result_queue.get() for _ in processes]
    results.sort(key=lambda result: result.worker_id)
    total_succeeded = sum(result.succeeded for result in results)
    total_locked = sum(result.locked for result in results)
    total_failed = sum(result.failed for result in results)
    total_elapsed = time.monotonic() - test_started_at
    wal_size = sqlite_sidecar_size(database, '-wal')
    shm_size = sqlite_sidecar_size(database, '-shm')
    peak_wal_size = max([wal_size, *(sample[0] for sample in sidecar_samples)])
    peak_shm_size = max([shm_size, *(sample[1] for sample in sidecar_samples)])
    quick_check, integrity_check = check_database(database, args.timeout)
    throughput = total_succeeded / total_elapsed if total_elapsed else 0
    worker_elapsed = max((result.elapsed_seconds for result in results), default=0)

    print(f'Working database: {database}')
    print(f'Writers: {args.writers}; operations per writer: {args.operations}; timeout: {args.timeout:.2f}s')
    print(f'Total test time: {total_elapsed:.2f}s')
    print(f'Succeeded writes: {total_succeeded}')
    print(f'Locked writes: {total_locked}')
    print(f'Other write failures: {total_failed}')
    print(f'Write throughput: {throughput:.2f} successful writes/s')
    print(f'Slowest writer time: {worker_elapsed:.2f}s')
    print(f'Backup during writes: {"ok" if args.backup and backup_error is None else backup_error or "not requested"}')
    if backup_elapsed is not None:
        print(f'Backup time: {backup_elapsed:.2f}s')
    print(f'VACUUM during writes: {"ok" if args.vacuum and vacuum_error is None else vacuum_error or "not requested"}')
    print(f'WAL peak size: {peak_wal_size} bytes')
    print(f'SHM peak size: {peak_shm_size} bytes')
    print(f'WAL size after writes: {wal_size} bytes')
    print(f'SHM size after writes: {shm_size} bytes')
    print(f'quick_check: {quick_check}')
    print(f'integrity_check: {integrity_check}')

    if temp_directory is not None:
        temp_directory.cleanup()


def check_database(database, timeout):
    connection = sqlite3.connect(database, timeout=timeout)
    try:
        return (connection.execute('PRAGMA quick_check').fetchall(), connection.execute('PRAGMA integrity_check').fetchall())
    finally:
        connection.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
