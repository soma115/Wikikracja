# Plan refaktoryzacji architektury Wikikracji

Cel: zmniejszyć sprzężenie między aplikacjami, wyeliminować „god modules” i side‑effecty na odległość. Każda faza powinna być mergowalna samodzielnie.

> Powiązany dokument: `docs/PLAN_refaktoryzacja_home.md` (konkretnie `home/views.py` i feed). Ten plik uzupełnia go o całościowy dekoupling aplikacji.

## Faza 1. Czat a głosowania / taski / dokumenty (najwyższy priorytet)

- [x] Dodać sygnały domenowe w `chat/signals.py` (`chat_room_requested`, `chat_message_requested`).
- [x] `glosowania/signals.py`: emitować `chat_room_requested` zamiast tworzyć `Room`/`Message` bezpośrednio.
- [x] `tasks/signals.py`: analogicznie — emitować zdarzenie, nie importować `chat.models`.
- [x] `board/signals.py`: emitować `chat_message_requested` zamiast `chat.utils.send_message_to_room`.
- [x] Rozszerzyć `chat/models.py` o pola `source_app` / `source_object_id` + migracja.
- [x] Wypełniać `source_app` przy tworzeniu pokoju.
- [x] `chat/views.py`: zamiast `Task.objects` / `Decyzja.objects` — grupować pokoje po `source_app`.
- [x] `chat/management/commands/chat_messages.py`: grupowanie pokoi po `source_app` zamiast `Task`/`Decyzja`.
- [x] `home/management/commands/fix_all_chat_connections.py`: uprościć przez `source_app`/`source_object_id`.

## Faza 2. Dashboard i search przez registry pluginów

- [x] Stworzyć `home/search_registry.py` i `home/dashboard_registry.py` na wzór `home/feed_registry.py`.
- [x] W każdej aplikacji dodać `<app>/search.py` i `<app>/dashboard.py` z providerami.
- [x] Zarejestrować providerów w `apps.py` poszczególnych aplikacji.
- [x] `home/services/search.py`: cienka warstwa agregująca wyniki z rejestru.
- [x] `home/services/dashboard.py`: cienka warstwa agregująca widgety z rejestru.
- [x] `home/views.py`: korzystać wyłącznie z `search_service` / `dashboard_service`, nie importować modeli innych aplikacji.

## Faza 3. Wspólne utility / widgets / kolory

- [x] Przenieść `home/widgets.py` do `zzz/widgets.py` (tymczasowo, core nie istnieje).
- [x] Przenieść `citizen_color_class` (i `citizen_color`) z `home/templatetags/feed_filters.py` do `zzz/templatetags/citizen_filters.py` (nazwa `filters.py` kolidowała z istniejącym `chat/templatetags/filters.py`).
- [x] Zaktualizować importy w `glosowania/forms.py`, `tasks/forms.py`, `events/forms.py`, `ankiety/forms.py`, `chat/serializers.py`, `chat/services.py`.
- [ ] (Opcjonalnie / konsultacja) Rozważyć przeniesienie `home/models.py` (`FeedItem`, `ReadStatus`) do `core`.

## Faza 4. Centralny dispatcher powiadomień

- [x] Zdefiniować sygnały domenowe (`zzz/signals.py`): `citizen_proposed`, `citizen_accepted`, `citizen_blocked`, `vote_started`, `vote_state_changed`, `task_created`, `important_post_published`, `event_starting`.
- [x] Zamienić ręczne wywołania `zzz.notifications` / `zzz.email` w widokach/sygnałach na emitowanie zdarzeń.
- [x] `zzz/notifications.py` jako główny odbiorca: odbiera sygnał i decyduje o FCM / WebSocket / email.
- [x] `obywatele/management/commands/count_citizens.py` oraz `glosowania/management/commands/vote.py`: emitować `citizen_accepted`/`citizen_blocked`/`citizen_deleted` i `vote_started`/`vote_state_changed` zamiast wołać `chat.signals` i `send_mail`.

## Faza 5. Management commands

- [x] `count_citizens`: rozdzielić logikę na liczenie reputacji/aktywację; chatowe sprzątanie do `chat/signals.py`.
- [x] `chat_messages`: używać `source_app` do grupowania (po fazie 1).
- [x] `fix_all_chat_connections`: używać `source_app`/`source_object_id` lub podzielić na per‑aplikacyjne kroki rejestrowane w czacie.

## Faza 6. Weryfikacja po każdej fazie

- [x] `python manage.py check`
- [x] `python -m pytest -q`
- [x] `ruff check .` i `ruff format --check .`
- [x] `npx jest` (jeśli dotyczy frontu)
- [x] Sprawdzić migracje (`python manage.py makemigrations --check --dry-run`) przed wdrożeniem.

## Uwagi i obserwacje z wykonywania

- Faza 1 zakończona. Backfill `source_app`/`source_object_id` dla istniejących pokoi został rozdzielony na osobne migracje w `tasks` i `glosowania`, aby uniknąć cyklicznych zależności `chat -> tasks -> chat`.
- Testy `test_*_not_saved_when_chat_room_creation_fails` zostały zaktualizowane, by mockować `chat.signals.Room.objects.create` (tam teraz tworzony jest pokój) zamiast `*.signals.Room.objects.create`.
- W `chat/models.py` dodano `Room.clean_title()`, które usuwa prefixy `Task #N: ` / `N. ` przy wyświetlaniu, więc UI zachowuje czytelne nazwy bez importowania modeli źródłowych.
- Migracje, `check`, `pytest` (461), `jest` (97), `ruff` oraz `ruff format --check` przeszły pomyślnie.
- Faza 2 zakończona. `home/services/search.py` i `home/services/dashboard.py` zostały przerobione na cienkie warstwy agregujące wyniki z `home/search_registry.py` i `home/dashboard_registry.py`. Każda aplikacja dostarcza własne `<app>/search.py` i/lub `<app>/dashboard.py`, rejestrowane w `apps.py`. `home/views.py` nie importuje już modeli z innych aplikacji; korzysta wyłącznie z usług rejestru.
- `home/services/dashboard.py` nadal zarządza wspólnymi elementami strony głównej (feed, quick links) oraz `DASHBOARD_MODULES`, ponieważ są to dane należące do samego modułu `home`.
- Faza 3 zakończona. `home/widgets.py` przeniesiono do `zzz/widgets.py`; `citizen_color_class` (wraz z `citizen_color`) przeniesiono z `home/templatetags/feed_filters.py` do `zzz/templatetags/citizen_filters.py` (nazwa `filters.py` kolidowała z `chat.templatetags.filters`). Zaktualizowano importy we wszystkich wskazanych plikach (`glosowania/forms.py`, `tasks/forms.py`, `events/forms.py`, `ankiety/forms.py`, `chat/serializers.py`, `chat/services.py`) oraz `home/templates/home/_user_avatar.html`. Opcjonalne przeniesienie `home/models.py` (`FeedItem`, `ReadStatus`) do `core` pominięto — wymagałoby utworzenia nowej aplikacji i migracji schematu, czyli konsultacji.
- Faza 4 zakończona. W `zzz/signals.py` zdefiniowano sygnały domenowe (`citizen_proposed`, `citizen_accepted`, `citizen_blocked`, `citizen_deleted`, `vote_started`, `vote_state_changed`, `task_created`, `important_post_published`, `event_starting`). `zzz/notifications.py` stał się centralnym odbiorcą i dispatchuje FCM / WebSocket / email. Ręczne wywołania powiadomień zastąpiono emisją sygnałów w `obywatele/forms.py`, `obywatele/views.py`, `obywatele/management/commands/count_citizens.py`, `glosowania/views.py`, `glosowania/management/commands/vote.py`, `events/services.py`, `tasks/signals.py` i `board/signals.py`. Logikę pokoi 1-to-1 przy akceptacji/usuwaniu obywatela przeniesiono do `chat/signals.py`. Dodatkowo w `zzz/notifications.py` dodano obsługę `django.db.utils.DatabaseError` przy ładowaniu odbiorców push oraz wysyłce broadcastów, aby tło nie kończyło się nieobsłużonym wyjątkiem przy blokadzie SQLite. Weryfikacja: `manage.py check`, `makemigrations --check --dry-run`, `ruff check .`, `ruff format --check .`, `pytest` (461/13) oraz `npx jest` (97) przeszły pomyślnie.
- Faza 5 zakończona. W `obywatele/management/commands/count_citizens.py` usunięto bezpośrednie sprzątanie pokoi czatu (`Room.allowed/muted_by/seen_by` oraz `groups/user_permissions`) oraz wywołanie `track_user_blocked`. Chatowe czyszczenie przy usuwaniu obywatela przeniesiono do odbiorcy `citizen_deleted` w `chat/signals.py` (`cleanup_user_chat_rooms`), który usuwa prywatne pokoje 1-to-1 i usuwa użytkownika z pozostałych relacji. Śledzenie blokady przeniesiono do odbiorcy `citizen_blocked` w `obywatele/signals.py` (`track_user_blocked`). `chat/management/commands/chat_messages.py` pogrupowano pokoje dynamicznie po `source_app` (lub `public`/`private` jako fallback) zamiast sztywnych gałęzi `Task`/`Decyzja`. `home/management/commands/fix_all_chat_connections.py` przestał importować `Task`/`Decyzja` z góry — korzysta teraz z `django.apps` wewnątrz metod i opiera wyszukiwanie na `source_app`/`source_object_id`. Weryfikacja: `manage.py check`, `makemigrations --check --dry-run`, `ruff check .`, `ruff format --check .`, `pytest` (461) oraz `npx jest` (97) przeszły pomyślnie.
