"""Testy widoków CRUD aplikacji bookkeeping.

Pokrywają kontrakt, którego pilnuje deduplikacja widoków/szablonów:
toolbar w kontekście list, redirecty na listy po create/update/delete,
ochrona usuwania przez ProtectedDeleteView i własność transakcji.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import SUCCESS, get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.translation import gettext as _

from bookkeeping.models import Category, Partner, Transaction
from bookkeeping.views import AssetDeleteView
from obywatele.models import Country
from resources.models import LEGACY_FINANCIAL_ASSET_SOURCE, LEGACY_PHYSICAL_ASSET_SOURCE, LEGACY_RESOURCE_LISTING_SOURCE, Entity, LegacyEntityReference

User = get_user_model()

LIST_URL_NAMES = (
    'bookkeeping:transaction_list',
    'bookkeeping:partner_list',
    'bookkeeping:category_list',
    'bookkeeping:asset_list',
    'bookkeeping:physical_asset_list',
    'bookkeeping:resource_list',
    'bookkeeping:report_list',
)
CTA_LIST_URL_NAMES = ('bookkeeping:transaction_list', 'bookkeeping:partner_list', 'bookkeeping:category_list', 'bookkeeping:asset_list', 'bookkeeping:physical_asset_list', 'bookkeeping:resource_list')


class BookkeepingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='bk', email='bk@example.com', password='x')
        cls.asset = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, code='TST', name='Test Asset', symbol='T')
        cls.asset.legacy_asset_pk = 900000
        LegacyEntityReference.objects.create(entity=cls.asset, source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=cls.asset.legacy_asset_pk)
        cls.entity = cls.asset
        cls.category = Category.objects.create(name='Test Cat')
        cls.partner = Partner.objects.create(name='Test Partner')
        cls.physical_asset = Entity.objects.create(entity_type=Entity.Type.PHYSICAL_ASSET, name='Community garden', country=Country.objects.get(code='PL'), city='Warsaw')
        cls.physical_asset.legacy_physical_pk = 910000
        LegacyEntityReference.objects.create(entity=cls.physical_asset, source_model=LEGACY_PHYSICAL_ASSET_SOURCE, source_pk=cls.physical_asset.legacy_physical_pk)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _transaction(self, author=None, payment_received_date=None, note=''):
        data = {'type': 'I', 'entity': self.asset, 'category': self.category, 'partner': self.partner, 'amount': 10, 'author': author or self.user, 'note': note}
        if payment_received_date is not None:
            data['payment_received_date'] = payment_received_date
        return Transaction.objects.create(**data)

    def test_list_views_render_with_menu_and_cta(self):
        for url_name in LIST_URL_NAMES:
            res = self.client.get(reverse(url_name))
            self.assertEqual(res.status_code, 200, url_name)
        for url_name in CTA_LIST_URL_NAMES:
            res = self.client.get(reverse(url_name))
            self.assertIn('cta_url', res.context, url_name)

    def test_views_require_login(self):
        client = Client()
        for url_name in LIST_URL_NAMES:
            self.assertEqual(client.get(reverse(url_name)).status_code, 302, url_name)

    def test_shared_edit_views_require_login(self):
        anonymous_client = Client()
        transaction = self._transaction()
        cases = (
            ('bookkeeping:asset_update', self.asset.legacy_asset_pk),
            ('bookkeeping:category_update', self.category),
            ('bookkeeping:partner_update', self.partner),
            ('bookkeeping:physical_asset_update', self.physical_asset.legacy_physical_pk),
            ('bookkeeping:transaction_update', transaction),
        )

        for url_name, instance in cases:
            pk = instance if isinstance(instance, int) else instance.pk
            url = reverse(url_name, args=[pk])
            with self.subTest(url_name=url_name, method='GET'):
                self.assertEqual(anonymous_client.get(url).status_code, 302)
            with self.subTest(url_name=url_name, method='POST'):
                self.assertEqual(anonymous_client.post(url, {}).status_code, 302)

    def test_asset_create_and_update(self):
        res = self.client.post(reverse('bookkeeping:asset_create'), {'code': 'PLN2', 'name': 'Złoty', 'symbol': 'zł', 'decimal_places': 2})
        self.assertEqual(res.status_code, 302)
        entity = Entity.objects.get(entity_type=Entity.Type.FINANCIAL_ASSET, code='PLN2')
        list_response = self.client.get(reverse('bookkeeping:asset_list'))
        self.assertContains(list_response, f'data-detail-url="{reverse("bookkeeping:asset_entity_detail", args=[entity.pk])}"')

        res = self.client.post(
            reverse('bookkeeping:asset_entity_update', args=[entity.pk]), {'code': 'PLN2', 'name': 'Polski złoty', 'symbol': 'zł', 'decimal_places': 2, 'is_currency': 'on', 'is_default': 'on'}
        )
        self.assertEqual(res.status_code, 302)
        entity.refresh_from_db()
        self.assertEqual(entity.name, 'Polski złoty')
        self.assertTrue(entity.is_default)

    def test_legacy_asset_url_updates_the_mapped_entity(self):
        response = self.client.post(reverse('bookkeeping:asset_update', args=[self.asset.legacy_asset_pk]), {'code': 'TST', 'name': 'Legacy URL edit', 'symbol': 'T', 'decimal_places': 2, 'is_currency': 'on'})

        self.assertRedirects(response, reverse('bookkeeping:asset_list'))
        self.asset.refresh_from_db()
        self.assertEqual(self.asset.name, 'Legacy URL edit')
        self.assertTrue(LegacyEntityReference.objects.filter(entity=self.asset, source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=self.asset.legacy_asset_pk).exists())

    def test_deleting_unused_financial_entity(self):
        self.client.post(reverse('bookkeeping:asset_create'), {'code': 'DEL', 'name': 'Delete unit', 'symbol': 'D', 'decimal_places': 2})
        entity = Entity.objects.get(entity_type=Entity.Type.FINANCIAL_ASSET, code='DEL')

        response = self.client.post(reverse('bookkeeping:asset_entity_delete', args=[entity.pk]))

        self.assertRedirects(response, reverse('bookkeeping:asset_list'))
        self.assertFalse(Entity.objects.filter(pk=entity.pk).exists())

    def test_physical_asset_create_and_update(self):
        data = {'name': 'Community hall', 'country': 'PL', 'city': 'Gdańsk', 'street': 'Długa', 'house_number': '4', 'apartment_number': '2', 'assignment_scope': Entity.AssignmentScope.COMMUNITY}
        response = self.client.post(reverse('bookkeeping:physical_asset_create'), data)

        self.assertRedirects(response, reverse('bookkeeping:physical_asset_list'))
        entity = Entity.objects.get(entity_type=Entity.Type.PHYSICAL_ASSET, name='Community hall')
        self.assertEqual(entity.country.code, 'PL')
        self.assertEqual(entity.city, 'Gdańsk')
        self.assertEqual(entity.author, self.user)
        self.assertEqual(entity.assignment_scope, Entity.AssignmentScope.COMMUNITY)
        list_response = self.client.get(reverse('bookkeeping:physical_asset_list'))
        self.assertContains(list_response, f'data-detail-url="{reverse("bookkeeping:physical_asset_entity_detail", args=[entity.pk])}"')

        response = self.client.post(reverse('bookkeeping:physical_asset_entity_update', args=[entity.pk]), {**data, 'name': 'Community venue'})

        self.assertRedirects(response, reverse('bookkeeping:physical_asset_list'))
        entity.refresh_from_db()
        self.assertEqual(entity.name, 'Community venue')
        self.assertEqual(entity.apartment_number, '2')
        self.assertEqual(entity.author, self.user)
        self.assertEqual(entity.assignment_scope, Entity.AssignmentScope.COMMUNITY)

    def test_legacy_physical_asset_url_updates_the_mapped_entity(self):
        data = {'name': 'Garden tools', 'country': 'PL', 'city': 'Warsaw', 'street': 'Old Street', 'house_number': '8', 'apartment_number': '1'}
        response = self.client.post(reverse('bookkeeping:physical_asset_update', args=[self.physical_asset.legacy_physical_pk]), {**data, 'assignment_scope': Entity.AssignmentScope.COMMUNITY})

        self.assertRedirects(response, reverse('bookkeeping:physical_asset_list'))
        self.physical_asset.refresh_from_db()
        self.assertEqual(self.physical_asset.name, 'Garden tools')
        self.assertEqual(self.physical_asset.street, 'Old Street')
        self.assertTrue(LegacyEntityReference.objects.filter(entity=self.physical_asset, source_model=LEGACY_PHYSICAL_ASSET_SOURCE, source_pk=self.physical_asset.legacy_physical_pk).exists())

    def test_physical_asset_creator_can_assign_another_active_member(self):
        assigned_user = User.objects.create_user(username='asset-assignee')
        data = {'name': 'Assigned community tool', 'country': 'PL', 'city': 'Gdańsk', 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': assigned_user.uzytkownik.pk}

        response = self.client.post(reverse('bookkeeping:physical_asset_create'), data)

        self.assertRedirects(response, reverse('bookkeeping:physical_asset_list'))
        entity = Entity.objects.get(name='Assigned community tool', entity_type=Entity.Type.PHYSICAL_ASSET)
        self.assertEqual(entity.author, self.user)
        self.assertEqual(entity.assigned_member, assigned_user.uzytkownik)
        self.assertEqual(entity.assignment_scope, Entity.AssignmentScope.MEMBER)

    def test_only_entity_author_can_change_its_assignment(self):
        create_data = {'name': 'Author-controlled asset', 'country': 'PL', 'city': 'Gdańsk', 'assignment_scope': Entity.AssignmentScope.COMMUNITY}
        self.client.post(reverse('bookkeeping:physical_asset_create'), create_data)
        entity = Entity.objects.get(name='Author-controlled asset', entity_type=Entity.Type.PHYSICAL_ASSET)
        other_user = User.objects.create_user(username='asset-non-author')
        assigned_user = User.objects.create_user(username='asset-non-author-assignee')
        other_client = Client()
        other_client.force_login(other_user)

        response = other_client.post(
            reverse('bookkeeping:physical_asset_entity_update', args=[entity.pk]), {**create_data, 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': assigned_user.uzytkownik.pk}
        )

        self.assertRedirects(response, reverse('bookkeeping:physical_asset_list'))
        entity.refresh_from_db()
        self.assertEqual(entity.assignment_scope, Entity.AssignmentScope.COMMUNITY)
        self.assertIsNone(entity.assigned_member_id)

    def test_physical_asset_requires_country_and_city(self):
        response = self.client.post(reverse('bookkeeping:physical_asset_create'), {'name': 'Incomplete asset', 'country': '', 'city': ''})

        self.assertEqual(response.status_code, 200)
        self.assertIn('country', response.context['form'].errors)
        self.assertIn('city', response.context['form'].errors)
        self.assertFalse(Entity.objects.filter(entity_type=Entity.Type.PHYSICAL_ASSET, name='Incomplete asset').exists())

    def test_physical_asset_requires_an_explicit_assignment(self):
        response = self.client.post(reverse('bookkeeping:physical_asset_create'), {'name': 'Unassigned asset', 'country': 'PL', 'city': 'Gdańsk'})

        self.assertEqual(response.status_code, 200)
        self.assertIn('assignment_scope', response.context['form'].errors)
        self.assertFalse(Entity.objects.filter(entity_type=Entity.Type.PHYSICAL_ASSET, name='Unassigned asset').exists())

    def test_edit_forms_render_prefilled_data(self):
        transaction = self._transaction()
        cases = (
            ('bookkeeping:asset_update', self.asset.legacy_asset_pk, self.entity, 'form'),
            ('bookkeeping:category_update', self.category.pk, self.category, 'form'),
            ('bookkeeping:partner_update', self.partner.pk, self.partner, 'form'),
            ('bookkeeping:physical_asset_update', self.physical_asset.legacy_physical_pk, self.physical_asset, 'form'),
            ('bookkeeping:transaction_update', transaction.pk, transaction, 'transaction_form'),
        )

        for url_name, object_pk, expected_instance, context_name in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name, args=[object_pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context[context_name].instance, expected_instance)

    def test_category_and_partner_forms_use_explicit_field_allowlists(self):
        cases = (
            ('bookkeeping:category_create', None, ('name',)),
            ('bookkeeping:category_update', self.category.pk, ('name',)),
            ('bookkeeping:partner_create', None, ('name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'street', 'house_number', 'apartment_number', 'notes')),
            ('bookkeeping:partner_update', self.partner.pk, ('name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'street', 'house_number', 'apartment_number', 'notes')),
            ('bookkeeping:physical_asset_create', None, ('name', 'country', 'city', 'street', 'house_number', 'apartment_number', 'assignment_scope', 'assigned_member')),
            ('bookkeeping:physical_asset_update', self.physical_asset.legacy_physical_pk, ('name', 'country', 'city', 'street', 'house_number', 'apartment_number')),
        )

        for url_name, pk, expected_fields in cases:
            with self.subTest(url_name=url_name):
                url = reverse(url_name, args=[pk]) if pk else reverse(url_name)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(tuple(response.context['form'].fields), expected_fields)

    def test_category_and_partner_update_saves_changes(self):
        response = self.client.post(reverse('bookkeeping:category_update', args=[self.category.pk]), {'name': 'Updated category'})
        self.assertEqual([message.level for message in get_messages(response.wsgi_request)], [SUCCESS])
        self.assertRedirects(response, reverse('bookkeeping:category_list'))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, 'Updated category')

        response = self.client.post(reverse('bookkeeping:partner_update', args=[self.partner.pk]), {'name': 'Updated partner'})
        self.assertRedirects(response, reverse('bookkeeping:partner_list'))
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.name, 'Updated partner')

    def test_partner_address_fields_save_without_rewriting_legacy_address(self):
        self.partner.address = 'Old full address'
        self.partner.save(update_fields=['address'])

        response = self.client.post(
            reverse('bookkeeping:partner_update', args=[self.partner.pk]),
            {'name': self.partner.name, 'address': self.partner.address, 'city': 'Gdańsk', 'country': 'Poland', 'street': 'Długa', 'house_number': '12A', 'apartment_number': '4'},
        )

        self.assertRedirects(response, reverse('bookkeeping:partner_list'))
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.address, 'Old full address')
        self.assertEqual(self.partner.street, 'Długa')
        self.assertEqual(self.partner.house_number, '12A')
        self.assertEqual(self.partner.apartment_number, '4')

    def test_edit_forms_rerender_errors_without_saving(self):
        transaction = self._transaction()
        cases = (
            ('bookkeeping:asset_update', self.asset, {'code': '', 'name': 'Test Asset', 'symbol': 'T', 'decimal_places': 2}, 'form'),
            ('bookkeeping:category_update', self.category, {'name': ''}, 'form'),
            ('bookkeeping:partner_update', self.partner, {'name': ''}, 'form'),
            ('bookkeeping:physical_asset_update', self.physical_asset, {'name': '', 'country': 'PL', 'city': 'Warsaw'}, 'form'),
            (
                'bookkeeping:transaction_update',
                transaction,
                {'type': 'I', 'entity': self.entity.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '-1', 'payment_received_date': '2026-01-01', 'note': ''},
                'transaction_form',
            ),
        )

        for url_name, instance, data, context_name in cases:
            with self.subTest(url_name=url_name):
                pk = getattr(instance, 'legacy_asset_pk', getattr(instance, 'legacy_physical_pk', instance.pk))
                response = self.client.post(reverse(url_name, args=[pk]), data)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context[context_name].errors)

    def test_category_and_partner_create_redirect_to_list(self):
        res = self.client.post(reverse('bookkeeping:category_create'), {'name': 'Nowa'})
        self.assertRedirects(res, reverse('bookkeeping:category_list'))
        self.assertTrue(Category.objects.filter(name='Nowa').exists())

        res = self.client.post(reverse('bookkeeping:partner_create'), {'name': 'Nowy Partner'})
        self.assertRedirects(res, reverse('bookkeeping:partner_list'))
        self.assertTrue(Partner.objects.filter(name='Nowy Partner').exists())

    def test_protected_delete_blocks_object_with_transactions(self):
        self._transaction()

        res = self.client.post(reverse('bookkeeping:asset_delete', args=[self.asset.legacy_asset_pk]))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Entity.objects.filter(pk=self.asset.pk).exists())

        res = self.client.get(reverse('bookkeeping:asset_delete', args=[self.asset.legacy_asset_pk]))
        self.assertTrue(res.context['has_dependencies'])
        self.assertEqual(res.context['error'], str(AssetDeleteView.protect_message))
        self.assertEqual(list(res.context['related_transactions']), list(Transaction.objects.all()))
        self.assertEqual(res.context['cancel_url'], reverse('bookkeeping:asset_list'))

    def test_protected_delete_removes_unused_object(self):
        res = self.client.post(reverse('bookkeeping:category_delete', args=[self.category.pk]))
        self.assertRedirects(res, reverse('bookkeeping:category_list'))
        self.assertFalse(Category.objects.filter(pk=self.category.pk).exists())

    def test_transaction_detail_navigation_preserves_search_context(self):
        first = self._transaction(payment_received_date=date(2026, 1, 1), note='navigation')
        middle = self._transaction(payment_received_date=date(2026, 1, 2), note='navigation')
        last = self._transaction(payment_received_date=date(2026, 1, 3), note='navigation')

        response = self.client.get(reverse('bookkeeping:transaction_detail', args=[middle.pk]), {'q': 'navigation'})

        self.assertEqual(response.context['previous_url'], f"{reverse('bookkeeping:transaction_detail', args=[last.pk])}?q=navigation")
        self.assertEqual(response.context['next_url'], f"{reverse('bookkeeping:transaction_detail', args=[first.pk])}?q=navigation")

    def test_transaction_detail_links_related_objects(self):
        transaction = self._transaction()

        response = self.client.get(reverse('bookkeeping:transaction_detail', args=[transaction.pk]))

        self.assertContains(response, f'href="{reverse("bookkeeping:partner_detail", args=[self.partner.pk])}"')
        self.assertContains(response, f'href="{reverse("bookkeeping:category_detail", args=[self.category.pk])}"')
        self.assertContains(response, f'href="{reverse("bookkeeping:asset_entity_detail", args=[self.asset.pk])}"')

    def test_asset_detail_does_not_repeat_code_as_badge(self):
        response = self.client.get(reverse('bookkeeping:asset_detail', args=[self.asset.legacy_asset_pk]))

        self.assertNotContains(response, 'tw-badge tw-badge-secondary')

    def test_physical_asset_detail_shows_location_and_active_member_apartment_number(self):
        self.physical_asset.street = 'Długa'
        self.physical_asset.house_number = '4'
        self.physical_asset.apartment_number = '2'
        self.physical_asset.save()

        response = self.client.get(reverse('bookkeeping:physical_asset_detail', args=[self.physical_asset.legacy_physical_pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Warsaw')
        self.assertContains(response, 'Długa')
        self.assertContains(response, '2')

        inactive_user = User.objects.create_user(username='inactive-member', is_active=False)
        self.client.force_login(inactive_user)
        response = self.client.get(reverse('bookkeeping:physical_asset_detail', args=[self.physical_asset.legacy_physical_pk]))
        self.assertEqual(response.status_code, 302)

    def test_partner_detail_shows_apartment_only_to_active_members(self):
        self.partner.apartment_number = '8'
        self.partner.save(update_fields=['apartment_number'])

        response = self.client.get(reverse('bookkeeping:partner_detail', args=[self.partner.pk]))
        self.assertContains(response, _('Apartment number'))
        self.assertContains(response, '>8</dd>')

        inactive_user = User.objects.create_user(username='inactive-partner-viewer', is_active=False)
        self.client.force_login(inactive_user)
        response = self.client.get(reverse('bookkeeping:partner_detail', args=[self.partner.pk]))
        self.assertEqual(response.status_code, 302)

    def test_partner_detail_keeps_missing_navigation_directions_visible(self):
        first = self.partner
        middle = Partner.objects.create(name='Middle Partner')
        last = Partner.objects.create(name='Last Partner')

        response = self.client.get(reverse('bookkeeping:partner_detail', args=[first.pk]))
        self.assertIsNone(response.context['prev_partner'])
        self.assertEqual(response.context['next_partner'].pk, middle.pk)
        self.assertContains(response, 'fa-chevron-left')
        self.assertContains(response, 'fa-chevron-right')
        self.assertContains(response, 'class="tw-detail-nav-btn tw-disabled"', count=1)

        response = self.client.get(reverse('bookkeeping:partner_detail', args=[last.pk]))
        self.assertEqual(response.context['prev_partner'].pk, middle.pk)
        self.assertIsNone(response.context['next_partner'])
        self.assertContains(response, 'fa-chevron-left')
        self.assertContains(response, 'fa-chevron-right')
        self.assertContains(response, 'class="tw-detail-nav-btn tw-disabled"', count=1)

    def test_transaction_update_and_delete_only_by_author(self):
        other = User.objects.create_user(username='other', email='o@example.com', password='x')
        txn = self._transaction(author=other)

        res = self.client.post(reverse('bookkeeping:transaction_delete', args=[txn.pk]))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Transaction.objects.filter(pk=txn.pk).exists())

        update_url = reverse('bookkeeping:transaction_update', args=[txn.pk])
        res = self.client.get(update_url)
        self.assertEqual(res.status_code, 403)
        res = self.client.post(
            update_url, {'type': 'O', 'entity': self.entity.pk, 'category': self.category.pk, 'partner': self.partner.pk, 'amount': '99', 'payment_received_date': '2026-01-02', 'note': 'Unauthorized'}
        )
        self.assertEqual(res.status_code, 403)
        txn.refresh_from_db()
        self.assertEqual(txn.amount, 10)
        self.assertEqual(txn.note, '')

    def test_unowned_transaction_can_be_claimed_once(self):
        transaction = self._transaction()
        transaction.author = None
        transaction.save(update_fields=['author'])

        response = self.client.post(reverse('bookkeeping:transaction_claim', args=[transaction.pk]))

        self.assertRedirects(response, reverse('bookkeeping:transaction_detail', args=[transaction.pk]))
        transaction.refresh_from_db()
        self.assertEqual(transaction.author, self.user)

        other = User.objects.create_user(username='claim-other', email='claim-other@example.com', password='x')
        self.client.force_login(other)
        self.client.post(reverse('bookkeeping:transaction_claim', args=[transaction.pk]))
        transaction.refresh_from_db()
        self.assertEqual(transaction.author, self.user)

    def test_transaction_create_sets_author_and_redirects(self):
        res = self.client.post(
            reverse('bookkeeping:transaction_create'),
            {'type': 'I', 'entity': self.entity.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '10.5', 'payment_received_date': '2026-01-01', 'note': ''},
        )
        txn = Transaction.objects.get()
        self.assertRedirects(res, reverse('bookkeeping:transaction_detail', args=[txn.pk]))
        self.assertEqual(txn.author, self.user)
        self.assertEqual(txn.entity.code, self.asset.code)

    def test_new_transaction_emits_push_event(self):
        with patch('core.notifications._dispatch_notification') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('bookkeeping:transaction_create'),
                    {'type': 'I', 'entity': self.entity.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '10.5', 'payment_received_date': '2026-01-01', 'note': ''},
                )

        self.assertEqual(response.status_code, 302)
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.kwargs['push_event'], 'transaction.created')

    def test_transaction_update_emits_push_event(self):
        transaction = self._transaction()
        with patch('core.notifications._dispatch_notification') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('bookkeeping:transaction_update', args=[transaction.pk]),
                    {'type': 'O', 'entity': self.entity.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'Updated'},
                )

        self.assertEqual(response.status_code, 302)
        self.assertEqual([message.level for message in get_messages(response.wsgi_request)], [SUCCESS])
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.kwargs['push_event'], 'transaction.updated')

    def test_transaction_update_respects_next_param(self):
        txn = self._transaction()
        next_url = reverse('bookkeeping:transaction_list')
        res = self.client.post(
            reverse('bookkeeping:transaction_update', args=[txn.pk]) + f'?next={next_url}',
            {'type': 'O', 'entity': self.entity.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'x'},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, next_url)
        txn.refresh_from_db()
        self.assertEqual(txn.type, 'O')

    def test_transaction_update_rejects_external_next_param(self):
        txn = self._transaction()
        res = self.client.post(
            reverse('bookkeeping:transaction_update', args=[txn.pk]) + '?next=https://evil.example/',
            {'type': 'O', 'entity': self.entity.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'x'},
        )
        self.assertEqual(res.status_code, 302)
        self.assertNotEqual(res.url, 'https://evil.example/')


class ResourceListingViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='resource-owner', password='secret', is_active=True)
        self.other_user = User.objects.create_user(username='resource-other', password='secret', is_active=True)
        self.viewer = User.objects.create_user(username='resource-viewer', password='secret', is_active=True)
        self.owner.uzytkownik.city = 'Gdansk'
        self.owner.uzytkownik.save(update_fields=['city'])
        self.client.force_login(self.owner)
        self.list_url = reverse('bookkeeping:resource_list')
        self.manage_url = reverse('bookkeeping:resource_manage')

    def _legacy_resource(self, profile, *, name, kind, description='', is_closed=False):
        entity = Entity.objects.create(entity_type=Entity.Type.RESOURCE, resource_kind=kind, name=name, description=description, is_closed=is_closed, assigned_member=profile)
        LegacyEntityReference.objects.create(entity=entity, source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=entity.pk)
        return entity

    def test_views_require_login(self):
        client = Client()

        for url in (self.list_url, self.manage_url, reverse('bookkeeping:resource_search')):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 302)

        self.assertEqual(client.post(reverse('bookkeeping:resource_create'), {}).status_code, 302)

    def test_create_and_edit_preserve_listing_owner(self):
        member_assignment = {'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': self.owner.uzytkownik.pk}
        response = self.client.post(reverse('bookkeeping:resource_create'), {'kind': 'give', 'name': 'Rower', 'description': 'Do oddania', **member_assignment})

        self.assertRedirects(response, self.manage_url)
        entity = Entity.objects.get(entity_type=Entity.Type.RESOURCE, name='Rower')
        self.assertEqual((entity.author, entity.assigned_member, entity.resource_kind, entity.name, entity.description), (self.owner, self.owner.uzytkownik, 'give', 'Rower', 'Do oddania'))
        self.assertFalse(LegacyEntityReference.objects.filter(entity=entity, source_model=LEGACY_RESOURCE_LISTING_SOURCE).exists())

        other_entity = Entity.objects.create(entity_type=Entity.Type.RESOURCE, author=self.other_user, assigned_member=self.other_user.uzytkownik, name='Other bike', resource_kind=Entity.ResourceKind.GIVE)
        response = self.client.post(reverse('bookkeeping:resource_entity_update', args=[entity.pk]), {'kind': 'sale', 'name': 'Rower miejski', 'description': 'Sprawny', **member_assignment})

        self.assertRedirects(response, self.manage_url)
        entity.refresh_from_db()
        self.assertEqual((entity.author, entity.assigned_member, entity.resource_kind, entity.name, entity.description), (self.owner, self.owner.uzytkownik, 'sale', 'Rower miejski', 'Sprawny'))
        self.assertTrue(Entity.objects.filter(pk=other_entity.pk).exists())

    def test_legacy_resource_url_updates_the_mapped_entity(self):
        entity = self._legacy_resource(self.owner.uzytkownik, name='Legacy drill', kind=Entity.ResourceKind.BORROW)

        response = self.client.post(
            reverse('bookkeeping:resource_update', args=[entity.pk]),
            {'kind': 'sale', 'name': 'Legacy drill', 'description': 'Available', 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': self.owner.uzytkownik.pk},
        )

        self.assertRedirects(response, self.manage_url)
        entity.refresh_from_db()
        self.assertEqual((entity.resource_kind, entity.description), ('sale', 'Available'))
        self.assertIsNone(entity.author_id)

    def test_resource_author_can_assign_to_another_member(self):
        response = self.client.post(
            reverse('bookkeeping:resource_create'),
            {'kind': 'give', 'name': 'Shared bicycle', 'description': 'Ready to collect', 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': self.other_user.uzytkownik.pk},
        )

        self.assertRedirects(response, self.manage_url)
        entity = Entity.objects.get(entity_type=Entity.Type.RESOURCE, name='Shared bicycle')
        self.assertEqual((entity.author, entity.assigned_member), (self.owner, self.other_user.uzytkownik))
        self.assertFalse(LegacyEntityReference.objects.filter(entity=entity, source_model=LEGACY_RESOURCE_LISTING_SOURCE).exists())

        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse('bookkeeping:resource_entity_update', args=[entity.pk]),
            {'kind': 'give', 'name': 'Shared bicycle', 'description': 'Updated description', 'assignment_scope': Entity.AssignmentScope.COMMUNITY},
        )

        self.assertRedirects(response, self.manage_url)
        entity.refresh_from_db()
        self.assertEqual(entity.author, self.owner)
        self.assertEqual(entity.assigned_member, self.other_user.uzytkownik)
        self.assertFalse(entity.is_community_owned)
        self.assertEqual(entity.description, 'Updated description')

    def test_resource_author_can_assign_to_the_community(self):
        response = self.client.post(
            reverse('bookkeeping:resource_create'),
            {'kind': 'borrow', 'name': 'Community drill', 'description': 'Available to everyone', 'assignment_scope': Entity.AssignmentScope.COMMUNITY, 'assigned_member': ''},
        )

        self.assertRedirects(response, self.manage_url)
        entity = Entity.objects.get(entity_type=Entity.Type.RESOURCE, name='Community drill')
        self.assertEqual(entity.author, self.owner)
        self.assertIsNone(entity.assigned_member_id)
        self.assertTrue(entity.is_community_owned)
        self.assertContains(self.client.get(self.list_url, {'q': 'Community drill'}), str(Entity.AssignmentScope.COMMUNITY.label))

    def test_legacy_resource_transferred_to_community_survives_profile_deletion(self):
        entity = self._legacy_resource(self.owner.uzytkownik, name='Shared legacy drill', kind=Entity.ResourceKind.BORROW)
        reference = LegacyEntityReference.objects.get(source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=entity.pk)

        response = self.client.post(
            reverse('bookkeeping:resource_update', args=[entity.pk]),
            {'kind': 'borrow', 'name': 'Shared legacy drill', 'description': 'Community property', 'assignment_scope': Entity.AssignmentScope.COMMUNITY, 'assigned_member': ''},
        )

        self.assertRedirects(response, self.manage_url)
        self.assertTrue(LegacyEntityReference.objects.filter(pk=reference.pk).exists())
        entity.refresh_from_db()
        self.assertTrue(entity.is_community_owned)
        self.assertIsNone(entity.author_id)

        self.owner.delete()
        entity.refresh_from_db()
        self.assertTrue(LegacyEntityReference.objects.filter(pk=reference.pk).exists())
        self.assertTrue(entity.is_community_owned)
        self.assertIsNone(entity.author_id)

        self.client.force_login(self.other_user)
        response = self.client.get(self.manage_url)
        self.assertEqual([item.pk for item in response.context['active_listings']], [entity.pk])
        response = self.client.post(
            reverse('bookkeeping:resource_update', args=[entity.pk]),
            {'kind': 'borrow', 'name': 'Shared legacy drill', 'description': 'Assigned to a member', 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': self.other_user.uzytkownik.pk},
        )
        self.assertRedirects(response, self.manage_url)
        entity.refresh_from_db()
        self.assertFalse(entity.is_community_owned)
        self.assertEqual(entity.assigned_member_id, self.other_user.uzytkownik.pk)
        self.assertIsNone(entity.author_id)

    def test_listing_names_remain_unique_per_owner_and_kind(self):
        listing = self._legacy_resource(self.owner.uzytkownik, name='Rower', kind=Entity.ResourceKind.GIVE)
        self._legacy_resource(self.owner.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.GIVE)
        self._legacy_resource(self.owner.uzytkownik, name='Rower', kind=Entity.ResourceKind.SALE)

        response = self.client.post(
            reverse('bookkeeping:resource_update', args=[listing.pk]),
            {'kind': 'give', 'name': ' WIERTARKA ', 'description': '', 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': self.owner.uzytkownik.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['resource_form'].errors)
        self.assertEqual(listing.name, 'Rower')

    def test_only_owner_can_edit_or_delete_listing(self):
        listing = self._legacy_resource(self.other_user.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.BORROW)

        self.assertEqual(self.client.get(reverse('bookkeeping:resource_update', args=[listing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('bookkeeping:resource_delete', args=[listing.pk])).status_code, 404)
        self.assertTrue(Entity.objects.filter(pk=listing.pk).exists())

    def test_owner_can_delete_listing(self):
        self.client.post(
            reverse('bookkeeping:resource_create'), {'kind': 'borrow', 'name': 'Wiertarka', 'description': '', 'assignment_scope': Entity.AssignmentScope.MEMBER, 'assigned_member': self.owner.uzytkownik.pk}
        )
        entity = Entity.objects.get(entity_type=Entity.Type.RESOURCE, assigned_member=self.owner.uzytkownik, name='Wiertarka')

        response = self.client.post(reverse('bookkeeping:resource_entity_delete', args=[entity.pk]))

        self.assertRedirects(response, self.manage_url)
        self.assertFalse(Entity.objects.filter(pk=entity.pk).exists())

    def test_deleting_profile_removes_its_legacy_entity_mirror(self):
        entity = self._legacy_resource(self.owner.uzytkownik, name='Profile drill', kind=Entity.ResourceKind.GIVE)

        self.owner.uzytkownik.delete()

        self.assertFalse(Entity.objects.filter(pk=entity.pk).exists())
        self.assertFalse(LegacyEntityReference.objects.filter(source_model=LEGACY_RESOURCE_LISTING_SOURCE, source_pk=entity.pk).exists())

    def test_owner_can_close_and_restore_listing(self):
        listing = self._legacy_resource(self.owner.uzytkownik, name='Rower', kind=Entity.ResourceKind.GIVE)
        toggle_url = reverse('bookkeeping:resource_toggle_closed', args=[listing.pk])

        response = self.client.post(toggle_url, {'closed': '1'})

        self.assertRedirects(response, self.manage_url)
        listing.refresh_from_db()
        self.assertTrue(listing.is_closed)
        reference = LegacyEntityReference.objects.get(source_model='bookkeeping.ResourceListing', source_pk=listing.pk)
        entity = reference.entity
        self.assertTrue(entity.is_closed)
        self.assertIsNone(entity.author_id)
        response = self.client.get(self.list_url, {'q': 'Rower'})
        self.assertFalse(response.context['resource_listings'])
        response = self.client.get(self.manage_url)
        self.assertEqual([item.pk for item in response.context['closed_listings']], [entity.pk])

        response = self.client.post(toggle_url, {'closed': '0'})

        self.assertRedirects(response, self.manage_url)
        listing.refresh_from_db()
        self.assertFalse(listing.is_closed)

    def test_only_owner_can_close_listing(self):
        listing = self._legacy_resource(self.other_user.uzytkownik, name='Rower', kind=Entity.ResourceKind.GIVE)

        response = self.client.post(reverse('bookkeeping:resource_toggle_closed', args=[listing.pk]), {'closed': '1'})

        self.assertEqual(response.status_code, 404)
        listing.refresh_from_db()
        self.assertFalse(listing.is_closed)

    def test_resource_catalog_filters_and_splits_offers_and_needs(self):
        self._legacy_resource(self.owner.uzytkownik, name='Rower', description='Do odebrania', kind=Entity.ResourceKind.GIVE)
        self._legacy_resource(self.other_user.uzytkownik, name='Rower', description='Szukam roweru', kind=Entity.ResourceKind.NEED)
        self._legacy_resource(self.owner.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.BORROW)
        self.client.force_login(self.viewer)

        response = self.client.get(self.list_url, {'q': 'Rower'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['offer_listings']), 1)
        self.assertEqual(len(response.context['need_listings']), 1)
        self.assertContains(response, 'Do odebrania')
        self.assertContains(response, 'Szukam roweru')
        self.assertContains(response, 'data-resource-search-url')
        self.assertNotContains(response, 'Wiertarka')

        response = self.client.get(self.list_url, {'kind': 'give', 'city': 'Gdansk'})
        self.assertEqual(len(response.context['offer_listings']), 1)
        self.assertEqual(len(response.context['need_listings']), 0)

    def test_common_resource_search_filters_entity_types_and_keeps_addresses_private(self):
        country = Country.objects.get(code='PL')
        physical_asset = Entity.objects.create(
            entity_type=Entity.Type.PHYSICAL_ASSET,
            name='Community greenhouse',
            description='Shared food garden',
            author=self.owner,
            is_community_owned=True,
            country=country,
            city='Gdansk',
            street='Secret Alley',
            house_number='42',
        )
        financial_asset = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, name='Community credit', code='CMCR', symbol='C')
        resource = Entity.objects.create(
            entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Community tools', description='Tools for the garden', author=self.owner, assigned_member=self.owner.uzytkownik
        )

        response = self.client.get(self.list_url, {'entity_type': 'all', 'q': 'Community'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual({entity.pk for entity in response.context['entity_results']}, {physical_asset.pk, financial_asset.pk, resource.pk})
        self.assertContains(response, 'Gdansk')
        self.assertNotContains(response, 'Secret Alley')

        response = self.client.get(self.list_url, {'entity_type': 'physical_asset', 'country': 'Poland', 'city': 'gdan', 'assignment': 'community'})
        self.assertEqual([entity.pk for entity in response.context['entity_results']], [physical_asset.pk])

    def test_common_search_limits_closed_resources_to_people_who_can_manage_them(self):
        own_closed = Entity.objects.create(
            entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='My archived resource', author=self.owner, assigned_member=self.owner.uzytkownik, is_closed=True
        )
        Entity.objects.create(
            entity_type=Entity.Type.RESOURCE, resource_kind=Entity.ResourceKind.GIVE, name='Other archived resource', author=self.other_user, assigned_member=self.other_user.uzytkownik, is_closed=True
        )

        owner_response = self.client.get(self.list_url, {'status': 'closed'})
        self.assertEqual([entity.pk for entity in owner_response.context['resource_listings']], [own_closed.pk])
        self.assertContains(owner_response, 'My archived resource')
        self.assertNotContains(owner_response, 'Other archived resource')

        self.client.force_login(self.viewer)
        viewer_response = self.client.get(self.list_url, {'entity_type': 'all', 'status': 'all'})
        self.assertFalse(viewer_response.context['resource_listings'])
        self.assertNotContains(viewer_response, 'My archived resource')
        self.assertNotContains(viewer_response, 'Other archived resource')

    def test_profile_link_can_filter_resource_catalog_to_that_owner(self):
        self._legacy_resource(self.owner.uzytkownik, name='Rower', kind=Entity.ResourceKind.GIVE)
        self._legacy_resource(self.other_user.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.GIVE)

        response = self.client.get(self.list_url, {'profile': self.owner.uzytkownik.pk})

        self.assertEqual([item.name for item in response.context['resource_listings']], ['Rower'])
        self.assertContains(response, f'name="profile" value="{self.owner.uzytkownik.pk}"')

    def test_invalid_profile_filters_return_empty_results_without_error(self):
        self._legacy_resource(self.owner.uzytkownik, name='Rower', kind=Entity.ResourceKind.GIVE)

        for profile_id in (chr(178), '9' * 20, '9' * 5000):
            with self.subTest(profile_id=profile_id[:20]):
                response = self.client.get(self.list_url, {'profile': profile_id})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['resource_listings'])

    def test_pagination_does_not_report_items_on_other_pages_as_missing(self):
        for index in range(24):
            self._legacy_resource(self.owner.uzytkownik, name=f'Offer {index:02d}', kind=Entity.ResourceKind.BORROW)
        self._legacy_resource(self.other_user.uzytkownik, name='Need one', kind=Entity.ResourceKind.NEED)

        first_page = self.client.get(self.list_url)
        self.assertEqual((first_page.context['offer_count'], first_page.context['need_count']), (24, 1))
        self.assertNotContains(first_page, 'class="tw-alert tw-alert-info md:tw-col-span-2 lg:tw-col-span-3"')

        second_page = self.client.get(self.list_url, {'page': 2})
        self.assertEqual((second_page.context['offer_count'], second_page.context['need_count']), (24, 1))
        self.assertNotContains(second_page, 'class="tw-alert tw-alert-info md:tw-col-span-2 lg:tw-col-span-3"')
        self.assertContains(second_page, 'Need one')

    def test_city_only_filter_includes_people_without_any_listings(self):
        self.other_user.uzytkownik.city = 'Krakow'
        self.other_user.uzytkownik.save(update_fields=['city'])

        response = self.client.get(self.list_url, {'city': 'Krakow'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([profile.pk for profile in response.context['location_profiles']], [self.other_user.uzytkownik.pk])
        self.assertFalse(response.context['resource_listings'])

    def test_bookkeeping_stepper_counts_listings_of_active_profiles(self):
        self._legacy_resource(self.owner.uzytkownik, name='Rower', kind=Entity.ResourceKind.GIVE)
        self._legacy_resource(self.other_user.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.BORROW)
        self._legacy_resource(self.owner.uzytkownik, name='Closed listing', kind=Entity.ResourceKind.GIVE, is_closed=True)
        inactive_user = User.objects.create_user(username='resource-inactive', password='secret', is_active=False)
        self._legacy_resource(inactive_user.uzytkownik, name='Inactive listing', kind=Entity.ResourceKind.GIVE)

        response = self.client.get(self.list_url)

        self.assertContains(response, 'class="tw-stepper-step-count">2</span>')

    def test_resource_search_respects_selected_kind(self):
        self._legacy_resource(self.owner.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.GIVE)

        response = self.client.get(reverse('bookkeeping:resource_search'), {'q': 'Wiert', 'kind': 'need'})

        self.assertEqual(response.json()['items'], [])

    def test_resource_search_does_not_suggest_resources_for_other_entity_types(self):
        self._legacy_resource(self.owner.uzytkownik, name='Wiertarka', kind=Entity.ResourceKind.GIVE)

        response = self.client.get(reverse('bookkeeping:resource_search'), {'q': 'Wiert', 'entity_type': 'physical_asset'})

        self.assertEqual(response.json()['items'], [])

    def test_resource_descriptions_are_escaped_and_urls_clickable(self):
        self._legacy_resource(self.owner.uzytkownik, name='Rower', description='<script>alert(1)</script> https://example.com', kind=Entity.ResourceKind.GIVE)

        response = self.client.get(self.list_url, {'q': 'Rower'})

        self.assertContains(response, 'href="https://example.com"')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
