"""
Django AppConfig for the 'zzz' application.

This module initializes the APScheduler background task scheduler when Django starts.
The scheduler replaces traditional cron jobs with in-process scheduled tasks that run
management commands at specific intervals.

Scheduled Tasks:
    - send_email_digest: Runs daily at 08:00 (sends an aggregated activity digest email)
    - vote: Runs daily at 08:05 (processes voting, creates 1-to-1 chat rooms)
    - count_citizens: Runs every 10 minutes (manages user reputation and activation)
    - update_site: Runs every hour (syncs Site model with environment variables)

The scheduler only starts when SCHEDULER_ENABLED=true is set in the environment
or when RUN_MAIN=true (Django development server reload detection).
"""

import logging
import os

from django.apps import AppConfig

log = logging.getLogger(__name__)


class SchedulerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zzz'

    def ready(self):
        """
        Called when Django starts.
        This is where we start the APScheduler for background tasks.
        """
        from django.db.backends.signals import connection_created

        def set_sqlite_wal(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                cursor = connection.cursor()
                cursor.execute('PRAGMA journal_mode=WAL;')

        connection_created.connect(set_sqlite_wal)

        # Only start scheduler in the main process, not in Django management commands
        # and not during migrations or other special operations
        if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('SCHEDULER_ENABLED') == 'true':
            try:
                from zzz.scheduler import start_scheduler

                start_scheduler()
                log.info("APScheduler initialized from SchedulerConfig.ready()")
            except Exception as e:
                log.error(f"Failed to start APScheduler: {e}", exc_info=True)
