from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from zzz.richtext import sanitize

TOOLBAR_HTML = mark_safe(
    '<div class="fmt-toolbar">'
    '<button class="fmt-btn" type="button" data-cmd="bold" title="Ctrl+B"><b>B</b></button>'
    '<button class="fmt-btn" type="button" data-cmd="italic" title="Ctrl+I"><i>I</i></button>'
    '<button class="fmt-btn" type="button" data-cmd="underline" title="Ctrl+U"><u>U</u></button>'
    '</div>'
)


class RichTextWidget(forms.Textarea):
    """
    Form widget that renders a contenteditable rich-text input with a B/I/U
    toolbar matching the chat composer. The contenteditable's HTML is mirrored
    into a hidden <input> so the form posts back exactly the same data shape
    as a regular Textarea.

    Allowed tags are defined centrally in `zzz.richtext.ALLOWED_TAGS`.
    """

    class Media:
        # DOMPurify is loaded globally by home/base.html (used by both chat and
        # this widget), so we only declare the widget-specific JS here.
        js = (
            'common/js/richtext-input.js',
        )
        css = {
            'all': ('chat/css/chat.css',),
        }

    def __init__(self, attrs=None, max_length=None, placeholder=''):
        super().__init__(attrs)
        self.max_length = max_length
        self.placeholder = placeholder

    def render(self, name, value, attrs=None, renderer=None):
        value = value or ''
        initial_html = sanitize(str(value), linkify=True)  # already safe HTML

        wrapper_attrs = (
            format_html(' data-max-length="{}"', int(self.max_length))
            if self.max_length else ''
        )
        placeholder_attr = (
            format_html(' data-placeholder="{}"', self.placeholder)
            if self.placeholder else ''
        )
        counter = (
            format_html(
                '<div class="msg-counter"><span class="msg-counter-val">{0}</span> / {0}</div>',
                int(self.max_length),
            )
            if self.max_length else ''
        )
        hidden = format_html('<input type="hidden" name="{}" value="{}">', name, value)
        editable_open = format_html(
            '<div class="richtext-input message-input-rich" contenteditable="true"'
            ' role="textbox" aria-multiline="true"{}>',
            placeholder_attr,
        )
        wrapper_open = format_html('<div class="richtext-wrapper" data-richtext{}>', wrapper_attrs)

        return mark_safe(
            f'{wrapper_open}{TOOLBAR_HTML}{editable_open}{initial_html}</div>{hidden}{counter}</div>'
        )

    def value_from_datadict(self, data, files, name):
        # JS keeps the hidden <input name="..."> in sync, so the standard
        # Textarea/CharField data path Just Works. The value already is the
        # exact HTML counted by the widget, so we use it raw for length.
        return data.get(name, '')
