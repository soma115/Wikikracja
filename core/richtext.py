"""
Shared rich-text sanitization for user-generated content.

Single source of truth for which HTML tags users may submit and how URLs
are auto-linkified. Used by chat (consumers, services) and by the
`|richtext` template filter for tasks/glosowania/events.
"""

import html as _html
import re

import bleach
import tinycss2
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = ['b', 'i', 'u', 'br', 'a']
ALLOWED_ATTRS = {'a': ['href', 'rel', 'target']}
TINYMCE_URL_ATTRS = {'action', 'cite', 'formaction', 'href', 'poster', 'src', 'srcdoc'}
TINYMCE_UNSAFE_PROTOCOLS = ('javascript:', 'vbscript:', 'data:')
TINYMCE_TAG_RE = re.compile(r'<\s*/?\s*([A-Za-z][^\s/>]*)')
TINYMCE_SCRIPT_RE = re.compile(r'<script\b[^>]*>.*?</script\s*>', re.IGNORECASE | re.DOTALL)


def _is_unsafe_url(value):
    normalized = re.sub(r'[\s\x00-\x1f]+', '', value).lower()
    return normalized.startswith(TINYMCE_UNSAFE_PROTOCOLS)


def _css_has_unsafe_url(tokens):
    for token in tokens:
        if token.type in ('error', 'parse-error'):
            return True
        if token.type == 'url' and _is_unsafe_url(token.value):
            return True
        if token.type == 'function':
            if token.lower_name == 'url' and _is_unsafe_url(tinycss2.serialize(token.arguments).strip(' \'"')):
                return True
            if _css_has_unsafe_url(token.arguments):
                return True
    return False


class TinyMCSSanitizer(CSSSanitizer):
    """Keep editor CSS declarations while rejecting executable URL values."""

    def sanitize_css(self, style):
        parsed = tinycss2.parse_declaration_list(style)
        if not parsed:
            return ''

        cleaned = []
        for token in parsed:
            if token.type == 'declaration':
                if not _css_has_unsafe_url(token.value):
                    cleaned.append(token)
            elif token.type in ('comment', 'whitespace'):
                if cleaned and cleaned[-1].type != token.type:
                    cleaned.append(token)
        return tinycss2.serialize(cleaned).strip()


TINYMCE_CSS_SANITIZER = TinyMCSSanitizer()


def _allow_tinymce_attribute(tag, name, value):
    name = name.lower()
    if name.startswith(('on', 'xmlns')) or name == 'srcdoc':
        return False
    if name in TINYMCE_URL_ATTRS:
        return not _is_unsafe_url(value)
    if name == 'style':
        return not _css_has_unsafe_url(tinycss2.parse_declaration_list(value))
    return True


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
    """Preserve TinyMCE HTML and CSS, removing executable content only."""
    if not text:
        return ''
    normalized = text.replace('\r\n', '\n').replace('\r', '\n')
    normalized = TINYMCE_SCRIPT_RE.sub('', normalized)
    normalized = re.sub(r'<script\b[^>]*/?>', '', normalized, flags=re.IGNORECASE)
    if not re.search(r'<[A-Za-z][^>]*>', normalized):
        normalized = normalized.replace('\n', '<br>')
    tags = {tag.lower() for tag in TINYMCE_TAG_RE.findall(normalized)}
    return bleach.clean(normalized, tags=tags, attributes=_allow_tinymce_attribute, css_sanitizer=TINYMCE_CSS_SANITIZER, strip=True)


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
