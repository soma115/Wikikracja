# Plan ograniczenia hałasu powiadomień

Celem jest ograniczenie hałasu przy zachowaniu prostoty. Najpierw wdrażamy małą zmianę rozwiązującą konkretny problem, a dopiero później rozważamy uogólnienie mechanizmu.

## Część I — minimalna pierwsza wersja

### Cel

Ograniczyć powiadomienia generowane przez kolejne, następujące po sobie edycje tego samego dokumentu.

Przykład:

1. dokument zostaje zmieniony — wysyłamy powiadomienie;
2. dokument zostaje zmieniony ponownie po kilku minutach — pomijamy powiadomienie;
3. po wygaśnięciu 90 minut kolejna edycja może ponownie wysłać powiadomienie.

### Zakres

Pierwsza wersja obejmuje wyłącznie powiadomienie o aktualizacji ważnego dokumentu, czyli przypadek `created=False` w odbiorniku `important_post_published`.

Nie zmieniamy zachowania:

- pierwszej publikacji dokumentu;
- utworzenia nowego dokumentu;
- zmiany widoczności;
- archiwizacji;
- ponownego udostępnienia;
- innych kategorii powiadomień;
- wiadomości e-mail.

Dzięki temu pierwsza wersja nie ryzykuje ukrycia ważnych zmian statusu ani nie przebudowuje całego systemu powiadomień.

### Zasada throttlingu

Dla kolejnych edycji tego samego dokumentu używamy jednego klucza:

```text
notification-throttle:{instance}:post:{post_id}:updated
```

`{instance}` izoluje trzynaście instancji Wikikracji korzystających ze wspólnego Redisa. Jako identyfikator instancji należy wykorzystać istniejącą domenę instancji, bez dodawania nowego modelu ani osobnego systemu konfiguracji.

Przykład:

```text
notification-throttle:example.org:post:123:updated
```

### Implementacja

1. Dodać w `core.notifications` mały helper oparty o `django.core.cache.cache.add()`.
2. Ustawić TTL na 90 minut, najlepiej przez jedną wartość konfiguracyjną:

   ```python
   NOTIFICATION_THROTTLE_SECONDS = 90 * 60
   ```

3. W `on_important_post_published` wywoływać helper tylko dla aktualizacji (`created=False`).
4. Jeżeli `cache.add()` utworzy klucz, wysłać istniejące powiadomienie push i WebSocket.
5. Jeżeli klucz już istnieje, pominąć oba kanały.
6. Przy błędzie cache zastosować fail-open: zalogować ostrzeżenie i wysłać powiadomienie.
7. Nie zmieniać payloadu FCM/WebSocket i nie dodawać parametrów technicznych do komunikatu dla klienta.

`cache.add()` jest istotne, ponieważ kilka workerów może jednocześnie obsługiwać edycje. Sekwencja `get()` + `set()` mogłaby wysłać duplikaty.

### Testy pierwszej wersji

Dodać tylko testy potrzebne dla tego przypadku:

1. pierwsza edycja dokumentu wysyła powiadomienie;
2. kolejna edycja tego samego dokumentu w ciągu 90 minut nie wysyła push ani WebSocket;
3. edycja innego dokumentu nie jest blokowana;
4. po wygaśnięciu TTL powiadomienie może zostać wysłane ponownie;
5. pierwsza publikacja dokumentu nadal wysyła powiadomienie;
6. awaria cache nie blokuje wysyłki;
7. klucz zawiera identyfikator instancji;
8. wartość throttlingu nie trafia do payloadu.

### Kryteria akceptacji

- Kolejne edycje tego samego ważnego dokumentu generują najwyżej jedno powiadomienie push/WebSocket w ciągu 90 minut.
- Edycje różnych dokumentów nie blokują się wzajemnie.
- Powiadomienia o utworzeniu i zmianach statusu pozostają bez zmian.
- Nie jest potrzebna migracja bazy danych.
- Nie powstaje nowa tabela ani ogólny framework deduplikacji.

## Część II — plan przyszły, nieobjęty pierwszą wersją

Dopiero po sprawdzeniu działania minimalnej wersji można rozważyć uogólnienie mechanizmu na inne źródła powiadomień.

Potencjalny zakres przyszłej zmiany:

- wspólny parametr throttlingu w centralnym dispatcherze;
- klucze `obiekt + typ zdarzenia` dla wszystkich kategorii;
- osobne klucze dla publikacji, archiwizacji, zmiany widoczności i edycji;
- niezależne zasady dla e-maili;
- konfiguracja różnych okien czasowych dla różnych typów zdarzeń;
- agregowanie pominiętych zdarzeń i wysyłanie podsumowań;
- dodatkowe metryki i diagnostyka throttlingu;
- szersze testy współbieżności dla wielu workerów i instancji.

Ta część nie powinna być implementowana razem z pierwszą wersją. Każde rozszerzenie należy najpierw uzasadnić konkretnym problemem i zaprojektować tak, aby nie komplikowało podstawowego przepływu.

## Pliki przewidziane do zmiany w pierwszej wersji

- `core/notifications.py` — prosty helper oraz użycie go dla aktualizacji dokumentu;
- `core/test_notifications.py` — testy ograniczone do aktualizacji dokumentów;
- ustawienia projektu — jedna wartość TTL, jeśli nie zostanie pozostawiona jako stała modułu.

Nie przewiduje się zmian w schemacie bazy danych, migracjach, kontraktach payloadów ani konfiguracji osobnych instancji Redis.
