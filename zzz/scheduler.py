import atexit
import logging
import os
import sys
import tempfile
import threading
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management import call_command

from core.sqlite import wal_size

log = logging.getLogger(__name__)

# Needed in case chat_rooms and count_citizens run concurrently. Both writing a lot to database.
_db_lock = threading.Lock()

# Global variables keep the scheduler singleton and its inter-process lock alive.
_scheduler = None
_scheduler_lock = threading.Lock()
_scheduler_lock_fd = None


def _acquire_scheduler_lock(lock_file_path):
    """Acquire a non-blocking process lock and keep its descriptor open."""
    lock_fd = None
    try:
        lock_fd = open(lock_file_path, 'a+')
        if os.name == 'nt':
            import msvcrt

            lock_fd.seek(0)
            lock_fd.write('1')
            lock_fd.flush()
            lock_fd.seek(0)
            msvcrt.locking(lock_fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except (IOError, OSError):
        if lock_fd is not None:
            lock_fd.close()
        return None


def should_start_scheduler():
    """Return whether the current process is an allowed scheduler process."""
    if os.getenv('SCHEDULER_ENABLED', '').lower() != 'true':
        return False
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'run_scheduler':
        return True
    return command == 'runserver' and os.getenv('RUN_MAIN') == 'true'


def start_scheduler():
    """Start the process-local scheduler once when this process is allowed to run it."""
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            return _scheduler
        if not should_start_scheduler():
            return None
        _scheduler = _start_scheduler()
        atexit.register(stop_scheduler)
        return _scheduler


def _start_scheduler():
    """
    Start APScheduler to run management commands on schedule.
    Uses file-based lock to ensure only one scheduler instance runs across multiple workers.
    Replaces cron jobs:
    - 0 8 * * * -> send_email_digest
    - */5 * * * * -> chat_rooms (every 5 minutes)
    - 5 8 * * * -> vote
    - */5 * * * * -> count_citizens (every 5 minutes)
    - 2 * * * * -> update_site (every hour)
    """
    global _scheduler_lock_fd

    lock_file_path = os.getenv('SCHEDULER_LOCK_FILE', os.path.join(tempfile.gettempdir(), 'wikikracja_scheduler.lock'))
    _scheduler_lock_fd = _acquire_scheduler_lock(lock_file_path)
    if _scheduler_lock_fd is None:
        log.info('Scheduler already running in another worker/process - skipping initialization')
        return None
    log.info('Acquired scheduler lock: %s', lock_file_path)

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)

    # Email activity digest - runs daily at 08:00
    scheduler.add_job(run_send_email_digest, trigger=CronTrigger(hour=8, minute=0), id='send_email_digest', name='Send email activity digests', replace_existing=True)
    log.info("Scheduled job: send_email_digest at 08:00 daily")

    # Chat rooms - runs every 5 minutes
    scheduler.add_job(run_chat_rooms, trigger=CronTrigger(minute='*/5'), id='chat_rooms', name='Create/Delete/Archive chat rooms', replace_existing=True)
    log.info("Scheduled job: chat_rooms every 5 minutes")

    # Vote - runs daily at 08:05
    scheduler.add_job(run_vote, trigger=CronTrigger(hour=8, minute=5), id='vote', name='Process voting and create 1-to-1 rooms', replace_existing=True)
    log.info("Scheduled job: vote at 08:05 daily")

    # Count citizens - runs every 5 minutes
    scheduler.add_job(run_count_citizens, trigger=CronTrigger(minute='*/5'), id='count_citizens', name='Count citizens and manage reputation', replace_existing=True)
    log.info("Scheduled job: count_citizens every 5 minutes")

    # Update site - runs every hour
    scheduler.add_job(run_update_site, trigger=CronTrigger(minute=2), id='update_site', name='Update Site domain and name from environment variables', replace_existing=True)
    log.info("Scheduled job: update_site every hour")

    # Check for events starting every minute
    scheduler.add_job(run_meeting_notification, trigger=CronTrigger(minute='*'), id='meeting_notification', name='Send notification when event starts', replace_existing=True)

    scheduler.start()
    log.info("APScheduler started successfully")

    return scheduler


def stop_scheduler():
    """Stop the process-local scheduler and release its file lock."""
    global _scheduler, _scheduler_lock_fd
    with _scheduler_lock:
        if _scheduler is not None and _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None
        if _scheduler_lock_fd is not None:
            _scheduler_lock_fd.close()
            _scheduler_lock_fd = None


def run_meeting_notification():
    """Send push and WebSocket notifications for events that are starting now."""
    from datetime import timedelta

    from django.utils import timezone
    from django.utils.translation import gettext_lazy as _

    from events.models import Event
    from events.services import notify_event_starting

    now = timezone.now()
    start_of_minute = now.replace(second=0, microsecond=0)
    end_of_minute = start_of_minute + timedelta(minutes=1)

    starting_occurrences = []
    one_time_events = Event.objects.filter(is_active=True, frequency='once', start_date__gte=start_of_minute, start_date__lt=end_of_minute)
    starting_occurrences.extend((event, event.start_date) for event in one_time_events)

    recurring_events = Event.objects.filter(is_active=True, frequency__in=('daily', 'weekly', 'monthly', 'monthly_ordinal', 'yearly'), start_date__lt=end_of_minute)
    for event in recurring_events:
        starting_occurrences.extend((event, occurrence) for occurrence in event.get_occurrences(start_of_minute, end_of_minute) if occurrence < end_of_minute)

    if not starting_occurrences:
        return  # Silent return - no events starting this minute

    starting_occurrences.sort(key=lambda item: item[1])
    for event, occurrence in starting_occurrences:
        try:
            # Format detailed notification body (time, place, description)
            event_time = timezone.localtime(occurrence).strftime('%H:%M')
            body_parts = [f"{_('Time')}: {event_time}"]

            if event.place:
                body_parts.append(f"{_('Place')}: {event.place}")

            if event.description:
                description = event.description.strip()
                if len(description) > 400:
                    description = description[:400] + "..."
                body_parts.append(f"{_('Description')}: {description}")

            body_text = " | ".join(body_parts)
            notify_event_starting(event, body=body_text)
        except Exception as e:
            log.error(f"Notification failed for event {event.id}: {e}")


def _run_command(command_name):
    """Generic command runner with timing and error handling."""
    started_at = time.monotonic()
    try:
        log.info('Running scheduler command=%s', command_name)
        call_command(command_name)
    except Exception as error:
        log.error('Scheduler command failed command=%s error=%s', command_name, error, exc_info=True)
    finally:
        log.info('Scheduler command finished command=%s duration=%.3fs wal_size=%s', command_name, time.monotonic() - started_at, wal_size())


def run_send_email_digest():
    """Execute send_email_digest management command"""
    with _db_lock:
        _run_command('send_email_digest')


def run_chat_rooms():
    """Execute chat_rooms management command"""
    with _db_lock:
        _run_command('chat_rooms')


def run_vote():
    """Execute vote management command"""
    with _db_lock:
        _run_command('vote')


def run_count_citizens():
    """Execute count_citizens management command"""
    with _db_lock:
        _run_command('count_citizens')


def run_update_site():
    """Execute update_site management command"""
    with _db_lock:
        _run_command('update_site')
