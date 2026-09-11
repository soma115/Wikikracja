# Adding new UI in Wikikracja

This checklist keeps the interface consistent. Before creating a new view, form, card or button, read `docs/UI_STANDARDS.html` and use existing shared components. If the existing component does not fit, extend it or update the standard rather than inventing a one-off exception.

The checklist applies to templates, CSS, JavaScript interactions and reusable form/layout components. For a documentation-only change, use the documentation checks in the verification section instead of running the full application suite.

Checked boxes below indicate practices verified in the current repository. Conditional or per-change actions intentionally remain unchecked until the next relevant change.

## One source of truth

- Visual patterns and icon semantics: `docs/UI_STANDARDS.html`
- Theme tokens: `home/static/home/css/tokens.css`
- Tailwind source and shared components: `home/static/home/css/tailwind.css`
- Generated CSS: `home/static/home/css/tailwind.build.css` — never edit by hand
- Shared template partials: `home/templates/home/includes/`
- Crispy/Tailwind form templates: `home/templates/tw/`
- Shared interaction primitives: `home/static/common/js/tw-*.js`
- Shared application behavior: `home/static/home/js/app.js`
- Shared mobile breakpoint: `home/static/common/js/breakpoints.js`
- Migration history and remaining work: `docs/TAILWIND_MIGRATION_PLAN.md`

## Before coding

- [ ] Search `home/templates/home/includes/`, `home/templates/tw/` and `docs/UI_STANDARDS.html` for an existing pattern.
- [ ] Decide whether the change extends a shared component or introduces a genuinely new pattern.
- [ ] Keep presentation in Tailwind/CSS, behavior in shared or view JavaScript, and data/permissions in the Django view or form.
- [ ] If the pattern is new, plan the corresponding updates to `tailwind.css`, `tailwind.config.js` (when safelisting is needed), `UI_STANDARDS.html` and this checklist.
- [ ] Do not modify generated files, collectstatic output or `docs/TODO.md`.

## Checklist for every new view/fragment

### 1. Layout

- [x] Use `{% extends 'home/base.html' %}`.
- [x] Wrap content in `{% block content %}`.
- [x] Use `tw-container tw-my-4` or `tw-container tw-section` for top-level spacing.
- [x] Do not use custom `.section` / `.section-heading`; use `tw-section` and `tw-section-heading`.
- [ ] Keep the stable page anatomy: module header, optional stepper, optional toolbar, optional grouping, `tw-proposals-list`, then empty state.

### 2. Toolbar

- [x] If the page has sorting, view toggles (list/grid/compact) or filters, include `home/templates/home/includes/toolbar.html`.
- [x] Toolbar must use `tw-toolbar`, `tw-sort-btn`, `tw-view-toggle-btn` and `tw-toolbar-divider`.
- [x] View switching must use `data-view="list|grid|compact"`, `data-view-container` and `[data-view-only]`.

### 3. Cards and lists

- [x] Use `tw-card` for content cards.
- [x] Card headers use `tw-card-header`; body uses `tw-card-body`.
- [x] Lists use `tw-proposals-list` (or its successor if documented otherwise) + `data-view-container`.
- [x] Empty states use the shared partial `home/includes/empty_state.html` (`tw-empty-state` + `tw-empty-state-icon`/`tw-empty-state-title`).
- [ ] Detail page headers use the shared partial `home/includes/detail_header.html` (`title` required; `back_url`, `badges_include`, `meta_include`, `actions_include`, `extra_class` optional).
- [x] Clickable rows/cards use `data-detail-url` + `role="link" tabindex="0"` (navigation handled by `app.js`); inner links/buttons keep `data-tw-stop-propagation`.
- [x] Do not create new `module-card`, `module-list`, `module-empty` classes.

### 4. Accessibility and semantics

- [x] Use the semantic element that matches the action: `<a>` for navigation, `<button type="button">` for in-page actions, and a real form submit button for form submission.
- [x] Give icon-only controls an accessible, localized `aria-label` and/or `title`; decorative icons use `aria-hidden="true"`.
- [x] Keep keyboard access for custom interactive elements: `role`, `tabindex`, and Enter/Space behavior must be provided together.
- [x] Keep state synchronized with `aria-pressed`, `aria-expanded`, `aria-controls` or `aria-hidden` where the component needs it.
- [x] Preserve visible focus styles and sufficient text/icon contrast; do not communicate state by color alone.
- [x] Use translated labels and titles for user-facing text, including empty states, tooltips and button labels.

### 5. Buttons and actions

- [x] Primary: `tw-btn tw-btn-primary`
- [x] Secondary: `tw-btn tw-btn-secondary` or `tw-btn tw-btn-outline-secondary`
- [x] Warning: `tw-btn tw-btn-warning`
- [x] Danger: `tw-btn tw-btn-danger`
- [x] Ghost/icon: `tw-btn tw-btn-ghost` or `tw-btn tw-btn-sm tw-btn-ghost`
- [x] CTA (floating/primary): `tw-btn-cta tw-btn-cta--round`, with a localized accessible label/title.
- [x] Use the icon dictionary for action semantics; do not choose a new icon variant for an existing action.
- [x] Avoid `.btn-icon-clean`, `.btn-ghost-old` and other pre-Tailwind classes.

### 6. Forms

- [x] Prefer `{% crispy form %}` with a `FormHelper`.
- [x] If you need per-field rendering, use `home/templates/tw/field.html` and `crispy_classmap`.
- [x] Do not hand-roll `is-invalid` / `form-control` wrappers.

### 7. Icons

- [x] Look up the semantic meaning in `docs/UI_STANDARDS.html`.
- [x] Use Font Awesome classes from the dictionary (`fa-check`, `fa-pen`, `fa-trash`, etc.).
- [x] If a new icon is genuinely needed, add it to `docs/UI_STANDARDS.html` first, then use it.
- [x] Use `fa-times` for close/cancel; do not use `fa-xmark`. Use `fa-triangle-exclamation` for warnings; do not use `fa-exclamation-triangle`. Use `fa-check-circle`/`fa-times-circle` for status; do not use `fa-circle-check`/`fa-circle-xmark`.

### 8. Inline styles

- [x] Inline `style="..."` is allowed **only** for dynamic CSS variables: `style="--featured-img: url('...')"` or `style="--vote-progress: {{ pct }}%"`.
- [x] In JavaScript, update dynamic CSS variables with `style.setProperty('--name', value)`; do not assign presentation through `element.style.display`, `cssText`, colors or dimensions.
- [x] Everything else (colors, spacing, visibility, width, height) must be a Tailwind utility class (`tw-*`). Use `tw-d-none`/`classList` for show/hide state.

### 9. New CSS

- [x] Every new class must have the `tw-` prefix.
- [x] If the class is generated dynamically, add it to the `safelist` in `tailwind.config.js`.
- [x] Do not add module-specific rules like `.ankiety-foo` or `.activity-bar` to `tailwind.css`.
- [x] Prefer extending an existing shared component or using utility classes.
- [ ] After changing `tailwind.css` or `tailwind.config.js`, run `npm run build:css`; never hand-edit `tailwind.build.css`.

### 10. JavaScript and interaction

- [x] Mobile breakpoint is `767.98px`; do not hardcode a new value. Use the shared `window.wkMobileMedia` (`home/static/common/js/breakpoints.js`, loaded in `base.html`) or the `mobileMedia` re-export in `chat/static/chat/js/utility.js`.
- [x] List/grid toggling goes through `PagePrefs` and `applyView` in `home/static/home/js/app.js`.
- [x] Use existing shared primitives from `home/static/common/js/` (`tw-modal.js`, `tw-dropdown.js`, `tw-collapse.js`, `tw-alert.js`, `tw-tooltip.js`, `tw-popover.js`, `tw-tab.js`) and their `data-tw-*` contracts instead of adding another implementation.
- [ ] Do not add a new `addEventListener('DOMContentLoaded')` if an existing shared initializer already covers the case; keep initialization idempotent for dynamic content.
- [x] Do not use inline `onclick`; use delegated/shared handlers and `data-tw-stop-propagation` where nested controls must not activate a parent card.

### 11. Responsive behavior

- [x] Use the existing Tailwind breakpoints and shared responsive utilities; do not introduce a second mobile threshold.
- [x] On mobile, preserve access to all actions. Prefer compact labels or icon-only controls with accessible labels before hiding a control.
- [x] Keep search and list/grid controls usable on one line where the shared toolbar pattern supports it; allow groups to wrap naturally when necessary.
- [x] Check list and grid separately: list items stay compact, while grid cards may show more content and be taller.

### 12. Verification

- [x] Documentation-only change: check Markdown links/formatting and review the diff; do not rebuild CSS or run the application suite.
- [ ] Template/CSS/JS change: run `npm run build:css` only when the Tailwind source/config changed, then run `python scripts/regression_scan.py` and `python scripts/ui_guard.py`.
- [ ] New shared pattern or broad UI change: also run `python scripts/ui_guard.py --all --strict` and update `docs/UI_STANDARDS.html` plus `docs/TAILWIND_MIGRATION_PLAN.md` when applicable.
- [ ] Django template/view/form change: run `python manage.py check` and the focused relevant tests.
- [ ] Python logic change: run `ruff check .`, `ruff format --check .` and focused `pytest` tests.
- [ ] JavaScript logic change: run `npm test -- --runInBand` or the focused Jest test file.
- [ ] Run `python manage.py collectstatic --noinput --dry-run` when static asset discovery or deployment behavior changed.

## When the guard blocks you

1. Read the `ui_guard.py` output. Issues are hard blockers; warnings are soft unless `--strict` is used.
2. If the guard complains about a genuinely new pattern that should become a standard, update `docs/UI_STANDARDS.html`, `tailwind.config.js` safelist and `docs/TAILWIND_MIGRATION_PLAN.md`, then re-run the guard.
3. If the guard is wrong (false positive), add the class to `ALLOWED_NON_TW_CLASSES` in `scripts/ui_guard.py` only if it is a legacy hook that is intentionally being kept; otherwise fix the template.

## Summary

> One view, one toolbar, one card, one button pattern. If it looks like it belongs in another module, it should use the same component.
