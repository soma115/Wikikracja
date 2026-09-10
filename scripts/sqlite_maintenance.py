"""Safe maintenance operations for an active SQLite database.

This script can:
- create a consistent backup with SQLite's Backup API using a 60-second timeout and batched copying;
- optionally run VACUUM after a completed backup;
- run PRAGMA quick_check and PRAGMA integrity_check;
- run a WAL checkpoint in a selected mode;
- refuse to overwrite an existing backup;
- require explicit confirmation before a TRUNCATE checkpoint;
- prune old backups only through an explicit `prune --confirm` command.

Usage (run from the project root):

The source database defaults to `SQLITE_DATABASE_PATH` or `db/db.sqlite3`.
The backup directory defaults to `SQLITE_BACKUP_DIR` or `backups`. If no
backup destination is supplied, the script creates a timestamped file in that
directory. Relative paths are resolved from the current working directory;
scheduled container jobs should use absolute paths and a persistent volume.

    # Create a timestamped backup in SQLITE_BACKUP_DIR (or ./backups).
    python scripts/sqlite_maintenance.py backup

    # Create a backup at an explicit destination.
    python scripts/sqlite_maintenance.py backup backups/db-20260910-040000.sqlite3

    # Create a backup and then run VACUUM on the source database.
    # Use only during the planned maintenance window after stopping/blocking writes.
    python scripts/sqlite_maintenance.py backup backups/db-20260910-040000.sqlite3 --vacuum-after

    # Check the active database.
    python scripts/sqlite_maintenance.py integrity-check

    # Run a non-blocking WAL checkpoint.
    python scripts/sqlite_maintenance.py checkpoint --mode PASSIVE

    # Run a manual VACUUM (requires a verified backup first).
    python scripts/sqlite_maintenance.py vacuum

    # Preview/use retention configured by SQLITE_BACKUP_RETENTION_DAYS.
    # Deletion requires explicit confirmation.
    python scripts/sqlite_maintenance.py prune --confirm

    # Use a database at a non-default path.
    python scripts/sqlite_maintenance.py --database /path/to/db.sqlite3 integrity-check

The backup destination must not already exist. Prefer an absolute destination
path in scheduled jobs so the backup location does not depend on the process
working directory. A separate backup process should copy only completed
`.sqlite3` files and ignore temporary/in-progress files.
"""

import argparse
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
load_dotenv(BASE_DIR / '.env.local')

DEFAULT_DATABASE = Path(os.getenv('SQLITE_DATABASE_PATH', 'db/db.sqlite3'))
DEFAULT_BACKUP_DIR = Path(os.getenv('SQLITE_BACKUP_DIR', 'backups'))
DEFAULT_RETENTION_DAYS = int(os.getenv('SQLITE_BACKUP_RETENTION_DAYS', '30'))
SQLITE_TIMEOUT_SECONDS = 60
BACKUP_PAGE_BATCH = 100
BACKUP_RETRY_SLEEP_SECONDS = 0.5


def backup(database, destination):
    if database.resolve() == destination.resolve():
        raise ValueError('Backup destination must differ from the database')
    if destination.exists():
        raise FileExistsError(f'Backup destination already exists: {destination}')

    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(database, timeout=SQLITE_TIMEOUT_SECONDS)
    target_connection = sqlite3.connect(destination, timeout=SQLITE_TIMEOUT_SECONDS)
    completed = False
    try:
        source_connection.backup(target_connection, pages=BACKUP_PAGE_BATCH, sleep=BACKUP_RETRY_SLEEP_SECONDS)
        completed = True
    finally:
        target_connection.close()
        source_connection.close()
        if not completed:
            destination.unlink(missing_ok=True)


def integrity_check(database):
    connection = sqlite3.connect(database, timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        quick_check = connection.execute('PRAGMA quick_check').fetchall()
        integrity = connection.execute('PRAGMA integrity_check').fetchall()
    finally:
        connection.close()
    return quick_check, integrity


def checkpoint(database, mode):
    connection = sqlite3.connect(database, timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        return connection.execute(f'PRAGMA wal_checkpoint({mode})').fetchone()
    finally:
        connection.close()


def vacuum(database):
    connection = sqlite3.connect(database, timeout=SQLITE_TIMEOUT_SECONDS)
    try:
        connection.execute('VACUUM')
    finally:
        connection.close()


def prune_backups(directory, retention_days):
    cutoff = datetime.now().timestamp() - timedelta(days=retention_days).total_seconds()
    removed = []
    for path in directory.glob('*.sqlite3'):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink()
            removed.append(path)
    return removed


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=DEFAULT_DATABASE)
    subparsers = parser.add_subparsers(dest='operation', required=True)

    backup_parser = subparsers.add_parser('backup')
    backup_parser.add_argument('destination', type=Path, nargs='?')
    backup_parser.add_argument('--vacuum-after', action='store_true')
    subparsers.add_parser('integrity-check')
    subparsers.add_parser('vacuum')

    prune_parser = subparsers.add_parser('prune')
    prune_parser.add_argument('--directory', type=Path, default=DEFAULT_BACKUP_DIR)
    prune_parser.add_argument('--days', type=int, default=DEFAULT_RETENTION_DAYS)
    prune_parser.add_argument('--confirm', action='store_true')

    checkpoint_parser = subparsers.add_parser('checkpoint')
    checkpoint_parser.add_argument('--mode', choices=('PASSIVE', 'FULL', 'RESTART', 'TRUNCATE'), default='PASSIVE')
    checkpoint_parser.add_argument('--confirm-truncate', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    database = args.database.resolve()
    if args.operation != 'prune' and not database.exists():
        raise SystemExit(f'Database does not exist: {database}')

    if args.operation == 'backup':
        destination = args.destination or DEFAULT_BACKUP_DIR / f'db-{datetime.now():%Y%m%d-%H%M%S}.sqlite3'
        destination = destination.resolve()
        backup(database, destination)
        print(f'Backup created: {destination}')
        if args.vacuum_after:
            vacuum(database)
            print('VACUUM completed')
    elif args.operation == 'integrity-check':
        quick_check, integrity = integrity_check(database)
        print(f'quick_check: {quick_check}')
        print(f'integrity_check: {integrity}')
        if quick_check != [('ok',)] or integrity != [('ok',)]:
            raise SystemExit(1)
    elif args.operation == 'vacuum':
        vacuum(database)
        print('VACUUM completed')
    elif args.operation == 'prune':
        if not args.confirm:
            raise SystemExit('prune requires --confirm')
        if args.days < 0:
            raise SystemExit('--days must be non-negative')
        removed = prune_backups(args.directory.resolve(), args.days)
        print(f'Removed {len(removed)} backup(s) older than {args.days} day(s)')
    else:
        if args.mode == 'TRUNCATE' and not args.confirm_truncate:
            raise SystemExit('TRUNCATE requires --confirm-truncate')
        result = checkpoint(database, args.mode)
        print(f'wal_checkpoint({args.mode}): {result}')


if __name__ == '__main__':
    main()
