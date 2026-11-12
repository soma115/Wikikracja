from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from bookkeeping.feed import get_feed_items
from bookkeeping.forms import PaymentPlanForm
from bookkeeping.models import Category, Partner, PaymentDue, PaymentPlan, PaymentReminderDelivery, Transaction
from bookkeeping.services import (
    _next_payment_date,
    asset_balances,
    cancel_payment_due,
    category_breakdown,
    confirm_payment_due,
    ensure_next_payment_periods,
    process_payment_reminders,
    update_next_payment_period,
)
from resources.models import Entity

User = get_user_model()


class PaymentPlanServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='payment-member', email='member@example.com', password='x')
        cls.inactive_user = User.objects.create_user(username='payment-inactive', email='inactive@example.com', password='x', is_active=False)
        cls.asset = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, code='PAY', name='Payment asset', symbol='P', is_default=True)
        cls.category = Category.objects.create(name='Payment category')
        cls.partner = Partner.objects.create(name='Payment partner')

    def make_plan(self, **kwargs):
        defaults = {
            'name': 'Annual membership',
            'direction': PaymentPlan.Direction.INCOMING,
            'amount': Decimal('120.00'),
            'entity': self.asset,
            'category': self.category,
            'recurrence': PaymentPlan.Recurrence.YEARLY,
            'first_due_date': date(2027, 1, 15),
            'next_due_date': date(2027, 1, 15),
            'author': self.user,
        }
        return PaymentPlan.objects.create(**(defaults | kwargs))

    def test_generation_creates_member_due_and_is_idempotent(self):
        plan = self.make_plan(first_due_date=date(2027, 1, 31), next_due_date=date(2027, 1, 31), recurrence=PaymentPlan.Recurrence.MONTHLY)
        plan.debtors.add(self.user)

        generated = ensure_next_payment_periods(plan.pk, today=date(2027, 1, 31))

        plan.refresh_from_db()
        self.assertEqual(generated, 2)
        self.assertEqual(list(plan.dues.values_list('due_date', flat=True)), [date(2027, 1, 31), date(2027, 2, 28)])
        self.assertEqual(plan.dues.filter(debtor=self.user).count(), 2)
        self.assertFalse(plan.dues.filter(debtor=self.inactive_user).exists())
        self.assertEqual(plan.next_due_date, date(2027, 3, 31))
        self.assertEqual(ensure_next_payment_periods(plan.pk, today=date(2027, 1, 31)), 0)

    def test_transaction_activity_formats_amount_using_asset_precision(self):
        self.asset.decimal_places = 3
        self.asset.save(update_fields=['decimal_places'])
        transaction = Transaction.objects.create(type=Transaction.INCOMING, entity=self.asset, category=self.category, partner=self.partner, amount=Decimal('12.34567'), author=self.user)

        item = next(item for item in get_feed_items(timezone.now() - timedelta(days=1)) if item['object_id'] == transaction.pk)

        self.assertTrue(item['title'].endswith('12.346 P'))

    def test_generation_creates_a_due_and_transaction_for_each_selected_payer(self):
        partner_payer = Partner.objects.create(name='Selected payer')
        plan = self.make_plan(recurrence=PaymentPlan.Recurrence.ONCE, first_due_date=date(2027, 1, 15), next_due_date=date(2027, 1, 15))
        plan.debtors.add(self.user)
        plan.debtor_partners.add(partner_payer)

        ensure_next_payment_periods(plan.pk, today=date(2027, 1, 1))

        dues = list(plan.dues.select_related('payment_transaction', 'debtor', 'debtor_partner'))
        self.assertEqual(len(dues), 2)
        member_due = next(due for due in dues if due.debtor_id)
        partner_due = next(due for due in dues if due.debtor_partner_id)
        self.assertEqual(member_due.debtor, self.user)
        self.assertEqual(partner_due.debtor_partner, partner_payer)
        self.assertEqual(Transaction.objects.filter(payment_due__in=dues, status=Transaction.Status.PLANNED).count(), 2)

    def test_existing_generated_due_without_transaction_is_backfilled(self):
        due_date = date(2026, 11, 13)
        plan = self.make_plan(first_due_date=due_date, next_due_date=date(2027, 11, 13), last_generated_date=due_date)
        due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=due_date, debtor=self.user)

        process_payment_reminders(today=date(2026, 11, 7))

        transaction = Transaction.objects.get(payment_due=due)
        self.assertEqual((transaction.status, transaction.payment_received_date), (Transaction.Status.PLANNED, due_date))

    def test_yearly_leap_day_returns_to_february_29_in_a_leap_year(self):
        plan = self.make_plan(first_due_date=date(2024, 2, 29), next_due_date=date(2024, 2, 29))

        self.assertEqual(_next_payment_date(plan, date(2027, 2, 28)), date(2028, 2, 29))

    def test_outgoing_due_copies_the_selected_treasurer(self):
        plan = self.make_plan(direction=PaymentPlan.Direction.OUTGOING, recurrence=PaymentPlan.Recurrence.ONCE, first_due_date=date(2027, 1, 15), next_due_date=date(2027, 1, 15))
        plan.treasurer = self.user
        plan.save(update_fields=['treasurer'])

        ensure_next_payment_periods(plan.pk, today=date(2027, 1, 1))

        due = PaymentDue.objects.get(plan=plan)
        self.assertIsNone(due.debtor_id)
        self.assertEqual(due.treasurer, self.user)
        plan.refresh_from_db()
        self.assertFalse(plan.is_active)
        self.assertIsNone(plan.next_due_date)

    def test_plan_edit_updates_only_next_unpaid_period(self):
        plan = self.make_plan(first_due_date=date(2027, 1, 31), next_due_date=date(2027, 1, 31), recurrence=PaymentPlan.Recurrence.MONTHLY)
        ensure_next_payment_periods(plan.pk, today=date(2027, 1, 31))
        plan.amount = Decimal('150.00')
        plan.save()

        update_next_payment_period(plan, today=date(2027, 1, 31))

        amounts = list(plan.dues.order_by('due_date').values_list('amount', flat=True))
        self.assertEqual(amounts, [Decimal('120.00000000'), Decimal('150.00000000')])
        planned_amounts = list(Transaction.objects.filter(payment_due__plan=plan).order_by('payment_received_date').values_list('amount', flat=True))
        self.assertEqual(planned_amounts, [Decimal('120.00000000'), Decimal('150.00000000')])

    def test_plan_edit_updates_next_period_payers_without_changing_paid_dues(self):
        plan = self.make_plan(first_due_date=date(2027, 1, 31), next_due_date=date(2027, 1, 31), recurrence=PaymentPlan.Recurrence.MONTHLY)
        plan.debtors.add(self.user)
        plan.debtor_partners.add(self.partner)
        ensure_next_payment_periods(plan.pk, today=date(2027, 1, 31))
        next_date = date(2027, 2, 28)
        paid_due = plan.dues.get(due_date=next_date, debtor=self.user)
        paid_transaction = paid_due.transaction
        paid_transaction.status = Transaction.Status.POSTED
        paid_transaction.save(update_fields=['status'])
        replacement_partner = Partner.objects.create(name='Replacement payer')
        plan.debtors.clear()
        plan.debtor_partners.set([replacement_partner])

        update_next_payment_period(plan, today=date(2027, 1, 31))

        paid_due.refresh_from_db()
        self.assertTrue(paid_due.is_paid)
        self.assertFalse(plan.dues.filter(due_date=next_date, debtor_partner=self.partner).exists())
        replacement_due = plan.dues.get(due_date=next_date, debtor_partner=replacement_partner)
        self.assertEqual(replacement_due.transaction.status, Transaction.Status.PLANNED)

    def test_planned_transactions_do_not_affect_financial_balances(self):
        plan = self.make_plan(first_due_date=date(2027, 1, 15), next_due_date=date(2027, 1, 15))
        ensure_next_payment_periods(plan.pk, today=date(2026, 11, 1))

        self.assertEqual(asset_balances(asset=self.asset), [])
        self.assertEqual(category_breakdown()[0], [])
        transaction = Transaction.objects.get(payment_due__plan=plan, status=Transaction.Status.PLANNED)
        self.assertEqual(get_feed_items(timezone.now() - timedelta(days=1)), [])
        transaction.status = Transaction.Status.POSTED
        transaction.save(update_fields=['status'])
        self.assertEqual(asset_balances(asset=self.asset)[0]['income'], plan.amount)
        self.assertEqual(len(get_feed_items(timezone.now() - timedelta(days=1))), 1)

    def test_confirming_payment_creates_transaction_and_deleting_it_reopens_due(self):
        plan = self.make_plan()
        due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=PaymentPlan.Direction.INCOMING, amount=plan.amount, entity=self.asset, category=self.category, due_date=date(2026, 1, 1), debtor=self.user
        )
        values = {
            'type': Transaction.INCOMING,
            'entity': self.asset,
            'partner': self.partner,
            'category': self.category,
            'amount': Decimal('120.00'),
            'payment_received_date': date(2026, 1, 2),
            'note': 'Annual membership',
        }

        with patch('bookkeeping.services.transaction_created.send'):
            transaction, created = confirm_payment_due(due.pk, values, self.user)

        due.refresh_from_db()
        self.assertTrue(created)
        self.assertEqual(Transaction.objects.filter(payment_due=due).count(), 1)
        self.assertEqual((due.status, due.paid_at, due.paid_by), ('paid', date(2026, 1, 2), self.user))

        transaction.delete()
        due.refresh_from_db()
        self.assertEqual(due.status, 'pending')
        self.assertIsNone(due.transaction)

    def test_confirm_payment_rejects_a_direction_different_from_the_due(self):
        plan = self.make_plan()
        due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=PaymentPlan.Direction.INCOMING, amount=plan.amount, entity=self.asset, category=self.category, due_date=date(2026, 1, 1), debtor=self.user
        )
        values = {'type': Transaction.OUTGOING, 'entity': self.asset, 'partner': self.partner, 'category': self.category, 'amount': Decimal('120.00'), 'payment_received_date': date(2026, 1, 2), 'note': ''}

        with patch('bookkeeping.services.transaction_created.send'):
            with self.assertRaises(ValidationError):
                confirm_payment_due(due.pk, values, self.user)
        self.assertFalse(Transaction.objects.filter(payment_due=due).exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
    def test_member_due_uses_digest_email_and_due_date_push(self):
        plan = self.make_plan(recurrence=PaymentPlan.Recurrence.ONCE, first_due_date=date(2026, 1, 1), next_due_date=None, is_active=False)
        due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=PaymentPlan.Direction.INCOMING, amount=plan.amount, entity=self.asset, category=self.category, due_date=date(2026, 1, 1), debtor=self.user
        )
        with patch('core.notifications.send_payment_due_email', return_value=True) as email, patch('core.notifications.send_payment_due_push', return_value=True) as push:
            process_payment_reminders(today=date(2026, 1, 1))
            process_payment_reminders(today=date(2026, 1, 2))

        self.assertEqual(email.call_count, 0)
        self.assertEqual(push.call_count, 1)
        self.assertEqual(PaymentReminderDelivery.objects.filter(due=due, status=PaymentReminderDelivery.Status.SENT).count(), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
    def test_outgoing_reminders_only_target_selected_recipients(self):
        plan = self.make_plan(direction=PaymentPlan.Direction.OUTGOING, recurrence=PaymentPlan.Recurrence.ONCE, first_due_date=date(2026, 1, 1), next_due_date=None, is_active=False)
        plan.treasurer = self.user
        plan.save(update_fields=['treasurer'])
        due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=PaymentPlan.Direction.OUTGOING, amount=plan.amount, entity=self.asset, category=self.category, due_date=date(2026, 1, 1))
        due.treasurer = self.user
        due.save(update_fields=['treasurer'])
        with patch('core.notifications.send_payment_due_email', return_value=True) as email, patch('core.notifications.send_payment_due_push', return_value=True) as push:
            process_payment_reminders(today=date(2026, 1, 1))

        email.assert_not_called()
        self.assertEqual(push.call_args.args[0], self.user)
        self.assertEqual(PaymentReminderDelivery.objects.filter(due=due).count(), 1)

    def test_failed_push_reminder_can_retry(self):
        plan = self.make_plan(direction=PaymentPlan.Direction.OUTGOING, recurrence=PaymentPlan.Recurrence.ONCE, first_due_date=date(2026, 1, 1), next_due_date=None, is_active=False)
        plan.treasurer = self.user
        plan.save(update_fields=['treasurer'])
        due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=PaymentPlan.Direction.OUTGOING, amount=plan.amount, entity=self.asset, category=self.category, due_date=date(2026, 1, 1), treasurer=self.user
        )
        with patch('core.notifications.send_payment_due_email') as email, patch('core.notifications.send_payment_due_push', side_effect=[RuntimeError('push unavailable'), True]) as push:
            process_payment_reminders(today=date(2026, 1, 1))
            process_payment_reminders(today=date(2026, 1, 2))

        email.assert_not_called()
        self.assertEqual(push.call_count, 2)
        self.assertEqual(PaymentReminderDelivery.objects.get(due=due, channel=PaymentReminderDelivery.Channel.PUSH).status, PaymentReminderDelivery.Status.SENT)

    def test_cannot_cancel_a_paid_due(self):
        plan = self.make_plan()
        due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=PaymentPlan.Direction.INCOMING, amount=plan.amount, entity=self.asset, category=self.category, due_date=date(2026, 1, 1), debtor=self.user
        )
        Transaction.objects.create(type=Transaction.INCOMING, entity=self.asset, partner=self.partner, category=self.category, amount=plan.amount, author=self.user, payment_due=due)

        with self.assertRaises(ValidationError):
            cancel_payment_due(due.pk, self.user)


class PaymentPlanViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='payment-viewer', email='viewer@example.com', password='x')
        cls.asset = Entity.objects.create(entity_type=Entity.Type.FINANCIAL_ASSET, code='VIEW', name='View asset', symbol='V', is_default=True)
        cls.category = Category.objects.create(name='View category')
        cls.partner = Partner.objects.create(name='View partner')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_new_payment_plan_form_only_offers_recurring_cycles(self):
        form = PaymentPlanForm()
        recurrence_values = {value for value, _label in form.fields['recurrence'].choices}

        self.assertEqual(recurrence_values, {PaymentPlan.Recurrence.MONTHLY, PaymentPlan.Recurrence.YEARLY})
        self.assertEqual(str(form.fields['entity'].label), 'Waluta')

    def test_transaction_list_and_detail_format_amount_using_asset_precision(self):
        self.asset.decimal_places = 3
        self.asset.save(update_fields=['decimal_places'])
        transaction = Transaction.objects.create(type=Transaction.INCOMING, entity=self.asset, category=self.category, partner=self.partner, amount=Decimal('12.34567'), author=self.user)

        list_response = self.client.get(reverse('bookkeeping:transaction_list'))
        detail_response = self.client.get(reverse('bookkeeping:transaction_detail', args=[transaction.pk]))

        self.assertContains(list_response, '12.346 V')
        self.assertContains(detail_response, '12.346 V')

    def test_edit_form_preselects_saved_member_and_partner_payers(self):
        inactive_payer = User.objects.create_user(username='inactive-payer', email='inactive-payer@example.com', password='x')
        plan = PaymentPlan.objects.create(
            name='Selected payers',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
        )
        plan.debtors.add(self.user, inactive_payer)
        plan.debtor_partners.add(self.partner)
        User.objects.filter(pk=inactive_payer.pk).update(is_active=False)

        response = self.client.get(reverse('bookkeeping:payment_plan_update', args=[plan.pk]))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertRegex(html, rf'<input[^>]*value="{self.user.pk}"[^>]*checked')
        self.assertRegex(html, rf'<input[^>]*value="{inactive_payer.pk}"[^>]*checked')
        self.assertRegex(html, rf'<input[^>]*value="{self.partner.pk}"[^>]*checked')
        self.assertIn('data-shift-range-select="true"', html)
        self.assertIn('data-select-all-checkboxes="debtors"', html)
        self.assertIn('data-select-all-checkboxes="debtor_partners"', html)
        self.assertIn('data-deselect-all-label="Odznacz wszystkich"', html)
        self.assertEqual(html.count('>Zaznacz wszystkich</button>'), 2)

    def test_edit_form_explains_and_disables_immutable_schedule_fields(self):
        plan = PaymentPlan.objects.create(
            name='Fixed schedule',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
        )

        response = self.client.get(reverse('bookkeeping:payment_plan_update', args=[plan.pk]))
        html = response.content.decode()

        self.assertContains(response, 'Po utworzeniu reguły nie można zmienić kierunku płatności')
        self.assertEqual(html.count('class="tw-disabled"'), 3)
        for field_name in ('direction', 'recurrence', 'first_due_date'):
            self.assertTrue(response.context['form'].fields[field_name].disabled)

    def test_active_members_can_create_and_view_payment_plans_and_dues(self):
        response = self.client.post(
            reverse('bookkeeping:payment_plan_create'),
            {
                'name': 'Membership dues',
                'description': '',
                'direction': PaymentPlan.Direction.INCOMING,
                'amount': '25',
                'entity': self.asset.pk,
                'category': self.category.pk,
                'partner': '',
                'debtors': [self.user.pk],
                'debtor_partners': [],
                'recurrence': PaymentPlan.Recurrence.MONTHLY,
                'first_due_date': timezone.localdate().isoformat(),
            },
        )

        self.assertRedirects(response, reverse('bookkeeping:payment_plan_list'))
        plan = PaymentPlan.objects.get(name='Membership dues')
        self.assertEqual(list(plan.debtors.values_list('pk', flat=True)), [self.user.pk])
        edit_response = self.client.get(reverse('bookkeeping:payment_plan_update', args=[plan.pk]))
        self.assertRegex(edit_response.content.decode(), rf'<input[^>]*value="{self.user.pk}"[^>]*checked')
        due = PaymentDue.objects.filter(plan=plan, debtor=self.user).order_by('due_date').first()
        self.assertTrue(plan.is_active)
        self.assertEqual(plan.dues.filter(debtor=self.user).count(), 2)
        planned_transactions = Transaction.objects.filter(payment_due__plan=plan).order_by('payment_received_date')
        self.assertEqual(planned_transactions.count(), 2)
        self.assertTrue(all(transaction.status == Transaction.Status.PLANNED for transaction in planned_transactions))
        recurring_response = self.client.get(reverse('bookkeeping:payment_plan_list'))
        self.assertEqual(len(recurring_response.context['payment_plans']), 1)
        self.assertEqual(recurring_response.context['payment_plans'][0].pk, plan.pk)
        transaction_list = self.client.get(reverse('bookkeeping:transaction_list'))
        self.assertEqual(transaction_list.status_code, 200)
        self.assertEqual({transaction.pk for transaction in transaction_list.context['transactions']}, set(planned_transactions.values_list('pk', flat=True)))
        self.assertContains(self.client.get(reverse('bookkeeping:transaction_detail', args=[planned_transactions.first().pk])), self.user.username)
        self.assertEqual(self.client.get(reverse('bookkeeping:payment_plan_detail', args=[plan.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('bookkeeping:payment_due_detail', args=[due.pk])).status_code, 200)

    def test_incoming_plan_requires_at_least_one_payer(self):
        response = self.client.post(
            reverse('bookkeeping:payment_plan_create'),
            {
                'name': 'Unassigned dues',
                'description': '',
                'direction': PaymentPlan.Direction.INCOMING,
                'amount': '25',
                'entity': self.asset.pk,
                'category': self.category.pk,
                'partner': '',
                'debtors': [],
                'debtor_partners': [],
                'recurrence': PaymentPlan.Recurrence.MONTHLY,
                'first_due_date': timezone.localdate().isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PaymentPlan.objects.filter(name='Unassigned dues').exists())
        self.assertIn('debtors', response.context['form'].errors)

    def test_partner_payer_is_shown_on_its_transaction(self):
        response = self.client.post(
            reverse('bookkeeping:payment_plan_create'),
            {
                'name': 'Partner dues',
                'description': '',
                'direction': PaymentPlan.Direction.INCOMING,
                'amount': '25',
                'entity': self.asset.pk,
                'category': self.category.pk,
                'partner': '',
                'debtors': [],
                'debtor_partners': [self.partner.pk],
                'recurrence': PaymentPlan.Recurrence.MONTHLY,
                'first_due_date': timezone.localdate().isoformat(),
            },
        )

        self.assertRedirects(response, reverse('bookkeeping:payment_plan_list'))
        plan = PaymentPlan.objects.get(name='Partner dues')
        self.assertEqual(list(plan.debtor_partners.values_list('pk', flat=True)), [self.partner.pk])
        edit_response = self.client.get(reverse('bookkeeping:payment_plan_update', args=[plan.pk]))
        self.assertRegex(edit_response.content.decode(), rf'<input[^>]*value="{self.partner.pk}"[^>]*checked')
        due = PaymentDue.objects.filter(plan__name='Partner dues', debtor_partner=self.partner).order_by('due_date').first()
        transaction = Transaction.objects.get(payment_due=due)
        detail_response = self.client.get(reverse('bookkeeping:transaction_detail', args=[transaction.pk]))
        self.assertContains(detail_response, self.partner.name)
        self.assertContains(detail_response, 'Płatnik')

    def test_deleting_plan_removes_unpaid_items_and_preserves_paid_transaction(self):
        plan = PaymentPlan.objects.create(
            name='Removable plan',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
        )
        paid_due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=timezone.localdate(), debtor=self.user)
        unpaid_due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=timezone.localdate(), debtor_partner=self.partner
        )
        paid_transaction = Transaction.objects.create(
            type=Transaction.INCOMING,
            status=Transaction.Status.POSTED,
            entity=self.asset,
            partner=self.partner,
            category=self.category,
            amount=plan.amount,
            payment_received_date=timezone.localdate(),
            author=self.user,
            payment_due=paid_due,
        )
        planned_transaction = Transaction.objects.create(
            type=Transaction.INCOMING, status=Transaction.Status.PLANNED, entity=self.asset, category=self.category, amount=plan.amount, payment_received_date=unpaid_due.due_date, payment_due=unpaid_due
        )

        confirmation = self.client.get(reverse('bookkeeping:payment_plan_delete', args=[plan.pk]))
        response = self.client.post(reverse('bookkeeping:payment_plan_delete', args=[plan.pk]))

        self.assertContains(confirmation, plan.name)
        self.assertContains(confirmation, '1')
        self.assertRedirects(response, reverse('bookkeeping:payment_plan_list'))
        self.assertFalse(PaymentPlan.objects.filter(pk=plan.pk).exists())
        self.assertFalse(PaymentDue.objects.filter(plan=plan).exists())
        paid_transaction.refresh_from_db()
        self.assertIsNone(paid_transaction.payment_due_id)
        self.assertFalse(Transaction.objects.filter(pk=planned_transaction.pk).exists())

    def test_partner_delete_is_blocked_while_referenced_by_payment_plan_or_due(self):
        plan = PaymentPlan.objects.create(
            name='Partner payer plan',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            partner=self.partner,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
        )
        plan.debtor_partners.add(self.partner)
        due = PaymentDue.objects.create(
            plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, partner=self.partner, due_date=timezone.localdate(), debtor_partner=self.partner
        )

        confirmation = self.client.get(reverse('bookkeeping:partner_delete', args=[self.partner.pk]))
        response = self.client.post(reverse('bookkeeping:partner_delete', args=[self.partner.pk]))

        self.assertContains(confirmation, plan.name)
        self.assertContains(confirmation, due.name)
        self.assertRedirects(response, reverse('bookkeeping:partner_delete', args=[self.partner.pk]))
        self.assertTrue(Partner.objects.filter(pk=self.partner.pk).exists())
        self.assertTrue(plan.debtor_partners.filter(pk=self.partner.pk).exists())
        self.assertTrue(PaymentDue.objects.filter(pk=due.pk, debtor_partner=self.partner).exists())

    def test_confirmation_form_posts_existing_planned_transaction(self):
        plan = PaymentPlan.objects.create(
            name='Membership dues',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
            author=self.user,
        )
        due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=timezone.localdate(), debtor=self.user)
        planned_transaction = Transaction.objects.create(
            type=Transaction.INCOMING,
            status=Transaction.Status.PLANNED,
            entity=self.asset,
            category=self.category,
            amount=plan.amount,
            payment_received_date=due.due_date,
            note=plan.name,
            author=self.user,
            payment_due=due,
        )
        response = self.client.post(
            reverse('bookkeeping:payment_due_confirm', args=[due.pk]),
            {
                'type': Transaction.INCOMING,
                'entity': self.asset.pk,
                'partner': self.partner.pk,
                'category': self.category.pk,
                'amount': '25',
                'payment_received_date': timezone.localdate().isoformat(),
                'note': 'Membership dues',
            },
        )

        transaction = Transaction.objects.get(payment_due=due)
        self.assertRedirects(response, reverse('bookkeeping:transaction_detail', args=[transaction.pk]))
        self.assertEqual(transaction.pk, planned_transaction.pk)
        self.assertEqual(transaction.status, Transaction.Status.POSTED)
        self.assertEqual(Transaction.objects.filter(payment_due=due).count(), 1)
        self.assertEqual(due.__class__.objects.get(pk=due.pk).status, 'paid')

    def test_deleting_posted_transaction_recreates_a_planned_transaction(self):
        plan = PaymentPlan.objects.create(
            name='Membership dues',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
            author=self.user,
        )
        due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=timezone.localdate(), debtor=self.user)
        posted = Transaction.objects.create(
            type=Transaction.INCOMING,
            status=Transaction.Status.POSTED,
            entity=self.asset,
            partner=self.partner,
            category=self.category,
            amount=plan.amount,
            payment_received_date=timezone.localdate(),
            author=self.user,
            payment_due=due,
        )

        response = self.client.post(reverse('bookkeeping:transaction_delete', args=[posted.pk]))

        planned = Transaction.objects.get(payment_due=due)
        self.assertRedirects(response, reverse('bookkeeping:transaction_list'))
        self.assertEqual((planned.status, planned.payment_received_date, due.__class__.objects.get(pk=due.pk).status), (Transaction.Status.PLANNED, due.due_date, 'pending'))

    def test_category_manager_counts_and_protects_payment_plans_and_dues(self):
        plan = PaymentPlan.objects.create(
            name='Membership dues',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
            author=self.user,
        )
        due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=timezone.localdate(), debtor=self.user)

        category_list = self.client.get(reverse('bookkeeping:category_api')).json()['categories']
        category = next(item for item in category_list if item['id'] == self.category.pk)
        items = self.client.get(reverse('bookkeeping:category_api_items', args=[self.category.pk])).json()
        response = self.client.post(reverse('bookkeeping:category_api_delete', args=[self.category.pk]))

        self.assertEqual(category['item_count'], 2)
        self.assertEqual(items['count'], 2)
        self.assertEqual([item.rsplit(': ', 1)[1] for item in items['items']], ['Membership dues', 'Membership dues'])
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.assertTrue(PaymentDue.objects.filter(pk=due.pk).exists())

    def test_unauthenticated_users_cannot_access_payment_pages_or_actions(self):
        client = Client()
        plan = PaymentPlan.objects.create(
            name='Membership dues',
            direction=PaymentPlan.Direction.INCOMING,
            amount=Decimal('25'),
            entity=self.asset,
            category=self.category,
            recurrence=PaymentPlan.Recurrence.MONTHLY,
            first_due_date=timezone.localdate(),
        )
        due = PaymentDue.objects.create(plan=plan, name=plan.name, direction=plan.direction, amount=plan.amount, entity=self.asset, category=self.category, due_date=timezone.localdate())

        self.assertEqual(client.get(reverse('bookkeeping:transaction_list')).status_code, 302)
        self.assertEqual(client.post(reverse('bookkeeping:payment_due_cancel', args=[due.pk])).status_code, 302)
