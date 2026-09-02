import json
import logging
import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import LoginView
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from site_settings.models import QuickLink, SiteSettings
from site_settings.services import get_branding_version

from .forms import RememberLoginForm
from .services import dashboard as dashboard_service
from .services import feed as feed_service
from .services import search as search_service

log = logging.getLogger(__name__)

ALL_SEARCH_CATS = ['post', 'task', 'decision', 'survey', 'event', 'citizen', 'chat']


def home(request: HttpRequest):
    if not request.user.is_authenticated:
        return render(request, 'home/home.html', dashboard_service.get_public_context())

    # Check if we should filter to show only unread items
    # Priority: URL parameter > session (synced from localStorage)
    url_filter = request.GET.get('filter')

    if url_filter is not None:
        # URL parameter takes precedence
        filter_unread = url_filter == 'unread'
        # Update session to match URL
        request.session['show_unread_only'] = filter_unread
    elif 'show_unread_only' in request.session:
        # Use saved preference from session (synced from localStorage)
        filter_unread = request.session['show_unread_only']
    else:
        # Default: show all items
        filter_unread = False

    context = dashboard_service.build_dashboard_context(request.user, filter_unread=filter_unread, month_param=request.GET.get('month', ''))
    # Expose feed unread count for context processors (e.g. topbar notif bell).
    request._unread_count = context.pop('_unread_count')

    return render(request, 'home/home.html', context)


@login_required
def activity_page(request):
    all_items = feed_service.generate_feed_items(request.user)
    unread_count = feed_service.get_unread_count(request.user, all_items)
    request._unread_count = unread_count

    # Filter unread only
    filter_unread = request.GET.get('filter') == 'unread'
    if filter_unread:
        all_items = [i for i in all_items if not i['is_read']]

    content_types = [
        ('', _('All')),
        ('post', _('Documents')),
        ('task', _('Activities')),
        ('decision', _('Votings')),
        ('survey', _('Ankiety')),
        ('event', _('Calendar')),
        ('citizen', _('Citizens')),
        ('room_messages', _('Chat')),
    ]

    selectable_types = [ct for ct in content_types if ct[0]]
    all_type_values = {ct[0] for ct in selectable_types}

    # Filter by content_type(s) (multi-select)
    is_filtered = request.GET.get('filtered') == '1'
    active_types = [t for t in request.GET.getlist('type') if t in all_type_values]
    # When the filter form was not used, an empty selection means "all".
    selected_types = list(active_types) if is_filtered else (list(all_type_values) if not active_types else list(active_types))
    if active_types:
        active_types_set = set(active_types)
        all_items = [i for i in all_items if i['content_type'] in active_types_set]
    all_types_selected = set(selected_types) == all_type_values

    # Sort
    sort = request.GET.get('sort', 'date')
    order = request.GET.get('order', 'desc')
    if sort == 'date':
        all_items.sort(key=lambda x: x['timestamp'], reverse=(order == 'desc'))

    next_order = "asc" if order == "desc" else "desc"
    type_query = "".join(f"&type={t}" for t in active_types)
    filter_query = "&filtered=1" if is_filtered else ""
    unread_query = "&filter=unread" if filter_unread else ""
    sort_url = f"?{filter_query}{type_query}{unread_query}&sort=date&order={next_order}"
    sort_url = sort_url.replace("?&", "?")
    toolbar_sort_items = [{"url": sort_url, "label": _("Date"), "active": True, "icon": "up" if next_order == "desc" else "down"}]
    toolbar_views = [{"name": "list", "icon": "list", "title": _("List")}, {"name": "grid", "icon": "grip", "title": _("Grid")}]

    return render(
        request,
        'home/activity.html',
        {
            'feed_items': all_items,
            'active_types': active_types,
            'is_filtered': is_filtered,
            'selected_types': selected_types,
            'all_types_selected': all_types_selected,
            'selectable_types': selectable_types,
            'sort': sort,
            'order': order,
            'filter_unread': filter_unread,
            'unread_count': unread_count,
            'content_types': content_types,
            'toolbar_sort_items': toolbar_sort_items,
            'toolbar_views': toolbar_views,
        },
    )


@login_required
@require_POST
def mark_as_read(request):
    """Mark a feed item as read"""
    content_type = request.POST.get('content_type')
    object_id = request.POST.get('object_id')

    if not content_type or not object_id:
        return JsonResponse({'success': False, 'error': 'Missing parameters'})

    try:
        object_id = int(object_id)
        feed_service.mark_feed_item_as_read(content_type, object_id, request.user)
        return JsonResponse({'success': True})

    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid parameters'})


@login_required
@require_POST
def mark_all_read(request):
    """Mark all feed items as read for the current user"""
    try:
        count = feed_service.mark_all_feed_items_as_read(request.user)
        return JsonResponse({'success': True, 'marked_count': count})

    except Exception as e:
        log.error(f"Error marking all as read for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def save_filter_state(request):
    """Save filter state in session"""
    try:
        filter_state = request.POST.get('show_unread_only', 'false').lower() == 'true'
        request.session['show_unread_only'] = filter_state
        request.session.modified = True
        return JsonResponse({'success': True})
    except Exception as e:
        log.error(f"Error saving filter state: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_POST
def mark_unread(request):
    """Mark a feed item as unread"""
    content_type = request.POST.get('content_type')
    object_id = request.POST.get('object_id')

    if not content_type or not object_id:
        return JsonResponse({'success': False, 'error': 'Missing parameters'})

    try:
        object_id = int(object_id)
        feed_service.mark_feed_item_as_unread(content_type, object_id, request.user)
        return JsonResponse({'success': True})

    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid parameters'})


@login_required
def global_search(request: HttpRequest):
    query = request.GET.get('q', '').strip()

    search_categories = [('post', _('Documents')), ('task', _('Activities')), ('decision', _('Votings')), ('survey', _('Surveys')), ('event', _('Event')), ('citizen', _('Citizens')), ('chat', _('Chat'))]

    # Multi-category selection.
    selected = [c for c in request.GET.getlist('cat') if c in ALL_SEARCH_CATS]
    if request.GET.get('filtered') == '1':
        active_cats = set(selected)
    else:
        active_cats = set(selected) if selected else set(ALL_SEARCH_CATS)

    results = search_service.run_global_search(query, active_cats, request.user)

    return render(request, 'home/search.html', {'query': query, 'results': results, 'active_cats': active_cats, 'all_cats_selected': active_cats == set(ALL_SEARCH_CATS), 'search_categories': search_categories})


class RememberLoginView(LoginView):
    form_class = RememberLoginForm
    template_name = 'home/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        remember = form.cleaned_data.get("remember_me")
        if remember:
            self.request.session.set_expiry(getattr(settings, "REMEMBER_ME_COOKIE_AGE", settings.SESSION_COOKIE_AGE))
        else:
            self.request.session.set_expiry(0)
        return response


@login_required
def haslo(request: HttpRequest):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, _('Your password has been changed.'))
            return redirect('obywatele:my_profile')
        else:
            messages.error(request, _('You typed something wrong. See what error appeared above and try again.'))
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'home/haslo.html', {'form': form})


def manifest(request):
    """Serve dynamic PWA manifest JSON"""
    ss = SiteSettings.get()
    if ss.has_brand_derivatives():
        derived_url = settings.MEDIA_URL + 'site_branding/derived/'
        version_q = f'?v={get_branding_version(ss)}'
        favicon_src = derived_url + 'favicon.ico' + version_q
        icon_192_src = derived_url + 'icon-192.png' + version_q
        icon_512_src = derived_url + 'icon-512.png' + version_q
    else:
        favicon_src = '/static/home/images/favicon.ico'
        icon_192_src = '/static/home/images/icon-192.png'
        icon_512_src = '/static/home/images/icon-512.png'

    from site_settings.params import get_param

    site_name = get_param('site_name') or settings.SITE_NAME
    data = {
        'name': site_name,
        'short_name': site_name[:12],
        'start_url': '/',
        'display': 'standalone',
        'orientation': 'any',
        'theme_color': '#375a7f',
        'background_color': '#000',
        "prefer_related_applications": False,
        "related_applications": [],
        # Required by Chrome on Android for FCM push to work reliably when the PWA
        # is installed to the home screen. 103953800507 is Google's fixed sender ID
        # used for the legacy GCM/FCM handshake; it is NOT your Firebase project ID.
        "gcm_sender_id": "103953800507",
        'icons': [
            {'src': favicon_src, 'sizes': "16x16 32x32 48x48", 'type': 'image/x-icon', "purpose": "any"},
            {'src': icon_192_src, 'sizes': "192x192", 'type': 'image/png', "purpose": "any"},
            {'src': icon_512_src, 'sizes': "512x512", 'type': 'image/png', "purpose": "any"},
        ],
    }
    response = JsonResponse(data, json_dumps_params={'ensure_ascii': False})
    # Let browsers revalidate so PWA name/description changes are picked up
    # without an app restart or manual cache clearing.
    response['Cache-Control'] = 'no-cache'
    return response


def firebase_messaging_sw(request):
    """Serve the Firebase Messaging service worker JavaScript file with injected Firebase config"""
    sw_path = os.path.join(settings.BASE_DIR, 'chat', 'static', 'chat', 'js', 'firebase-messaging-sw.js')

    if not os.path.exists(sw_path):
        return HttpResponse("Firebase Messaging Service Worker not found", status=404)

    with open(sw_path, 'r', encoding='utf-8') as f:
        sw_content = f.read()

    # Inject Firebase config from settings, replacing the entire JS object block
    firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
    config_str = f"const firebaseConfig = {json.dumps(firebase_config)};"
    sw_content = re.sub(r'const\s+firebaseConfig\s*=\s*\{[\s\S]*?\};', config_str, sw_content, count=1)

    response = HttpResponse(sw_content, content_type='application/javascript')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    response['Service-Worker-Allowed'] = "/"
    return response


def dynamic_settings_js(request: HttpRequest):
    """Serve dynamic JS file with Firebase client config for FCM"""
    firebase_config = getattr(settings, 'FIREBASE_CONFIG', {})
    firebase_vapid_key = getattr(settings, 'FIREBASE_VAPID_KEY', '')
    js_content = f"export const FIREBASE_CONFIG = {json.dumps(firebase_config)};\n"
    js_content += f"export const FIREBASE_VAPID_KEY = {json.dumps(firebase_vapid_key)};\n"
    response = HttpResponse(js_content, content_type='application/javascript')
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def site_admin(request: HttpRequest) -> HttpResponse:
    if request.method == 'POST' and 'save_quick_link' in request.POST:
        title = request.POST.get('quick_link_title')
        url = request.POST.get('quick_link_url')
        order = request.POST.get('quick_link_order', 0)
        if title and url:
            QuickLink.objects.create(title=title, url=url, order=order)
            messages.success(request, _('Link added.'))
        return redirect('site_admin')

    if request.method == 'POST' and 'edit_quick_link' in request.POST:
        link_id = request.POST.get('edit_quick_link')
        title = request.POST.get('quick_link_title')
        url = request.POST.get('quick_link_url')
        order = request.POST.get('quick_link_order', 0)
        try:
            link = QuickLink.objects.get(id=link_id)
            link.title = title
            link.url = url
            link.order = order
            link.save()
            messages.success(request, _('Link updated.'))
        except QuickLink.DoesNotExist:
            messages.error(request, _("Link doesn't exist."))
        return redirect('site_admin')

    if request.method == 'POST' and 'reorder_quick_links' in request.POST:
        order_data = json.loads(request.POST.get('order', '[]'))
        for index, link_id in enumerate(order_data):
            try:
                link = QuickLink.objects.get(id=link_id)
                link.order = index
                link.save()
            except QuickLink.DoesNotExist:
                continue
        return JsonResponse({'ok': True})

    if request.method == 'POST' and 'delete_quick_link' in request.POST:
        link_id = request.POST.get('delete_quick_link')
        try:
            link = QuickLink.objects.get(id=link_id)
            link.delete()
            messages.success(request, _('Link deleted.'))
        except QuickLink.DoesNotExist:
            messages.error(request, _("Link doesn't exist."))
        return redirect('site_admin')

    return render(request, 'home/site_admin.html', dashboard_service.get_site_admin_context(request.user))
