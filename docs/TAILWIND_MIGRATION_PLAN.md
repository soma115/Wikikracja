# Plan migracji na Tailwind

Cel: przejście z Bootstrap + rozproszony custom CSS na jeden pipeline Tailwind, bez zmiany dotychczasowego wyglądu. Migracja bazowa (fazy 0–5) została zakończona; dalsze etapy domykają zależności, testy regresji i utrzymanie standardu UI.

---

## Faza 0 — Fundament

- [x] Zainstalować Tailwind CLI (`tailwindcss` już w `node_modules`).
- [x] Utworzyć `tailwind.config.js` z prefixem `tw-` (unika konfliktów z Bootstrapem) i kolorami z tokens.css.
- [x] Utworzyć `home/static/home/css/tailwind.css` jako źródło Tailwind.
- [x] Dodać `postcss.config.js` i skrypty buildu w `package.json` (`npm run build:css` / `watch:css`).
- [x] Dodać `<link rel="stylesheet" href="{% static 'home/css/tailwind.build.css' %}">` do `base.html`; po zakończeniu migracji pozostawić obok niego wyłącznie `tokens.css`.
- [x] Wylistować obecne klasy CSS do zamiany w `docs/TAILWIND_CLASS_INVENTORY.md`.
- [x] Dodać testową klasę Tailwind (`tw-text-accent`) do powitania w `home/home.html` i zbudować CSS.

## Faza 1 — Komponenty podstawowe Tailwind

- [x] Zdefiniować `tw-btn`, `tw-btn-primary`, `tw-btn-secondary`, `tw-btn-sm`, `tw-btn-outline-*` w Tailwind naśladujące obecny wygląd.
- [x] Zdefiniować `tw-card`, `tw-card-header`, `tw-card-body`, `tw-card-footer`.
- [x] Zdefiniować `tw-badge`, `tw-badge-proposition`, `tw-badge-discussion`, `tw-badge-referendum`, `tw-badge-approved`, `tw-badge-rejected`.
- [x] Zdefiniować `tw-form-control`, `tw-form-select`, `tw-form-label`.
- [x] Zdefiniować `tw-alert`, `tw-alert-info`, `tw-alert-success`, `tw-alert-warning`, `tw-alert-danger`.
- [x] Dodać `safelist` w `tailwind.config.js`, żeby komponenty były generowane zanim zostaną użyte w szablonach.
- [x] Zweryfikować build (`npm run build:css`) — wszystkie komponenty są w `tailwind.build.css`.

## Faza 2 — Globalny layout (base.html)

- [x] Przepisać `body`, `.layout-wrapper`, `.main-area`, `.main-content` na Tailwind (`tw-layout-wrapper`, `tw-main-area`, `tw-main-content`).
- [x] Przepisać `.topbar` i jego elementy (breadcrumb, search, theme toggle, bell) na `tw-topbar`, `tw-topbar-breadcrumb`, `tw-search-box`, `tw-notif-bell`, `tw-notif-count`.
- [x] Przepisać `.sidebar` (logo, nawigacja, bottom links, close/toggle) na `tw-sidebar`, `tw-sidebar-logo`, `tw-sidebar-nav`, `tw-nav-item`, `tw-nav-icon`, `tw-nav-text`, `tw-sidebar-bottom`, `tw-sidebar-toggle-btn`, `tw-sidebar-close-btn`.
- [x] Przepisać `.toast-container` i `.toast-msg` na `tw-toast-container`, `tw-toast-msg`, `tw-toast-close`, `tw-toast-{level}`.
- [x] Przepisać notyfikacje banner (`#notification-permission-banner`) na `tw-alert tw-alert-info` / `tw-alert-warning`.
- [x] Naprawić mobile: w `tailwind.css` dodano reguły responsywne dla `tw-sidebar` (fixed + `translateX(-100%)`, `.sidebar-open`), `tw-topbar`, `tw-main-content` i `tw-sidebar-bottom`.
- [x] Usunąć zastąpione `navigation.css` i `layout.css`; potrzebne reguły zostały scalone z pipeline’em Tailwind w fazie 5.5.

## Faza 3 — Strona główna (home/home.html)

- [x] **3.1 Sekcja niezalogowana + powitanie**
  - [x] Przepisać `section` dla niezalogowanych, guziki (`Login`, `Sign Up`, `Reset password`, `Message developer`) na `tw-btn`.
  - [x] Przepisać powitanie (`Hi, <username>`), `section-heading`, `text-muted`.
  - Uwaga: kolory w `tailwind.config.js` wskazują na `var(--*)` z `tokens.css` (jedno źródło prawdy, wsparcie dark/light). `module_card.html` przepisany razem z sekcją (grid `tw-grid` zamiast `row`/`col`).
- [x] **3.2 Layout kafelków**
  - [x] Zdefiniować `tw-dashboard-grid`, `tw-dashboard-tile`, `tw-dashboard-tile--1x1/2x1` w `tailwind.css`.
  - [x] Zdefiniować `tw-dashboard-tile-header`, `tw-tile-heading`, `tw-section-heading`.
  - Uwaga: `dashboard-tile--compact` i `drag-handle` pozostają semantycznymi hakami JS (`home.html`, `sortable-list.js`), a ich wygląd jest zdefiniowany w pipeline Tailwind.
  - Uwaga: `tailwind.config.js` nadpisuje `theme.screens` breakpointami Bootstrapa (`sm:576, md:768, lg:992, xl:1200, 2xl:1400`), żeby warianty responsywne zachowywały się jak dotychczas, także na mobile.
- [x] **3.3 Kafelek Ważne linki**
  - [x] Przepisać `quick-links-scroll`, `quick-link-row`, `quick-link-circle`, progress bar (`tw-quick-links-scroll`, `tw-quick-link-circle`, `tw-quick-link-row`, `tw-progress`/`tw-progress-bar`).
  - Uwaga: `.is-read` i `.progress-label` pozostają semantycznymi hakami JS; komponenty wizualne korzystają z `tw-quick-*` i `tw-progress-*`.
- [x] **3.4 Kafelek Aktywność**
  - [x] Przepisać `activity-feed-row`, `unread-item`, badge status, `task-dash-link`, `stretched-link` (+ `tw-task-dash-row`, `tw-unread-row`, `tw-dashboard-counter-btn`, `tw-activity-more`, `tw-text-primary-link`, `tw-badge-status*`).
  - Uwaga: `content_type_color` zwraca nazwy Bootstrapowe (`primary`/`warning`/`success`/`info`/`danger`/`secondary`/`dark`) — dodano `tw-badge-*` dla nich i wpisano do `safelist` (klasa składana dynamicznie w szablonie).
  - Uwaga: zachowane haki JS to `.activity-feed-row`, `.task-dash-link`, `.unread-item`, `#activity-feed-body`, `#activity-feed-more` i atrybuty `data-*`; kontenery kart używają `tw-card`/`tw-card-header`.
- [x] **3.5 Kafelek Wybrane dokumenty**
  - [x] ~~Bootstrap carousel~~ → własny lekki slider (`tw-featured-carousel` + `tw-featured-carousel-track/-item` + `tw-carousel-btn/-prev/-next` + inline JS w `home.html`). Tailwind nie ma wbudowanej karuzeli, a Flowbite nie współpracuje z prefiksem `tw-` — dlatego natywna implementacja zamiast nowej zależności.
  - [x] Dodać `tw-tile-carousel-wrapper`, `tw-featured-carousel`, `tw-featured-carousel-title`, `tw-link-more` w `tailwind.css`.
  - [x] Podtytuł dokumentu na slajdzie (`tw-featured-carousel-subtitle`); podpis theme-aware (`--text-primary` + gradient z `--bg-card`); jasność obrazka przez token `--featured-img-brightness` (0.6 dark / 1.3 light). `board/dashboard.py` pobiera `subtitle` w `.only()`.
  - Uwaga: poniżej 992px (grid 1-kolumnowy) kafelki nie mają narzuconej wysokości — `tw-tile-carousel-wrapper` dostaje `flex: none`, a `tw-featured-carousel` `aspect-ratio: 16/9` + `object-fit: cover` na img: stała, kompaktowa wysokość i obrazek zawsze wypełnia cały obszar niezależnie od proporcji.
- [x] **3.6 Kafelek Najbliższe wydarzenia**
  - [x] Przepisać `dot-public`, `dot-private`, `task-dash-row`, `stretched-link`, empty state na `tw-*`.
- [x] **3.7 Kafelki głosowań (propozycje, dyskusje, aktywne)**
  - [x] Przepisać `badge-proposition`, `badge-discussion`, `badge-referendum` na `tw-badge-*` i resztę kafelków na `tw-*`.
- [x] **3.8 Kafelek Moje aktywności**
- [x] **3.9 Kafelek Nowi ludzie**
- [x] **3.10 Kafelek Finanse**
- [x] **3.11 Kafelek Chat**
- [x] **3.12 Kafelek Umiejętności i zasoby**
- [x] **3.13 Kafelek Aktywni użytkownicy**
- [x] **3.14 Kafelek Kalendarz**
- [x] Po zakończeniu fazy: usunąć `modules.css` / `utilities.css` fragmenty dotyczące dashboardu.
  - Usunięto martwe reguły: `.link-more`, `.dashboard-counter-btn`, `.quick-links-scroll`, `.quick-link-*`, `.dot-public/dot-private`, `.balance-positive/negative`, `.hr-subtle`, progress helpers, `.dashboard-grid`, `.dashboard-tile*`, `.dashboard-tile-header`, `.tile-carousel-wrapper`, `.featured-carousel*`, `.chat-msg-*`, `.asset-chip`, `.wspol-stat-value`, `.wspol-stat-label`, `.wspol-section-title`, `.tile-heading`, `.tile-text-muted`, `.onboarding-hint` z `utilities.css` / `modules.css` / `layout.css`.
  - Pozostawione: `.task-dash-row`, `.task-dash-link`, `.badge-status*`, `.text-primary-link`, `.drag-handle`, `.sortable-ghost/chosen`, `.profile-email`, `.section-heading` — używane w innych modułach.

## Faza 4 — Moduły aplikacji

- [x] **4.1 Board** (`board/*`)
  - [x] `board/templates/board/board.html` — toolbar, kategorie, widok listy/siatki, kafelki dokumentów.
  - [x] `home/templates/home/includes/toolbar.html` — wspólny toolbar (używany też w innych modułach).
  - [x] `board/templates/board/post_detail.html` — widok szczegółu, załączniki, akcje.
  - [x] `board/templates/board/post_form.html` — formularz dokumentu.
  - [x] `board/templates/board/post_confirm_delete.html`.
  - [x] `board/templates/board/attachment_confirm_delete.html`.
  - [x] `board/templates/board/_post_card.html`.
  - Uwaga: użytkownik zaktualizował `board/templates/board/board.html` (featured-image background z CSS var `--featured-img`). Zachowano ten pattern.
- [x] **4.2 Obywatele** (`obywatele/*`)
  - [x] `obywatele/templates/obywatele/parameters.html` — parametry społeczności.
  - [x] `obywatele/templates/obywatele/start.html` — lista obywateli (toolbar, widok listy/siatki, status dots).
  - [x] `obywatele/templates/obywatele/poczekalnia.html` — poczekalnia kandydatów.
  - [x] `obywatele/templates/obywatele/assets.html` — zasoby / umiejętności.
  - [x] `obywatele/templates/obywatele/my_assets.html` — edycja własnych zasobów.
  - [x] `obywatele/templates/obywatele/my_profile.html` — mój profil, zakładki.
  - [x] `obywatele/templates/obywatele/szczegoly.html` — szczegóły obywatela.
  - [x] `obywatele/templates/obywatele/citizen_*.html` oraz partiale `_citizen_*.html` — zakładki profilu.
  - [x] `obywatele/templates/obywatele/candidate_edit.html`, `dodaj.html`, `change_email.html`, `change_username.html` — formularze.
  - [x] `obywatele/templates/obywatele/onboarding_details.html`, `onboarding_waiting.html` — onboarding.
  - [x] `obywatele/templates/obywatele/menu.html` — nawigacja stepper (stare klasy stepper pozostawione, CTA na Tailwind).
  - [x] `obywatele/templates/obywatele/includes/notification_row.html`.
- [x] **4.3 Głosowania** (`glosowania/*`)
  - [x] `glosowania/templates/glosowania/menu.html` — menu / lista.
  - [x] `glosowania/templates/glosowania/list.html` — lista propozycji.
  - [x] `glosowania/templates/glosowania/szczegoly.html` — szczegóły głosowania.
  - [x] `glosowania/templates/glosowania/_proposal_card.html`, `_proposed_brand_mark.html`, `_view_toggle.html`.
  - [x] `glosowania/templates/glosowania/dodaj.html`, `edit.html`, `edit_argument.html`, `delete_argument.html`.
  - [x] `glosowania/templates/glosowania/parameters.html`, `parameters_propose.html`.
  - [x] `glosowania/templates/glosowania/historia.html`.
- [x] **4.4 Ankiety** (`ankiety/*`)
  - [x] `ankiety/templates/ankiety/survey_list.html` — lista ankiet.
  - [x] `ankiety/templates/ankiety/survey_form.html` — formularz ankiety.
  - [x] `ankiety/templates/ankiety/survey_detail.html` — szczegóły ankiety.
  - [x] `ankiety/templates/ankiety/_survey_results.html` — wyniki.
- [x] **4.5 Events** (`events/*`)
  - [x] `events/templates/events/event_list.html` — lista wydarzeń.
  - [x] `events/templates/events/event_form.html` — formularz wydarzenia.
  - [x] `events/templates/events/event_detail.html` — szczegóły wydarzenia.
  - [x] `events/templates/events/event_confirm_delete.html` — potwierdzenie usunięcia.
  - [x] `events/templates/events/_agenda_chunk.html`, `_event_card.html` — partial.
- [x] **4.6 Tasks** (`tasks/*`)
  - [x] `tasks/templates/tasks/menu.html` — stepper.
  - [x] `tasks/templates/tasks/task_list.html` — lista zadań, toolbar, modal kategorii.
  - [x] `tasks/templates/tasks/_task_card.html`, `_task_list_partial.html`, `_empty_state.html` — karty zadań.
  - [x] `tasks/templates/tasks/task_detail.html` — szczegóły zadania.
  - [x] `tasks/templates/tasks/task_form.html`, `task_close.html`, `task_help.html`, `task_stats.html` — formularze i strony pomocnicze.
- [x] **4.7 Bookkeeping** (`bookkeeping/*`)
  - [x] `bookkeeping/templates/bookkeeping/_nav.html` — nawigacja.
  - [x] `bookkeeping/templates/bookkeeping/_report_pivot.html` — pivot raportów.
  - [x] `bookkeeping/templates/bookkeeping/transaction_list.html`, `transaction_form.html`, `transaction_confirm_delete.html`.
  - [x] `bookkeeping/templates/bookkeeping/asset_list.html`, `asset_form.html`, `asset_confirm_delete.html`.
  - [x] `bookkeeping/templates/bookkeeping/category_list.html`, `category_form.html`, `category_confirm_delete.html`.
  - [x] `bookkeeping/templates/bookkeeping/partner_list.html`, `partner_form.html`, `partner_detail.html`, `partner_confirm_delete.html`.
  - [x] `bookkeeping/templates/bookkeeping/report_list.html`, `confirm_delete.html`.
- [x] **4.8 Chat** (`chat/*`)
  - [x] `chat/templates/chat/chat.html` — lista pokoi i obszar wiadomości.
  - [x] `chat/templates/chat/room_link.html` — link pokoju w liście.
  - [x] `chat/templates/chat/_embedded_chat.html` — osadzony widget czatu.
  - [x] `chat/templates/chat/add.html` — formularz tworzenia pokoju.
  - [x] `chat/templates/chat/guest_message.html` — formularz gościa.
  - [x] `chat/static/chat/js/handlers.js` — poprawka przełączania listy przy resize.
- [x] **4.9 Strony globalne**
  - [x] `home/templates/home/search.html`
  - [x] `home/templates/home/activity.html`
  - [x] `home/templates/home/site_admin.html`
  - [x] `home/templates/home/haslo.html`
  - [x] `home/templates/home/password_reset_form.html`, `password_reset_done.html`, `password_reset_confirm.html`, `password_reset_complete.html`
  - [x] `templates/allauth/account/login.html`
  - [x] `templates/allauth/account/signup.html`
  - [x] `templates/allauth/account/password_reset*.html`, `password_set.html`, `password_change.html`, `email*.html`, `email_confirm.html`, `verification_sent.html`, `verified_email_required.html`, `account_inactive.html`, `logout.html`, `signup_closed.html`

## Faza 5 — Porządki i usunięcie starego CSS

- [x] **5.1 Audyt** — sprawdzić, które stare pliki CSS i klasy są jeszcze używane.
- [x] **5.2 Usunięcie martwych fragmentów**
  - [x] Usunięty `home/static/home/css/cards.css` (reguła `.card-body { color }` była redundantna wobec `.tw-card`).
  - [x] Usunięta paginacja z `tables.css` (klasy `.pagination`/`.page-link` nieużywane).
  - [x] Usunięta zakładka `.nav-tabs` z `navigation.css` (nieużywana) i oczyszczony błędny selektor grupujący z `.pagination .page-link:hover`.
  - [x] Usunięta martwa klasa `.description-truncate` z `base.css`.
- [x] **5.3 Dokończenie migracji surowych klas do `tw-*`** — wszystkie surowe klasy Bootstrap w szablonach zostały zamienione na `tw-*` (lub objęte własnymi regułami); pozostały wyłącznie klasy modułowe/haki (`btn-cta`, `btn-cta-label`, `btn-icon-clean`, `nav-status`, `action-btn`, `task-vote-btn`, `sort-btn`, `fmt-btn`, `cal-table`, `progress-label`, `copy-feedback`, `message-btn` itp.).
  - [x] **5.3.1 Pierwsze 31 plików** — `home/*` (site_admin, activity, search, password_*, haslo), `allauth/account/*`, `chat/*`, `board/post_form.html`, `obywatele/szczegoly.html`, `bookkeeping/*` (transaction_list, report_list, partner_list, category_list, asset_list, _report_pivot, _nav, transaction_form, transaction_confirm_delete, partner_form, partner_detail, category_form, asset_form, confirm_delete). Dodatkowo oczyszczono `home/home.html`, `home/base.html`, `home/includes/module_card.html` jako globalne szablony wpływające na te widoki.
  - [x] **5.3.2 Kolejne pliki** — `events`, `glosowania`, `tasks`, `ankiety`, `board`, `obywatele` i `home`. Surowe klasy Bootstrap usunięto z 90+ szablonów; pozostawiono wyłącznie semantyczne haki modułowe CSS/JS.
- [x] **5.4 Usunięcie załączania `darkly.css` / Bootstrap — podział na podfazy**
  - [x] **5.4.1 Tabele i formularze** — dodać brakujące `tw-*` (`tw-table-sm`, `tw-table-hover`, `tw-d-*-table-cell`, `tw-form-check*`, `tw-form-text`, `tw-input-group`, `tw-input-group-text`, `tw-invalid-feedback`, `tw-form-control-sm`, `tw-form-select-sm`, `tw-text-body`) do `tailwind.css` i `safelist`; zastąpiono surowe klasy w szablonach obywatele, ankiety, board, chat, home, tasks, bookkeeping, glosowania oraz w forms.py i JS kolumn.
  - [x] **5.4.2 Listy grupowe i utility** — dodać `tw-d-*` (display utilities), `tw-disabled`; uzupełnić `tw-list-group-flush`, `tw-text-body`, `tw-stretched-link`; zastąpiono surowe `list-group*` w board, glosowania, obywatele; `stretched-link` w home; `disabled` w glosowania; `d-none` w home/activity, home/app, obywatele/citizens_list oraz w całym czacie (handlers, templates, domapi, chat-core, chat-embedded, Jest).
  - [x] **5.4.3 Modale, dropdowny, collapse** — dodać `tw-modal*`, `tw-fade`, `tw-dropdown*`, `tw-btn-close`, `tw-collapse`; stworzono `home/static/common/js/tw-modal.js`, `tw-dropdown.js`, `tw-collapse.js`; przepisano szablony modali/dropdownów/collapse na `tw-*` i `data-tw-*`; zastąpiono `bootstrap.Modal/Dropdown/Collapse` w `app.js`, `chat.js`, `handlers.js`, `category-manager.js`, `chat-core.js`, `domapi.js`; podpięto nowe skrypty w `base.html`; tooltips/popovers/tabs nadal używają Bootstrap JS (5.4.5 dopiero po nich).
  - [x] **5.4.4 Crispy Forms** — stworzono własny template pack `tw` w `home/templates/tw/` (43 szablony oparte na `crispy_bootstrap5`), dodano filtr `crispy_classmap` w `home/templatetags/crispy_classmap.py` do mapowania klas Bootstrap na `tw-*`; zmieniono `CRISPY_TEMPLATE_PACK` i `CRISPY_ALLOWED_TEMPLATE_PACKS` na `tw`; poprawiono `events/forms.py`, `bookkeeping/forms.py`, `board/forms.py` na `tw-*`; dodano `.tw-form-check-inline` do `tailwind.css`.
  - [x] **5.4.5 Usunięcie Bootstrap JavaScript i `data-bs-*`** — stworzono `home/static/common/js/tw-tooltip.js`, `tw-popover.js`, `tw-tab.js`, `tw-alert.js`; dodano style `tw-tooltip`, `tw-popover`, `tw-tab-*` do `tailwind.css`; podpięto skrypty w `base.html`; zmigrowano wszystkie `data-bs-toggle="tooltip"`, `data-bs-toggle="popover"`, `data-bs-toggle="tab"` na `data-tw-*` w szablonach i JS (`app.js`, `tasks.js`, `task_form.html`); poprawiono `home/templates/tw/layout/modal.html` i `alert.html` na `data-tw-dismiss`; usunięto `{% bootstrap_javascript %}` i `{% bootstrap_css %}` z `home/templates/home/base.html`, `obywatele/parameters.html`, `glosowania/parameters.html`, `templates/allauth/account/signup.html`, `templates/allauth/account/logout.html`.
  - [x] **5.4.6 Usunięcie `darkly.css`** — zastąpiono wszystkie `var(--bs-*)` projektowymi tokenami w `tailwind.css`, `modules.css`, `base.css`, `tables.css`, `layout.css`, `utilities.css`, `forms.css`, `light-mode.css`; rozbudowano `tokens.css` o `--color-*`, `--table-*`, `--popover-*`, `--badge-*`, `--alert-*`, `--bg-tertiary` itp.; usunięto `darkly.css` z `home/templates/home/base.html`; fizycznie usunięto `home/static/home/css/darkly.css`; ostatnie surowe klasy Bootstrap w szablonach/JS (`table`, `table-hover`, `table-sm`, `table-responsive`, `progress`/`progress-bar`, `btn`/`btn-sm`/`btn-*`, `badge-*`, `nav-item`/`nav-icon`/`nav-text` w sidebarze, `visually-hidden`, `blockquote`, `text-decoration-none` itp.) zamieniono na `tw-*`; zaktualizowano `obywatele/tables.py`, JS chat/citizens_list/app.
- [x] **5.5 Usunięcie pozostałych starych plików CSS** — reguły z `base.css`, `navigation.css`, `forms.css`, `buttons.css`, `feedback.css`, `tables.css`, `typography.css`, `modules.css`, `utilities.css`, `layout.css` i `light-mode.css` scalono do `home/static/home/css/tailwind.css` (sekcja na początku `@layer components`, w dawnej kolejności `<link>`). Przy scalaniu odrzucono reguły martwe (selektory klas/id bez żadnego użycia w szablonach, JS ani Pythonie) oraz reguły w pełni pokryte przez bliźniacze klasy `tw-*` (np. `.form-control`, `.form-check-input`, `.sidebar-toggle-btn`, `.layout-wrapper`, `.status-dot`, `.btn-success`, `.btn-outline-*`, `.toast-container`, `.dropdown-*`, `.list-group-item`, `.modal-*`, `.alert-*`, `.badge-*`, `.board-post-card`, `.post-*`, `.table-striped/.table-hover`). Zachowano pod oryginalnymi nazwami wszystkie klasy niestandardowe używane przez szablony/JS/Python (w tym klasy składane dynamicznie: `toast-{{…}}`, `status-dot--{{…}}`, `task-meta-status-{{…}}`, `s{{…}}`, `avatar-{{…}}`, `citizen-color-*`, `cal-day-link--selected`, `events-calendar--loading`, `fieldset-{{…}}`) oraz klasy generowane przez zewnętrzne biblioteki (`captcha`, `tox-tinymce`). Dla reguł odrzuconych jako pokryte dodano brakujące stany pod nazwami `tw-*` (`.tw-sidebar-toggle-btn:hover`, `select.tw-form-select option`, `.tw-form-check-input:not(:checked):not(:focus):not(:disabled)`). Usunięto wszystkie 11 linków i fizycznie usunięto pliki; `base.html` ładuje już tylko `tokens.css` + `tailwind.build.css`.
- [x] **5.6 Pozostawić `tokens.css`** jako źródło prawdy dla kolorów.
- [x] **5.7 `tailwind.build.css` i `collectstatic`** — budowany automatycznie, podpięty pod `collectstatic`.

## Etap A — Domknięcie migracji

- [x] Usunąć tagi `{% bootstrap_messages %}` i `{% load django_bootstrap5 %}`; komunikaty obsługuje globalny komponent `tw-toast-*` w `base.html`.
- [x] Usunąć `django-bootstrap5` z `INSTALLED_APPS` i `requirements.txt`.
- [x] Usunąć `crispy-bootstrap5` z `INSTALLED_APPS` i zastąpić zależność bezpośrednią `django-crispy-forms==2.7`; własny template pack `tw` pozostaje jedynym aktywnym packiem.
- [x] Zastąpić `django_tables2/bootstrap5.html` projektowym `home/templates/tw/table.html` i usunąć zależność tabel od klasy `.table`.
- [x] Scalić `chat/static/chat/css/chat.css` z `home/static/home/css/tailwind.css`, usunąć osobny arkusz i jego linki.
- [x] Usunąć oczywiste aliasy selektorów Bootstrap (`.btn`, `.table`, `.alert`, `.card`, layout/sidebar) oraz przełączyć ich konsumentów na `tw-*`.
- [x] Zachować prefix `tw-` jako trwałą przestrzeń nazw projektu i zaktualizować komentarze konfiguracji.
- [x] Wykonać końcowy build, testy, `collectstatic` i skany repozytorium bez zależności Bootstrap — CSS build, Django check, Ruff, Jest 171/171, pytest 772/772 i `collectstatic --dry-run` zakończone powodzeniem.

## Etap B — Zabezpieczenie przed regresjami

- [x] Dodać testy Jest dla `TwModal`, `TwDropdown`, `TwCollapse`, `TwTab`, `TwTooltip`, `TwPopover` i `TwAlert`.
- [x] Dodać test CI zabraniający ponownego użycia `data-bs-*`, `bootstrap.*`, `django_bootstrap5`, `crispy_bootstrap5`, `--bs-*` i usuniętych arkuszy.
- [x] Dodać test sprawdzający, że `tailwind.build.css` jest aktualny względem `tailwind.css` i konfiguracji.
- [x] Dodać reprezentatywne testy Playwright dla desktop/mobile oraz motywów dark/light (dashboard, formularz, tabela, modal, dropdown, zakładki).
- [x] Dodać automatyczne kontrole dostępności dla wspólnych komponentów interaktywnych.

## Etap C — Utrzymanie standardu UI

- [x] Ujednolicić `docs/UI_STANDARDS.html` z produkcyjnymi `tokens.css` i `tailwind.build.css`, aby dokumentacja nie miała niezależnej implementacji komponentów.
- [x] Utrzymywać `tokens.css` jako jedyne źródło kolorów i parametrów motywu.
- [x] Nowe komponenty dodawać do `@layer components` tylko wtedy, gdy nie wystarczają istniejące utilities i komponenty `tw-*`.
- [x] Okresowo usuwać martwe klasy z safelist i semantyczne haki, które przestały być używane.
- [ ] Po ustabilizowaniu UI wrócić do funkcji produktowych z `docs/TODO.md` bez kolejnego szerokiego refaktoringu CSS.

## Zasady zastosowane podczas migracji

1. **Zawsze ładuj Tailwind obok starych stylów** — dopóki dany komponent nie jest w pełni przepisany.
2. **Jeden komponent = jeden krok** — nie przerabiać wszystkiego naraz.
3. **Naśladować obecny wygląd** — kolory, odstępy, radiusy, cienie mają pochodzić z `tokens.css`.
4. **Nie usuwać starego CSS przedwcześnie** — usuwamy dopiero po zweryfikowaniu, że Tailwind go zastępuje.
5. **Testować na jednym widoku** — każdy kafelek / strona powinna wyglądać dobrze zanim przejdziemy dalej.
6. **Aktualizować ten plan** — odhaczać checkboxy i dopisywać napotkane problemy.

---

*Plan utworzony: {{ plan_date|default:"teraz" }}*
