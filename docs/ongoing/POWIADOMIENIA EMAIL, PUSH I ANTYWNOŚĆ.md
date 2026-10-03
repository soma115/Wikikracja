# Powiadomienia e-mail, PUSH i aktywność

## Uzgodnione zachowanie

- Potwierdzenie e-maila, reset hasła i link onboardingowy po potwierdzeniu są wysyłane natychmiast; nie należą do digestu.
- Digest obejmuje zmiany w Działaniach, Ludziach, Dokumentach, Kalendarzu, Głosowaniach, Finansach i Ankietach oraz nowe wiadomości czatu z fragmentem treści. Częstotliwość wynika z profilu: codziennie, tygodniowo, miesięcznie albo nigdy.
- „Ludzie” oznacza zdarzenia członkowskie (propozycja, przyjęcie, blokada); edycje pól profilu nie są wpisami digestu ani aktywności.
- `/aktywnosc/` pokazuje zmiany ze wszystkich modułów, w tym dodanie argumentu Za/Przeciw w głosowaniu.
- Push FCM i WebSocket trafia do aktywnych użytkowników z włączonymi powiadomieniami danego modułu; odbiorcy nie są dodatkowo ograniczani do osób powiązanych z obiektem.
- Powiadomienia czatu są limitowane osobno dla użytkownika i pokoju: pierwsze jest natychmiastowe; kolejne w ciągu godziny zastępują oczekujące, a po godzinie wysyłane jest najnowsze. Otwarcie pokoju odblokowuje natychmiastową wysyłkę.
- Wysłanie wiadomości przez użytkownika włącza powiadomienia w tym pokoju, także po wcześniejszym ręcznym wyciszeniu. Nie zmienia globalnego ustawienia w `/obywatele/settings/`.
- W ustawieniach profilu jest przełącznik PUSH dla Finansów.

## Stan wdrożenia

### E-maile natychmiastowe

Potwierdzenie adresu, reset hasła, link onboardingowy po potwierdzeniu i e-mail powitalny przy przyjęciu obywatela pozostały w dotychczasowych przepływach. Nie przeniesiono ich do digestu; pełny zestaw testów projektu przeszedł.

### Digest i `/aktywnosc/`

Wspólny feed i digest uwzględniają wpisy modułów oraz:

- nowe argumenty Za/Przeciw w Głosowaniach;
- głosy Pomogę/Nie róbmy przy Działaniach;
- zmiany Kalendarza niezależnie od tego, czy wydarzenie zaczyna się w najbliższych 6 dniach; nadchodzące terminy nadal są osobnymi przypomnieniami;
- utworzenie i edycje Ankiet;
- utworzenie i edycje transakcji; historyczne transakcje bez `updated_at` zachowują datę utworzenia.

Wpisy argumentów i głosów działają na istniejącym typie/read-state elementu nadrzędnego, bez dokładania nowego typu w bazie.

### PUSH

Katalog zdarzeń `PUSH_EVENTS` znajduje się w `zzz.settings.py`, a wspólny dispatcher jest w `core.notifications`. Wszystkie uzgodnione klucze są obecne; flagi FCM i WebSocket można wyłączać niezależnie. Nieznany klucz blokuje wysyłkę i jest logowany. Nadal obowiązują ustawienia użytkownika, globalne wypisanie, ustawienia urządzenia i wyciszenie pokoju.

Preferencja Finansów `push_notifications_bookkeeping` jest domyślnie wyłączona. Dodano ją do profilu, filtra odbiorców i przełącznika `/obywatele/settings/` (migracja `obywatele.0053`). `bookkeeping.0033` dodaje `Transaction.updated_at` dla digestu/aktywności edytowanych transakcji.

### Czat

Kolejka i istniejący worker Redis limitują powiadomienia osobno dla użytkownika i pokoju; w trakcie limitu zachowują najnowszą wiadomość. Otwarcie lub oznaczenie pokoju jako przeczytanego usuwa oczekujące powiadomienie i limit. WebSocket respektuje teraz tę samą preferencję profilu co FCM. Wiadomość wysłana przez użytkownika usuwa jego wpis zarówno z `muted_by`, jak i `manually_muted_by`, bez zmiany ustawień profilu.

## Konfiguracja zdarzeń PUSH

Konfiguracja jest przeznaczona dla programistów — użytkownicy nie dostają przełączników poszczególnych zdarzeń. Preferencja użytkownika pozostaje nadrzędna wobec `PUSH_EVENTS`: wyłączona kategoria lub globalne wypisanie blokuje wysyłkę nawet wtedy, gdy klucz i kanał są włączone. Istniejące wcześniej, ale celowo wyłączone typy zdarzeń również są wymienione; ich FCM i WebSocket domyślnie mają `False`.

```python
PUSH_EVENTS = {
    # Działania — preferencja: task
    "task.created": {"module": "task", "fcm": True, "websocket": True},
    "task.helper_joined": {"module": "task", "fcm": True, "websocket": True},
    "task.status_changed": {"module": "task", "fcm": True, "websocket": True},
    # Ludzie — preferencja: obywatele
    "citizen.proposed": {"module": "obywatele", "fcm": True, "websocket": True},
    "citizen.accepted": {"module": "obywatele", "fcm": False, "websocket": False},
    "citizen.blocked": {"module": "obywatele", "fcm": False, "websocket": False},
    # Dokumenty — preferencja: post
    "document.created": {"module": "post", "fcm": True, "websocket": True},
    "document.important_updated": {"module": "post", "fcm": False, "websocket": False},
    # Kalendarz — preferencja: events
    "event.created": {"module": "events", "fcm": True, "websocket": True},
    "event.updated": {"module": "events", "fcm": False, "websocket": False},
    "event.starting": {"module": "events", "fcm": True, "websocket": True},
    # Głosowania — preferencja: glosowania
    "vote.proposed": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.modified": {"module": "glosowania", "fcm": False, "websocket": False},
    "vote.argument_added": {"module": "glosowania", "fcm": False, "websocket": False},
    "vote.discussion_started": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.started": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.approved": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.rejected": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.rejected_no_signatures": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.last_day": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.buffer_restarted": {"module": "glosowania", "fcm": True, "websocket": True},
    # Finanse — preferencja: bookkeeping
    "transaction.created": {"module": "bookkeeping", "fcm": True, "websocket": True},
    "transaction.updated": {"module": "bookkeeping", "fcm": False, "websocket": False},
    # Ankiety — preferencja: survey
    "survey.created": {"module": "survey", "fcm": True, "websocket": True},
    "survey.updated": {"module": "survey", "fcm": False, "websocket": False},
    # Czat — preferencja: chat; dodatkowo obowiązuje wyciszenie per pokój
    "chat.message": {"module": "chat", "fcm": True, "websocket": True},
    "chat.mention": {"module": "chat", "fcm": True, "websocket": True},
}
```

## Zadania

1. [x] Zachować natychmiastowe e-maile i istniejące przepływy.
2. [x] Uzupełnić digest dla wskazanych modułów i zachować częstotliwości oraz fragmenty wiadomości czatu.
3. [x] Dodać argumenty głosowań i głosy na Działania do `/aktywnosc/` oraz digestu.
4. [x] Podłączyć wszystkie zdarzenia PUSH z katalogu, z odbiorcami zgodnymi z preferencjami modułów.
5. [x] Dodać `PUSH_EVENTS` z pełnym zestawem kluczy, niezależnymi kanałami i blokowaniem nieznanych zdarzeń.
6. [x] Dodać przełącznik PUSH Finansów i `updated_at` transakcji wraz z migracjami i tłumaczeniami.
7. [x] Dodać throttling czatu, scalanie do najnowszej wiadomości i reset po otwarciu pokoju.
8. [x] Po wysłaniu wiadomości usuwać także ręczne wyciszenie danego pokoju; nie zmieniać profilu.
9. [x] Dodać testy regresji dla feedów, odbiorców, katalogu PUSH, Finansów i czatu.

## Weryfikacja

- [x] Pełny runner: Ruff, formatowanie, regression scan, UI guard, Tailwind, Django check, `compilemessages`, `collectstatic --clear`, 1155 testów pytest i 300 testów Jest — zaliczone.
- [x] Playwright na dedykowanym koncie z ignorowanego `.env.local`: 35 testów zaliczonych, 14 pominiętych.

## Źródła implementacji

- PUSH: `zzz/settings.py`, `core/notifications.py`, `core/signals.py`.
- Digest/feed: `core/services/feed.py`, `glosowania/feed.py`, `tasks/feed.py`, `events/feed.py`, `ankiety/feed.py`, `bookkeeping/feed.py`.
- Czat: `chat/notification_queue.py`, `chat/notifications.py`, `chat/command_handlers.py`, `chat/models.py`.
- Preferencje: `obywatele/models.py`, `obywatele/views.py`.

**Status:** implementacja i weryfikacja planu zakończone.