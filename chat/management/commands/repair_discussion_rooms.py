from collections import defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ankiety.models import Survey
from board.models import Post
from chat.models import Room
from chat.signals import ensure_discussion_room_for_instance
from glosowania.models import Decyzja
from tasks.models import Task


class Command(BaseCommand):
    help = 'Create missing discussion rooms for documents, votes, surveys, and tasks.'

    model_map = {'board': Post, 'glosowania': Decyzja, 'ankiety': Survey, 'tasks': Task}

    def add_arguments(self, parser):
        parser.add_argument('--app', choices=tuple(self.model_map), help='Repair only one source app.')
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument('--dry-run', action='store_true', help='Only report objects that need a room.')
        modes.add_argument('--audit', action='store_true', help='Read-only audit of linked rooms and memberships.')
        modes.add_argument('--repair-source-data', action='store_true', help='Repair only unambiguous source links and add missing active members.')
        parser.add_argument('--confirm-reviewed-backup', action='store_true', help='Confirm the audit was reviewed and a backup exists before data repair.')

    def handle(self, *args, **options):
        models = {options['app']: self.model_map[options['app']]} if options['app'] else self.model_map
        if options['audit']:
            self._audit(models)
            return
        if options['repair_source_data']:
            if not options['confirm_reviewed_backup']:
                raise CommandError('--repair-source-data requires --confirm-reviewed-backup after reviewing the audit.')
            self._repair_source_data(models)
            return

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

    def _audit(self, models):
        active_user_ids = set(get_user_model().objects.filter(is_active=True).values_list('pk', flat=True))
        issue_count = 0
        objects_by_app = {}

        for app_label, model in models.items():
            objects = list(model.objects.select_related('chat_room').prefetch_related('chat_room__allowed').order_by('pk'))
            objects_by_app[app_label] = objects
            object_ids = {instance.pk for instance in objects}
            rooms = list(Room.objects.filter(source_app=app_label).prefetch_related('allowed').order_by('pk'))
            rooms_by_source_id = defaultdict(list)
            for room in rooms:
                rooms_by_source_id[room.source_object_id].append(room)

            for source_object_id, matching_rooms in rooms_by_source_id.items():
                if source_object_id is None:
                    issue_count += 1
                    self.stdout.write(f'{app_label}: source object #{source_object_id} has {len(matching_rooms)} linked chat room(s): {[room.pk for room in matching_rooms]}')
                if source_object_id not in object_ids:
                    issue_count += 1
                    self.stdout.write(f'{app_label}: room(s) {[room.pk for room in matching_rooms]} reference a missing source object #{source_object_id}')

                for room in matching_rooms:
                    issue_count += self._audit_membership(app_label, room, active_user_ids)

            for instance in objects:
                room = instance.chat_room
                if room is None:
                    issue_count += 1
                    self.stdout.write(f'{app_label} #{instance.pk}: missing chat-room relation; {len(rooms_by_source_id.get(instance.pk, []))} source room(s) found')
                    continue
                if room.source_app != app_label or room.source_object_id != instance.pk:
                    issue_count += 1
                    self.stdout.write(f'{app_label} #{instance.pk}: room #{room.pk} has source {room.source_app!r} #{room.source_object_id}; expected {app_label!r} #{instance.pk}')
                    issue_count += self._audit_membership(f'{app_label} #{instance.pk}', room, active_user_ids)

        room_keys = Room.objects.exclude(source_object_id__isnull=True).values_list('pk', 'source_app', 'source_object_id')
        for (app_label, source_object_id), room_ids in self._duplicate_source_room_keys(room_keys).items():
            issue_count += 1
            self.stdout.write(f'{app_label}: source object #{source_object_id} has {len(room_ids)} linked chat room(s): {room_ids}')

        for app_label, model in self.model_map.items():
            if app_label not in objects_by_app:
                objects_by_app[app_label] = model.objects.only('pk', 'chat_room_id').order_by('pk')
        for room_id, owners in self._duplicate_room_links(objects_by_app).items():
            issue_count += 1
            self.stdout.write(f'Room #{room_id} is linked to multiple source objects: {owners}')

        for room in Room.objects.direct_messages().prefetch_related('allowed'):
            if len(room.allowed.all()) != 2:
                issue_count += 1
                self.stdout.write(f'Unclassified private room #{room.pk}: expected exactly two members, found {len(room.allowed.all())}')

        unscoped_rooms = Room.objects.filter(source_app='', source_object_id__isnull=False)
        for room in unscoped_rooms:
            issue_count += 1
            self.stdout.write(f'Room #{room.pk} has source object #{room.source_object_id} but no source app')

        if issue_count:
            self.stdout.write(self.style.WARNING(f'Audit found {issue_count} issue(s); no data was changed.'))
        else:
            self.stdout.write(self.style.SUCCESS('Audit found no discussion-room inconsistencies; no data was changed.'))

    @staticmethod
    def _duplicate_source_room_keys(room_keys):
        rooms_by_source = defaultdict(list)
        for room_id, app_label, source_object_id in room_keys:
            if source_object_id is not None:
                rooms_by_source[app_label, source_object_id].append(room_id)
        return {source: room_ids for source, room_ids in rooms_by_source.items() if len(room_ids) > 1}

    @staticmethod
    def _duplicate_room_links(objects_by_app):
        owners_by_room = defaultdict(list)
        for app_label, objects in objects_by_app.items():
            for instance in objects:
                if instance.chat_room_id:
                    owners_by_room[instance.chat_room_id].append(f'{app_label} #{instance.pk}')
        return {room_id: owners for room_id, owners in owners_by_room.items() if len(owners) > 1}

    def _audit_membership(self, label, room, active_user_ids):
        member_ids = {user.pk for user in room.allowed.all()}
        missing = active_user_ids - member_ids
        inactive = member_ids - active_user_ids
        issues = 0
        if missing:
            issues += 1
            self.stdout.write(f'{label} room #{room.pk}: missing {len(missing)} active member(s)')
        if inactive:
            issues += 1
            self.stdout.write(f'{label} room #{room.pk}: has {len(inactive)} inactive member(s)')
        return issues

    def _repair_source_data(self, models):
        active_user_ids = set(get_user_model().objects.filter(is_active=True).values_list('pk', flat=True))
        repaired_links = 0
        repaired_metadata = 0
        added_memberships = 0
        conflicts = []

        for app_label, model in models.items():
            objects = list(model.objects.select_related('chat_room').order_by('pk'))
            rooms_by_source_id = defaultdict(list)
            for room in Room.objects.filter(source_app=app_label).order_by('pk'):
                rooms_by_source_id[room.source_object_id].append(room)

            for instance in objects:
                source_rooms = rooms_by_source_id.get(instance.pk, [])
                if len(source_rooms) > 1:
                    conflicts.append(f'{app_label} #{instance.pk}: duplicate source rooms {[room.pk for room in source_rooms]}')
                    continue

                room = instance.chat_room
                if room is None and source_rooms:
                    room = source_rooms[0]
                    model.objects.filter(pk=instance.pk, chat_room__isnull=True).update(chat_room_id=room.pk)
                    repaired_links += 1
                elif room is None:
                    conflicts.append(f'{app_label} #{instance.pk}: no source-tagged room exists; possible legacy title match requires manual review')
                    continue

                if room.source_app == app_label and room.source_object_id == instance.pk:
                    pass
                elif not room.source_app and room.source_object_id is None:
                    duplicate = Room.objects.filter(source_app=app_label, source_object_id=instance.pk).exclude(pk=room.pk).exists()
                    if duplicate:
                        conflicts.append(f'{app_label} #{instance.pk}: another room already claims source link #{room.pk}')
                        continue
                    updated = Room.objects.filter(pk=room.pk, source_app='', source_object_id__isnull=True).update(source_app=app_label, source_object_id=instance.pk)
                    if not updated:
                        conflicts.append(f'{app_label} #{instance.pk}: room #{room.pk} changed during repair')
                        continue
                    room.source_app = app_label
                    room.source_object_id = instance.pk
                    repaired_metadata += 1
                else:
                    conflicts.append(f'{app_label} #{instance.pk}: room #{room.pk} has conflicting source {room.source_app!r} #{room.source_object_id}')
                    continue

                member_ids = set(room.allowed.values_list('pk', flat=True))
                missing_user_ids = active_user_ids - member_ids
                if missing_user_ids:
                    Room.allowed.through.objects.bulk_create([Room.allowed.through(room_id=room.pk, user_id=user_id) for user_id in missing_user_ids], ignore_conflicts=True)
                    Room.apply_default_notification_preferences([room.pk], missing_user_ids)
                    added_memberships += len(missing_user_ids)

        if repaired_metadata:
            from core.services.feed import invalidate_feed_cache

            invalidate_feed_cache()
        self.stdout.write(self.style.SUCCESS(f'Repaired {repaired_links} room link(s), {repaired_metadata} source marker(s), and added {added_memberships} membership(s).'))
        for conflict in conflicts:
            self.stderr.write(self.style.WARNING(f'Skipped ambiguous record: {conflict}'))
        if conflicts:
            raise CommandError(f'{len(conflicts)} ambiguous record(s) need manual review; completed unambiguous repairs are safe to rerun.')
