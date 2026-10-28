from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase


class DropRetiredElibraryBookMigrationTest(TransactionTestCase):
    migration = ('obywatele', '0058_drop_retired_elibrary_book')

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.addCleanup(self.drop_legacy_table)
        MigrationRecorder(connection).record_unapplied(*self.migration)
        self.addCleanup(self.restore_migrations)

    def drop_legacy_table(self):
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS "elibrary_book"')

    def restore_migrations(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_drops_legacy_book_table_and_preserves_uploader_account(self):
        user = get_user_model().objects.create_user(username='legacy-elibrary-uploader')
        user_table = connection.ops.quote_name(get_user_model()._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE TABLE "elibrary_book" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "uploader_id" bigint NULL REFERENCES {user_table} ("id") DEFERRABLE INITIALLY DEFERRED)')
            cursor.execute('INSERT INTO "elibrary_book" ("uploader_id") VALUES (%s)', [user.pk])

        MigrationExecutor(connection).migrate([self.migration])

        self.assertNotIn('elibrary_book', connection.introspection.table_names())
        self.assertTrue(get_user_model().objects.filter(pk=user.pk).exists())

    def test_succeeds_when_legacy_book_table_is_absent(self):
        self.assertNotIn('elibrary_book', connection.introspection.table_names())

        MigrationExecutor(connection).migrate([self.migration])

        self.assertNotIn('elibrary_book', connection.introspection.table_names())
