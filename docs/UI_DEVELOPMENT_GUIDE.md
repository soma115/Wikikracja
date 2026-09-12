# Adding and maintaining UI in Wikikracja

This document describes how to add or change user interface code without fragmenting the visual language of Wikikracja. It applies to Django templates, Tailwind CSS, JavaScript interactions, forms and reusable page components.

The guiding rule is simple: **reuse the shared pattern first; extend it when necessary; introduce a new pattern only when the existing one cannot express the requirement.**

For the visual reference and icon semantics, always consult [`UI_STANDARDS.html`](UI_STANDARDS.html).

## 1. Sources of truth

| Concern | Authoritative source |
| --- | --- |
| Visual patterns and icon meanings | `docs/UI_STANDARDS.html` |
| Theme tokens | `home/static/home/css/tokens.css` |
| Tailwind source and shared components | `home/static/home/css/tailwind.css` |
| Generated CSS | `home/static/home/css/tailwind.build.css` — generated, never edit manually |
| Shared page partials | `home/templates/home/includes/` |
| Crispy/Tailwind form templates | `home/templates/tw/` |
| Shared UI behavior | `home/static/common/js/tw-*.js` |
| Shared application behavior | `home/static/home/js/app.js` |
| Shared ready handler | `window.wkOnReady` in `home/static/common/js/dom-utils.js` |
| Mobile media query | `window.wkMobileMedia` from `home/static/common/js/breakpoints.js` |
| Migration history | `docs/TAILWIND_UI_GUIDE.md` |

Do not create another module-specific stylesheet, duplicate a shared partial, or edit generated `static/` output by hand.

## 2. Before changing a page

1. Search these locations for an existing implementation:
   - `home/templates/home/includes/`
   - `home/templates/tw/`
   - `home/static/common/js/`
   - `docs/UI_STANDARDS.html`
2. Identify the page type: list/grid, detail, form, dashboard tile, modal, dropdown or another established pattern.
3. Keep responsibilities separate:
   - Tailwind/CSS controls presentation;
   - JavaScript controls interaction and state transitions;
   - Django views, forms and services provide data and permissions.
4. Decide whether the change extends an existing component or introduces a new pattern.
5. Do not modify `docs/TODO.md` unless the user explicitly asks for it. Do not edit generated CSS or collectstatic output manually.

## 3. Page structure

### 3.1 List and grid pages

List/grid pages use this anatomy:

1. module header;
2. optional stepper;
3. optional toolbar;
4. optional grouping or filters;
5. `tw-proposals-list` with `data-view-container`;
6. shared empty state when there are no results.

Use:

- `home/templates/home/includes/toolbar.html` for sorting, filtering, search and view switching;
- `data-view="list|grid|compact"` on view controls;
- `data-view-container` on the view root;
- `data-view-only="list|grid|compact"` for view-specific content;
- `PagePrefs` and `applyView` in `home/static/home/js/app.js` for persistence and switching.

The list view is compact and shows less information. The grid view may show more content and use taller cards. Do not create a separate module-specific list/grid implementation when the shared toolbar and `tw-proposals-list` can express the page.

### 3.2 Detail pages

Every detail page uses `home/templates/home/includes/detail_header.html` for its main header.

The partial accepts:

- `title` — required;
- `back_url` and `back_label` — optional navigation back to a list;
- `back_include` — optional contextual back-link partial when navigation needs `data-tw-back`;
- `badges_include` — optional status badges partial;
- `meta_include` — optional metadata partial;
- `actions_include` — optional action buttons partial;
- `navigation_include` — optional Previous/Next controls partial;
- `extra_class` — optional additional class.

The partial standardizes the header only. It does **not** remove or replace module-specific content. Voting arguments, survey results, document attachments, task actions, chat links and other domain sections remain in the page or in their own partials.

Use the shared metadata variants when presenting detail data:

- `tw-detail-meta` for a short, wrapping row of author, date, status and counters;
- `tw-detail-fields` for a multi-field label/value layout, typically on a `<dl>`.

Do not mix metadata variants for equivalent information within one page unless the domain structure requires it.

For detail page headings use `h1` for the page title, `h2` for major sections and `h3` for subsections. Use `tw-detail-section-label`, `tw-detail-section-text` and `tw-detail-subsection` for labelled content sections. Keep exactly `1rem` between `detail_header` and the first content card; do not add a second parent `gap` on that boundary. Keep domain-specific cards such as arguments, attachments and profile tables when they provide meaningful structure.

Use `tw-btn tw-btn-sm tw-btn-outline-secondary` with `fa-arrow-left` for back navigation. Use `tw-detail-nav` and `tw-detail-nav-btn` with chevron icons for Previous/Next controls; icon-only controls require `title` and `aria-label`, while unavailable items use `tw-disabled` and `aria-disabled="true"`. Edit and delete actions in detail views are icon-only `tw-detail-nav-btn` controls with `fa-pen` / `fa-trash` and accessible labels. Delete controls always add `tw-text-danger`; do not introduce module-specific delete colors. Put author, coordinator, dates and status in the header metadata row below the title. If the page includes an embedded chat for the same object, do not render a second standalone chat link.

If an existing detail page has actions that do not fit `actions_include`, keep those actions in the page body while still using the shared header. Do not duplicate the title or move business logic into the shared partial.

### 3.3 Forms

Use the project Crispy/Tailwind form integration:

```django
{% crispy form %}
```

When a field must be rendered separately, use `home/templates/tw/field.html` and the `crispy_classmap` filter. Do not hand-roll Bootstrap-style `form-control` or `is-invalid` wrappers.

Use semantic HTML:

- `<a>` for navigation;
- `<button type="button">` for in-page actions;
- submit buttons inside forms for form submission.

## 4. Shared components

Prefer these existing components before writing new markup:

- `tw-btn`, `tw-btn-primary`, `tw-btn-secondary`, `tw-btn-warning`, `tw-btn-danger`;
- `tw-btn-ghost` for low-emphasis or icon actions;
- `tw-btn-cta tw-btn-cta--round` for the shared add/primary CTA;
- `tw-card`, `tw-card-header`, `tw-card-body`;
- `tw-badge-*` for statuses and categories;
- `tw-alert` and its level variants;
- `home/templates/home/includes/empty_state.html`;
- `home/templates/home/includes/toolbar.html`;
- `home/templates/home/includes/stepper.html`;
- `home/templates/home/includes/detail_header.html`;
- `home/templates/home/includes/modal_header.html`;
- `home/templates/tw/` form/layout templates.

Repeated empty states, card structures, counters, toolbars and modals should be extended centrally instead of copied into each application.

## 5. CSS rules

### Naming and pipeline

- New visual classes use the `tw-` prefix.
- Module-specific classes such as `.ankiety-foo` or `.activity-bar` do not belong in `tailwind.css`.
- Use tokens from `tokens.css` instead of repeating colors, spacing or theme values.
- Use existing utilities and shared components before adding a new rule.
- Add dynamically generated class names to `tailwind.config.js` safelist when content scanning cannot discover them.
- After changing `tailwind.css` or `tailwind.config.js`, regenerate CSS with `npm run build:css`.
- Never hand-edit `home/static/home/css/tailwind.build.css`.

### Inline styles

Inline styles are allowed only for dynamic CSS custom properties, for example:

```html
<div style="--featured-img: url('{{ image.url }}')"></div>
<div style="--vote-progress: {{ percentage }}%"></div>
```

Static colors, spacing, dimensions and visibility belong in `tw-*` classes. JavaScript should use `classList` and `tw-d-none` for visibility, or `style.setProperty('--name', value)` for dynamic CSS variables. Do not assign `element.style.display`, `cssText`, colors or dimensions for ordinary UI state.

## 6. JavaScript and interaction

### Initialization

Use the shared ready handler for page initializers:

```javascript
window.wkOnReady(function () {
    // Initialize the page or component here.
});
```

`window.wkOnReady` runs the callback once whether the script loads before or after `DOMContentLoaded`. Keep initializers safe for pages where their target elements are absent and safe to call for dynamic content.

Do not add another independent `DOMContentLoaded` listener when an existing shared initializer already handles the component. The shared component scripts in `home/static/common/js/` already implement their own ready-state handling and should not be duplicated.

Use the existing interaction primitives and their `data-tw-*` contracts:

- `tw-modal.js`;
- `tw-dropdown.js`;
- `tw-collapse.js`;
- `tw-alert.js`;
- `tw-tooltip.js`;
- `tw-popover.js`;
- `tw-tab.js`.

Do not use inline `onclick`. For nested links or buttons inside clickable cards, use `data-tw-stop-propagation`.

### Clickable cards and rows

Use `data-detail-url` with `role="link"` and `tabindex="0"`. Navigation and keyboard activation are handled by `app.js`. Inner links and buttons must stop parent-card propagation with `data-tw-stop-propagation`.

## 7. Accessibility and localization

- Give icon-only controls a localized `aria-label` and/or `title`.
- Mark decorative icons with `aria-hidden="true"`.
- Keep `aria-pressed`, `aria-expanded`, `aria-controls` and `aria-hidden` synchronized with the actual state.
- Custom interactive elements need matching `role`, `tabindex` and Enter/Space behavior.
- Preserve visible focus styles and adequate contrast. Do not communicate state by color alone.
- Translate user-facing labels, titles, tooltips, empty states and error messages.
- Use the icon dictionary in `docs/UI_STANDARDS.html`. Do not introduce another icon for an existing meaning.

Current icon conventions include:

- `fa-check` — save/confirm;
- `fa-times` — cancel/close;
- `fa-arrow-left` — back;
- `fa-pen` — edit;
- `fa-trash` — delete;
- `fa-plus` — add;
- `fa-list` / `fa-grip` — list/grid view;
- `fa-sort` with `fa-arrow-up` / `fa-arrow-down` — sorting state.

## 8. Responsive behavior

Use the existing Tailwind breakpoints. The shared toolbar responsive breakpoint is `591.98px`; other mobile behavior uses `767.98px` and `window.wkMobileMedia` instead of hardcoding another threshold.

On mobile:

- preserve access to all actions;
- prefer shorter labels or icon-only controls with accessible labels before hiding anything;
- in the shared toolbar, keep the search group flexible (`flex: 1 1 0`, `min-width: 1rem`) above `591.98px`, and move it to a full-width row above the filter and List / Grid button row below `591.98px`;
- keep the filter and List / Grid buttons together in their row; do not implement a module-specific ordering;
- keep list items compact while allowing grid cards to show more information.

## 9. Introducing a genuinely new pattern

A new component is justified only when an existing shared component cannot represent the requirement without harming clarity or accessibility.

When introducing one:

1. implement it in the shared Tailwind pipeline (`tailwind.css`, and `tailwind.config.js` safelist if needed);
2. document its visual and semantic rules in `docs/UI_STANDARDS.html`;
3. update `docs/TAILWIND_UI_GUIDE.md` when the change affects migration scope or remaining work;
4. document the usage and constraints here;
5. add focused regression tests when the component has interaction or accessibility behavior.

Do not add a new component only to avoid adapting an existing shared pattern.

## 10. Verification

Use the repository `.venv` for all Python commands. Do not use system `python`, `pytest` or `ruff` aliases.

### Documentation-only change

Review the Markdown, links and diff. No application test suite is needed.

### Template, CSS or JavaScript change

```powershell
npm run build:css
.venv\Scripts\python.exe scripts\regression_scan.py
.venv\Scripts\python.exe scripts\ui_guard.py
```

For a broad UI change, also run:

```powershell
.venv\Scripts\python.exe scripts\ui_guard.py --all --strict
```

### Django, Python or static-file change

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe manage.py collectstatic --noinput --dry-run
```

Run focused pytest tests for the affected behavior. For JavaScript changes, run:

```powershell
npm test -- --runInBand
```

### Full verification

When the change is broad or the full application suite is required, use:

```powershell
.venv\Scripts\python.exe scripts\run_tests.py
```

The full runner verifies Ruff, regression scanning, Tailwind freshness, Django checks, collectstatic, pytest, Jest and Playwright. It may prepare `.env` and run `collectstatic --clear`; do not use it when those side effects are not acceptable.

## 11. When a guard blocks the change

1. Read the `ui_guard.py` output.
2. Fix issues in the template, CSS or JavaScript rather than bypassing the guard.
3. If the pattern is genuinely new, update `UI_STANDARDS.html`, the Tailwind safelist and the migration plan when applicable, then rerun the guard.
4. Add a class to `ALLOWED_NON_TW_CLASSES` only when it is an intentional, documented legacy or third-party hook.

## 12. Definition of done

A UI change is ready when:

- it uses an existing shared pattern or documents a justified new one;
- list/grid, detail and form pages follow their respective structures;
- all new classes use the shared `tw-*` pipeline;
- keyboard, screen-reader and localization requirements are covered;
- JavaScript initialization is shared and idempotent;
- focused tests and the relevant UI guards pass;
- generated files were regenerated by their tools, not edited manually;
- unrelated working-tree changes and `docs/TODO.md` were left untouched.
