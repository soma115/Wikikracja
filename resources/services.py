import unicodedata
from collections import defaultdict

from django.db.models import Q

from .models import Entity


def search_entities(user, *, entity_type='', query='', resource_kind='', city='', voivodeship='', country='', status='active', assignment='all'):
    """Search entities without exposing inactive-member or unrelated closed listings."""
    profile = getattr(user, 'uzytkownik', None)
    queryset = Entity.objects.select_related('country', 'assigned_member__uid', 'assigned_member__country', 'assigned_member__voivodeship')

    resource_visibility = Q(entity_type=Entity.Type.RESOURCE, is_closed=False) & (Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True))
    if profile and user.is_active:
        resource_visibility |= Q(entity_type=Entity.Type.RESOURCE, is_closed=True) & (Q(author=user) | Q(assigned_member=profile) | Q(is_community_owned=True))
    queryset = queryset.filter(Q(entity_type=Entity.Type.FINANCIAL_ASSET) | resource_visibility)

    valid_entity_types = {value for value, _ in Entity.Type.choices}
    if entity_type in valid_entity_types:
        queryset = queryset.filter(entity_type=entity_type)
    elif entity_type != 'all':
        queryset = queryset.filter(entity_type=Entity.Type.RESOURCE)

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(code__icontains=query)
            | Q(symbol__icontains=query)
            | Q(assigned_member__uid__username__icontains=query)
            | Q(assigned_member__uid__first_name__icontains=query)
            | Q(assigned_member__uid__last_name__icontains=query)
        )
    if resource_kind in Entity.ResourceKind.values:
        queryset = queryset.filter(entity_type=Entity.Type.RESOURCE, resource_kind=resource_kind)
    if city:
        queryset = queryset.filter(Q(city__icontains=city) | Q(assigned_member__city__icontains=city))
    if voivodeship:
        queryset = queryset.filter(assigned_member__voivodeship__name__iexact=voivodeship)
    if country:
        queryset = queryset.filter(Q(country__name__icontains=country) | Q(assigned_member__country__name__icontains=country))

    if status == 'closed':
        queryset = queryset.filter(entity_type=Entity.Type.RESOURCE, is_closed=True)
    elif status != 'all':
        queryset = queryset.filter(is_closed=False)

    if assignment == Entity.AssignmentScope.MEMBER:
        queryset = queryset.filter(assigned_member__isnull=False)
    elif assignment == Entity.AssignmentScope.COMMUNITY:
        queryset = queryset.filter(is_community_owned=True)
    elif assignment == Entity.AssignmentScope.UNASSIGNED:
        queryset = queryset.filter(assigned_member__isnull=True, is_community_owned=False)

    return queryset.order_by('entity_type', 'resource_kind', 'name', 'pk')


def _normalized_resource_name(value):
    return ' '.join(unicodedata.normalize('NFC', value or '').casefold().split())


def match_active_offers_for_needs(user, profile):
    """Return public active offers with the same normalized name as visible active needs."""
    if not user.is_active or profile is None:
        return []

    public_active = Entity.objects.filter(entity_type=Entity.Type.RESOURCE, is_closed=False).filter(Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True))
    needs = list(public_active.filter(resource_kind=Entity.ResourceKind.NEED).filter(Q(author=user) | Q(assigned_member=profile) | Q(is_community_owned=True)).order_by('name', 'pk'))
    if not needs:
        return []

    offers_by_name = defaultdict(list)
    offers = public_active.exclude(resource_kind=Entity.ResourceKind.NEED).select_related('assigned_member__uid').order_by('name', 'pk')
    for offer in offers:
        normalized_name = _normalized_resource_name(offer.name)
        if normalized_name:
            offers_by_name[normalized_name].append(offer)

    return [{'need': need, 'offers': offers_by_name[normalized_name]} for need in needs if (normalized_name := _normalized_resource_name(need.name)) in offers_by_name]
