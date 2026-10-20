import math
from urllib.parse import urlencode

from django.db.models import Q
from django.urls import reverse

from bookkeeping.models import Partner
from resources.models import Entity
from zzz.templatetags.citizen_filters import user_display_name

from .models import Country, Uzytkownik

MAP_TYPES = frozenset({'citizen', 'partner', 'resource'})
COUNTRY_CODE_ALIASES = {'polska': 'PL'}


def normalize_country(value, countries=None):
    """Resolve a partner's legacy country text using exact catalog names/codes only."""
    normalized = (value or '').strip().casefold()
    if not normalized:
        return None
    if normalized in COUNTRY_CODE_ALIASES:
        return COUNTRY_CODE_ALIASES[normalized]

    if countries is None:
        countries = Country.objects.values_list('code', 'name')
    for code, name in countries:
        if normalized in (code.casefold(), name.strip().casefold()):
            return code.upper()
    return None


def normalize_city(value):
    return (value or '').strip().casefold()


def location_key(location):
    country_code = (location.get('country_code') or '').strip().upper()
    city = normalize_city(location.get('city'))
    if not country_code or not city:
        return None

    street = (location.get('street') or '').strip()
    house_number = (location.get('house_number') or '').strip()
    if street and house_number:
        return country_code, city, street.casefold(), house_number.casefold()
    return country_code, city, '', ''


def _address_text(*, street='', house_number='', apartment_number='', city='', country='', legacy_address=''):
    structured = ' '.join(part for part in (street.strip(), house_number.strip()) if part)
    if apartment_number:
        structured = f'{structured}, {apartment_number.strip()}' if structured else apartment_number.strip()

    parts = [part for part in (legacy_address.strip(), structured, city.strip(), country.strip()) if part]
    return ', '.join(dict.fromkeys(parts))


def _location(country_code, city, street='', house_number=''):
    if not (street and house_number):
        street = house_number = ''
    return {'country_code': country_code or '', 'city': (city or '').strip(), 'street': (street or '').strip(), 'house_number': (house_number or '').strip()}


def get_map_location_records():
    """Collect explicit, non-financial map records; never include contact or notes fields."""
    records = []

    profiles = (
        Uzytkownik.objects.filter(uid__is_active=True)
        .exclude(city__isnull=True)
        .exclude(city='')
        .select_related('uid', 'country')
        .only('id', 'city', 'country__code', 'country__name', 'street', 'house_number', 'apartment_number', 'uid__id', 'uid__username', 'uid__first_name', 'uid__last_name')
    )
    for profile in profiles:
        if not profile.city.strip():
            continue
        records.append(
            {
                'type': 'citizen',
                'name': user_display_name(profile.uid),
                'address': _address_text(street=profile.street, house_number=profile.house_number, apartment_number=profile.apartment_number, city=profile.city, country=profile.country.name),
                'url': reverse('obywatele:obywatele_szczegoly', kwargs={'pk': profile.uid_id}),
                'location': _location(profile.country.code, profile.city, profile.street, profile.house_number),
            }
        )

    country_rows = list(Country.objects.values_list('code', 'name'))
    countries_by_code = {code: name for code, name in country_rows}
    partners = Partner.objects.only('id', 'name', 'address', 'city', 'country', 'street', 'house_number', 'apartment_number')
    for partner in partners:
        country_code = normalize_country(partner.country, country_rows)
        country_name = countries_by_code.get(country_code, partner.country or '')
        records.append(
            {
                'type': 'partner',
                'name': partner.name,
                'address': _address_text(
                    street=partner.street, house_number=partner.house_number, apartment_number=partner.apartment_number, city=partner.city or '', country=country_name, legacy_address=partner.address or ''
                ),
                'url': reverse('bookkeeping:partner_detail', kwargs={'pk': partner.pk}),
                'location': _location(country_code, partner.city, partner.street, partner.house_number),
            }
        )

    resources = (
        Entity.objects.filter(entity_type=Entity.Type.RESOURCE, is_closed=False)
        .filter(Q(is_community_owned=True) | Q(assigned_member__uid__is_active=True))
        .exclude(country__isnull=True)
        .exclude(city='')
        .select_related('country')
        .only('name', 'city', 'country__code', 'country__name')
    )
    for resource in resources:
        if not resource.city.strip():
            continue
        records.append(
            {
                'type': 'resource',
                'name': resource.name,
                'address': _address_text(city=resource.city, country=resource.country.name),
                'url': f"{reverse('bookkeeping:resource_list')}?{urlencode({'q': resource.name})}",
                'location': _location(resource.country.code, resource.city),
            }
        )

    return records


def build_map_payload(records, coordinate_for_location, *, show_details):
    """Make privacy-specific payloads while resolving each precise location once."""
    resolved = {}
    guest_points = set()
    markers = {}
    unmapped = []

    for record in records:
        if record.get('type') not in MAP_TYPES:
            continue

        key = location_key(record.get('location') or {})
        if key is None:
            coordinates = None
        elif key not in resolved:
            resolved[key] = coordinate_for_location(record['location'])
            coordinates = resolved[key]
        else:
            coordinates = resolved[key]

        coordinates = _validated_coordinates(coordinates)
        if coordinates is None:
            if show_details:
                unmapped.append({**{key: record[key] for key in ('type', 'name', 'address', 'url')}, 'unmapped': True})
            continue

        latitude, longitude = coordinates
        if not show_details:
            guest_points.add((latitude, longitude))
            continue

        entry = {key: record[key] for key in ('name', 'address', 'url')}
        marker_key = (record['type'], latitude, longitude)
        marker = markers.setdefault(marker_key, {'type': record['type'], 'latitude': latitude, 'longitude': longitude, 'items': []})
        marker['items'].append(entry)

    if not show_details:
        return {'points': [{'lat': latitude, 'lon': longitude} for latitude, longitude in sorted(guest_points)]}

    return {'markers': list(markers.values()), 'unmapped': unmapped}


def _validated_coordinates(value):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        return None
    try:
        latitude, longitude = map(float, value)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude
