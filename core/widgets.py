from django import forms
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.richtext import sanitize

TOOLBAR_HTML = mark_safe(
    '<div class="tw-fmt-toolbar">'
    '<button class="tw-fmt-btn" type="button" data-cmd="bold" title="Ctrl+B"><b>B</b></button>'
    '<button class="tw-fmt-btn" type="button" data-cmd="italic" title="Ctrl+I"><i>I</i></button>'
    '<button class="tw-fmt-btn" type="button" data-cmd="underline" title="Ctrl+U"><u>U</u></button>'
    '</div>'
)


class RichTextWidget(forms.Textarea):
    """
    Form widget that renders a contenteditable rich-text input with a B/I/U
    toolbar matching the chat composer. The contenteditable's HTML is mirrored
    into a hidden <input> so the form posts back exactly the same data shape
    as a regular Textarea.

    Allowed tags are defined centrally in `core.richtext.ALLOWED_TAGS`.
    """

    class Media:
        # DOMPurify is loaded globally by home/base.html (used by both chat and
        # this widget), so we only declare the widget-specific JS here.
        js = ('common/js/richtext-input.js',)

    def __init__(self, attrs=None, max_length=None, placeholder=''):
        super().__init__(attrs)
        self.max_length = max_length
        self.placeholder = placeholder

    def render(self, name, value, attrs=None, renderer=None):
        value = value or ''
        initial_html = sanitize(str(value), linkify=True)  # already safe HTML

        # crispy-forms marks invalid fields by mutating the widget's own
        # `self.attrs` dict (not the `attrs` param) to add "is-invalid" (see
        # tw/field.html + crispy_forms_field.CrispyFieldNode). Merge the same
        # way Django's default Widget.get_context() does, or we won't see it.
        # Our markup doesn't have a normal <input class="...">> for that class
        # to land on, so mirror it onto the wrapper; the shared Tailwind
        # invalid-feedback rule uses that state to show the error message.
        final_attrs = self.build_attrs(self.attrs, attrs)
        is_invalid = 'is-invalid' in final_attrs.get('class', '').split()

        wrapper_attrs = format_html(' data-max-length="{}"', int(self.max_length)) if self.max_length else ''
        placeholder_attr = format_html(' data-placeholder="{}"', self.placeholder) if self.placeholder else ''
        counter = format_html('<div class="tw-msg-counter"><span class="tw-msg-counter-val">{0}</span> / {0}</div>', int(self.max_length)) if self.max_length else ''
        hidden = format_html('<input type="hidden" name="{}" value="{}">', name, value)
        editable_open = format_html('<div class="tw-richtext-input tw-message-input-rich" contenteditable="true" role="textbox" aria-multiline="true"{}>', placeholder_attr)
        wrapper_open = format_html('<div class="tw-richtext-wrapper{}" data-richtext{}>', ' is-invalid' if is_invalid else '', wrapper_attrs)

        return mark_safe(f'{wrapper_open}{TOOLBAR_HTML}{editable_open}{initial_html}</div>{hidden}{counter}</div>')

    def value_from_datadict(self, data, files, name):
        # JS keeps the hidden <input name="..."> in sync, so the standard
        # Textarea/CharField data path Just Works. The value already is the
        # exact HTML counted by the widget, so we use it raw for length.
        return data.get(name, '')


class CounterTextarea(forms.Textarea):
    """
    Plain ``<textarea>`` with a live character counter and a native
    ``maxlength`` attribute.

    Unlike RichTextWidget, this counts exactly what gets submitted — no HTML
    tags, no sanitization round-trip — so the on-screen counter always
    matches the backend's ``max_length`` validation exactly.
    """

    class Media:
        js = ('common/js/textarea-counter.js',)
        # .tw-msg-counter/.tw-msg-counter--warn/.tw-msg-counter--error styles are in tailwind.css (global).

    def __init__(self, attrs=None, max_length=None):
        self.max_length = max_length
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        # crispy-forms mutates the widget's own `self.attrs` dict (not the
        # `attrs` param) to add "is-invalid" — merge the same way Django's
        # default Widget.render()/get_context() does, or we won't see it.
        final_attrs = self.build_attrs(self.attrs, attrs)
        # Mirror "is-invalid" onto the wrapper div too: it is the sibling of
        # the rendered feedback block, so the shared Tailwind validation rule
        # needs that state to show the message (see RichTextWidget.render).
        is_invalid = 'is-invalid' in final_attrs.get('class', '').split()
        attrs = dict(attrs or {})
        attrs.setdefault('data-charcounter', '')
        if self.max_length:
            attrs.setdefault('maxlength', int(self.max_length))
        textarea_html = super().render(name, value, attrs, renderer)
        if not self.max_length:
            return textarea_html
        counter = format_html('<div class="tw-msg-counter"><span class="tw-msg-counter-val">{0}</span> / {0}</div>', int(self.max_length))
        wrapper_class = 'tw-textarea-counter-wrapper is-invalid' if is_invalid else 'tw-textarea-counter-wrapper'
        return mark_safe(format_html('<div class="{}">{}{}</div>', wrapper_class, textarea_html, counter))

    def value_from_datadict(self, data, files, name):
        # Browsers normalize <textarea> line endings to CRLF ("\r\n") when
        # constructing the submitted form data, even though the DOM's
        # `.value` (what the JS counter reads and `maxlength` enforces) only
        # ever has "\n". Left alone, that extra "\r" per line makes the
        # server see more characters than the counter ever showed the user
        # (e.g. 3000 on screen, but 3029 by the time Django validates it).
        # Normalize back to "\n" so both sides count the same string.
        value = data.get(name, '')
        if value:
            value = value.replace('\r\n', '\n').replace('\r', '\n')
        return value


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = 'datetime-local'

    def format_value(self, value):
        if value is None:
            return ''
        if hasattr(value, 'strftime'):
            if timezone.is_naive(value):
                local_time = value
            else:
                local_time = timezone.localtime(value)
            return local_time.strftime('%Y-%m-%dT%H:%M')
        return value
