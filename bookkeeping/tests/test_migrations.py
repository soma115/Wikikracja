from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ResourceListingMoveMigrationTest(TransactionTestCase):
    migrate_from = [('bookkeeping', '0033_transaction_updated_at'), ('obywatele', '0055_individual_resource_assignments')]
    migrate_to = [('bookkeeping', '0036_resourcelisting_is_closed'), ('obywatele', '0056_remove_resourceassignment_unique_resource_assignment_name_ci_and_more')]

    def setUp(self):
        super().setUp()
        self.assertTrue(connection.vendor == 'sqlite' and connection.creation.is_in_memory_db(connection.settings_dict['NAME']), 'Migration tests require an in-memory test database')
        self.original_targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        self.addCleanup(self.migrate, self.original_targets)
        self.migrate(self.migrate_from)

        User = self.apps.get_model(settings.AUTH_USER_MODEL)
        Uzytkownik = self.apps.get_model('obywatele', 'Uzytkownik')
        self.user = User.objects.create(username='resource-migration')
        self.profile = Uzytkownik.objects.create(uid_id=self.user.pk)
        ResourceAssignment = self.apps.get_model('obywatele', 'ResourceAssignment')
        self.assignment = ResourceAssignment.objects.create(profile_id=self.profile.pk, name='Rower', description='Do oddania', kind='give')
        self.original_values = {
            'id': self.assignment.pk,
            'profile_id': self.profile.pk,
            'name': self.assignment.name,
            'description': self.assignment.description,
            'kind': self.assignment.kind,
            'created_at': self.assignment.created_at,
            'updated_at': self.assignment.updated_at,
        }
        self.migrate(self.migrate_to)

    def applied_apps(self):
        executor = MigrationExecutor(connection)
        return executor.loader.project_state(list(executor.loader.applied_migrations)).apps

    def migrate(self, targets):
        MigrationExecutor(connection).migrate(targets)
        self.apps = self.applied_apps()

    def test_forward_move_preserves_listing_data_and_identity(self):
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        listing = ResourceListing.objects.get(pk=self.original_values['id'])

        self.assertEqual(
            {
                'id': listing.pk,
                'profile_id': listing.profile_id,
                'name': listing.name,
                'description': listing.description,
                'kind': listing.kind,
                'created_at': listing.created_at,
                'updated_at': listing.updated_at,
            },
            self.original_values,
        )
        self.assertFalse(listing.is_closed)
        with self.assertRaises(LookupError):
            self.apps.get_model('obywatele', 'ResourceAssignment')

    def test_reverse_move_restores_rows_written_after_moving(self):
        ResourceListing = self.apps.get_model('bookkeeping', 'ResourceListing')
        ResourceListing.objects.filter(pk=self.original_values['id']).update(name='Rower miejski')

        self.migrate(self.migrate_from)
        ResourceAssignment = self.apps.get_model('obywatele', 'ResourceAssignment')
        self.assertEqual(ResourceAssignment.objects.get(pk=self.original_values['id']).name, 'Rower miejski')

        self.migrate(self.migrate_to)
