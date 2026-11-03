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
- Aktywność Działań i digest uwzględniają głosy Pomogę/Blokuj.
- Digest koordynatora zaczyna się od listy osób, które chcą dołączyć do jego zespołów, ale nie zostały jeszcze zatwierdzone. Każda pozycja prowadzi do działania i przypomina, że koordynator może zaakceptować tę osobę, jeśli chce.
- Zmiany wydarzeń są uwzględniane niezależnie od tego, czy wydarzenie zaczyna się w najbliższych dniach. Przypomnienia o nadchodzących terminach są osobnym mechanizmem.
- Uwzględniane są utworzenia i edycje Ankiet oraz transakcji. Dla historycznych transakcji bez `updated_at` data utworzenia pozostaje datą wpisu.
- Restart głosowania po utracie bufora jest osobnym, wyróżnionym zdarzeniem digestu; szczegóły znajdują się w sekcji [Restart referendum po utracie głosów](#restart-referendum-po-utracie-głosów).

Wpis argumentu lub głosu jest prezentowany w kontekście elementu nadrzędnego; nie wymaga osobnego typu w bazie ani osobnego typu read-state.

## PUSH i WebSocket

`PUSH_EVENTS` w `zzz/settings.py` jest katalogiem programistycznym zdarzeń, a `core.notifications` wspólnym dispatcherem. Katalog określa moduł preferencji i niezależnie włącza kanały FCM oraz WebSocket. Aktualny zestaw kluczy i ustawień kanałów jest utrzymywany w kodzie `PUSH_EVENTS` — nie kopiować go tutaj, żeby uniknąć rozbieżności.

Kontrakty:

- Nieznany lub niepoprawny klucz zdarzenia blokuje wysyłkę i jest logowany. Nie dodawaj osobnych przełączników dla zdarzeń w ustawieniach użytkownika.
- Odbiorcą jest aktywny użytkownik z włączoną preferencją danego modułu; obecna wysyłka nie ogranicza listy odbiorców do osób powiązanych z obiektem zdarzenia.
- Wyłączona preferencja modułu lub globalne wypisanie ma pierwszeństwo przed konfiguracją zdarzenia. FCM dodatkowo respektuje ustawienia urządzeń (telefon/tablet i komputer); powiadomienia czatu respektują wyciszenie nadawcy w danym pokoju.
- Preferencja PUSH dla Finansów (`push_notifications_bookkeeping`) jest domyślnie wyłączona i ma przełącznik w `/obywatele/settings/`.
- Brak konfiguracji Firebase wyłącza FCM bez wyłączania niezależnego kanału WebSocket.

## Restart referendum po utracie głosów

Przy zamykaniu referendum zadanie `manage.py vote` porównuje liczbę wpisów
`KtoJuzGlosowal` w SQLite z liczbą głosów oczekujących w Redisie. Jeśli liczby
się różnią, system nie liczy częściowego wyniku: czyści bufor głosów i listę
osób, które już zagłosowały, rozpoczyna pełny nowy okres i zwiększa
`referendum_restart_count`. Wcześniejsze głosy oraz wydane do nich kody
weryfikacyjne są nieważne. Tożsamość wyboru pozostaje anonimowa.

Utrata danych po restarcie systemu lub Redis nie jest wykrywana natychmiast.
Obecny mechanizm wykrywa rozbieżność dopiero przy zamykaniu referendum i wtedy
uruchamia poniższe powiadomienia.

- **Strona referendum:** szczegóły referendum z `referendum_restart_count > 0`
  pokazują ostrzeżenie. W otwartym głosowaniu informuje ono o konieczności
  ponownego głosowania i terminie; po zamknięciu wyjaśnia, że wynik dotyczy
  ostatniej rundy.
- **Daily Digest:** restart jest umieszczany w wyróżnionej sekcji wersji
  tekstowej i HTML, z linkiem do szczegółów referendum. Trafia do digestu
  zgodnie z częstotliwością i ustawieniami poczty użytkownika, nie jako
  natychmiastowy e-mail. Link prowadzi do
  `/glosowania/details/<id>/` na domenie danej instancji.
- **Push i WebSocket:** przejście `buffer_restart` jest mapowane na
  `vote.buffer_restarted`. Odbiorcami są aktywni użytkownicy z włączoną
  preferencją powiadomień dla Głosowań. FCM wymaga dodatkowo aktywnego
  urządzenia i skonfigurowanej usługi Firebase; WebSocket jest niezależnym
  kanałem. Treść informuje o utracie wcześniejszych głosów, nowym terminie
  i ponownym głosowaniu, ale nie zawiera danych o wyborze ani o tym, kto
  głosował.

Digest identyfikuje nowe restarty przez `referendum_restart_count` oraz
`data_ostatniej_modyfikacji >= last_email_digest_at`. Drugie pole jest ogólną
datą modyfikacji decyzji, nie osobnym znacznikiem restartu; jeśli późniejszy
zapis decyzji spowoduje powtarzanie starego alertu, dokładniejsze śledzenie
wymaga osobnego projektu migracji i zmiany schematu.

## Powiadomienia czatu

Kolejka Redis ogranicza powiadomienia osobno dla pary użytkownik–pokój. Pierwsze powiadomienie jest wysyłane natychmiast; w ciągu następnej godziny kolejne zdarzenia zastępują oczekujące, tak że po upływie limitu dostarczana jest najnowsza wiadomość. Otwarcie lub oznaczenie pokoju jako przeczytanego czyści oczekujące powiadomienie i limit dla tej pary.

Wysłanie wiadomości przez użytkownika ponownie włącza powiadomienia w tym pokoju, usuwając wyciszenie pokojowe (także ręczne). Nie zmienia globalnej preferencji profilu w `/obywatele/settings/`.

## Główne miejsca implementacji i testów

- Preferencje, globalne wypisanie i tokeny wypisania: `obywatele/models.py`, `obywatele/views.py`, `core/services/notifications.py`.
- Dispatcher, reguły PUSH i odbiorcy: `core/notifications.py`, konfiguracja `zzz/settings.py`.
- Feed i agregacja digestu: `core/services/feed.py` oraz providery `board/feed.py`, `bookkeeping/feed.py`, `chat/feed.py`, `events/feed.py`, `glosowania/feed.py`, `tasks/feed.py`, `ankiety/feed.py` i `obywatele/feed.py`.
- Wysyłka digestu: `home/management/commands/send_email_digest.py`; harmonogram: `zzz/scheduler.py`.
- Kolejka i zachowanie powiadomień czatu: `chat/notification_queue.py`, `chat/notifications.py`, `chat/command_handlers.py`.
- Testy regresji: `home/test_email_digest.py`, `home/test_feed.py`, `core/test_feed.py`, `core/test_notifications.py`, `core/test_unsubscribe.py`, `glosowania/tests/test_vote_command.py`, `glosowania/tests/test_views.py`, `chat/tests/test_notifications.py` oraz testy providerów w odpowiednich modułach.

Przy zmianie funkcjonalności uruchamiaj testy dotkniętych modułów zgodnie z `AGENTS.md`; dla zmian UI obowiązują dodatkowo wskazane tam kontrole UI.

## Zakres poza tą dokumentacją

Filtry `/aktywnosc/` działające bez przeładowania strony są osobnym, nadal zapisanym zadaniem w `docs/ongoing/_TODO.md`. Nie należały do zakończonego planu digestu, katalogu PUSH ani zakresu zdarzeń aktywności opisanego powyżej.

## Zamknięcie pierwotnego planu

Pierwotny plan implementacyjny został zakończony: wszystkie jego punkty i kontrole były oznaczone jako wykonane. W zapisanej weryfikacji końcowej pełny runner zaliczył Ruff, formatowanie, regression scan, UI guard, build Tailwind, Django check, `compilemessages`, `collectstatic --clear`, 1155 testów pytest i 300 testów Jest. Playwright na dedykowanym koncie zaliczył 35 testów, 14 pominięto. To wynik historyczny z zamknięcia planu, nie deklaracja wyniku aktualnego uruchomienia.
