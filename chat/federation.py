"""Small HTTP protocol for trusted Wikikracja instance-to-instance chat."""

import asyncio
import hashlib
import ipaddress
import json
import logging
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import gettext_lazy as gettext

from core.richtext import strip_tags
from site_settings.params import get_param
from zzz.templatetags.citizen_filters import user_display_name

from .models import Message, Room

log = logging.getLogger(__name__)

FEDERATION_SOURCE = 'federation'
FEDERATION_MESSAGE_PATH = 'chat/federation/message/'
FEDERATION_REACTION_PATH = 'chat/federation/reaction/'
FEDERATION_READ_PATH = 'chat/federation/read/'
FEDERATION_INFO_PATH = 'chat/federation/info/'
FEDERATION_TIMEOUT = 5
FEDERATION_MAX_BODY = 64 * 1024
FEDERATION_STATUS_TTL = 60


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_federation_opener = build_opener(_NoRedirectHandler)


def normalize_instance_url(value):
    """Return a canonical origin URL or raise ValueError."""
    raw = (value or '').strip()
    parsed = urlsplit(raw)
    allowed_schemes = {'https'} | ({'http'} if settings.DEBUG else set())
    if parsed.scheme not in allowed_schemes or not parsed.hostname:
        raise ValueError(gettext('Use a valid HTTPS instance address.'))
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ValueError(gettext('Enter only the instance address, without a path.'))
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(gettext('The instance address contains an invalid port.')) from exc
    return urlunsplit((parsed.scheme, parsed.netloc, '', '', '')).rstrip('/')


def instance_endpoint(instance_url, path):
    return f'{instance_url.rstrip("/")}/{path}'


def local_instance_url():
    domain = getattr(settings, 'SITE_DOMAIN', '')
    if not domain:
        return ''
    if '://' not in domain:
        domain = f'{"http" if settings.DEBUG else "https"}://{domain}'
    try:
        return normalize_instance_url(domain)
    except ValueError:
        log.warning('Invalid SITE_DOMAIN configured for federation: %s', domain)
        return ''


def local_instance_name():
    return get_param('site_name') or getattr(settings, 'SITE_NAME', '') or local_instance_url()


def _is_private_hostname(hostname):
    try:
        return ipaddress.ip_address(hostname).is_private
    except ValueError:
        return hostname.lower() in {'localhost', 'localhost.localdomain'}


def validate_outbound_host(instance_url):
    """Reject obvious SSRF targets before making a server-side request."""
    hostname = urlsplit(instance_url).hostname
    if not hostname or _is_private_hostname(hostname):
        raise ValueError(gettext('The instance address cannot point to a local network.'))


def _read_json(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode('utf-8')
    request = Request(url, data=data, headers={'Accept': 'application/json', 'Content-Type': 'application/json'} if data else {'Accept': 'application/json'}, method='POST' if data else 'GET')
    with _federation_opener.open(request, timeout=FEDERATION_TIMEOUT) as response:
        body = response.read(FEDERATION_MAX_BODY + 1)
        if len(body) > FEDERATION_MAX_BODY:
            raise ValueError('Federation response is too large')
        if response.status != 200:
            raise ValueError(f'Federation returned HTTP {response.status}')
        return json.loads(body.decode('utf-8'))


def discover_instance(instance_url):
    validate_outbound_host(instance_url)
    response = _read_json(instance_endpoint(instance_url, FEDERATION_INFO_PATH))
    name = str(response.get('name') or '').strip()[:255]
    if not name:
        raise ValueError(gettext('The remote instance did not provide a group name.'))
    return name


def refresh_federated_status(room, force=False):
    """Refresh the cached peer-consent and transport status for one room."""
    if not room.federated_instance_url:
        return room
    now = timezone.now()
    if not force and room.federation_last_checked_at and (now - room.federation_last_checked_at).total_seconds() < FEDERATION_STATUS_TTL:
        return room

    peer_configured = False
    communication_ok = False
    last_communication = room.federation_last_communication_at
    try:
        source_url = local_instance_url()
        if not source_url:
            raise ValueError('Local instance URL is not configured')
        validate_outbound_host(room.federated_instance_url)
        status_url = instance_endpoint(room.federated_instance_url, FEDERATION_INFO_PATH)
        status_url = f'{status_url}?{urlencode({"source_url": source_url})}'
        response = _read_json(status_url)
        peer_configured = bool(response.get('accepts_source_url'))
        communication_ok = True
        last_communication = now
    except (OSError, URLError, ValueError, TimeoutError) as exc:
        log.info('Federation status check failed for %s from %s: %s', room.federated_instance_url, local_instance_url(), exc)

    room.federation_peer_configured = peer_configured
    room.federation_communication_ok = communication_ok
    room.federation_last_checked_at = now
    room.federation_last_communication_at = last_communication
    room.save(update_fields=['federation_peer_configured', 'federation_communication_ok', 'federation_last_checked_at', 'federation_last_communication_at'])
    return room


def ensure_federated_room(instance_url, name=''):
    """Create or reactivate one local room for a configured remote instance."""
    remote_name = (name or instance_url).strip()[:255]
    if Room.objects.filter(title=remote_name).exclude(federated_instance_url=instance_url).exists():
        hostname = urlsplit(instance_url).hostname or instance_url
        remote_name = f'{remote_name} ({hostname})'[:255]
    room, _created = Room.objects.get_or_create(
        federated_instance_url=instance_url, defaults={'title': remote_name, 'federated_instance_name': remote_name, 'source_app': FEDERATION_SOURCE, 'public': True, 'protected': True}
    )
    changed = []
    if room.source_app != FEDERATION_SOURCE:
        room.source_app = FEDERATION_SOURCE
        changed.append('source_app')
    if room.federated_instance_name != remote_name:
        room.federated_instance_name = remote_name
        changed.append('federated_instance_name')
    if room.title != remote_name and not room.messages.exists():
        room.title = remote_name
        changed.append('title')
    if room.archived:
        room.archived = False
        changed.append('archived')
    if changed:
        room.save(update_fields=changed)
    room.allowed.set(User.objects.filter(is_active=True))
    return room


def deactivate_federated_room(instance_url):
    Room.objects.filter(federated_instance_url=instance_url).update(archived=True)


def get_configured_room(source_url):
    try:
        normalized = normalize_instance_url(source_url)
    except ValueError:
        return None
    return Room.objects.filter(federated_instance_url=normalized, source_app=FEDERATION_SOURCE, archived=False).first()


def make_federation_message_id(source_url, source_message_id):
    return hashlib.sha256(f'{source_url}\0{source_message_id}'.encode('utf-8')).hexdigest()


@database_sync_to_async
def _local_sender_name(message_id):
    message = Message.objects.select_related('sender').get(pk=message_id)
    if message.anonymous:
        return 'Anonymous'
    if message.sender is None:
        return 'System'
    return user_display_name(message.sender)


@database_sync_to_async
def _message_federation_reference(message_id):
    message = Message.objects.get(pk=message_id)
    source_url = message.federation_source_url or local_instance_url()
    source_message_id = message.federation_source_message_id or str(message.id)
    return source_url, source_message_id


async def _deliver_event(room, path, payload):
    if not room.federated_instance_url:
        return
    validate_outbound_host(room.federated_instance_url)
    await asyncio.to_thread(_read_json, instance_endpoint(room.federated_instance_url, path), payload)


async def deliver_message(room, message):
    """Send a local message to its configured peer without blocking chat."""
    try:
        source_url = local_instance_url()
        if not source_url:
            log.warning('Cannot federate message %s: local instance URL is not configured', message.id)
            return
        sender_name = await _local_sender_name(message.id)
        source_name = await database_sync_to_async(local_instance_name)()
        payload = {'source_url': source_url, 'source_name': source_name, 'source_message_id': str(message.id), 'sender_name': sender_name, 'message': strip_tags(message.text)}
        await _deliver_event(room, FEDERATION_MESSAGE_PATH, payload)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception('Federated message %s could not be sent to %s', message.id, room.federated_instance_url)


@database_sync_to_async
def federated_actor_name(user_id):
    user = User.objects.select_related('uzytkownik').get(pk=user_id)
    return user_display_name(user)


def schedule_federated_event(coroutine):
    task = asyncio.create_task(coroutine)
    task.add_done_callback(_log_federated_event_error)
    return task


def _log_federated_event_error(task):
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception:
        log.exception('Federated event task failed')


async def deliver_reaction(room, message_id, reaction, added, actor_id, actor_name):
    try:
        source_url = local_instance_url()
        message_source_url, message_source_id = await _message_federation_reference(message_id)
        payload = {
            'source_url': source_url,
            'message_source_url': message_source_url,
            'message_source_id': message_source_id,
            'reaction': reaction,
            'added': bool(added),
            'actor_id': str(actor_id),
            'actor_name': actor_name,
        }
        log.info('Sending federated reaction target=%s reaction=%s message=%s', room.federated_instance_url, reaction, message_id)
        await _deliver_event(room, FEDERATION_REACTION_PATH, payload)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception('Federated reaction for message %s could not be sent to %s', message_id, room.federated_instance_url)


async def deliver_read(room, message_id, actor_id, actor_name):
    try:
        source_url = local_instance_url()
        message_source_url, message_source_id = await _message_federation_reference(message_id)
        payload = {'source_url': source_url, 'message_source_url': message_source_url, 'message_source_id': message_source_id, 'actor_id': str(actor_id), 'actor_name': actor_name}
        log.info('Sending federated read target=%s message=%s', room.federated_instance_url, message_id)
        await _deliver_event(room, FEDERATION_READ_PATH, payload)
    except asyncio.CancelledError:
        raise
    except Exception:
        log.exception('Federated read marker for message %s could not be sent to %s', message_id, room.federated_instance_url)


def _find_federated_message(source_url, message_source_url, message_source_id):
    local_url = local_instance_url()
    if message_source_url == local_url:
        try:
            message_id = int(message_source_id)
        except (TypeError, ValueError):
            return None
        return Message.objects.filter(room__federated_instance_url=source_url, pk=message_id).first()
    return Message.objects.filter(federation_source_url=message_source_url, federation_source_message_id=str(message_source_id)).first()


def _federated_read_by_payload(message):
    from core.presence import presence_data
    from zzz.templatetags.citizen_filters import citizen_color_class, user_initials

    entries = []
    for entry in message.read_by.select_related('user__uzytkownik').order_by('id'):
        user = entry.user
        entries.append(
            {
                'user_id': user.id,
                'username': user.username,
                'display_name': user_display_name(user),
                'initials': user_initials(user),
                'avatar_url': '/static/home/images/favicon.ico',
                'citizen_color_class': citizen_color_class(user.username),
                **presence_data(user),
            }
        )
    for entry in message.federated_read_by or []:
        if isinstance(entry, dict) and entry.get('display_name'):
            display_name = str(entry['display_name'])
            entries.append(
                {
                    'user_id': None,
                    'username': display_name,
                    'display_name': display_name,
                    'initials': display_name[:2].upper(),
                    'avatar_url': '/static/home/images/anonymous.svg',
                    'citizen_color_class': citizen_color_class(display_name),
                    'presence_status': 'red',
                    'presence_source': '',
                    'presence_timestamp': None,
                }
            )
    return entries


def apply_federated_reaction(source_url, message_source_url, message_source_id, reaction, added, actor_id, actor_name):
    message = _find_federated_message(source_url, message_source_url, message_source_id)
    if message is None or reaction not in {'bulb', 'question', 'upvote', 'downvote'}:
        return None
    reactions = message.reactions if isinstance(message.reactions, dict) else {}
    actor_key = f'{source_url}:{actor_id}'
    values = list(reactions.get(reaction, []))
    if added and actor_key not in values:
        values.append(actor_key)
    if not added:
        values = [value for value in values if value != actor_key]
    reactions[reaction] = values
    if reaction in {'upvote', 'downvote'}:
        opposite = 'downvote' if reaction == 'upvote' else 'upvote'
        reactions[opposite] = [value for value in reactions.get(opposite, []) if value != actor_key]
    message.reactions = reactions
    message.save(update_fields=['reactions'])
    return message, {'bulb': len(reactions.get('bulb', [])), 'question': len(reactions.get('question', [])), 'upvotes': len(reactions.get('upvotes', [])), 'downvotes': len(reactions.get('downvotes', []))}


def apply_federated_read(source_url, message_source_url, message_source_id, actor_id, actor_name):
    message = _find_federated_message(source_url, message_source_url, message_source_id)
    if message is None:
        return None
    entries = list(message.federated_read_by or [])
    key = (source_url, str(actor_id))
    if not any((entry.get('source_url'), str(entry.get('actor_id'))) == key for entry in entries if isinstance(entry, dict)):
        entries.append({'source_url': source_url, 'actor_id': str(actor_id), 'display_name': str(actor_name)[:255]})
        message.federated_read_by = entries
        message.save(update_fields=['federated_read_by'])
    return message, _federated_read_by_payload(message)


def validate_incoming_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid federation payload')
    source_url = normalize_instance_url(payload.get('source_url'))
    source_message_id = str(payload.get('source_message_id') or '').strip()
    sender_name = str(payload.get('sender_name') or '').strip()
    message = str(payload.get('message') or '')
    if not source_message_id or len(source_message_id) > 100 or not sender_name or len(sender_name) > 255 or not message or len(message) > 40000:
        raise ValueError('Invalid federation payload')
    return source_url, source_message_id, sender_name, message
