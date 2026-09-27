from django.core.management.base import BaseCommand, CommandError

from ankiety.models import Survey
from board.models import Post
from chat.signals import ensure_discussion_room_for_instance
from glosowania.models import Decyzja
from tasks.models import Task


class Command(BaseCommand):
    help = 'Create missing discussion rooms for documents, votes, surveys, and tasks.'

    model_map = {'board': Post, 'glosowania': Decyzja, 'ankiety': Survey, 'tasks': Task}

    def add_arguments(self, parser):
        parser.add_argument('--app', choices=tuple(self.model_map), help='Repair only one source app.')
        parser.add_argument('--dry-run', action='store_true', help='Only report objects that need a room.')

    def handle(self, *args, **options):
        models = {options['app']: self.model_map[options['app']]} if options['app'] else self.model_map
        missing = 0
        repaired = 0
        failures = []

        for app_label, model in models.items():
            queryset = model.objects.filter(chat_room__isnull=True).order_by('pk')
            for instance in queryset.iterator():
                missing += 1
                if options['dry_run']:
                    self.stdout.write(f'{app_label} #{instance.pk}: {instance}')
                    continue
                try:
                    ensure_discussion_room_for_instance(instance)
                except Exception as exc:
                    failures.append(f'{app_label} #{instance.pk}: {exc}')
                    self.stderr.write(self.style.ERROR(f'Failed {app_label} #{instance.pk}: {exc}'))
                    continue
                repaired += 1
                self.stdout.write(f'Repaired {app_label} #{instance.pk}: {instance}')

        action = 'would repair' if options['dry_run'] else 'repaired'
        self.stdout.write(self.style.SUCCESS(f'{action} {missing} missing discussion room(s); {repaired} changed.'))
        if failures:
            raise CommandError(f'{len(failures)} room(s) could not be repaired.')
