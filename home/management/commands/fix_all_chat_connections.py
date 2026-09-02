import logging
import traceback
from datetime import datetime

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand
from django.db import DatabaseError, transaction

from chat.models import Room

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Unified command to fix chat room connections for tasks and votes.
    Combines functionality from:
    - update_chat_room_relations.py (votes + tasks)
    - fix_task_chat_connections.py (advanced task fixing)
    - backfill_task_chat_rooms.py (simple task backfill)

    SAFETY FEATURES:
    - Dry run mode by default
    - Transaction safety
    - Comprehensive error handling
    - Debug output
    - Statistics and validation
    """

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', default=True, help='Show what would be fixed without making changes (default: enabled)')
        parser.add_argument('--no-dry-run', action='store_false', dest='dry_run', help='Apply changes to database')
        parser.add_argument('--force', action='store_true', help='Force re-linking even if already linked')
        parser.add_argument('--debug', action='store_true', help='Enable detailed debug output')
        parser.add_argument('--tasks-only', action='store_true', help='Process only tasks (skip votes)')
        parser.add_argument('--votes-only', action='store_true', help='Process only votes (skip tasks)')
        parser.add_argument('--batch-size', type=int, default=100, help='Process items in batches to avoid memory issues (default: 100)')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stats = {
            'tasks': {'total': 0, 'already_linked': 0, 'newly_linked': 0, 'fixed_broken_links': 0, 'missing_rooms': 0, 'multiple_rooms': 0, 'errors': 0},
            'votes': {'total': 0, 'already_linked': 0, 'newly_linked': 0, 'missing_rooms': 0, 'errors': 0},
        }
        self.debug_enabled = False
        self.dry_run = True  # Default to safe mode

    def debug(self, message):
        """Print debug message if debug mode is enabled"""
        if self.debug_enabled:
            timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            self.stdout.write(self.style.HTTP_INFO(f"[DEBUG {timestamp}] {message}"))

    def safe_execute(self, operation_name, operation_func, *args, **kwargs):
        """Safely execute database operation with error handling"""
        try:
            return operation_func(*args, **kwargs)
        except DatabaseError as e:
            self.stats['tasks' if 'task' in operation_name.lower() else 'votes']['errors'] += 1
            self.stdout.write(self.style.ERROR(f"Database error in {operation_name}: {e}"))
            if self.debug_enabled:
                self.stdout.write(traceback.format_exc())
            return None
        except Exception as e:
            self.stats['tasks' if 'task' in operation_name.lower() else 'votes']['errors'] += 1
            self.stdout.write(self.style.ERROR(f"Unexpected error in {operation_name}: {e}"))
            if self.debug_enabled:
                self.stdout.write(traceback.format_exc())
            return None

    def process_votes(self):
        """Process vote (Decyzja) chat room connections."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("PROCESSING VOTES (DECYZJE)")
        self.stdout.write("=" * 60)

        Decyzja = django_apps.get_model('glosowania', 'decyzja')
        decisions = Decyzja.objects.all()
        self.stats['votes']['total'] = decisions.count()
        self.debug(f"Found {decisions.count()} decisions to process")

        batch_size = self.batch_size
        for i in range(0, decisions.count(), batch_size):
            batch = decisions[i : i + batch_size]
            self.debug(f"Processing vote batch {i // batch_size + 1}: {batch.count()} items")

            for decyzja in batch:
                self.safe_execute(f"vote_{decyzja.pk}", self._process_single_vote, decyzja)

    def _process_single_vote(self, decyzja):
        """Process a single vote's chat room connection using source_app metadata."""
        # Skip if already linked and not forcing
        if decyzja.chat_room_id and not self.force:
            self.stats['votes']['already_linked'] += 1
            self.debug(f"Vote #{decyzja.pk} already linked to room #{decyzja.chat_room_id}")
            return

        expected_title = decyzja.get_chat_room_title()

        # Prefer rooms tagged with source metadata; fallback to title lookups for legacy data.
        room = Room.objects.filter(source_app='glosowania', source_object_id=decyzja.pk).first()
        if not room:
            old_title = f"Vote #{decyzja.pk}: {decyzja.title[:20]}"
            for title in (expected_title, old_title):
                room = Room.objects.filter(title=title).first()
                if room:
                    self.debug(f"Found vote #{decyzja.pk} room by title: '{title}'")
                    break

        if room:
            self._link_decyzja_to_room(decyzja, room, expected_title)
        else:
            self.stats['votes']['missing_rooms'] += 1
            if not self.dry_run:
                self.stdout.write(self.style.WARNING(f"  No room found for vote #{decyzja.pk}: '{decyzja.title[:20]}'"))

    def _link_decyzja_to_room(self, decyzja, room, expected_title):
        """Link a decyzja to a room and fix title/source metadata if needed."""
        title_changed = room.title != expected_title
        source_missing = room.source_app != 'glosowania' or room.source_object_id != decyzja.pk
        if not title_changed and not source_missing and decyzja.chat_room_id == room.id:
            self.stats['votes']['already_linked'] += 1
            return

        if self.dry_run:
            self.stdout.write(f"  [DRY RUN] Would link vote #{decyzja.pk} -> room '{room.title}'")
            self.stats['votes']['newly_linked'] += 1
            return

        update_fields = []
        if title_changed:
            room.title = expected_title
            update_fields.append('title')
        if source_missing:
            room.source_app = 'glosowania'
            room.source_object_id = decyzja.pk
            update_fields.extend(['source_app', 'source_object_id'])
        if update_fields:
            room.save(update_fields=update_fields)

        with transaction.atomic():
            type(decyzja).objects.filter(pk=decyzja.pk).update(chat_room=room)

        self.stdout.write(self.style.SUCCESS(f"  Linked vote #{decyzja.pk} -> room '{room.title}'"))
        self.stats['votes']['newly_linked'] += 1

    def process_tasks(self):
        """Process task chat room connections."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("PROCESSING TASKS")
        self.stdout.write("=" * 60)

        Task = django_apps.get_model('tasks', 'task')
        tasks = Task.objects.all()
        self.stats['tasks']['total'] = tasks.count()
        self.debug(f"Found {tasks.count()} tasks to process")

        batch_size = self.batch_size
        for i in range(0, tasks.count(), batch_size):
            batch = tasks[i : i + batch_size]
            self.debug(f"Processing task batch {i // batch_size + 1}: {batch.count()} items")

            for task in batch:
                self.safe_execute(f"task_{task.pk}", self._process_single_task, task)

    def _process_single_task(self, task):
        """Process a single task's chat room connection using source_app metadata."""
        # Skip if already linked and not forcing
        if task.chat_room_id and not self.force:
            self.stats['tasks']['already_linked'] += 1
            self.debug(f"Task #{task.pk} already linked to room #{task.chat_room_id}")
            return

        expected_title = task.get_chat_room_title()

        # Prefer rooms tagged with source metadata; fallback to title lookups for legacy data.
        room = Room.objects.filter(source_app='tasks', source_object_id=task.pk).first()
        if not room:
            expected_pattern = f"Task #{task.id}:"
            matching_rooms = Room.objects.filter(title__startswith=expected_pattern, protected=True)
            if matching_rooms.count() > 1:
                self.stats['tasks']['multiple_rooms'] += 1
                self.stdout.write(self.style.ERROR(f"  Multiple rooms found for task #{task.id}: {list(matching_rooms.values_list('title', flat=True))}"))
                return
            room = matching_rooms.first()
            if room:
                self.debug(f"Found task #{task.pk} room by title pattern")

        if not room:
            room = Room.objects.filter(title=expected_title).first()
            if room:
                self.debug(f"Found task #{task.pk} room by exact title")

        if room:
            self._link_task_to_room(task, room, expected_title)
        else:
            self.stats['tasks']['missing_rooms'] += 1
            if not self.dry_run:
                self.stdout.write(self.style.WARNING(f"  No room found for task #{task.id}: '{task.title}'"))

    def _link_task_to_room(self, task, room, expected_title):
        """Link a task to a room and fix title/source metadata if needed."""
        title_changed = room.title != expected_title
        source_missing = room.source_app != 'tasks' or room.source_object_id != task.pk
        if not title_changed and not source_missing and task.chat_room_id == room.id:
            self.stats['tasks']['already_linked'] += 1
            return

        if self.dry_run:
            self.stdout.write(f"  [DRY RUN] Would link task #{task.id} -> room '{expected_title}'")
            if title_changed:
                self.stats['tasks']['fixed_broken_links'] += 1
            else:
                self.stats['tasks']['newly_linked'] += 1
            return

        update_fields = []
        if title_changed:
            room.title = expected_title
            update_fields.append('title')
        if source_missing:
            room.source_app = 'tasks'
            room.source_object_id = task.pk
            update_fields.extend(['source_app', 'source_object_id'])
        if update_fields:
            room.save(update_fields=update_fields)

        with transaction.atomic():
            type(task).objects.filter(pk=task.pk).update(chat_room=room)

        if title_changed:
            self.stats['tasks']['fixed_broken_links'] += 1
            self.stdout.write(self.style.SUCCESS(f"  Fixed task #{task.id}: updated room title to '{expected_title}'"))
        else:
            self.stats['tasks']['newly_linked'] += 1
            self.stdout.write(f"  Linked task #{task.id} -> room '{expected_title}'")

    def validate_environment(self):
        """Validate that required models and relationships exist"""
        self.stdout.write("Validating environment...")

        try:
            # Test basic model access
            room_count = Room.objects.count()
            self.stdout.write(f"  Rooms: {room_count}")

            source_apps = [('tasks', 'task'), ('glosowania', 'decyzja')]
            for app_label, model_name in source_apps:
                try:
                    Model = django_apps.get_model(app_label, model_name)
                    count = Model.objects.count()
                    self.stdout.write(f"  {model_name.capitalize()}s: {count}")
                    sample = Model.objects.first()
                    if sample:
                        has_chat_room = hasattr(sample, 'chat_room')
                        self.stdout.write(f"  {model_name}.chat_room field exists: {has_chat_room}")
                except LookupError as e:
                    self.stdout.write(self.style.WARNING(f"  {app_label}.{model_name} not available: {e}"))

            return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Environment validation failed: {e}"))
            if self.debug_enabled:
                self.stdout.write(traceback.format_exc())
            return False

    def print_summary(self):
        """Print comprehensive summary of operations"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("OPERATION SUMMARY")
        self.stdout.write("=" * 60)

        if not self.votes_only:
            self.stdout.write("\nTASKS:")
            self.stdout.write(f"  Total processed: {self.stats['tasks']['total']}")
            self.stdout.write(f"  Already linked: {self.stats['tasks']['already_linked']}")
            self.stdout.write(f"  Newly linked: {self.stats['tasks']['newly_linked']}")
            self.stdout.write(f"  Fixed broken links: {self.stats['tasks']['fixed_broken_links']}")
            self.stdout.write(f"  No room found: {self.stats['tasks']['missing_rooms']}")
            self.stdout.write(f"  Multiple rooms found: {self.stats['tasks']['multiple_rooms']}")
            self.stdout.write(f"  Errors: {self.stats['tasks']['errors']}")

        if not self.tasks_only:
            self.stdout.write("\nVOTES:")
            self.stdout.write(f"  Total processed: {self.stats['votes']['total']}")
            self.stdout.write(f"  Already linked: {self.stats['votes']['already_linked']}")
            self.stdout.write(f"  Newly linked: {self.stats['votes']['newly_linked']}")
            self.stdout.write(f"  No room found: {self.stats['votes']['missing_rooms']}")
            self.stdout.write(f"  Errors: {self.stats['votes']['errors']}")

        total_processed = self.stats['tasks']['total'] + self.stats['votes']['total']
        total_new_links = self.stats['tasks']['newly_linked'] + self.stats['votes']['newly_linked']
        total_fixed = self.stats['tasks']['fixed_broken_links']
        total_errors = self.stats['tasks']['errors'] + self.stats['votes']['errors']

        self.stdout.write("\nOVERALL:")
        self.stdout.write(f"  Total items processed: {total_processed}")
        self.stdout.write(f"  New links created: {total_new_links}")
        self.stdout.write(f"  Broken links fixed: {total_fixed}")
        self.stdout.write(f"  Total errors: {total_errors}")

        if self.dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN MODE - No changes were made. Use --no-dry-run to apply changes."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nOperations completed! New links: {total_new_links}, Fixed: {total_fixed}, Errors: {total_errors}"))

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("Chat Room Connection Fixer"))
        self.stdout.write("=" * 60)

        # Parse options
        self.dry_run = options['dry_run']
        self.force = options['force']
        self.debug_enabled = options['debug']
        self.tasks_only = options['tasks_only']
        self.votes_only = options['votes_only']
        self.batch_size = options['batch_size']

        # Validate options
        if self.tasks_only and self.votes_only:
            self.stdout.write(self.style.ERROR("Cannot specify both --tasks-only and --votes-only"))
            return

        if self.dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No changes will be made. Use --no-dry-run to apply changes."))

        if self.debug_enabled:
            self.stdout.write(self.style.HTTP_INFO("DEBUG MODE ENABLED"))

        # Validate environment
        if not self.validate_environment():
            return

        # Process items
        try:
            if not self.votes_only:
                self.process_tasks()

            if not self.tasks_only:
                self.process_votes()

        except KeyboardInterrupt:
            self.stdout.write(self.style.ERROR("\nOperation interrupted by user"))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Fatal error: {e}"))
            if self.debug_enabled:
                self.stdout.write(traceback.format_exc())
            return

        # Print summary
        self.print_summary()
