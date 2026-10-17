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

from bookkeeping.models import Asset, Category, Partner, ResourceListing, Transaction
from bookkeeping.views import AssetDeleteView

User = get_user_model()

LIST_URL_NAMES = ('bookkeeping:transaction_list', 'bookkeeping:partner_list', 'bookkeeping:category_list', 'bookkeeping:asset_list', 'bookkeeping:resource_list', 'bookkeeping:report_list')
CTA_LIST_URL_NAMES = ('bookkeeping:transaction_list', 'bookkeeping:partner_list', 'bookkeeping:category_list', 'bookkeeping:asset_list', 'bookkeeping:resource_list')


class BookkeepingViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='bk', email='bk@example.com', password='x')
        cls.asset = Asset.objects.create(code='TST', name='Test Asset', symbol='T')
        cls.category = Category.objects.create(name='Test Cat')
        cls.partner = Partner.objects.create(name='Test Partner')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _transaction(self, author=None, payment_received_date=None, note=''):
        data = {'type': 'I', 'asset': self.asset, 'category': self.category, 'partner': self.partner, 'amount': 10, 'author': author or self.user, 'note': note}
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
        cases = (('bookkeeping:asset_update', self.asset), ('bookkeeping:category_update', self.category), ('bookkeeping:partner_update', self.partner), ('bookkeeping:transaction_update', transaction))

        for url_name, instance in cases:
            url = reverse(url_name, args=[instance.pk])
            with self.subTest(url_name=url_name, method='GET'):
                self.assertEqual(anonymous_client.get(url).status_code, 302)
            with self.subTest(url_name=url_name, method='POST'):
                self.assertEqual(anonymous_client.post(url, {}).status_code, 302)

    def test_asset_create_and_update(self):
        res = self.client.post(reverse('bookkeeping:asset_create'), {'code': 'PLN2', 'name': 'Złoty', 'symbol': 'zł', 'decimal_places': 2})
        self.assertEqual(res.status_code, 302)
        asset = Asset.objects.get(code='PLN2')

        res = self.client.post(reverse('bookkeeping:asset_update', args=[asset.pk]), {'code': 'PLN2', 'name': 'Polski złoty', 'symbol': 'zł', 'decimal_places': 2})
        self.assertEqual(res.status_code, 302)
        asset.refresh_from_db()
        self.assertEqual(asset.name, 'Polski złoty')

    def test_edit_forms_render_prefilled_data(self):
        transaction = self._transaction()
        cases = (
            ('bookkeeping:asset_update', self.asset, 'form'),
            ('bookkeeping:category_update', self.category, 'form'),
            ('bookkeeping:partner_update', self.partner, 'form'),
            ('bookkeeping:transaction_update', transaction, 'transaction_form'),
        )

        for url_name, instance, context_name in cases:
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name, args=[instance.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context[context_name].instance, instance)

    def test_category_and_partner_forms_use_explicit_field_allowlists(self):
        cases = (
            ('bookkeeping:category_create', None, ('name',)),
            ('bookkeeping:category_update', self.category.pk, ('name',)),
            ('bookkeeping:partner_create', None, ('name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'notes')),
            ('bookkeeping:partner_update', self.partner.pk, ('name', 'email', 'phone', 'web_page', 'address', 'city', 'country', 'notes')),
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

    def test_edit_forms_rerender_errors_without_saving(self):
        transaction = self._transaction()
        cases = (
            ('bookkeeping:asset_update', self.asset, {'code': '', 'name': 'Test Asset', 'symbol': 'T', 'decimal_places': 2}, 'form'),
            ('bookkeeping:category_update', self.category, {'name': ''}, 'form'),
            ('bookkeeping:partner_update', self.partner, {'name': ''}, 'form'),
            (
                'bookkeeping:transaction_update',
                transaction,
                {'type': 'I', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '-1', 'payment_received_date': '2026-01-01', 'note': ''},
                'transaction_form',
            ),
        )

        for url_name, instance, data, context_name in cases:
            with self.subTest(url_name=url_name):
                response = self.client.post(reverse(url_name, args=[instance.pk]), data)
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

        res = self.client.post(reverse('bookkeeping:asset_delete', args=[self.asset.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())

        res = self.client.get(reverse('bookkeeping:asset_delete', args=[self.asset.pk]))
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
        self.assertContains(response, f'href="{reverse("bookkeeping:asset_detail", args=[self.asset.pk])}"')

    def test_asset_detail_does_not_repeat_code_as_badge(self):
        response = self.client.get(reverse('bookkeeping:asset_detail', args=[self.asset.pk]))

        self.assertNotContains(response, 'tw-badge tw-badge-secondary')

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
            update_url, {'type': 'O', 'asset': self.asset.pk, 'category': self.category.pk, 'partner': self.partner.pk, 'amount': '99', 'payment_received_date': '2026-01-02', 'note': 'Unauthorized'}
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
            {'type': 'I', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '10.5', 'payment_received_date': '2026-01-01', 'note': ''},
        )
        txn = Transaction.objects.get()
        self.assertRedirects(res, reverse('bookkeeping:transaction_detail', args=[txn.pk]))
        self.assertEqual(txn.author, self.user)

    def test_new_transaction_emits_push_event(self):
        with patch('core.notifications._dispatch_notification') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse('bookkeeping:transaction_create'),
                    {'type': 'I', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '10.5', 'payment_received_date': '2026-01-01', 'note': ''},
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
                    {'type': 'O', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'Updated'},
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
            {'type': 'O', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'x'},
        )
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, next_url)
        txn.refresh_from_db()
        self.assertEqual(txn.type, 'O')

    def test_transaction_update_rejects_external_next_param(self):
        txn = self._transaction()
        res = self.client.post(
            reverse('bookkeeping:transaction_update', args=[txn.pk]) + '?next=https://evil.example/',
            {'type': 'O', 'asset': self.asset.pk, 'partner': self.partner.pk, 'category': self.category.pk, 'amount': '20', 'payment_received_date': '2026-01-02', 'note': 'x'},
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

    def test_views_require_login(self):
        client = Client()

        for url in (self.list_url, self.manage_url, reverse('bookkeeping:resource_search')):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 302)

        self.assertEqual(client.post(reverse('bookkeeping:resource_create'), {}).status_code, 302)

    def test_create_and_edit_preserve_listing_owner(self):
        response = self.client.post(reverse('bookkeeping:resource_create'), {'kind': 'give', 'name': 'Rower', 'description': 'Do oddania'})

        self.assertRedirects(response, self.manage_url)
        listing = ResourceListing.objects.get(name='Rower')
        self.assertEqual(listing.profile, self.owner.uzytkownik)

        other_listing = ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)
        response = self.client.post(reverse('bookkeeping:resource_update', args=[listing.pk]), {'kind': 'sale', 'name': 'Rower miejski', 'description': 'Sprawny'})

        self.assertRedirects(response, self.manage_url)
        listing.refresh_from_db()
        other_listing.refresh_from_db()
        self.assertEqual((listing.profile, listing.kind, listing.name, listing.description), (self.owner.uzytkownik, ResourceListing.Kind.SALE, 'Rower miejski', 'Sprawny'))
        self.assertEqual((other_listing.profile, other_listing.kind, other_listing.name), (self.other_user.uzytkownik, ResourceListing.Kind.GIVE, 'Rower'))

    def test_listing_names_remain_unique_per_owner_and_kind(self):
        listing = ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.GIVE)
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', kind=ResourceListing.Kind.SALE)

        response = self.client.post(reverse('bookkeeping:resource_update', args=[listing.pk]), {'kind': 'give', 'name': ' WIERTARKA ', 'description': ''})

        self.assertEqual(response.status_code, 200)
        self.assertIn('name', response.context['resource_form'].errors)
        listing.refresh_from_db()
        self.assertEqual(listing.name, 'Rower')

    def test_only_owner_can_edit_or_delete_listing(self):
        listing = ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.BORROW)

        self.assertEqual(self.client.get(reverse('bookkeeping:resource_update', args=[listing.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('bookkeeping:resource_delete', args=[listing.pk])).status_code, 404)
        self.assertTrue(ResourceListing.objects.filter(pk=listing.pk).exists())

    def test_owner_can_delete_listing(self):
        listing = ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.BORROW)

        response = self.client.post(reverse('bookkeeping:resource_delete', args=[listing.pk]))

        self.assertRedirects(response, self.manage_url)
        self.assertFalse(ResourceListing.objects.filter(pk=listing.pk).exists())

    def test_owner_can_close_and_restore_listing(self):
        listing = ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)
        toggle_url = reverse('bookkeeping:resource_toggle_closed', args=[listing.pk])

        response = self.client.post(toggle_url, {'closed': '1'})

        self.assertRedirects(response, self.manage_url)
        listing.refresh_from_db()
        self.assertTrue(listing.is_closed)
        response = self.client.get(self.list_url, {'q': 'Rower'})
        self.assertFalse(response.context['resource_listings'])
        response = self.client.get(self.manage_url)
        self.assertEqual([item.pk for item in response.context['closed_listings']], [listing.pk])

        response = self.client.post(toggle_url, {'closed': '0'})

        self.assertRedirects(response, self.manage_url)
        listing.refresh_from_db()
        self.assertFalse(listing.is_closed)

    def test_only_owner_can_close_listing(self):
        listing = ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)

        response = self.client.post(reverse('bookkeeping:resource_toggle_closed', args=[listing.pk]), {'closed': '1'})

        self.assertEqual(response.status_code, 404)
        listing.refresh_from_db()
        self.assertFalse(listing.is_closed)

    def test_resource_catalog_filters_and_splits_offers_and_needs(self):
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', description='Do odebrania', kind=ResourceListing.Kind.GIVE)
        ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Rower', description='Szukam roweru', kind=ResourceListing.Kind.NEED)
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.BORROW)
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

    def test_profile_link_can_filter_resource_catalog_to_that_owner(self):
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)
        ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.GIVE)

        response = self.client.get(self.list_url, {'profile': self.owner.uzytkownik.pk})

        self.assertEqual([item.name for item in response.context['resource_listings']], ['Rower'])
        self.assertContains(response, f'name="profile" value="{self.owner.uzytkownik.pk}"')

    def test_invalid_profile_filters_return_empty_results_without_error(self):
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)

        for profile_id in (chr(178), '9' * 20, '9' * 5000):
            with self.subTest(profile_id=profile_id[:20]):
                response = self.client.get(self.list_url, {'profile': profile_id})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.context['resource_listings'])

    def test_pagination_does_not_report_items_on_other_pages_as_missing(self):
        for index in range(24):
            ResourceListing.objects.create(profile=self.owner.uzytkownik, name=f'Offer {index:02d}', kind=ResourceListing.Kind.BORROW)
        ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Need one', kind=ResourceListing.Kind.NEED)

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
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', kind=ResourceListing.Kind.GIVE)
        ResourceListing.objects.create(profile=self.other_user.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.BORROW)
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Closed listing', kind=ResourceListing.Kind.GIVE, is_closed=True)
        inactive_user = User.objects.create_user(username='resource-inactive', password='secret', is_active=False)
        ResourceListing.objects.create(profile=inactive_user.uzytkownik, name='Inactive listing', kind=ResourceListing.Kind.GIVE)

        response = self.client.get(self.list_url)

        self.assertContains(response, 'class="tw-stepper-step-count">2</span>')

    def test_resource_search_respects_selected_kind(self):
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Wiertarka', kind=ResourceListing.Kind.GIVE)

        response = self.client.get(reverse('bookkeeping:resource_search'), {'q': 'Wiert', 'kind': 'need'})

        self.assertEqual(response.json()['items'], [])

    def test_resource_descriptions_are_escaped_and_urls_clickable(self):
        ResourceListing.objects.create(profile=self.owner.uzytkownik, name='Rower', description='<script>alert(1)</script> https://example.com', kind=ResourceListing.Kind.GIVE)

        response = self.client.get(self.list_url, {'q': 'Rower'})

        self.assertContains(response, 'href="https://example.com"')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
