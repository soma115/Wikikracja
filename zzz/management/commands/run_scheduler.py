import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from zzz.scheduler import start_scheduler, stop_scheduler


class Command(BaseCommand):
    help = 'Run the Wikikracja APScheduler as a dedicated process.'

    def handle(self, *args, **options):
        call_command('update_site')
        scheduler = start_scheduler()
        if scheduler is None:
            raise CommandError('Scheduler did not start; enable SCHEDULER_ENABLED for run_scheduler.')

        self.stdout.write(self.style.SUCCESS('Wikikracja scheduler is running.'))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write('Stopping Wikikracja scheduler...')
        finally:
            stop_scheduler()
