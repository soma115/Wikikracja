import io
import json
import logging
import os
import uuid
from datetime import timedelta as td

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError
from django.db.models import Count, Exists, OuterRef, Prefetch
from django.db.models.functions import Lower
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
from PIL import Image

from chat.forms import GuestMessageForm, RoomForm
from chat.i18n import get_translations
from chat.models import Room
from chat.services import send_message
from site_settings.params import get_param

log = logging.getLogger(__name__)


@login_required
def open_dm(request: HttpRequest, pk: int):
    target = get_object_or_404(User, pk=pk, is_active=True)
    if target == request.user:
        return redirect('chat:chat')

    room = Room.find_with_users(request.user, target)
    if room is None:
        title = '-'.join(sorted([request.user.username, target.username]))
        try:
            room = Room.objects.create(title=title, public=False)
        except IntegrityError:
            room = Room.objects.get(title__iexact=title)
        room.allowed.set((request.user, target))

    if room.archived:
        room.archived = False
        room.save(update_fields=['archived'])

    return redirect(f"{reverse('chat:chat')}#room_id={room.id}")


@login_required
def add_room(request: HttpRequest):
    """
    Add public chat room
    """
    if request.method != 'POST':
        return render(request, 'chat/add.html', {'form': RoomForm()})

    form = RoomForm(request.POST)
    if not form.is_valid():
        return render(request, 'chat/add.html', {'form': form})

    room = form.save(commit=False)
    room.last_activity = timezone.now()
    room.save()

    # Allow active user access to the new public room
    active_users = User.objects.filter(is_active=True)
    room.allowed.set(active_users)

    return redirect(f"{reverse('chat:chat')}#room_id={room.id}")


def _public_room_prefetch():
    # Public rooms can have hundreds of `allowed` users — keep that prefetch lean.
    return [Prefetch('allowed', queryset=User.objects.only('id', 'username')), Prefetch('muted_by', queryset=User.objects.only('id'))]


def _private_room_prefetch():
    # Private (DM) rooms need the other user's avatar — pull uzytkownik in the same query.
    return [Prefetch('allowed', queryset=User.objects.select_related('uzytkownik')), Prefetch('muted_by', queryset=User.objects.only('id'))]


@login_required
def chat(request: HttpRequest):
    """
    Root page view. This is essentially a single-page app, if you ignore the
    login and admin parts.
    """
    base_rooms = (
        Room.objects.filter(allowed=request.user.id)
        .select_related('last_message_sender')
        .annotate(messages_count=Count('messages'), is_seen=Exists(Room.seen_by.through.objects.filter(room_id=OuterRef('pk'), user_id=request.user.id)))
        .order_by(Lower('title'))
    )

    public_rooms_active = base_rooms.filter(public=True, archived=False, source_app='').prefetch_related(*_public_room_prefetch())
    public_rooms_archived = base_rooms.filter(public=True, archived=True, source_app='').prefetch_related(*_public_room_prefetch())

    private_active = base_rooms.filter(public=False, archived=False).prefetch_related(*_private_room_prefetch())
    private_archived = base_rooms.filter(public=False, archived=True).prefetch_related(*_private_room_prefetch())

    tasks_tree_active = base_rooms.filter(source_app='tasks', archived=False).prefetch_related(*_public_room_prefetch()).order_by('source_object_id')
    tasks_tree_archived = base_rooms.filter(source_app='tasks', archived=True).prefetch_related(*_public_room_prefetch()).order_by('source_object_id')

    votes_tree_active = base_rooms.filter(source_app='glosowania', archived=False).prefetch_related(*_public_room_prefetch()).order_by('source_object_id')
    votes_tree_archived = base_rooms.filter(source_app='glosowania', archived=True).prefetch_related(*_public_room_prefetch()).order_by('source_object_id')

    posts_tree_active = base_rooms.filter(source_app='board', archived=False).prefetch_related(*_public_room_prefetch()).order_by('source_object_id')
    posts_tree_archived = base_rooms.filter(source_app='board', archived=True).prefetch_related(*_public_room_prefetch()).order_by('source_object_id')

    return render(
        request,
        "chat/chat.html",
        {
            'translations': get_translations(),
            'public_rooms_active': public_rooms_active,
            'public_rooms_archived': public_rooms_archived,
            'tasks_tree_active': tasks_tree_active,
            'tasks_tree_archived': tasks_tree_archived,
            'votes_tree_active': votes_tree_active,
            'votes_tree_archived': votes_tree_archived,
            'posts_tree_active': posts_tree_active,
            'posts_tree_archived': posts_tree_archived,
            'private_active': private_active,
            'private_archived': private_archived,
            'user': request.user,
            'ARCHIVE_PUBLIC_CHAT_ROOM': td(days=get_param('archive_public_chat_room')).days,
            'DELETE_PUBLIC_CHAT_ROOM': td(days=get_param('delete_public_chat_room')).days,
            'MESSAGE_MAX_LENGTH': settings.MESSAGE_MAX_LENGTH,
        },
    )


def check_image_type(file_path):
    try:
        with Image.open(file_path) as img:
            return img.format.lower()
    except Exception:
        return None


MAX_LONG_SIDE = 1920


@login_required
def upload_image(request: HttpRequest):
    filenames = []
    for image in request.FILES.getlist('images'):
        if check_image_type(image) is None:
            return JsonResponse({'error': 'bad type'})

        image.seek(0)
        if image.size > (settings.UPLOAD_IMAGE_MAX_SIZE_MB * 1000000):
            return JsonResponse({'error': 'file too big'})

        image.seek(0)
        with Image.open(image) as img:
            img = img.convert('RGBA') if img.mode in ('RGBA', 'LA', 'P') else img.convert('RGB')
            if max(img.width, img.height) > MAX_LONG_SIDE:
                img.thumbnail((MAX_LONG_SIDE, MAX_LONG_SIDE), Image.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format='WEBP', quality=85, method=4)
            file_bytes = buffer.getvalue()

        filename = f"{uuid.uuid4()}.webp"
        path = default_storage.save(f"uploads/{filename}", ContentFile(file_bytes))
        filenames.append(os.path.basename(path))

    return JsonResponse({'filenames': filenames})


@login_required
def unread_count(request: HttpRequest):
    from chat.services import get_unread_count_for_user

    count = get_unread_count_for_user(request.user)
    return JsonResponse({"count": count})


@login_required
def rename_room(request: HttpRequest, room_id: int):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        new_title = (json.loads(request.body).get('title') or '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    room = get_object_or_404(Room, id=room_id, public=True, protected=False)
    if not room.allowed.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Access denied'}, status=403)

    form = RoomForm(data={'title': new_title}, instance=room)
    if not form.is_valid():
        errors = form.errors.get('title', [])
        return JsonResponse({'error': errors[0] if errors else 'Błąd walidacji.'}, status=400)

    old_title = Room.objects.get(id=room_id).title
    room = form.save()
    if room.title != old_title:
        log.info(f"Room {room_id} renamed from '{old_title}' to '{room.title}' by user {request.user.id}")
        async_to_sync(send_message)(room, f'📝 {request.user.username} zmienił(a) nazwę pokoju z "{old_title}" na "{room.title}".', sender=None, anonymous=False, linkify=False)
    return JsonResponse({'success': True, 'title': room.title})


@require_http_methods(['GET', 'POST'])
def guest_message(request: HttpRequest):
    """Anonymous guest message submission to the Inbox room."""
    if request.method == 'POST':
        form = GuestMessageForm(request.POST)
        if form.is_valid():
            # Rate limit by remote IP
            remote_ip = request.META.get('REMOTE_ADDR') or 'unknown'
            cache_key = f'guest_message_limit:{remote_ip}'
            attempts = cache.get(cache_key, 0)
            if attempts >= 3:
                form.add_error(None, _('Too many messages. Please try again later.'))
            else:
                inbox = Room.objects.filter(is_inbox=True, public=True).first()
                if inbox is None:
                    form.add_error(None, _('The public inbox is not available at the moment.'))
                else:
                    message_text = f"Od: {form.cleaned_data['guest_name']} ({form.cleaned_data['guest_email']})\n\n{form.cleaned_data['message']}"
                    async_to_sync(send_message)(inbox, message_text, sender=None, anonymous=True, guest_email=form.cleaned_data['guest_email'], guest_name=form.cleaned_data['guest_name'], linkify=True)
                    cache.set(cache_key, attempts + 1, timeout=300)
                    return render(request, 'chat/guest_message.html', {'form': GuestMessageForm(), 'sent': True})
    else:
        form = GuestMessageForm()

    return render(request, 'chat/guest_message.html', {'form': form, 'sent': False})
