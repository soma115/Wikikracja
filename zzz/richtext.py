"""
Shared rich-text sanitization for user-generated content.

Single source of truth for which HTML tags users may submit and how URLs
are auto-linkified. Used by chat (consumers, services) and by the
`|richtext` template filter for tasks/glosowania/events.
"""

import re

import bleach

ALLOWED_TAGS = ['b', 'i', 'u', 'br', 'a']
ALLOWED_ATTRS = {'a': ['href', 'rel', 'target']}


def _set_link_target(attrs, new=False):
    """bleach.linkify callback: external links open in a new tab."""
    from zzz.utils import get_site_domain

    href = attrs.get((None, 'href'), '')
    domain = get_site_domain()
    is_internal = href.startswith('/') or href.startswith(f'http://{domain}') or href.startswith(f'https://{domain}')
    if not is_internal:
        attrs[(None, 'target')] = '_blank'
        attrs[(None, 'rel')] = 'noopener'
    return attrs


def sanitize(text: str, *, linkify: bool = True) -> str:
    """Sanitize user HTML, keeping only ALLOWED_TAGS and (optionally) auto-linking URLs.

    Normalizes line endings (CRLF/CR/LF) to <br> — single source of truth so callers
    (chat consumers, RichTextWidget, |richtext filter) don't each carry their own
    replace. Eliminates ghost empty lines from legacy DB content with raw \\n.
    """
    if not text:
        return ''
    normalized = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>')
    cleaned = bleach.clean(normalized, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    if linkify:
        cleaned = bleach.linkify(cleaned, callbacks=[_set_link_target])
    return cleaned


_TAG_RE = re.compile(r'<[^>]+>')


def strip_tags(text: str) -> str:
    """Remove all HTML tags — for plain-text snippets (notifications, quotes)."""
    return _TAG_RE.sub('', text or '')
