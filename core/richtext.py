"""
Shared rich-text sanitization for user-generated content.

Single source of truth for which HTML tags users may submit and how URLs
are auto-linkified. Used by chat (consumers, services) and by the
`|richtext` template filter for tasks/glosowania/events.
"""

import html as _html
import re

import bleach

ALLOWED_TAGS = ['b', 'i', 'u', 'br', 'a']
ALLOWED_ATTRS = {'a': ['href', 'rel', 'target']}


def _set_link_target(attrs, new=False):
    """bleach.linkify callback: external links open in a new tab."""
    from core.utils import get_site_domain

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


def plain_text(html: str, max_length: int | None = None) -> str:
    """Convert HTML to plain text while preserving line breaks from `<br>` and `<p>`.

    Decodes HTML entities and optionally truncates to `max_length` without
    cutting off words. Use this for feed descriptions and email snippets where
    newlines should survive but rich formatting should not.
    """
    if not html:
        return ''
    text = re.sub(r'</p>', '\n\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = _TAG_RE.sub('', text)
    text = _html.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    if max_length and len(text) > max_length:
        cut = text.rfind(' ', 0, max_length)
        if cut <= 0:
            cut = max_length
        text = text[:cut].rstrip() + '...'
    return text


def one_line_snippet(html: str, max_length: int = 120) -> str:
    """Return a single-line plain-text snippet from HTML.

    Line breaks and multiple spaces are collapsed to one space, then the text
    is trimmed and truncated to `max_length` without cutting off words.
    """
    text = plain_text(html)
    if not text:
        return ''
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > max_length:
        cut = text.rfind(' ', 0, max_length)
        if cut <= 0:
            cut = max_length
        text = text[:cut].rstrip() + '...'
    return text
