# Plan ograniczenia hałasu powiadomień

Celem jest ograniczenie hałasu przy zachowaniu prostoty. Najpierw wdrażamy małą zmianę rozwiązującą konkretny problem, a dopiero później rozważamy uogólnienie mechanizmu.

## Status planu

- [x] Minimalna pierwsza wersja została zaimplementowana.
- [x] Testy pierwszej wersji przechodzą.
- [ ] Część przyszła pozostaje odłożona do czasu pojawienia się konkretnej potrzeby.

Legenda: `[x]` — wykonane, `[ ]` — do wykonania, `[-]` — świadomie poza zakresem.

## Część I — minimalna pierwsza wersja

### 1. Cel

- [x] Ograniczyć powiadomienia generowane przez kolejne, następujące po sobie edycje tego samego dokumentu.

Przykład:

1. dokument zostaje zmieniony — wysyłamy powiadomienie;
2. dokument zostaje zmieniony ponownie po kilku minutach — pomijamy powiadomienie;
3. po wygaśnięciu 90 minut kolejna edycja może ponownie wysłać powiadomienie.

### 2. Zakres

- [x] Objąć wyłącznie powiadomienie o aktualizacji ważnego dokumentu (`created=False` w `important_post_published`).
- [-] Nie ograniczać pierwszej publikacji dokumentu.
- [-] Nie ograniczać utworzenia nowego dokumentu.
- [-] Nie ograniczać zmiany widoczności.
- [-] Nie ograniczać archiwizacji.
- [-] Nie ograniczać ponownego udostępnienia.
- [-] Nie obejmować innych kategorii powiadomień.
- [-] Nie obejmować wiadomości e-mail.

Dzięki temu pierwsza wersja nie ryzykuje ukrycia ważnych zmian statusu ani nie przebudowuje całego systemu powiadomień.

### 3. Klucz throttlingu

- [x] Używać jednego klucza dla kolejnych edycji tego samego dokumentu:

  ```text
  notification-throttle:{instance}:post:{post_id}:updated
  ```

- [x] Izolować trzynaście instancji Wikikracji przez identyfikator domeny instancji.
- [x] Korzystać ze wspólnego Redisa bez tworzenia osobnego Redisa dla każdej instancji.

Przykład:

```text
notification-throttle:example.org:post:123:updated
```

### 4. Implementacja

- [x] Dodać w `core.notifications` helper oparty o `django.core.cache.cache.add()`.
- [x] Ustawić TTL na 90 minut przez jedną wartość konfiguracyjną:

  ```python
  NOTIFICATION_THROTTLE_SECONDS = 90 * 60
  ```

- [x] Wywoływać helper w `on_important_post_published` tylko dla aktualizacji (`created=False`).
- [x] Wysyłać istniejące powiadomienie push i WebSocket, gdy `cache.add()` utworzy klucz.
- [x] Pomijać oba kanały, gdy klucz już istnieje.
- [x] Stosować fail-open przy błędzie cache: zapisać ostrzeżenie i wysłać powiadomienie.
- [x] Nie zmieniać payloadu FCM/WebSocket.
- [x] Nie dodawać parametrów technicznych do komunikatu dla klienta.
- [x] Użyć operacji atomowej zamiast sekwencji `get()` + `set()`, aby uniknąć duplikatów przy równoczesnej pracy workerów.

### 5. Testy

- [x] Sprawdzić, że pierwsza edycja dokumentu wysyła powiadomienie.
- [x] Sprawdzić, że kolejna edycja tego samego dokumentu w ciągu 90 minut nie wysyła push ani WebSocket.
- [x] Sprawdzić, że edycja innego dokumentu nie jest blokowana.
- [x] Sprawdzić możliwość ponownej wysyłki po wygaśnięciu TTL.
- [x] Sprawdzić, że pierwsza publikacja dokumentu nadal wysyła powiadomienie.
- [x] Sprawdzić fail-open przy awarii cache.
- [x] Sprawdzić obecność identyfikatora instancji w kluczu.
- [x] Sprawdzić, że wartość throttlingu nie trafia do payloadu.
- [x] Uruchomić testy `core/test_notifications.py`.
- [x] Uruchomić test `DomainNotificationSignalTest`.
- [x] Uruchomić Ruff dla zmienionych plików.

### 6. Kryteria akceptacji

- [x] Kolejne edycje tego samego ważnego dokumentu generują najwyżej jedno powiadomienie push/WebSocket w ciągu 90 minut.
- [x] Edycje różnych dokumentów nie blokują się wzajemnie.
- [x] Powiadomienia o utworzeniu i zmianach statusu pozostają bez zmian.
- [x] Nie jest potrzebna migracja bazy danych.
- [x] Nie powstaje nowa tabela ani ogólny framework deduplikacji.

## Część II — plan przyszły, nieobjęty pierwszą wersją

Dopiero po sprawdzeniu działania minimalnej wersji można rozważyć uogólnienie mechanizmu na inne źródła powiadomień.

### 1. Uogólnienie mechanizmu

- [ ] Ocenić, czy pojawiły się kolejne przypadki powtarzalnych powiadomień.
- [ ] Rozważyć wspólny parametr throttlingu w centralnym dispatcherze.
- [ ] Nie wprowadzać uogólnienia bez konkretnego problemu i testu opisującego oczekiwane zachowanie.

### 2. Dalsze typy zdarzeń

- [ ] Rozważyć klucze `obiekt + typ zdarzenia` dla innych kategorii.
- [ ] Rozważyć osobne klucze dla publikacji, archiwizacji, zmiany widoczności i edycji.
- [ ] Ustalić, które zdarzenia muszą omijać throttling.

### 3. Dalsze kanały i czas

- [ ] Osobno przeanalizować zasady dla e-maili.
- [ ] Rozważyć różne okna czasowe dla różnych typów zdarzeń.
- [ ] Nie łączyć push, WebSocket i e-mail bez uzasadnienia zachowaniem użytkowników.

### 4. Agregowanie i obserwowalność

- [ ] Rozważyć agregowanie pominiętych zdarzeń i wysyłanie podsumowań.
- [ ] Rozważyć metryki liczby pominiętych powiadomień.
- [ ] Dodać szersze testy współbieżności dla wielu workerów i instancji, jeśli będzie taka potrzeba.

Ta część nie powinna być implementowana razem z pierwszą wersją. Każde rozszerzenie należy najpierw uzasadnić konkretnym problemem i zaprojektować tak, aby nie komplikowało podstawowego przepływu.

## Pliki pierwszej wersji

- [x] `core/notifications.py` — helper i użycie go dla aktualizacji dokumentu.
- [x] `core/test_notifications.py` — testy ograniczone do aktualizacji dokumentów.
- [x] `zzz/settings.py` — konfigurowalna wartość TTL.
- [-] Brak zmian w schemacie bazy danych i migracjach.
- [-] Brak zmian w kontraktach payloadów.
- [-] Brak osobnych instancji Redis.
