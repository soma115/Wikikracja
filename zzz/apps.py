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

The scheduler only starts in the dedicated ``run_scheduler`` management
command or in the child process of the Django development server.
"""

import logging
import sys

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

        def configure_sqlite(sender, connection, **kwargs):
            if connection.vendor != 'sqlite':
                return
            timeout = float(connection.settings_dict.get('OPTIONS', {}).get('timeout', 60))
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode=WAL')
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.execute(f'PRAGMA busy_timeout={int(timeout * 1000)}')
            log.info('SQLite connection configured with WAL, foreign_keys=ON, busy_timeout_ms=%s', int(timeout * 1000))

        connection_created.connect(configure_sqlite, dispatch_uid='zzz.sqlite.configure', weak=False)

        # Start only in the dedicated scheduler command or the runserver child.
        # Management commands such as migrate and update_site must stay side-effect free.
        try:
            from zzz.scheduler import should_start_scheduler, start_scheduler

            command = sys.argv[1] if len(sys.argv) > 1 else ''
            if should_start_scheduler() and command != 'run_scheduler':
                if start_scheduler() is not None:
                    log.info("APScheduler initialized from SchedulerConfig.ready()")
        except Exception as e:
            log.error(f"Failed to initialize APScheduler: {e}", exc_info=True)
