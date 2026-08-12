# Standaryzacja wyglądu Wikikracji

Plik-tracker dla operacji uporządkowania frontendu. Znajdują się tu nazwane etapy; po zakończeniu każdego etapu zaznaczam checkboxy i przechodzę do następnego dopiero po akceptacji.

---

## Faza 0 — Porządek w CSS (szybkie wygrane, niskie ryzyko)

- [x] 0.1 `home/static/home/css/utilities.css`
  - usunięto duplikat `.border-radius-0`,
  - scalono `.quick-link-circle` i zamieniono kolory na tokeny,
  - `.citizen-color-0`…`.citizen-color-11` przeniesione do `tokens.css`,
  - `.diff-add`, `.diff-remove`, `.historia-badge`, `.historia-current-badge` — kolory na tokeny.
- [x] 0.2 `home/static/home/css/modules.css`
  - naprawiono błędy formatowania (brak nowej linii po `}` oraz brak `/*` w komentarzu),
  - zamieniono część `rgba(255,255,255,…)` na `--color-surface-offset` / `--color-surface-dynamic`.
- [x] 0.3 `home/static/home/css/layout.css`
  - poprawiono formatowanie końcówki pliku,
  - `.notif-count` box-shadow na `--badge-rejected-glow` (nowy token),
  - `.section-divider` i `.bg-glass-sm` na tokeny,
  - uporządkowano `.quick-link-item` (jedna definicja, token tła).
- [x] 0.4 `home/static/home/css/buttons.css`
  - `.btn-success:hover` `#00a07a` → `var(--badge-approved-color)`.
- [x] 0.5 `board/static/board/board.css` oraz `chat/static/chat/css/chat.css`
  - `board-post-card` box-shadow → `--shadow-overlay`,
  - `.post-header` gradient → token powierzchni,
  - `#fff` w czacie / image viewer → `var(--text-inverse)`.
- [x] 0.6 Weryfikacja
  - `.venv\Scripts\python manage.py collectstatic --noinput --clear` OK,
  - `.venv\Scripts\python manage.py check` OK,
  - `.venv\Scripts\python -m ruff check .` OK,
  - `npx jest` OK (7 suite, 83 testów).

## Faza 1 — Wspólne komponenty HTML

- [x] 1.1 Wspólny toolbar
  - utworzono `home/templates/home/includes/toolbar.html` z parametrami: CTA (link/button), sort, kategorie, widoki, extra_include,
  - zastosowano w `tasks/task_list.html`, `board/board.html`, `events/event_list.html`, `glosowania/_view_toggle.html`, `ankiety/survey_list.html`, `home/activity.html`,
  - widoki generowane są w widokach Pythona (`toolbar_sort_items`, `toolbar_views`).
- [x] 1.2 Wspólny dropdown kategorii
  - utworzono `categories/templates/categories/_category_filter.html`,
  - używany w `tasks/task_list.html` i `board/board.html` (parametr `key_attr` slug/pk),
  - zachowano selektory JS (`catFilterBtn`, `catFilterPanel`, `catFilterLabel`, `catAllRow`).
- [x] 1.3 Karty na desktop (`home/home.html`)
  - utworzono `home/templates/home/includes/module_card.html`,
  - dane modułów przeniesione do `home/views.py` (`DASHBOARD_MODULES`),
  - pętla zamiast 8 ręcznych kart.
- [x] 1.4 Weryfikacja
  - `ruff check .` OK,
  - `manage.py check` OK,
  - `collectstatic --noinput --clear` OK,
  - `npx jest` OK (83/83),
  - serwer deweloperski uruchomiony, podgląd dostępny.

## Faza 2 — Wspólny JavaScript (app.js)

- [x] 2.1 Filtrowanie kategorii
  - utworzono `window.initCategoryFilter()` w `home/static/home/js/app.js`,
  - obsługuje `.proposal-card[data-category]` (tasks) i `.board-category-group[data-category-pk]` (board),
  - usunięto lokalne IIFE z `tasks/task_list.html` i `board/board.html`.
- [x] 2.2 View toggles
  - `PagePrefs.applyView()` rozszerzony o `data-view-only` (agenda/grid dla events),
  - `events/event_list.html` używa wspólnego kontenera `data-view-container`,
  - usunięto lokalny `showView()` z `events/event_list.html`.
- [x] 2.3 Inline `<script>` do `app.js`
  - Quick Links → `app.js` (DOMContentLoaded),
  - `trimActivityFeed` → `app.js`,
  - `toggleArgForm` → `window.toggleArgForm()` w `app.js`,
  - togglowanie sekcji obywatela → `app.js`,
  - klikalne wiersze tabeli → `app.js`.
- [x] 2.4 Weryfikacja
  - `ruff check . --no-cache` OK,
  - `manage.py check` OK,
  - `collectstatic --noinput --clear` OK,
  - `npx jest` OK (83/83).

## Faza 3 — Ujednolicenie nazewnictwa klas

- [x] 3.1 `tasks/templates/tasks/_task_card.html`
  - `proposal-card*` → `task-card*` (header, title, num, chevron, badges, preview, meta, author, coordinator, date, category, helpers, against, body, section, chat, details),
  - zaktualizowano `tasks/static/tasks/js/tasks.js`,
  - w `home/static/home/css/modules.css` dodano aliasy `.task-*` obok `.proposal-*`.
- [x] 3.2 `proposal-chat-link` → `chat-link` (globalnie)
  - `obywatele/szczegoly.html`, `obywatele/start.html`, `glosowania/szczegoly.html`, `glosowania/_proposal_card.html`, `tasks/task_detail.html`, `tasks/_task_card.html`, `modules.css`.
- [x] 3.3 Weryfikacja
  - `ruff check . --no-cache` OK,
  - `manage.py check` OK,
  - `collectstatic --noinput --clear` OK,
  - `npx jest` OK (83/83).

## Faza 4 — Moduły nietypowe

- [x] 4.1 `bookkeeping/templates/bookkeeping/asset_list.html` (i pozostałe listy bookkeeping)
  - wspólny toolbar `home/includes/toolbar.html` we wszystkich listach,
  - CTA `btn-cta`, nawigacja jako `sort_items`,
  - tabele z `table-hover-rows`,
  - akcje `btn-outline-secondary` / `btn-outline-danger`,
  - `bookkeeping/views.py`: `_bookkeeping_toolbar()` + poprawka `except (ValueError, TypeError):`.
- [x] 4.2 `events/templates/events/event_list.html`
  - własny skrypt widoku zastąpiony `PagePrefs` w Fazie 2.2,
  - wspólny toolbar z `cta_url`, `views` i `extra_include='events/_calendar_trigger.html'` już używany.
- [x] 4.3 Weryfikacja
  - `ruff check . --no-cache` OK,
  - `manage.py check` OK,
  - `collectstatic --noinput --clear` OK,
  - `npx jest` OK (83/83).

## Faza 5 — Widoki-specyficzne arkusze CSS

- [x] 5.1 `board/static/board/board.css`
  - style `.board-post-card`, `.post-header`, `.post-title`, `.post-subtitle`, `.post-content`, `.post-featured-image`, `.attachment-uploaded-at` oraz responsywność przeniesione do sekcji `BOARD POST DETAIL` w `home/static/home/css/modules.css`,
  - plik `board/static/board/board.css` usunięty,
  - usunięto `<link rel="stylesheet" href="{% static 'board/board.css' %}">` z `board/templates/board/post_detail.html`.
- [x] 5.2 `chat/static/chat/css/chat.css`
  - przeniesiono generyczne komponenty inputu richtext (`.richtext-wrapper`, `.message-input-rich`) do `home/static/home/css/forms.css` (ładowany globalnie),
  - z `chat/static/chat/css/chat.css` usunięto powyższe reguły oraz mobilny override dla `.message-input-rich`,
  - `home/widgets.py` — `RichTextWidget` i `CounterTextarea` nie ładują już `chat/css/chat.css` (`.msg-counter` jest w `buttons.css`),
  - w `chat.css` pozostały: layout czatu, wiadomości, pokoje, lightbox i specyficzne komponenty czatu.
- [x] 5.3 Weryfikacja
  - `ruff check . --no-cache` OK,
  - `manage.py check` OK,
  - `collectstatic --noinput --clear` OK,
  - `npx jest` OK (83/83),
  - `AGENTS.md` zaktualizowany.

## Faza 6 — Weryfikacja końcowa

- [x] 6.1 `python manage.py check` OK
- [x] 6.2 `python manage.py collectstatic --noinput --clear` OK
- [x] 6.3 `npx jest` OK (7 suite, 83 testów)
- [x] 6.4 `ruff check .` oraz `ruff format --check .` OK
  - `ruff format .` sformatował 33 pliki,
  - ponowne `ruff check .` i `ruff format --check .` przechodzą.
- [x] 6.5 Przegląd wizualny kluczowych widoków: do potwierdzenia przez użytkownika (serwer działa pod http://127.0.0.1:8000).
