import logging

from django.utils.translation import gettext_lazy as _

from site_settings.models import QuickLink

from ..dashboard_registry import collect_dashboard_context, collect_public_context, collect_site_admin_context
from .feed import generate_feed_items, get_unread_count

log = logging.getLogger(__name__)


DASHBOARD_MODULES = [
    {
        'name': _('Voting'),
        'icon': 'fa-vote-yea',
        'url': 'glosowania:proposition',
        'description': _('Democratic decision-making — submit proposals, collect signatures, vote on ongoing referendums and track results.'),
    },
    {'name': _('Citizens'), 'icon': 'fa-users', 'url': 'obywatele:obywatele', 'description': _('Member directory — browse citizen profiles, check roles and track community activity.')},
    {
        'name': _('Documents'),
        'icon': 'fa-chalkboard',
        'url': 'board:start',
        'description': _('Documents and blog — create and publish content, including a public blog visible to visitors outside the community.'),
    },
    {'name': _('Calendar'), 'icon': 'fa-calendar-days', 'url': 'events:list', 'description': _('Upcoming community events — one-off and recurring. Stay informed about meetings, deadlines and activities.')},
    {'name': _('Activities'), 'icon': 'fa-list-check', 'url': 'tasks:list', 'description': _('Activity management — create, assign and track activities within the community. See who is responsible for what.')},
    {
        'name': _('Bookkeeping'),
        'icon': 'fa-coins',
        'url': 'bookkeeping:transaction_list',
        'description': _('Community finances — record income and expenses, maintain transparency over shared funds and budgets.'),
    },
    {'name': _('Chat'), 'icon': 'fa-comments', 'url': 'chat:chat', 'description': _('Real-time messaging — communicate in topic-based chat rooms linked to referendums and community groups.')},
    {'name': _('Surveys'), 'icon': 'fa-clipboard-question', 'url': 'ankiety:list', 'description': _('Surveys and quick polls — collect opinions, run questionnaires and make better group decisions.')},
]


def build_dashboard_context(user, feed_items=None, filter_unread=False, month_param=''):
    """Build the full context dict for the home/dashboard view."""
    if feed_items is None:
        feed_items = generate_feed_items(user)

    request_unread_count = get_unread_count(user, feed_items)

    if filter_unread:
        feed_items = [item for item in feed_items if not item['is_read']]

    context = collect_dashboard_context(user, month_param)
    context.update(
        {
            'feed_items': feed_items,
            'filter_unread': filter_unread,
            'last_feed_items': [i for i in feed_items if i['content_type'] != 'event'][:6],
            'unread_items_no_events': [item for item in feed_items if not item['is_read'] and item['content_type'] != 'event'],
            '_unread_count': request_unread_count,
            'quick_links': list(QuickLink.objects.order_by('order')),
        }
    )
    return context


def get_public_context():
    """Build context for the public landing page (anonymous user)."""
    context = collect_public_context()
    context.setdefault('dashboard_modules', DASHBOARD_MODULES)
    context.setdefault('start', None)
    return context


def get_site_admin_context(user):
    """Build context for the site admin page."""
    context = collect_site_admin_context(user)
    context['quick_links'] = list(QuickLink.objects.order_by('order'))
    return context
