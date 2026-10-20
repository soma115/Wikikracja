import hashlib
import json
import math
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

from .map_data import location_key, normalize_city

GEOCODE_SUCCESS_TTL = 30 * 24 * 60 * 60
GEOCODE_FAILURE_TTL = 15 * 60
NOMINATIM_INTERVAL_SECONDS = 1.1
NOMINATIM_LOCK_KEY = 'wikikracja:map-geocode:request-lock'
NOMINATIM_NEXT_REQUEST_KEY = 'wikikracja:map-geocode:next-request'
CACHE_MISS = object()
RATE_LIMITED = object()


def geocode_location(location):
    """Resolve a city or confirmed street address, caching each normalized key."""
    key = location_key(location)
    if key is None:
        return None

    country_code, city, street, house_number = key
    if street and house_number:
        address_result = _cached_search(
            ('address', country_code, city, street, house_number), {'country_code': country_code, 'city': location['city'], 'street': location['street'], 'house_number': location['house_number']}
        )
        if address_result is RATE_LIMITED:
            return None
        if address_result is not None:
            return address_result

    city_result = _cached_search(('city', country_code, city), {'country_code': country_code, 'city': location['city']})
    return None if city_result is RATE_LIMITED else city_result


def get_cached_coordinates(location):
    """Read known results without causing a request to the geocoder."""
    key = location_key(location)
    if key is None:
        return None

    country_code, city, street, house_number = key
    if street and house_number:
        address_coordinates = _coordinates_from_cache(('address', country_code, city, street, house_number))
        if address_coordinates is not None:
            return address_coordinates
    return _coordinates_from_cache(('city', country_code, city))


def _coordinates_from_cache(key_parts):
    try:
        value = cache.get(_cache_key(key_parts), CACHE_MISS)
    except Exception:
        return None
    return None if value is CACHE_MISS else value


def _cached_search(key_parts, location):
    cache_key = _cache_key(key_parts)
    try:
        cached_result = cache.get(cache_key, CACHE_MISS)
    except Exception:
        return None
    if cached_result is not CACHE_MISS:
        return cached_result

    results = _search_nominatim(location)
    if results is RATE_LIMITED:
        return RATE_LIMITED
    coordinates = _select_result(results, location)
    try:
        cache.set(cache_key, coordinates, GEOCODE_SUCCESS_TTL if coordinates else GEOCODE_FAILURE_TTL)
    except Exception:
        return None
    return coordinates


def _search_nominatim(location):
    endpoint = getattr(settings, 'MAP_GEOCODER_URL', 'https://nominatim.openstreetmap.org/search')
    user_agent = getattr(settings, 'MAP_GEOCODER_USER_AGENT', '')
    parsed_endpoint = urlsplit(endpoint)
    if parsed_endpoint.scheme != 'https' or not parsed_endpoint.netloc or not user_agent:
        return []

    has_exact_address = bool(location.get('street') and location.get('house_number'))
    query = {'format': 'jsonv2', 'addressdetails': 1, 'limit': 5 if has_exact_address else 1, 'countrycodes': location['country_code'].lower(), 'city': location['city']}
    if has_exact_address:
        query['street'] = f"{location['house_number']} {location['street']}"

    if not _wait_for_nominatim_slot():
        return RATE_LIMITED

    request = Request(f'{endpoint}?{urlencode(query)}', headers={'User-Agent': user_agent, 'Accept': 'application/json'})
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _select_result(results, location):
    exact_matches = []
    city_matches = []
    city_centers = []
    for result in results:
        if not isinstance(result, dict):
            continue
        address = result.get('address') or {}
        if not isinstance(address, dict) or _normalize_geocoder_text(address.get('country_code')) != location['country_code'].casefold():
            continue
        if not _result_matches_city(result, address, location['city']):
            continue

        coordinates = _coordinates_from_result(result)
        if coordinates is None:
            continue
        city_matches.append(coordinates)
        if result.get('class') == 'place' and result.get('type') in {'city', 'town', 'village', 'municipality', 'hamlet'}:
            city_centers.append(coordinates)

        if location.get('street') and location.get('house_number') and _result_matches_address(address, location['street'], location['house_number']):
            exact_matches.append(coordinates)

    if location.get('street') and location.get('house_number'):
        confirmed = set(exact_matches)
        return next(iter(confirmed)) if len(confirmed) == 1 else None
    if city_centers:
        return city_centers[0]
    if len(city_matches) == 1:
        return city_matches[0]
    return None


def _result_matches_city(result, address, city):
    expected = normalize_city(city)
    values = [address.get(key, '') for key in ('city', 'town', 'village', 'municipality', 'hamlet')]
    values.append(result.get('name', ''))
    return expected in {_normalize_geocoder_text(value) for value in values if value}


def _result_matches_address(address, street, house_number):
    street_fields = ('road', 'residential', 'pedestrian', 'footway', 'path')
    matched_street = any(_normalize_geocoder_text(address.get(field)) == normalize_city(street) for field in street_fields if address.get(field))
    return matched_street and _normalize_geocoder_text(address.get('house_number')) == normalize_city(house_number)


def _normalize_geocoder_text(value):
    return value.strip().casefold() if isinstance(value, str) else ''


def _coordinates_from_result(result):
    try:
        latitude = float(result['lat'])
        longitude = float(result['lon'])
    except (KeyError, TypeError, ValueError):
        return None
    if math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    return None


def _cache_key(parts):
    digest = hashlib.sha256('|'.join(parts).encode('utf-8')).hexdigest()
    return f'wikikracja:map-geocode:v1:{digest}'


def _wait_for_nominatim_slot():
    token = uuid.uuid4().hex
    lock_deadline = time.monotonic() + 10
    while time.monotonic() < lock_deadline:
        try:
            acquired = cache.add(NOMINATIM_LOCK_KEY, token, timeout=5)
        except Exception:
            return False
        if not acquired:
            time.sleep(0.05)
            continue

        try:
            next_allowed = cache.get(NOMINATIM_NEXT_REQUEST_KEY, 0)
            wait_seconds = next_allowed - time.time()
            if wait_seconds <= 0:
                cache.set(NOMINATIM_NEXT_REQUEST_KEY, time.time() + NOMINATIM_INTERVAL_SECONDS, timeout=60)
                return True
        except Exception:
            return False
        finally:
            try:
                if cache.get(NOMINATIM_LOCK_KEY) == token:
                    cache.delete(NOMINATIM_LOCK_KEY)
            except Exception:
                pass

        time.sleep(min(wait_seconds, 0.25))
    return False
