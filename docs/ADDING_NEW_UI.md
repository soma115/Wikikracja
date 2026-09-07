# Adding new UI in Wikikracja

This checklist keeps the interface consistent. Before creating a new view, form, card or button, read `docs/UI_STANDARDS.html` and use existing shared components. If the existing component does not fit, extend it or update the standard rather than inventing a one-off exception.

## One source of truth

- Components: `docs/UI_STANDARDS.html` (reference document + icon dictionary)
- Theme tokens: `home/static/home/css/tokens.css`
- Component CSS: `home/static/home/css/tailwind.css`
- Generated CSS: `home/static/home/css/tailwind.build.css`
- Shared partials: `home/templates/home/includes/`
- Shared JS: `home/static/home/js/app.js`, `home/static/common/js/`
- Design plan: `docs/TAILWIND_MIGRATION_PLAN.md`

## Checklist for every new view/fragment

### 1. Layout

- [ ] Use `{% extends 'home/base.html' %}`.
- [ ] Wrap content in `{% block content %}`.
- [ ] Use `tw-container tw-my-4` or `tw-container tw-section` for top-level spacing.
- [ ] Do not use custom `.section` / `.section-heading`; use `tw-section` and `tw-section-heading`.

### 2. Toolbar

- [ ] If the page has sorting, view toggles (list/grid/compact) or filters, include `home/templates/home/includes/toolbar.html`.
- [ ] Toolbar must use `tw-toolbar`, `tw-sort-btn`, `tw-view-toggle-btn` and `tw-toolbar-divider`.
- [ ] View switching must use `data-view="list|grid|compact"`, `data-view-container` and `[data-view-only]`.

### 3. Cards and lists

- [ ] Use `tw-card` for content cards.
- [ ] Card headers use `tw-card-header`; body uses `tw-card-body`.
- [ ] Lists use `tw-proposals-list` (or its successor if documented otherwise) + `data-view-container`.
- [ ] Empty states use the shared partial or copy the `tw-proposals-empty` pattern.
- [ ] Do not create new `module-card`, `module-list`, `module-empty` classes.

### 4. Buttons and actions

- [ ] Primary: `tw-btn tw-btn-primary`
- [ ] Secondary: `tw-btn tw-btn-secondary` or `tw-btn tw-btn-outline-secondary`
- [ ] Danger: `tw-btn tw-btn-danger`
- [ ] Ghost/icon: `tw-btn tw-btn-ghost` or `tw-btn tw-btn-sm tw-btn-ghost`
- [ ] CTA (floating/primary): `tw-btn-cta`
- [ ] Avoid `.btn-icon-clean`, `.btn-ghost-old` and other pre-Tailwind classes.

### 5. Forms

- [ ] Prefer `{% crispy form %}` with a `FormHelper`.
- [ ] If you need per-field rendering, use `home/templates/tw/field.html` and `crispy_classmap`.
- [ ] Do not hand-roll `is-invalid` / `form-control` wrappers.

### 6. Icons

- [ ] Look up the semantic meaning in `docs/UI_STANDARDS.html`.
- [ ] Use Font Awesome classes from the dictionary (`fa-check`, `fa-pen`, `fa-trash`, etc.).
- [ ] If a new icon is genuinely needed, add it to `docs/UI_STANDARDS.html` first, then use it.
- [ ] Do not mix `fa-xmark` and `fa-times` for the same action.

### 7. Inline styles

- [ ] Inline `style="..."` is allowed **only** for dynamic CSS variables: `style="--featured-img: url('...')"` or `style="--vote-progress: {{ pct }}%"`.
- [ ] Everything else (colors, spacing, visibility, width, height) must be a Tailwind utility class (`tw-*`).

### 8. New CSS

- [ ] Every new class must have the `tw-` prefix.
- [ ] If the class is generated dynamically, add it to the `safelist` in `tailwind.config.js`.
- [ ] Do not add module-specific rules like `.ankiety-foo` or `.activity-bar` to `tailwind.css`.
- [ ] Prefer extending an existing shared component or using utility classes.

### 9. JavaScript

- [ ] Mobile breakpoint is `767.98px`; do not hardcode a new value. Use a shared helper when one exists.
- [ ] List/grid toggling goes through `PagePrefs` and `applyView` in `home/static/home/js/app.js`.
- [ ] Do not add a new `addEventListener('DOMContentLoaded')` if `window.pageReady` or `initModule` helpers already cover the case.

### 10. Before you commit

- [ ] `npm run build:css` (regenerates `tailwind.build.css`)
- [ ] `python scripts/regression_scan.py` (Bootstrap/deleted-CSS guard + inline-style check)
- [ ] `python scripts/ui_guard.py` (checks changed files against UI standards)
- [ ] `python scripts/ui_guard.py --all --strict` (full audit if you touched many files)
- [ ] `python manage.py check`
- [ ] `ruff check .` and `ruff format --check .`
- [ ] `python manage.py collectstatic --noinput --dry-run`
- [ ] `npm test -- --runInBand` (if JS changed)
- [ ] `pytest` (if Python logic changed)

## When the guard blocks you

1. Read the `ui_guard.py` output. Issues are hard blockers; warnings are soft unless `--strict` is used.
2. If the guard complains about a genuinely new pattern that should become a standard, update `docs/UI_STANDARDS.html`, `tailwind.config.js` safelist and `docs/TAILWIND_MIGRATION_PLAN.md`, then re-run the guard.
3. If the guard is wrong (false positive), add the class to `ALLOWED_NON_TW_CLASSES` in `scripts/ui_guard.py` only if it is a legacy hook that is intentionally being kept; otherwise fix the template.

## Summary

> One view, one toolbar, one card, one button pattern. If it looks like it belongs in another module, it should use the same component.
