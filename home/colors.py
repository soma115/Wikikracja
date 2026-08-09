"""Single source of truth for category/content-type -> Bootstrap color mapping.

This mapping used to be duplicated independently in home/views.py
(global_search's per-result type_color literals), in
home/templatetags/feed_filters.py (content_type_color) and in the CSS
data-color rules in home/templates/home/search.html. It is now defined
once here and reused everywhere via the CATEGORY_COLORS dict and the
category_color() helper / template filter.
"""

CATEGORY_COLORS = {
    'post': 'primary',
    'task': 'warning',
    'event': 'success',
    'message': 'info',
    'room_messages': 'info',  # grouped room messages content type
    'chat': 'info',           # global search "chat" category (rooms + messages)
    'decision': 'danger',
    'citizen': 'secondary',
    'membership': 'secondary',
    'transaction': 'primary',
    'survey': 'dark',
}

DEFAULT_COLOR = 'secondary'


def category_color(key):
    """Return the Bootstrap color class for a category / content-type key."""
    return CATEGORY_COLORS.get(key, DEFAULT_COLOR)
