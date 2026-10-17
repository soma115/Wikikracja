"""
Serwisy aplikacji bookkeeping — agregacje używane przez widoki, pulpit, raporty.

Single source of truth dla "ile mamy w PLN / BTC / EUR / ..." — wszystkie miejsca,
które kiedyś sumowały transakcje per asset (ReportView, pulpit, transaction_list),
docelowo wołają stąd, żeby nie powielać logiki i nie ryzykować mieszania walut.
"""

from decimal import Decimal

from django.db.models import Count, Q, Sum

from resources.models import LEGACY_FINANCIAL_ASSET_SOURCE, Entity, LegacyEntityReference

from .models import Asset, Category, Transaction


def _financial_entity(asset):
    if isinstance(asset, Entity):
        return asset if asset.entity_type == Entity.Type.FINANCIAL_ASSET else None
    if isinstance(asset, Asset):
        reference = LegacyEntityReference.objects.filter(source_model=LEGACY_FINANCIAL_ASSET_SOURCE, source_pk=asset.pk).select_related('entity').first()
        return reference.entity if reference else None
    return None


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

    Parametr asset przyjmuje finansową encję; stary obiekt Asset jest akceptowany
    przejściowo przez mapowanie LegacyEntityReference.
    Filtry łączą się AND: asset_balances(year=2026, asset=pln) → tylko 2026 + tylko PLN.
    """
    qs = Transaction.objects.all()
    if year is not None:
        qs = qs.filter(payment_received_date__year=year)
    if category is not None:
        qs = qs.filter(category=category)
    if partner is not None:
        qs = qs.filter(partner=partner)
    if asset is not None:
        entity = _financial_entity(asset)
        if entity is None:
            return []
        qs = qs.filter(entity=entity)

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
    qs = Transaction.objects.all()
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
