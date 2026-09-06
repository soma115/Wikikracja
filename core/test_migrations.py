import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from textwrap import dedent

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone


class ReadStatusMigrationTest(TransactionTestCase):
    before = [('core', None), ('home', '0014_alter_feeditem_content_type_and_more')]
    after = [('core', '0001_initial')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, original_targets)
        self.migrate(self.before)
        self.ContentType = self.apps.get_model('contenttypes', 'ContentType')
        self.Permission = self.apps.get_model('auth', 'Permission')
        User = self.apps.get_model(settings.AUTH_USER_MODEL)
        self.users = [User.objects.create(username=f'readstatus-migration-{i}') for i in range(2)]
        self.group = self.apps.get_model('auth', 'Group').objects.create(name='readstatus-migration')
        self.content_type, _ = self.ContentType.objects.get_or_create(app_label='home', model='readstatus')
        permissions = [
            self.Permission.objects.get_or_create(content_type=self.content_type, codename=f'{action}_readstatus', defaults={'name': f'Can {action} read status'})[0]
            for action in ('add', 'change', 'delete', 'view')
        ]
        self.users[0].user_permissions.add(*permissions)
        self.group.permissions.add(*permissions)
        self.users[1].groups.add(self.group)
        ReadStatus = self.apps.get_model('home', 'ReadStatus')
        for user in self.users:
            for content_type, _ in ReadStatus._meta.get_field('content_type').choices:
                ReadStatus.objects.create(user=user, content_type=content_type, object_id=42)
        ReadStatus.objects.update(read_at=timezone.now() - timedelta(days=7))
        self.original_rows = self.rows(ReadStatus)
        self.original_schema = self.schema()
        self.original_permissions = self.permissions()
        self.assertEqual(len(self.original_permissions), 4)
        self.original_assignments = self.assignments()
        constraints = self.original_schema[1]
        self.assertEqual(constraints['readstatus_user_content_idx']['columns'], ['user_id', 'content_type'])
        self.assertTrue(constraints['readstatus_user_content_idx']['index'])
        self.assertTrue(any(c['unique'] and c['columns'] == ['user_id', 'content_type', 'object_id'] for c in constraints.values()))
        self.assertTrue(any(c['primary_key'] and c['columns'] == ['id'] for c in constraints.values()))
        self.assertTrue(any(c['foreign_key'] and c['columns'] == ['user_id'] for c in constraints.values()))

    def applied_apps(self):
        executor = MigrationExecutor(connection)
        return executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        ContentType.objects.clear_cache()
        self.apps = self.applied_apps()

    def rows(self, model):
        return list(model.objects.order_by('pk').values('id', 'read_at', 'object_id', 'user_id', 'content_type'))

    def schema(self):
        with connection.cursor() as cursor:
            return sorted(connection.introspection.table_names(cursor)), connection.introspection.get_constraints(cursor, 'home_readstatus')

    def permissions(self):
        return list(self.Permission.objects.filter(content_type__model='readstatus', content_type__app_label__in=['home', 'core']).order_by('pk').values_list('pk', 'codename', 'name', 'content_type_id'))

    def assignments(self):
        return (
            [list(user.user_permissions.order_by('pk').values_list('pk', flat=True)) for user in self.users],
            list(self.group.permissions.order_by('pk').values_list('pk', flat=True)),
            [list(user.groups.order_by('pk').values_list('pk', flat=True)) for user in self.users],
        )

    def assert_preserved(self, app_label, rows):
        ReadStatus = self.apps.get_model(app_label, 'ReadStatus')
        other_label = 'home' if app_label == 'core' else 'core'
        self.assertEqual(ReadStatus._meta.db_table, 'home_readstatus')
        self.assertEqual(self.rows(ReadStatus), rows)
        self.assertEqual(self.schema(), self.original_schema)
        self.assertNotIn('core_readstatus', connection.introspection.table_names())
        self.assertEqual(self.apps.get_model('home', 'FeedItem')._meta.db_table, 'home_feeditem')
        with self.assertRaises(LookupError):
            self.apps.get_model(other_label, 'ReadStatus')
        self.assertEqual(list(self.ContentType.objects.filter(model='readstatus', app_label__in=['home', 'core']).values_list('pk', 'app_label')), [(self.content_type.pk, app_label)])
        self.assertEqual(self.permissions(), self.original_permissions)
        self.assertEqual(self.assignments(), self.original_assignments)
        for historical_user in self.users:
            user = get_user_model().objects.get(pk=historical_user.pk)
            for _, codename, _, _ in self.original_permissions:
                self.assertTrue(user.has_perm(f'{app_label}.{codename}'))
                self.assertFalse(user.has_perm(f'{other_label}.{codename}'))
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReadStatus.objects.create(user_id=rows[0]['user_id'], content_type=rows[0]['content_type'], object_id=rows[0]['object_id'])
        self.assertEqual(self.rows(ReadStatus), rows)

    def test_upgrade_preserves_rows_schema_and_permissions_after_post_migrate(self):
        self.assert_preserved('home', self.original_rows)
        for _ in range(2):
            call_command('migrate', database=connection.alias, fake_initial=True, interactive=False, verbosity=0)
            self.apps = self.applied_apps()
            self.assert_preserved('core', self.original_rows)

    def test_reverse_preserves_new_writes_permissions_and_reapplies(self):
        self.migrate(self.after)
        self.assert_preserved('core', self.original_rows)
        ReadStatus = self.apps.get_model('core', 'ReadStatus')
        ReadStatus.objects.create(user_id=self.users[1].pk, content_type='post', object_id=99)
        ReadStatus.objects.filter(pk=self.original_rows[0]['id']).update(read_at=timezone.now())
        rows = self.rows(ReadStatus)
        self.migrate(self.before)
        self.assert_preserved('home', rows)
        self.migrate(self.after)
        self.assert_preserved('core', rows)

    def test_management_commands_support_split_upgrade_and_rollback(self):
        for app_label, migration_name in (('home', '0015_remove_readstatus_state'), ('core', '0001_initial'), ('core', 'zero'), ('home', '0014_alter_feeditem_content_type_and_more')):
            with self.subTest(app_label=app_label, migration=migration_name):
                call_command('migrate', app_label, migration_name, database=connection.alias, interactive=False, verbosity=0)
                self.apps = self.applied_apps()
                owner = 'core' if migration_name == '0001_initial' else 'home'
                self.assertEqual(list(self.ContentType.objects.filter(model='readstatus', app_label__in=['home', 'core']).values_list('pk', 'app_label')), [(self.content_type.pk, owner)])
                self.assertEqual(self.permissions(), self.original_permissions)
                self.assertEqual(self.assignments(), self.original_assignments)
                if migration_name in ('0001_initial', '0014_alter_feeditem_content_type_and_more'):
                    self.assert_preserved(owner, self.original_rows)
        call_command('migrate', database=connection.alias, interactive=False, verbosity=0)
        self.apps = self.applied_apps()
        self.assert_preserved('core', self.original_rows)

    def test_management_command_rolls_back_core_dependency_with_home(self):
        self.migrate(self.after)
        call_command('migrate', 'home', '0014_alter_feeditem_content_type_and_more', database=connection.alias, interactive=False, verbosity=0)
        self.apps = self.applied_apps()
        self.assert_preserved('home', self.original_rows)
        call_command('migrate', database=connection.alias, interactive=False, verbosity=0)
        self.apps = self.applied_apps()
        self.assert_preserved('core', self.original_rows)

    def assert_conflict_preserves_records(self, reverse):
        if reverse:
            self.migrate(self.after)
        source, target = ('core', 'home') if reverse else ('home', 'core')
        collision = self.ContentType.objects.create(app_label=target, model='readstatus')
        self.addCleanup(collision.delete)
        for _, codename, name, _ in self.original_permissions:
            permission = self.Permission.objects.create(content_type=collision, codename=codename, name=name)
            self.users[0].user_permissions.add(permission)
            self.group.permissions.add(permission)
        content_types = list(self.ContentType.objects.filter(model='readstatus').order_by('pk').values())
        permissions, assignments = self.permissions(), self.assignments()
        with self.assertRaisesRegex(RuntimeError, f'from {source} to {target}: both content types exist'):
            self.migrate(self.before if reverse else self.after)
        self.assertEqual(list(self.ContentType.objects.filter(model='readstatus').order_by('pk').values()), content_types)
        self.assertEqual(self.permissions(), permissions)
        self.assertEqual(self.assignments(), assignments)
        self.assertEqual(self.rows(self.apps.get_model(source, 'ReadStatus')), self.original_rows)
        self.assertEqual(self.schema(), self.original_schema)

    def test_forward_conflict_keeps_both_content_types_and_permissions(self):
        self.assert_conflict_preserves_records(reverse=False)

    def test_reverse_conflict_keeps_both_content_types_and_permissions(self):
        self.assert_conflict_preserves_records(reverse=True)


class ReadStatusFreshInstallTest(SimpleTestCase):
    def test_fresh_install_uses_legacy_table_and_core_permissions(self):
        code = dedent("""
            from unittest.mock import patch

            with patch('dotenv.load_dotenv', return_value=False), patch('pathlib.Path.mkdir'):
                import django
                from django.conf import settings

                settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
                django.setup()

            from django.contrib.contenttypes.models import ContentType
            from django.contrib.auth.models import Permission
            from django.core.management import call_command
            from django.db import connection
            from core.models import ReadStatus
            from home.models import FeedItem

            assert connection.settings_dict['NAME'] == ':memory:'
            call_command('migrate', interactive=False, verbosity=0, fake_initial=True)
            tables = connection.introspection.table_names()
            assert ReadStatus._meta.db_table == 'home_readstatus'
            assert 'home_readstatus' in tables and 'core_readstatus' not in tables
            assert ReadStatus.objects.count() == 0
            assert FeedItem._meta.app_label == 'home' and FeedItem._meta.db_table in tables
            content_type = ContentType.objects.get(app_label='core', model='readstatus')
            assert not ContentType.objects.filter(app_label='home', model='readstatus').exists()
            assert set(Permission.objects.filter(content_type=content_type).values_list('codename', flat=True)) == {
                'add_readstatus', 'change_readstatus', 'delete_readstatus', 'view_readstatus',
            }
            assert Permission.objects.filter(content_type__model='readstatus', content_type__app_label__in=['home', 'core']).count() == 4
            """)
        env = os.environ | {
            'DJANGO_SETTINGS_MODULE': 'zzz.test_settings',
            'SCHEDULER_ENABLED': 'false',
            'RUN_MAIN': 'false',
            'DEBUG': 'false',
            'SECRET_KEY': 'isolated-readstatus-migration-test-key',
            'EMAIL_BACKEND': 'django.core.mail.backends.locmem.EmailBackend',
            'FIREBASE_CERT_PATH': '',
            'GOOGLE_APPLICATION_CREDENTIALS': '',
            'FIREBASE_CERT_JSON': '',
            'FIREBASE_CERT_BASE64': '',
            'LOGGING_DESTINATION': 'console',
            'LOGGING_JSON': '',
            'PYTHONDONTWRITEBYTECODE': '1',
        }
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, f'Fresh install subprocess failed:\n{result.stdout}\n{result.stderr}')
