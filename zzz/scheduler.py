import logging
import os
import tempfile
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management import call_command

log = logging.getLogger(__name__)

# Needed in case chat_rooms and count_citizens run concurrently. Both writing a lot to database.
_db_lock = threading.Lock()

# Global variable to hold the lock file descriptor
_scheduler_lock_fd = None


def start_scheduler():
    """
    Start APScheduler to run management commands on schedule.
    Uses file-based lock to ensure only one scheduler instance runs across multiple workers.
    Replaces cron jobs:
    - 1 12,18 * * * -> chat_messages
    - */5 * * * * -> chat_rooms (every 5 minutes)
    - 5 8 * * * -> vote
    - */5 * * * * -> count_citizens (every 5 minutes)
    - 2 * * * * -> update_site (every hour)
    """
    global _scheduler_lock_fd

    # Try to acquire exclusive lock on scheduler lock file
    lock_file_path = os.getenv("SCHEDULER_LOCK_FILE", os.path.join(tempfile.gettempdir(), 'wikikracja_scheduler.lock'))
    try:
        _scheduler_lock_fd = open(lock_file_path, 'w')
        if os.name != 'nt':
            import fcntl

            fcntl.flock(_scheduler_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            log.info(f"Acquired scheduler lock: {lock_file_path}")
    except IOError as e:
        log.info("Scheduler already running in another worker/process - skipping initialization " + str(e))
        return None

    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)

    # Chat messages - runs at 12, 18
    scheduler.add_job(run_chat_messages, trigger=CronTrigger(hour='12,18', minute=1), id='chat_messages', name='Send chat message emails', replace_existing=True)
    log.info("Scheduled job: chat_messages at 12, 18")

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

    starting_events = Event.objects.filter(is_active=True, start_date__gte=start_of_minute, start_date__lt=end_of_minute).order_by('start_date')

    if not starting_events.exists():
        return  # Silent return - no events starting this minute

    for event in starting_events:
        try:
            # Format detailed notification body (time, place, description)
            event_time = timezone.localtime(event.start_date).strftime('%H:%M')
            body_parts = [f"{_('Time')}: {event_time}"]

            if event.place:
                body_parts.append(f"{_('Place')}: {event.place}")

            if event.description:
                description = event.description.strip()
                if len(description) > 200:
                    description = description[:200] + "..."
                body_parts.append(f"{_('Description')}: {description}")

            body_text = " | ".join(body_parts)
            notify_event_starting(event, body=body_text)
        except Exception as e:
            log.error(f"Notification failed for event {event.id}: {e}")


def _run_command(command_name):
    """Generic command runner with error handling"""
    try:
        log.info(f"Running {command_name} command")
        call_command(command_name)
        log.info(f"{command_name} command completed")
    except Exception as e:
        log.error(f"Error running {command_name}: {e}", exc_info=True)


def run_chat_messages():
    """Execute chat_messages management command"""
    with _db_lock:
        _run_command('chat_messages')


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
