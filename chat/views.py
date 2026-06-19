import io
import json
import logging
import uuid
from datetime import timedelta as td

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, Exists, OuterRef, Prefetch
from django.db.models.functions import Lower
from django.dispatch import receiver
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from PIL import Image

from chat.forms import RoomForm
from chat.models import Room
from chat.utils import send_message_to_room
from chat.signals import user_accepted, user_deleted
from glosowania.models import Decyzja
from tasks.models import Task

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
        return render(request, 'chat/add.html', {
            'form': RoomForm()
        })

    form = RoomForm(request.POST)
    if not form.is_valid():
        return render(request, 'chat/add.html', {
            'form': form
        })

    room = form.save(commit=False)
    room.last_activity = timezone.now()
    room.save()

    # Allow active user access to new public rooms
    active_users = User.objects.filter(is_active=True)
    public_rooms = Room.objects.filter(public=True)
    for pr in public_rooms:
        pr.allowed.set(active_users)

    return redirect(f"{reverse('chat:chat')}#room_id={room.id}")


def _chat_room_prefetches():
    return [
        Prefetch('chat_room__seen_by', queryset=User.objects.only('id')),
        Prefetch('chat_room__muted_by', queryset=User.objects.only('id')),
    ]


@login_required
def chat(request: HttpRequest):
    """
    Root page view. This is essentially a single-page app, if you ignore the
    login and admin parts.
    """
    base_rooms = Room.objects.filter(allowed=request.user.id).select_related('last_message_sender').annotate(messages_count=Count('messages'), is_seen=Exists(Room.seen_by.through.objects.filter(room_id=OuterRef('pk'), user_id=request.user.id))).order_by(Lower("title"))

    # Public rooms can have hundreds of `allowed` users — keep that prefetch lean.
    public_allowed = Prefetch('allowed', queryset=User.objects.only('id', 'username'))
    # Private (DM) rooms need the other user's avatar — pull uzytkownik in the same query.
    private_allowed = Prefetch('allowed', queryset=User.objects.select_related('uzytkownik'))

    public_pool = base_rooms.prefetch_related(public_allowed, 'muted_by')
    private_pool = base_rooms.prefetch_related(private_allowed, 'muted_by')

    public_active = public_pool.filter(public=True, archived=False)
    public_archived = public_pool.filter(public=True, archived=True)
    private_active = private_pool.filter(public=False, archived=False)
    private_archived = private_pool.filter(public=False, archived=True)

    task_room_ids = Task.objects.filter(chat_room__isnull=False).values_list('chat_room_id', flat=True)
    vote_room_ids = Decyzja.objects.filter(chat_room__isnull=False).values_list('chat_room_id', flat=True)

    public_rooms_active = public_active.exclude(id__in=task_room_ids).exclude(id__in=vote_room_ids)
    public_rooms_archived = public_archived.exclude(id__in=task_room_ids).exclude(id__in=vote_room_ids)

    tasks_tree_active = Task.objects.filter(
        chat_room__isnull=False,
        chat_room__allowed=request.user,
        chat_room__archived=False,
    ).select_related('chat_room', 'chat_room__last_message_sender').prefetch_related(*_chat_room_prefetches()).order_by('title')

    tasks_tree_archived = Task.objects.filter(
        chat_room__isnull=False,
        chat_room__allowed=request.user,
        chat_room__archived=True,
    ).select_related('chat_room', 'chat_room__last_message_sender').prefetch_related(*_chat_room_prefetches()).order_by('title')

    votes_tree_active = Decyzja.objects.filter(
        chat_room__isnull=False,
        chat_room__allowed=request.user,
        chat_room__archived=False,
    ).select_related('chat_room', 'chat_room__last_message_sender').prefetch_related(*_chat_room_prefetches()).order_by('title')

    votes_tree_archived = Decyzja.objects.filter(
        chat_room__isnull=False,
        chat_room__allowed=request.user,
        chat_room__archived=True,
    ).select_related('chat_room', 'chat_room__last_message_sender').prefetch_related(*_chat_room_prefetches()).order_by('title')

    return render(request, "chat/chat.html", {
        'translations': get_translations(),
        'public_rooms_active': public_rooms_active,
        'public_rooms_archived': public_rooms_archived,
        'tasks_tree_active': tasks_tree_active,
        'tasks_tree_archived': tasks_tree_archived,
        'votes_tree_active': votes_tree_active,
        'votes_tree_archived': votes_tree_archived,
        'private_active': private_active,
        'private_archived': private_archived,
        'user': request.user,
        'ARCHIVE_PUBLIC_CHAT_ROOM': td(days=settings.ARCHIVE_PUBLIC_CHAT_ROOM).days,
        'DELETE_PUBLIC_CHAT_ROOM': td(days=settings.DELETE_PUBLIC_CHAT_ROOM).days,
        'MESSAGE_MAX_LENGTH': settings.MESSAGE_MAX_LENGTH,
    })


def check_image_type(file_path):
    try:
        with Image.open(file_path) as img:
            return img.format.lower()
    except Exception:
        return None


MAX_LONG_SIDE = 1920


@csrf_exempt
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
        with open(f"{settings.BASE_DIR}/media/uploads/{filename}", "wb") as f:
            f.write(file_bytes)
        filenames.append(filename)

    return JsonResponse({'filenames': filenames})


def get_translations():
    # Slownik literalny z jawnym _() na kazdym kluczu - makemessages potrafi
    # wyciagnac kazdy string. Wzor {x: _(x) for x in strings} jest niewidoczny
    # dla xgettext, przez co tlumaczenia byly tracone przy kazdym makemessages.
    return {
        "Today": _("Today"),
        "Yesterday": _("Yesterday"),
        "Tomorrow": _("Tomorrow"),
        "Anonymous": _("Anonymous"),
        "Enable Notifications": _("Enable Notifications"),
        "Yes": _("Yes"),
        "edit": _("edit"),
        "edited": _("edited"),
        "Changes History": _("Changes History"),
        "Close": _("Close"),
        "Loading...": _("Loading..."),
        "Copy link": _("Copy link"),
        "Copy message link": _("Copy message link"),
        "Link copied": _("Link copied"),
        "Could not copy link": _("Could not copy link"),
        "Reply to the appropriate message...": _("Reply to the appropriate message..."),
        "Upvote": _("Upvote"),
        "Downvote": _("Downvote"),
        "Title": _("Title"),
        "Sunday": _("Sunday"),
        "Monday": _("Monday"),
        "Tuesday": _("Tuesday"),
        "Wednesday": _("Wednesday"),
        "Thursday": _("Thursday"),
        "Friday": _("Friday"),
        "Saturday": _("Saturday"),
        "Jan": _("Jan"),
        "Feb": _("Feb"),
        "Mar": _("Mar"),
        "Apr": _("Apr"),
        "May": _("May"),
        "Jun": _("Jun"),
        "Jul": _("Jul"),
        "Aug": _("Aug"),
        "Sep": _("Sep"),
        "Oct": _("Oct"),
        "Nov": _("Nov"),
        "Dec": _("Dec"),
        "Unread": _("Unread"),
        "Show only unread rooms": _("Show only unread rooms"),
        "Sorting and filter": _("Sorting and filter"),
        "Likes": _("Likes"),
        "Popular": _("Popular"),
        "attachment": _("attachment"),
        "Mute room": _("Mute room"),
        "Unmute room": _("Unmute room"),
        "Shift+↵ new line · Ctrl+B bold · Ctrl+I italic · - or * list": _("Shift+↵ new line · Ctrl+B bold · Ctrl+I italic · - or * list"),
        "Select a room from the list": _("Select a room from the list"),
        "No unread messages": _("No unread messages"),
        "Tap {icon} above the list to disable the unread filter": _("Tap {icon} above the list to disable the unread filter"),
        "Disable the unread filter": _("Disable the unread filter"),
    }


@receiver(user_accepted)
def create_one2one_rooms(sender, **kwargs):
    # Create all 1to1 rooms
    active_users = User.objects.filter(is_active=True)
    # i = request.user
    # i = kwargs['user']
    for i in active_users:
        for j in active_users:
            # User A will not talk to user A
            if i == j:
                continue
            # Avoid A-B B-A because it is the same thing
            t = sorted([i.username, j.username])
            title = '-'.join(t)
            existing_room = Room.find_with_users(i, j)

            # check if room for user i and j exists, if so make sure room name is correct
            if existing_room is not None:
                existing_room.title = title
                existing_room.save()
            # if not - create new room
            else:
                try:
                    r = Room.objects.create(title=title, public=False)
                    r.allowed.set((
                        i,
                        j,
                    ))
                except IntegrityError:
                    r = Room.objects.get(title__iexact=title)
                    r.allowed.set((
                        i,
                        j,
                    ))


@receiver(user_deleted)
def delete_one2one_rooms(sender, user, **kwargs):
    rooms_to_delete = Room.objects.filter(public=False, allowed=user)
    for room in rooms_to_delete:
        log.info(f"Room {room} deleted.")
    rooms_to_delete.delete()


@login_required
def room_data(request: HttpRequest, room_id: int):
    """
    JSON endpoint for embedded chat widget.
    Returns room metadata and translations needed by chat-embedded.js.
    """
    try:
        room = Room.objects.get(id=room_id, allowed=request.user)
    except Room.DoesNotExist:
        return JsonResponse({
            'error': 'Not found'
        }, status=404)

    return JsonResponse({
        'room_id': room.id,
        'title': room.title,
        'translations': get_translations(),
    })


@login_required
def toggle_notifications(request: HttpRequest):
    """
    Toggle notifications for a room (HTTP fallback for WebSocket handler).
    POST parameters:
    - room_id: ID of the room
    - enabled: boolean (true/false) - true to enable, false to disable
    """
    if request.method != 'POST':
        return JsonResponse({
            'error': 'Method not allowed'
        }, status=405)

    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')
        enabled = data.get('enabled')

        if room_id is None or enabled is None:
            return JsonResponse({
                'error': 'Missing room_id or enabled parameter'
            }, status=400)

        room = Room.objects.get(id=room_id)

        # Check if user is allowed in this room
        if not room.allowed.filter(id=request.user.id).exists():
            return JsonResponse({
                'error': 'Access denied'
            }, status=403)

        # Add or remove user from muted_by list
        if enabled:
            # Enable notifications: remove from muted_by
            if room.muted_by.filter(id=request.user.id).exists():
                room.muted_by.remove(request.user)
                log.info(f"User {request.user.id} enabled notifications for room {room_id}")
        else:
            # Disable notifications: add to muted_by
            if not room.muted_by.filter(id=request.user.id).exists():
                room.muted_by.add(request.user)
                log.info(f"User {request.user.id} muted notifications for room {room_id}")

        return JsonResponse({
            'success': True,
            'room_id': room_id,
            'notifications_enabled': not room.muted_by.filter(id=request.user.id).exists()
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Invalid JSON'
        }, status=400)
    except Room.DoesNotExist:
        return JsonResponse({
            'error': 'Room not found'
        }, status=404)
    except Exception as e:
        log.error(f"Error toggling notifications: {e}")
        return JsonResponse({
            'error': str(e)
        }, status=500)


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
        send_message_to_room(
            room_title=room.title,
            message_text=f'📝 {request.user.username} zmienił(a) nazwę pokoju z "{old_title}" na "{room.title}".',
            sender=None,
            anonymous=False,
        )
    return JsonResponse({'success': True, 'title': room.title})
