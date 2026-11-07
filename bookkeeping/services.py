"""
Serwisy aplikacji bookkeeping — agregacje używane przez widoki, pulpit, raporty.

Single source of truth dla "ile mamy w PLN / BTC / EUR / ..." — wszystkie miejsca,
które kiedyś sumowały transakcje per asset (ReportView, pulpit, transaction_list),
docelowo wołają stąd, żeby nie powielać logiki i nie ryzykować mieszania walut.
"""

import logging
from calendar import monthrange
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.signals import transaction_created
from core.utils import build_site_url
from obywatele.models import Uzytkownik
from resources.models import Entity

from .models import Category, PaymentDue, PaymentPlan, PaymentReminderDelivery, Transaction

log = logging.getLogger(__name__)


def asset_balances(year=None, category=None, partner=None, asset=None):
    """
    Zwraca listę dictów per jednostka finansowa:

        [
            {'asset': Entity(PLN), 'income': Decimal, 'expenses': Decimal,
             'balance': Decimal, 'txn_count': int},
            ...
        ]

    Reguły:
      - income = suma amount dla transakcji typu INCOMING (zawsze dodatnia)
      - expenses = suma amount dla transakcji typu OUTGOING (zawsze dodatnia)
      - balance = income - expenses (może być ujemny)
      - txn_count = liczba transakcji (I + O razem)
      - Encje bez ŻADNEJ transakcji w danym filtrze są pomijane (nie zaśmiecamy UI).
      - Sortowanie: default asset (is_default=True) pierwszy, reszta wg code alfabetycznie.

    Parametr asset przyjmuje finansową encję.
    Filtry łączą się AND: asset_balances(year=2026, asset=pln) → tylko 2026 + tylko PLN.
    """
    qs = Transaction.objects.filter(status=Transaction.Status.POSTED)
    if year is not None:
        qs = qs.filter(payment_received_date__year=year)
    if category is not None:
        qs = qs.filter(category=category)
    if partner is not None:
        qs = qs.filter(partner=partner)
    if asset is not None:
        if not isinstance(asset, Entity) or asset.entity_type != Entity.Type.FINANCIAL_ASSET:
            return []
        qs = qs.filter(entity=asset)

    # Jedno zapytanie group-by entity, conditional sum dla I/O — żeby nie robić 2 query per entity.
    aggregated = qs.values('entity').annotate(income=Sum('amount', filter=Q(type=Transaction.INCOMING)), expenses=Sum('amount', filter=Q(type=Transaction.OUTGOING)), txn_count=Count('id'))

    # Materializujemy do dict, żeby raz pobrać encje zamiast N+1.
    by_entity_id = {row['entity']: row for row in aggregated if row['entity'] is not None}
    entity_objs = {entity.pk: entity for entity in Entity.objects.filter(entity_type=Entity.Type.FINANCIAL_ASSET, pk__in=by_entity_id)}

    result = []
    for entity_id, row in by_entity_id.items():
        entity = entity_objs.get(entity_id)
        if entity is None:
            continue
        income = row['income'] or Decimal('0')
        expenses = row['expenses'] or Decimal('0')
        result.append({'asset': entity, 'income': income, 'expenses': expenses, 'balance': income - expenses, 'txn_count': row['txn_count']})

    # Sort: default first, reszta alfabetycznie po code.
    result.sort(key=lambda r: (not r['asset'].is_default, r['asset'].code))
    return result


def category_breakdown(year=None):
    """
    Pivot kategorie × aktywa dla raportu /bookkeeping/report/.

    Zwraca trójkę (pivot_rows, asset_columns, asset_totals):

      pivot_rows:    [{'category_name': str, 'by_asset': {asset_id: Decimal (net)}}, ...]
                     posortowane alfabetycznie po category_name. Brakujące pary
                     (kategoria, asset) NIE pojawiają się w by_asset — template
                     renderuje '—' dla pustych komórek.
      asset_columns: [Entity, Entity, ...] — kolejność default-first, reszta wg code.
                     Tylko assety które mają jakiekolwiek transakcje w danym roku.
      asset_totals:  {asset_id: Decimal} — suma kolumny (= "Suma roku" w UI).

    Net = INCOMING - OUTGOING (może być ujemny). Kategoria NULL → '—'.

    Filtr year=None oznacza CAŁĄ historię (dla widoku "All Years Summary").
    """
    qs = Transaction.objects.filter(status=Transaction.Status.POSTED)
    if year is not None:
        qs = qs.filter(payment_received_date__year=year)

    # Agregat per (category, entity, type) — jedno query, suma per typ transakcji.
    aggregated = qs.values('category', 'entity', 'type').annotate(total=Sum('amount'))

    # net[(category_id_or_None, entity_id)] = Decimal (income - expenses)
    net = {}
    used_entity_ids = set()
    for row in aggregated:
        entity_id = row['entity']
        if entity_id is None:
            continue
        used_entity_ids.add(entity_id)
        key = (row['category'], entity_id)
        sign = 1 if row['type'] == Transaction.INCOMING else -1
        net[key] = net.get(key, Decimal('0')) + sign * (row['total'] or Decimal('0'))

    # Resolve obiekty: jedno IN-query na Category, jedno na Entity.
    cat_ids = {k[0] for k in net if k[0] is not None}
    cat_map = {c.id: c.name for c in Category.objects.filter(id__in=cat_ids)}
    asset_map = {entity.id: entity for entity in Entity.objects.filter(pk__in=used_entity_ids, entity_type=Entity.Type.FINANCIAL_ASSET)}

    # Asset columns: default first, reszta wg code (spójne z asset_balances).
    asset_columns = sorted(asset_map.values(), key=lambda a: (not a.is_default, a.code))

    # Buduj pivot_rows: dict per kategoria → {category_name, by_asset}
    rows_by_cat = {}
    for (cat_id, asset_id), value in net.items():
        cat_name = cat_map.get(cat_id, '—') if cat_id is not None else '—'
        row = rows_by_cat.setdefault(cat_id, {'category_name': cat_name, 'by_asset': {}})
        # Brakujące pary (zero net) pomijamy żeby template renderował '—' przez `not in`.
        # Edge case: net dokładnie 0 (income == expenses) — wtedy też pomijamy, bo
        # "0,00" i "—" niosą tę samą informację (brak salda netto).
        if value != 0:
            row['by_asset'][asset_id] = value

    # Usuń kategorie które po cleanupie nie mają ŻADNYCH wartości (wszystkie pary 0).
    pivot_rows = [r for r in rows_by_cat.values() if r['by_asset']]
    pivot_rows.sort(key=lambda r: r['category_name'])

    # Sumy kolumn — tylko z niezerowych komórek (te same które trafiły do pivot_rows).
    asset_totals = {}
    for row in pivot_rows:
        for asset_id, value in row['by_asset'].items():
            asset_totals[asset_id] = asset_totals.get(asset_id, Decimal('0')) + value

    # Asset columns ogranicz do tych z niezerowymi totals (consistency: nie pokazuj
    # kolumny w tabeli jeśli wszystkie jej komórki są puste/zerowe).
    asset_columns = [a for a in asset_columns if a.pk in asset_totals]

    return pivot_rows, asset_columns, asset_totals


def _next_payment_date(plan, current_date):
    if plan.recurrence == PaymentPlan.Recurrence.MONTHLY:
        month_index = current_date.year * 12 + current_date.month
        year, month = divmod(month_index, 12)
        month += 1
        day = min(plan.first_due_date.day, monthrange(year, month)[1])
        return current_date.replace(year=year, month=month, day=day)
    if plan.recurrence == PaymentPlan.Recurrence.YEARLY:
        year = current_date.year + 1
        day = min(plan.first_due_date.day, monthrange(year, plan.first_due_date.month)[1])
        return current_date.replace(year=year, month=plan.first_due_date.month, day=day)
    return None


def _ensure_planned_transaction(due, plan):
    if due.cancelled_at or due.is_paid:
        return due.transaction
    return Transaction.objects.get_or_create(
        payment_due=due,
        defaults={
            'type': due.direction,
            'status': Transaction.Status.PLANNED,
            'entity': due.entity,
            'partner': due.partner,
            'category': due.category,
            'amount': due.amount,
            'payment_received_date': due.due_date,
            'note': due.name,
            'author': plan.author,
        },
    )[0]


def _payment_plan_payers(plan):
    has_explicit_selection = plan.debtors.exists() or plan.debtor_partners.exists()
    member_ids = list(plan.debtors.filter(is_active=True, uzytkownik__uid__is_active=True).values_list('pk', flat=True))
    partner_ids = list(plan.debtor_partners.values_list('pk', flat=True))
    if not has_explicit_selection:
        member_ids = list(Uzytkownik.objects.filter(uid__is_active=True).values_list('uid_id', flat=True))
    return member_ids, partner_ids, has_explicit_selection


def ensure_next_payment_periods(plan_id, today=None):
    today = today or timezone.localdate()
    generated = 0
    with db_transaction.atomic():
        plan = PaymentPlan.objects.select_for_update().get(pk=plan_id)
        pending_dues = (
            plan.dues.filter(cancelled_at__isnull=True)
            .filter(Q(payment_transaction__isnull=True) | Q(payment_transaction__status=Transaction.Status.PLANNED))
            .select_related('payment_transaction', 'entity', 'category', 'partner', 'debtor_partner')
        )
        for due in pending_dues:
            _ensure_planned_transaction(due, plan)

        while plan.is_active and plan.next_due_date and (plan.last_generated_date is None or plan.last_generated_date <= today):
            due_date = plan.next_due_date
            defaults = {'name': plan.name, 'direction': plan.direction, 'amount': plan.amount, 'entity': plan.entity, 'category': plan.category, 'partner': plan.partner, 'treasurer': plan.treasurer}
            if plan.direction == PaymentPlan.Direction.INCOMING:
                member_ids, partner_ids, _has_explicit_selection = _payment_plan_payers(plan)
                for member_id in member_ids:
                    due = PaymentDue.objects.get_or_create(plan=plan, due_date=due_date, debtor_id=member_id, defaults=defaults)[0]
                    _ensure_planned_transaction(due, plan)
                for partner_id in partner_ids:
                    due = PaymentDue.objects.get_or_create(plan=plan, due_date=due_date, debtor_partner_id=partner_id, defaults=defaults)[0]
                    _ensure_planned_transaction(due, plan)
            else:
                due = PaymentDue.objects.get_or_create(plan=plan, due_date=due_date, debtor=None, defaults=defaults)[0]
                _ensure_planned_transaction(due, plan)

            plan.last_generated_date = due_date
            if plan.recurrence == PaymentPlan.Recurrence.ONCE:
                plan.next_due_date = None
                plan.is_active = False
            else:
                plan.next_due_date = _next_payment_date(plan, due_date)
            plan.save(update_fields=['last_generated_date', 'next_due_date', 'is_active', 'updated_at'])
            generated += 1
            if due_date > today:
                break
    return generated


def restore_planned_transaction(due_id):
    with db_transaction.atomic():
        due = PaymentDue.objects.select_for_update().select_related('plan').get(pk=due_id)
        return _ensure_planned_transaction(due, due.plan)


@db_transaction.atomic
def update_next_payment_period(plan, today=None):
    today = today or timezone.localdate()
    dues = PaymentDue.objects.filter(plan=plan, due_date__gt=today, cancelled_at__isnull=True).filter(Q(payment_transaction__isnull=True) | Q(payment_transaction__status=Transaction.Status.PLANNED))
    next_due_date = dues.order_by('due_date').values_list('due_date', flat=True).first()
    if next_due_date:
        next_dues = dues.filter(due_date=next_due_date).select_related('payment_transaction')
        next_dues.update(name=plan.name, amount=plan.amount, entity=plan.entity, category=plan.category, partner=plan.partner, treasurer=plan.treasurer, updated_at=timezone.now())
        if plan.direction == PaymentPlan.Direction.INCOMING:
            member_ids, partner_ids, has_explicit_selection = _payment_plan_payers(plan)
            if has_explicit_selection:
                selected_payers = {(member_id, None) for member_id in member_ids} | {(None, partner_id) for partner_id in partner_ids}
                for due in next_dues.select_related('debtor', 'debtor_partner', 'payment_transaction'):
                    if (due.debtor_id, due.debtor_partner_id) not in selected_payers:
                        if due.transaction:
                            due.transaction.delete()
                        due.delete()
                due_defaults = {'name': plan.name, 'direction': plan.direction, 'amount': plan.amount, 'entity': plan.entity, 'category': plan.category, 'partner': plan.partner, 'treasurer': plan.treasurer}
                for member_id in member_ids:
                    due = PaymentDue.objects.get_or_create(plan=plan, due_date=next_due_date, debtor_id=member_id, defaults=due_defaults)[0]
                    _ensure_planned_transaction(due, plan)
                for partner_id in partner_ids:
                    due = PaymentDue.objects.get_or_create(plan=plan, due_date=next_due_date, debtor_partner_id=partner_id, defaults=due_defaults)[0]
                    _ensure_planned_transaction(due, plan)
        for due in next_dues:
            planned_transaction = due.transaction
            if planned_transaction and planned_transaction.status == Transaction.Status.PLANNED:
                planned_transaction.amount = plan.amount
                planned_transaction.entity = plan.entity
                planned_transaction.category = plan.category
                planned_transaction.partner = plan.partner
                planned_transaction.note = plan.name
                planned_transaction.save(update_fields=['amount', 'entity', 'category', 'partner', 'note', 'updated_at'])
            else:
                _ensure_planned_transaction(due, plan)


def delete_payment_plan(plan_id):
    with db_transaction.atomic():
        plan = PaymentPlan.objects.select_for_update().get(pk=plan_id)
        due_ids = list(PaymentDue.objects.select_for_update().filter(plan=plan).values_list('pk', flat=True))
        dues = list(PaymentDue.objects.filter(pk__in=due_ids).select_related('payment_transaction'))
        paid_transaction_ids = []
        planned_transaction_ids = []
        for due in dues:
            transaction = due.transaction
            if transaction is None:
                continue
            if transaction.status == Transaction.Status.POSTED:
                paid_transaction_ids.append(transaction.pk)
            else:
                planned_transaction_ids.append(transaction.pk)

        if planned_transaction_ids:
            Transaction.objects.filter(pk__in=planned_transaction_ids).delete()
        if paid_transaction_ids:
            Transaction.objects.filter(pk__in=paid_transaction_ids).update(payment_due=None, updated_at=timezone.now())
        PaymentDue.objects.filter(plan=plan).delete()
        plan.delete()


def confirm_payment_due(due_id, values, user):
    with db_transaction.atomic():
        due = PaymentDue.objects.select_for_update().select_related('plan').get(pk=due_id)
        existing_transaction = Transaction.objects.filter(payment_due=due).first()
        if existing_transaction and existing_transaction.status == Transaction.Status.POSTED:
            return existing_transaction, False
        if due.cancelled_at:
            raise ValidationError(_('This payment due has been cancelled.'))
        if values['type'] != due.direction:
            raise ValidationError(_('Transaction direction must match the payment due.'))

        transaction = existing_transaction or Transaction(payment_due=due)
        transaction.type = due.direction
        transaction.status = Transaction.Status.POSTED
        transaction.entity = values['entity']
        transaction.partner = values['partner']
        transaction.category = values['category']
        transaction.amount = values['amount']
        transaction.payment_received_date = values['payment_received_date']
        transaction.note = values['note']
        transaction.author = user
        try:
            with db_transaction.atomic():
                transaction.save()
        except IntegrityError:
            existing_transaction = Transaction.objects.filter(payment_due=due).first()
            if existing_transaction:
                return existing_transaction, False
            raise
        transaction_url = build_site_url(reverse('bookkeeping:transaction_detail', kwargs={'pk': transaction.pk}))
        db_transaction.on_commit(lambda: transaction_created.send(sender=Transaction, transaction=transaction, url=transaction_url))
    return transaction, True


def cancel_payment_due(due_id, user):
    with db_transaction.atomic():
        due = PaymentDue.objects.select_for_update().get(pk=due_id)
        if due.is_paid:
            raise ValidationError(_('A paid payment due cannot be cancelled.'))
        if due.cancelled_at is None:
            if due.transaction:
                due.transaction.delete()
            due.cancelled_at = timezone.now()
            due.cancelled_by = user
            due.save(update_fields=['cancelled_at', 'cancelled_by', 'updated_at'])
    return due


def process_payment_reminders(today=None):
    from core.notifications import send_payment_due_email, send_payment_due_push

    today = today or timezone.localdate()
    for plan_id in PaymentPlan.objects.values_list('pk', flat=True):
        ensure_next_payment_periods(plan_id, today=today)

    dues = (
        PaymentDue.objects.filter(due_date__lte=today, cancelled_at__isnull=True)
        .filter(Q(payment_transaction__isnull=True) | Q(payment_transaction__status=Transaction.Status.PLANNED))
        .select_related('plan', 'entity', 'debtor', 'payment_transaction')
        .select_related('treasurer')
        .order_by('due_date', 'pk')
    )
    for due in dues:
        if due.debtor_id:
            recipients = [due.debtor] if due.debtor.is_active else []
        else:
            recipients = [due.treasurer] if due.treasurer and due.treasurer.is_active else []
        if not recipients:
            continue
        due_url = reverse('bookkeeping:payment_due_detail', kwargs={'pk': due.pk})
        title = _('Payment due')
        body = f'{due.name}: {due.amount} {due.entity.symbol} — {due.due_date:%d.%m.%Y}\n{build_site_url(due_url)}'
        for recipient in recipients:
            channels = (PaymentReminderDelivery.Channel.PUSH,) if due.debtor_id else PaymentReminderDelivery.Channel.values
            for channel in channels:
                now = timezone.now()
                stale_before = now - timedelta(minutes=15)
                with db_transaction.atomic():
                    delivery = PaymentReminderDelivery.objects.get_or_create(due=due, recipient=recipient, channel=channel)[0]
                    delivery = PaymentReminderDelivery.objects.select_for_update().get(pk=delivery.pk)
                    if delivery.status in (PaymentReminderDelivery.Status.SENT, PaymentReminderDelivery.Status.SKIPPED):
                        continue
                    if delivery.status == PaymentReminderDelivery.Status.SENDING and delivery.claimed_at and delivery.claimed_at > stale_before:
                        continue
                    delivery.status = PaymentReminderDelivery.Status.SENDING
                    delivery.claimed_at = now
                    delivery.attempts += 1
                    delivery.save(update_fields=['status', 'claimed_at', 'attempts'])
                try:
                    if channel == PaymentReminderDelivery.Channel.EMAIL:
                        sent = send_payment_due_email(recipient, title, body)
                    else:
                        sent = send_payment_due_push(recipient, title, body, due_url, due.pk)
                    PaymentReminderDelivery.objects.filter(pk=delivery.pk).update(
                        status=PaymentReminderDelivery.Status.SENT if sent else PaymentReminderDelivery.Status.SKIPPED, claimed_at=None, sent_at=timezone.now() if sent else None, last_error=''
                    )
                except Exception as error:
                    log.warning('Payment reminder failed due=%s recipient=%s channel=%s error=%s', due.pk, recipient.pk, channel, error, exc_info=True)
                    PaymentReminderDelivery.objects.filter(pk=delivery.pk).update(status=PaymentReminderDelivery.Status.PENDING, claimed_at=None, last_error=str(error)[:500])
