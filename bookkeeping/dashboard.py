from decimal import Decimal

from django.db.models import Q

from resources.models import Entity

from .services import asset_balances


def get_context(user, month_param: str = '') -> dict:
    """Return dashboard widgets for community finances."""
    resources = Entity.objects.filter(entity_type=Entity.Type.RESOURCE, is_closed=False)

    def active_owner_count(kind):
        return resources.filter(resource_kind=kind).filter(Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True)).values('is_community_owned', 'assigned_member_id').distinct().count()

    give_away_count = active_owner_count(Entity.ResourceKind.GIVE)
    borrow_count = active_owner_count(Entity.ResourceKind.BORROW)
    for_sale_count = active_owner_count(Entity.ResourceKind.SALE)
    resource_counts = {'give_away_count': give_away_count, 'borrow_count': borrow_count, 'for_sale_count': for_sale_count}

    default_asset = Entity.get_default_financial_asset()
    if default_asset is None:
        return {'default_asset': None, 'default_income': None, 'default_expenses': None, 'default_balance': None, 'default_symbol': None, **resource_counts}

    balances = asset_balances(asset=default_asset)
    if balances:
        row = balances[0]
        default_income, default_expenses, default_balance = row['income'], row['expenses'], row['balance']
    else:
        default_income = default_expenses = default_balance = Decimal('0')

    return {'default_asset': default_asset, 'default_income': default_income, 'default_expenses': default_expenses, 'default_balance': default_balance, 'default_symbol': default_asset.symbol, **resource_counts}
