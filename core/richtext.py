"""
Shared rich-text sanitization for user-generated content.

Single source of truth for which HTML tags users may submit and how URLs
are auto-linkified. Used by chat (consumers, services) and by the
`|richtext` template filter for tasks/glosowania/events.
"""

import html as _html
import re

import bleach
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = ['b', 'i', 'u', 'br', 'a']
ALLOWED_ATTRS = {'a': ['href', 'rel', 'target']}
TINYMCE_TAGS = {
    'a',
    'abbr',
    'address',
    'article',
    'aside',
    'audio',
    'b',
    'blockquote',
    'br',
    'caption',
    'cite',
    'code',
    'col',
    'colgroup',
    'dd',
    'del',
    'details',
    'div',
    'dl',
    'dt',
    'em',
    'figcaption',
    'figure',
    'footer',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'header',
    'hr',
    'i',
    'img',
    'ins',
    'kbd',
    'li',
    'main',
    'mark',
    'nav',
    'ol',
    'p',
    'pre',
    'q',
    's',
    'samp',
    'section',
    'small',
    'source',
    'span',
    'strong',
    'sub',
    'summary',
    'sup',
    'table',
    'tbody',
    'td',
    'tfoot',
    'th',
    'thead',
    'time',
    'tr',
    'u',
    'ul',
    'var',
    'video',
}
TINYMCE_URL_ATTRS = {'action', 'cite', 'href', 'poster', 'src'}
TINYMCE_PROTOCOLS = ['http', 'https', 'mailto']
TINYMCE_GLOBAL_ATTRS = {'class', 'dir', 'id', 'lang', 'role', 'style', 'title'}
TINYMCE_TAG_ATTRS = {
    'a': {'download', 'rel', 'target'},
    'audio': {'controls', 'loop', 'muted', 'preload'},
    'col': {'span', 'width'},
    'colgroup': {'span', 'width'},
    'img': {'alt', 'height', 'loading', 'width'},
    'iframe': {'allow', 'allowfullscreen', 'frameborder', 'height', 'loading', 'name', 'referrerpolicy', 'sandbox', 'width'},
    'source': {'height', 'media', 'sizes', 'type', 'width'},
    'table': {'border', 'cellpadding', 'cellspacing', 'height', 'width'},
    'td': {'colspan', 'headers', 'rowspan', 'scope'},
    'th': {'colspan', 'headers', 'rowspan', 'scope'},
    'video': {'autoplay', 'controls', 'height', 'loop', 'muted', 'poster', 'preload', 'width'},
}
TINYMCE_TAGS.add('iframe')
TINYMCE_CSS_SANITIZER = CSSSanitizer()


def _allow_tinymce_attribute(tag, name, value):
    if name.lower().startswith(('on', 'xmlns')):
        return False
    if name in TINYMCE_URL_ATTRS:
        normalized = value.strip().lower()
        return not normalized.startswith(('javascript:', 'vbscript:', 'data:'))
    return name in TINYMCE_GLOBAL_ATTRS or name in TINYMCE_TAG_ATTRS.get(tag, set()) or name.startswith(('aria-', 'data-'))


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
    """Sanitize simple rich text and normalize its line endings."""
    if not text:
        return ''
    normalized = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>')
    cleaned = bleach.clean(normalized, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    if linkify:
        cleaned = bleach.linkify(cleaned, callbacks=[_set_link_target])
    return cleaned


def sanitize_tinymce(text: str) -> str:
    """Preserve TinyMCE HTML while removing executable content and unsafe URLs."""
    if not text:
        return ''
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    if not re.search(r'<[A-Za-z][^>]*>', normalized):
        normalized = normalized.replace('\n', '<br>')
    return bleach.clean(normalized, tags=TINYMCE_TAGS, attributes=_allow_tinymce_attribute, protocols=TINYMCE_PROTOCOLS, css_sanitizer=TINYMCE_CSS_SANITIZER, strip=True)


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
