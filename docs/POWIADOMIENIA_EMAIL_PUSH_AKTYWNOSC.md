# Powiadomienia, digest e-mail i aktywność

Dokument opisuje obowiązujące zachowanie i kontrakty systemu powiadomień. To dokumentacja utrzymywana wraz z kodem, nie plan wdrożenia. Zmiany w zachowaniu należy wprowadzać w odpowiednich modułach i aktualizować tę stronę.

## Zasady dostarczania

### E-mail

- Potwierdzenie adresu e-mail, reset hasła, wiadomość onboardingowa po potwierdzeniu oraz wiadomość powitalna po przyjęciu obywatela pozostają natychmiastowymi e-mailami w swoich dotychczasowych przepływach. Nie są częścią digestu.
- Digest aktywności jest osobnym, cyklicznym e-mailem. Użytkownik wybiera częstotliwość: codziennie, tygodniowo, miesięcznie albo nigdy.
- Granice okresów digestu są liczone od 08:00 czasu lokalnego: dzień, tydzień rozpoczynający się w sobotę albo miesiąc rozpoczynający się pierwszego dnia. Wysyłkę uruchamia scheduler. Gdy w okresie nie ma wpisów, znacznik ostatniego digestu jest aktualizowany, by nie przetwarzać ponownie tego samego okresu.
- Wiadomości e-mail z powiadomieniami subskrypcyjnymi udostępniają nagłówki `List-Unsubscribe`; wspólne wypisanie jest przechowywane w profilu i blokuje kolejne subskrypcyjne digesty oraz powiadomienia.

### Digest i `/aktywnosc/`

Digest jest budowany ze wspólnego feedu i obejmuje wpisy z Działań, Ludzi, Dokumentów, Kalendarza, Głosowań, Finansów, Ankiet oraz wiadomości czatu. Wiadomości czatu są grupowane, a digest zawiera krótki fragment treści; wzmianka o odbiorcy jest jawnie oznaczona.

Obowiązujące szczegóły zakresu:

- „Ludzie” oznacza zdarzenia członkowskie, takie jak propozycja, przyjęcie lub blokada. Zwykłe edycje profilu nie są aktywnością ani wpisem digestu.
- Aktywność Głosowań obejmuje dodane argumenty Za/Przeciw; nie ujawnia wyboru ani kodu głosującego.
- Aktywność Działań i digest uwzględniają głosy Pomogę/Nie róbmy.
- Zmiany wydarzeń są uwzględniane niezależnie od tego, czy wydarzenie zaczyna się w najbliższych dniach. Przypomnienia o nadchodzących terminach są osobnym mechanizmem.
- Uwzględniane są utworzenia i edycje Ankiet oraz transakcji. Dla historycznych transakcji bez `updated_at` data utworzenia pozostaje datą wpisu.
- Dodatkowe zdarzenia, takie jak wznowione głosowania po awarii, są składane osobno w digescie.

Wpis argumentu lub głosu jest prezentowany w kontekście elementu nadrzędnego; nie wymaga osobnego typu w bazie ani osobnego typu read-state.

## PUSH i WebSocket

`PUSH_EVENTS` w `zzz/settings.py` jest katalogiem programistycznym zdarzeń, a `core.notifications` wspólnym dispatcherem. Katalog określa moduł preferencji i niezależnie włącza kanały FCM oraz WebSocket. Aktualny zestaw kluczy i ustawień kanałów jest utrzymywany w kodzie `PUSH_EVENTS` — nie kopiować go tutaj, żeby uniknąć rozbieżności.

Kontrakty:

- Nieznany lub niepoprawny klucz zdarzenia blokuje wysyłkę i jest logowany. Nie dodawaj osobnych przełączników dla zdarzeń w ustawieniach użytkownika.
- Odbiorcą jest aktywny użytkownik z włączoną preferencją danego modułu; obecna wysyłka nie ogranicza listy odbiorców do osób powiązanych z obiektem zdarzenia.
- Wyłączona preferencja modułu lub globalne wypisanie ma pierwszeństwo przed konfiguracją zdarzenia. FCM dodatkowo respektuje ustawienia urządzeń (telefon/tablet i komputer); powiadomienia czatu respektują wyciszenie nadawcy w danym pokoju.
- Preferencja PUSH dla Finansów (`push_notifications_bookkeeping`) jest domyślnie wyłączona i ma przełącznik w `/obywatele/settings/`.
- Brak konfiguracji Firebase wyłącza FCM bez wyłączania niezależnego kanału WebSocket.

## Powiadomienia czatu

Kolejka Redis ogranicza powiadomienia osobno dla pary użytkownik–pokój. Pierwsze powiadomienie jest wysyłane natychmiast; w ciągu następnej godziny kolejne zdarzenia zastępują oczekujące, tak że po upływie limitu dostarczana jest najnowsza wiadomość. Otwarcie lub oznaczenie pokoju jako przeczytanego czyści oczekujące powiadomienie i limit dla tej pary.

Wysłanie wiadomości przez użytkownika ponownie włącza powiadomienia w tym pokoju, usuwając wyciszenie pokojowe (także ręczne). Nie zmienia globalnej preferencji profilu w `/obywatele/settings/`.

## Główne miejsca implementacji i testów

- Preferencje, globalne wypisanie i tokeny wypisania: `obywatele/models.py`, `obywatele/views.py`, `core/services/notifications.py`.
- Dispatcher, reguły PUSH i odbiorcy: `core/notifications.py`, konfiguracja `zzz/settings.py`.
- Feed i agregacja digestu: `core/services/feed.py` oraz providery `board/feed.py`, `bookkeeping/feed.py`, `chat/feed.py`, `events/feed.py`, `glosowania/feed.py`, `tasks/feed.py`, `ankiety/feed.py` i `obywatele/feed.py`.
- Wysyłka digestu: `home/management/commands/send_email_digest.py`; harmonogram: `zzz/scheduler.py`.
- Kolejka i zachowanie powiadomień czatu: `chat/notification_queue.py`, `chat/notifications.py`, `chat/command_handlers.py`.
- Testy regresji: `home/test_email_digest.py`, `home/test_feed.py`, `core/test_feed.py`, `core/test_notifications.py`, `core/test_unsubscribe.py`, `chat/tests/test_notifications.py` oraz testy providerów w odpowiednich modułach.

Przy zmianie funkcjonalności uruchamiaj testy dotkniętych modułów zgodnie z `AGENTS.md`; dla zmian UI obowiązują dodatkowo wskazane tam kontrole UI.

## Zakres poza tą dokumentacją

Filtry `/aktywnosc/` działające bez przeładowania strony są osobnym, nadal zapisanym zadaniem w `docs/ongoing/_TODO.md`. Nie należały do zakończonego planu digestu, katalogu PUSH ani zakresu zdarzeń aktywności opisanego powyżej.

## Zamknięcie pierwotnego planu

Pierwotny plan implementacyjny został zakończony: wszystkie jego punkty i kontrole były oznaczone jako wykonane. W zapisanej weryfikacji końcowej pełny runner zaliczył Ruff, formatowanie, regression scan, UI guard, build Tailwind, Django check, `compilemessages`, `collectstatic --clear`, 1155 testów pytest i 300 testów Jest. Playwright na dedykowanym koncie zaliczył 35 testów, 14 pominięto. To wynik historyczny z zamknięcia planu, nie deklaracja wyniku aktualnego uruchomienia.
