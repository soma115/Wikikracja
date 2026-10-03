# Powiadomienia e-mail, PUSH i aktywność

## Uzgodnione zachowanie

- Potwierdzenie e-maila, reset hasła i link onboardingowy po potwierdzeniu są wysyłane natychmiast; nie należą do digestu.
- Digest obejmuje zmiany w Działaniach, Ludziach, Dokumentach, Kalendarzu, Głosowaniach, Finansach i Ankietach oraz nowe wiadomości czatu z fragmentem treści. Częstotliwość wynika z profilu: codziennie, tygodniowo, miesięcznie albo nigdy.
- `/aktywnosc/` pokazuje zmiany ze wszystkich modułów, w tym dodanie argumentu Za/Przeciw w głosowaniu.
- Push FCM i WebSocket trafia do aktywnych użytkowników z włączonymi powiadomieniami danego modułu; odbiorcy nie są dodatkowo ograniczani do osób powiązanych z obiektem.
- Powiadomienia czatu są limitowane osobno dla użytkownika i pokoju: pierwsze jest natychmiastowe; kolejne w ciągu godziny zastępują oczekujące, a po godzinie wysyłane jest najnowsze. Otwarcie pokoju odblokowuje natychmiastową wysyłkę.
- Wysłanie wiadomości przez użytkownika włącza powiadomienia w tym pokoju, także po wcześniejszym ręcznym wyciszeniu. Nie zmienia globalnego ustawienia w `/obywatele/settings/`.
- W ustawieniach profilu ma być przełącznik PUSH dla Finansów.

## Stan obecny i braki

### E-maile natychmiastowe

- **Stan:** potwierdzenie adresu i link onboardingowy są obsługiwane w przepływie allauth/onboardingu; reset hasła obsługuje allauth. Przyjęcie obywatela ma osobny e-mail powitalny.
- **Brak:** zachować istniejące przepływy i objąć je testami regresji; nie przenosić ich do digestu.

### Digest

- **Stan:** częstotliwości `daily` / `weekly` / `monthly` / `never` i cykliczna wysyłka już istnieją. Digest korzysta ze wspólnego feedu, agreguje wpisy i wiadomości czatu oraz zawiera fragment treści wiadomości.
- **Brak:** zweryfikować kompletność zmian ze wszystkich modułów. Argumenty głosowań nie są obecnie wpisami globalnego feedu.

### `/aktywnosc/`

- **Stan:** wspólny feed zbiera wpisy z Obywateli, Głosowań, Działań, Dokumentów, Kalendarza, Finansów, Ankiet i Czatu.
- **Brak:** provider Głosowań zwraca zmodyfikowane decyzje, ale nie dodane argumenty. Osobista aktywność argumentów autora nie zastępuje wpisu w globalnym feedzie.

### PUSH według modułów

- **Stan:** istnieją kategorie preferencji dla Obywateli, Głosowań, Czatu, Wydarzeń, Dokumentów, Działań i Ankiet. Wspólny broadcast filtruje odbiorców według preferencji kategorii.
- **Braki:** nie ma kategorii Finansów. Nowe działanie, ważny dokument i ankieta mają odbiorniki, które obecnie nie wysyłają FCM ani WebSocket. Nie ma odbiornika propozycji nowego użytkownika ani nowego wydarzenia. Rozpoczynające się wydarzenie wysyła oba kanały. Zadanie cykliczne jawnie wysyła powiadomienia o obsługiwanych zmianach głosowań, w tym ostatnim dniu i restarcie po błędzie bufora; trzeba sprawdzić pełne pokrycie propozycji i zmian stanu. Edycja propozycji i argumenty należą do digestu/aktywności, nie do uzgodnionego zakresu PUSH. Dla Finansów feed transakcji istnieje, ale brak powiadomień PUSH.
- **Czat:** wiadomości przechodzą przez kolejkę Redis i są wysyłane przez WebSocket oraz FCM. Nie ma limitu godzinnego per użytkownik/pokój; potwierdzenie kliknięcia powiadomienia jedynie zapisuje log. FCM sprawdza ustawienia profilu, ale WebSocket z indywidualnej kolejki nie stosuje ich w ten sam sposób. Po napisaniu wiadomości usuwane jest domyślne wyciszenie pokoju, lecz ręczne wyciszenie pozostaje.

Preferencje profilu dostępne obecnie dla PUSH: `push_notifications_obywatele`, `push_notifications_glosowania`, `push_notifications_chat`, `push_notifications_events`, `push_notifications_post`, `push_notifications_task`, `push_notifications_survey`. Ich wartości domyślne nie są jednakowe.

## Konfiguracja zdarzeń PUSH

Konfiguracja jest przeznaczona dla programistów — nie dodajemy użytkownikom przełączników dla poszczególnych zdarzeń. Ustawienia profilu pozostają nadrzędne: zdarzenie i kanał mogą być włączone w konfiguracji, ale PUSH nadal nie zostanie wysłany, jeśli użytkownik wyłączył powiadomienia modułu lub wszystkie powiadomienia. Preferencje urządzenia oraz wyciszenie pokoju również pozostają dodatkowymi warunkami.

Katalog `PUSH_EVENTS` będzie utrzymywany w istniejących ustawieniach Django (`zzz.settings.py`), a wspólny dispatcher w `core.notifications` będzie go odczytywał. Każde zdarzenie ma stabilny klucz, kategorię preferencji użytkownika i niezależne flagi kanałów FCM/WebSocket. Programista może wyłączyć zdarzenie albo pojedynczy kanał przez zmianę wartości `True` na `False`. Na początku katalog zawiera wszystkie klucze z poniższej listy; wszystkie kanały są domyślnie włączone zgodnie z uzgodnionym zakresem.

```python
PUSH_EVENTS = {
    # Działania — preferencja: task
    "task.created": {"module": "task", "fcm": True, "websocket": True},
    "task.helper_joined": {"module": "task", "fcm": True, "websocket": True},
    "task.status_changed": {"module": "task", "fcm": True, "websocket": True},

    # Ludzie — preferencja: obywatele
    "citizen.proposed": {"module": "obywatele", "fcm": True, "websocket": True},

    # Dokumenty — preferencja: post
    "document.created": {"module": "post", "fcm": True, "websocket": True},

    # Kalendarz — preferencja: events
    "event.created": {"module": "events", "fcm": True, "websocket": True},
    "event.starting": {"module": "events", "fcm": True, "websocket": True},

    # Głosowania — preferencja: glosowania
    "vote.proposed": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.discussion_started": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.started": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.approved": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.rejected": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.rejected_no_signatures": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.last_day": {"module": "glosowania", "fcm": True, "websocket": True},
    "vote.buffer_restarted": {"module": "glosowania", "fcm": True, "websocket": True},

    # Finanse — preferencja: bookkeeping (do dodania)
    "transaction.created": {"module": "bookkeeping", "fcm": True, "websocket": True},

    # Ankiety — preferencja: survey
    "survey.created": {"module": "survey", "fcm": True, "websocket": True},

    # Czat — preferencja: chat; dodatkowo obowiązuje wyciszenie per pokój
    "chat.message": {"module": "chat", "fcm": True, "websocket": True},
    "chat.mention": {"module": "chat", "fcm": True, "websocket": True},
}
```

Nadawcy będą przekazywać klucz zdarzenia do wspólnego dispatchera zamiast samodzielnie ustawiać `send_push` i `send_websocket`. Dispatcher sprawdzi flagę zdarzenia/kanału, a następnie preferencję modułu i globalne wyłączenie użytkownika. Nieznane klucze powinny powodować czytelny błąd walidacji lub testu, nie ciche wysłanie bez konfiguracji. Nie dodajemy osobnego pliku YAML/JSON ani per-zdarzeniowych przełączników użytkownika.

## Zadania

1. [ ] Zachować natychmiastową wysyłkę potwierdzenia e-maila, resetu hasła i linku onboardingowego; dodać lub uzupełnić testy bez zmian w tych przepływach.
2. [ ] Zweryfikować kompletność digestu dla Działań, Ludzi, Dokumentów, Kalendarza, Głosowań, Finansów, Ankiet i Czatu; zachować częstotliwości z profilu oraz fragmenty wiadomości czatu.
3. [ ] Dodać wpis o nowym argumencie Za/Przeciw do wspólnego feedu Głosowań, aby pojawiał się w `/aktywnosc/` i digescie; zachować grupowanie oraz oznaczanie jako przeczytane.
4. [ ] Dodać i podłączyć wszystkie zdarzenia z katalogu `PUSH_EVENTS`; osobne klucze statusów głosowań umożliwiają ich późniejsze niezależne włączanie i wyłączanie.
5. [ ] Zastosować bramkowanie katalogu w dispatcherze dla FCM i WebSocket. Preferencje użytkownika, globalne wyłączenie, preferencje urządzenia i wyciszenie pokoju muszą pozostać nadrzędnymi warunkami wysyłki.
6. [ ] Dodać preferencję PUSH Finansów do profilu, filtrowania odbiorców, endpointu przełącznika i widoku `/obywatele/settings/`; uzupełnić tłumaczenia. Zmiana schematu wymaga migracji i osobnego potwierdzenia przed jej wykonaniem.
7. [ ] Dodać limit czatu per użytkownik i pokój: pierwsze powiadomienie natychmiast, kolejne w ciągu godziny zastępowane najnowszym, najnowsze wysyłane po godzinie. Otwarcie pokoju odblokowuje wysyłkę; reguła obejmuje wszystkie pokoje oraz FCM/WebSocket.
8. [ ] Po wysłaniu wiadomości usuwać wyciszenie danego pokoju zarówno z `muted_by`, jak i `manually_muted_by`. Nie zmieniać preferencji profilu ani wyciszeń w innych pokojach.
9. [ ] Dodać testy regresji: kompletność katalogu i obsługa nieznanych kluczy, pierwszeństwo preferencji użytkownika, oba kanały PUSH, ustawienie Finansów, pokrycie feedu/digestu, limit czatu, najnowsze oczekujące powiadomienie, odblokowanie po otwarciu pokoju i usunięcie ręcznego wyciszenia po wysłaniu wiadomości.

## Źródła obecnej implementacji

- Digest: `home/management/commands/send_email_digest.py`, `core/services/feed.py`.
- Preferencje profilu i przełączniki: `obywatele/models.py`, `obywatele/views.py`.
- Dispatcher, kategorie PUSH i sygnały: `core/notifications.py`, `core/signals.py`.
- Aktywność i Głosowania: `core/feed_registry.py`, `home/views.py`, `glosowania/feed.py`.
- Kolejka i powiadomienia czatu: `chat/notification_queue.py`, `chat/notifications.py`, `chat/models.py`, `chat/services.py`, `chat/push_api.py`.
- Ustawienia Django: `zzz/settings.py`.

**Status:** wymagania i katalog zdarzeń opisane; poniższe zadania nie są jeszcze wdrożone.