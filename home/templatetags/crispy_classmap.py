import re

from django import template

register = template.Library()


_CLASS_MAP = {
    "form-control": "tw-form-control",
    "form-select": "tw-form-select",
    "form-label": "tw-form-label",
    "col-form-label": "tw-form-label",
    "form-check": "tw-form-check",
    "form-check-input": "tw-form-check-input",
    "form-check-inline": "tw-form-check-inline",
    "form-check-label": "tw-form-check-label",
    "form-switch": "tw-form-switch",
    "form-text": "tw-form-text",
    "invalid-feedback": "tw-invalid-feedback",
    "valid-feedback": "tw-valid-feedback",
    "tab-pane": "tw-tab-pane",
    "active": "tw-active",
    "show": "tw-show",
    "fade": "tw-fade",
    "alert": "tw-alert",
    "alert-primary": "tw-alert-primary",
    "alert-secondary": "tw-alert-secondary",
    "alert-success": "tw-alert-success",
    "alert-danger": "tw-alert-danger",
    "alert-warning": "tw-alert-warning",
    "alert-info": "tw-alert-info",
    "alert-dark": "tw-alert-dark",
    "alert-block": "tw-alert-block",
    "input-group": "tw-input-group",
    "input-group-text": "tw-input-group-text",
    "mb-3": "tw-mb-3",
    "mb-2": "tw-mb-2",
    "mt-3": "tw-mt-3",
    "mt-2": "tw-mt-2",
    "me-2": "tw-me-2",
    "ms-2": "tw-ms-2",
    "p-3": "tw-p-3",
    "p-2": "tw-p-2",
    "row": "",
    "btn": "tw-btn",
    "btn-primary": "tw-btn-primary",
    "btn-secondary": "tw-btn-secondary",
    "btn-success": "tw-btn-success",
    "btn-danger": "tw-btn-danger",
    "btn-warning": "tw-btn-warning",
    "btn-info": "tw-btn-info",
    "btn-light": "tw-btn-light",
    "btn-dark": "tw-btn-dark",
    "btn-link": "tw-btn-link",
    "btn-outline-primary": "tw-btn-outline-primary",
    "btn-outline-secondary": "tw-btn-outline-secondary",
    "btn-outline-success": "tw-btn-outline-success",
    "btn-outline-danger": "tw-btn-outline-danger",
    "btn-outline-warning": "tw-btn-outline-warning",
    "btn-outline-info": "tw-btn-outline-info",
    "btn-outline-light": "tw-btn-outline-light",
    "btn-outline-dark": "tw-btn-outline-dark",
    "col": "tw-col-span-12",
    "form-horizontal": "",
    "form-group": "",
    "form-inline": "tw-flex tw-flex-wrap tw-items-center tw-gap-2",
}

_COL_RE = re.compile(r"\bcol(?:-(sm|md|lg|xl|xxl))?-?(\d+|auto)?\b")


def _map_col(match):
    bp = match.group(1)
    size = match.group(2)
    if not size or size == "auto":
        return "tw-col-span-12" if not bp else f"{bp}:tw-col-span-12"
    return f"tw-col-span-{size}" if not bp else f"tw-col-span-12 {bp}:tw-col-span-{size}"


@register.filter
def crispy_classmap(value):
    """Map known crispy layout classes to project tw-* equivalents."""
    if not value or not isinstance(value, str):
        return value
    classes = value.split()
    mapped = []
    for cls in classes:
        if cls in _CLASS_MAP:
            if _CLASS_MAP[cls]:
                mapped.append(_CLASS_MAP[cls])
        elif _COL_RE.match(cls):
            mapped.append(_map_col(_COL_RE.match(cls)))
        else:
            mapped.append(cls)
    return " ".join(m for m in mapped if m)
