from django.urls import reverse
from django.utils.translation import gettext_lazy as _

CITIZEN_SETTINGS_PAGE_NAMES = frozenset({'my_profile', 'haslo', 'my_assets', 'change_email', 'change_username', 'upload_avatar', 'set_language', 'toggle_notification', 'request_deletion', 'cancel_deletion'})

CITIZEN_SETTINGS_NAV_NAMES = frozenset({'my_profile', 'haslo', 'my_assets', 'change_email', 'change_username'})


def default_toolbar_views():
    return [{'name': 'list', 'icon': 'list', 'title': _('List')}, {'name': 'grid', 'icon': 'grip', 'title': _('Grid')}]


NAVIGATION_ITEMS = (
    {'namespace': None, 'url_name': 'home', 'label': _('Desktop'), 'icon': 'house', 'active_class': 'active tw-active'},
    {'namespace': 'tasks', 'url_name': 'tasks:list', 'label': _('Activities'), 'icon': 'bolt', 'prefs_scope': 'tasks', 'active_class': 'active tw-active'},
    {'namespace': 'obywatele', 'url_name': 'obywatele:obywatele', 'label': _('Citizens'), 'icon': 'users', 'prefs_scope': 'obywatele', 'active_class': 'active tw-active'},
    {'namespace': 'board', 'url_name': 'board:start', 'label': _('Documents'), 'icon': 'chalkboard', 'prefs_scope': 'board', 'active_class': 'active tw-active'},
    {'namespace': 'events', 'url_name': 'events:list', 'label': _('Calendar'), 'icon': 'calendar-days', 'prefs_scope': 'events', 'active_class': 'active tw-active'},
    {'namespace': 'glosowania', 'url_name': 'glosowania:proposition', 'label': _('Votings'), 'icon': 'landmark', 'prefs_scope': 'glosowania', 'active_class': 'active tw-active'},
    {'namespace': 'bookkeeping', 'url_name': 'bookkeeping:transaction_list', 'label': _('Finance'), 'icon': 'wallet', 'prefs_scope': 'bookkeeping', 'active_class': 'active tw-active'},
    {'namespace': 'ankiety', 'url_name': 'ankiety:list', 'label': _('Surveys'), 'icon': 'clipboard-question', 'active_class': 'active tw-active'},
    {'namespace': 'chat', 'url_name': 'chat:chat', 'label': _('Chat'), 'icon': 'comment-dots', 'data_nav': 'chat', 'active_class': 'tw-active'},
)


def _is_citizen_settings_page(match):
    return match and match.namespace == 'obywatele' and match.url_name in CITIZEN_SETTINGS_PAGE_NAMES


def _is_active(item, match):
    if not match:
        return False
    if item['url_name'] == 'home':
        return match.url_name == 'home'
    if match.namespace != item['namespace']:
        return False
    return not _is_citizen_settings_page(match)


def _current_module(match):
    if not match:
        return _('…')
    if match.url_name == 'home':
        return _('Desktop')
    if match.url_name == 'activity':
        return _('Activity')
    if _is_citizen_settings_page(match):
        return _('Settings')
    for item in NAVIGATION_ITEMS:
        if item['namespace'] == match.namespace:
            return item['label']
    return _('…')


def _current_module_url(match):
    if not match:
        return reverse('home')
    if match.url_name == 'home':
        return reverse('home')
    if match.url_name == 'activity':
        return reverse('activity')
    if _is_citizen_settings_page(match):
        return reverse('obywatele:my_profile')
    for item in NAVIGATION_ITEMS:
        if item['namespace'] == match.namespace:
            return reverse(item['url_name'])
    return reverse('home')


def get_navigation_context(request):
    match = getattr(request, 'resolver_match', None)
    items = []
    for item in NAVIGATION_ITEMS:
        nav_item = {**item, 'href': reverse(item['url_name']), 'active': _is_active(item, match)}
        if item.get('prefs_scope'):
            nav_item['base_href'] = nav_item['href']
        items.append(nav_item)

    return {
        'navigation_items': items,
        'current_module': _current_module(match),
        'current_module_url': _current_module_url(match),
        'settings_active': bool(match and match.namespace == 'obywatele' and match.url_name in CITIZEN_SETTINGS_NAV_NAMES),
    }
