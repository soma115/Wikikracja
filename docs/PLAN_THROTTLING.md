# Plan ograniczenia hałasu powiadomień

## Cel

Ograniczyć powtarzające się powiadomienia generowane przez wielokrotne zdarzenia dotyczące tego samego źródła, bez gubienia niezależnych i istotnych zmian.

Przykład: wielokrotna edycja dokumentu nie powinna wysyłać użytkownikom kolejnego powiadomienia częściej niż raz na 90 minut.

## Uzgodnione zasady

- Throttling obejmuje wszystkie powiadomienia dotyczące tego samego źródła.
- Źródło jest identyfikowane jako `obiekt + typ zdarzenia`, np. `post:123:updated`.
- Różne typy zdarzeń tego samego obiektu mają osobne klucze i nie blokują się wzajemnie.
- Pierwsze powiadomienie o nowym źródle jest zawsze wysyłane.
- Kolejne powiadomienie z tym samym kluczem w ciągu 90 minut jest pomijane.
- Pominięcie nie przesuwa początku okna; TTL liczy się od pierwszego przyznanego powiadomienia.
- Push i WebSocket współdzielą jedno okno throttlingu.
- E-mail nie jest objęty tym mechanizmem.
- Throttling działa wspólnie dla workerów jednej instancji Wikikracji.
- Trzynaście instancji Wikikracji korzysta ze wspólnego Redis, ale każda instancja ma oddzielny namespace kluczy.
- W przypadku niedostępności cache obowiązuje fail-open: powiadomienie zostaje wysłane.

## Proponowane rozwiązanie

### 1. Centralny mechanizm w `core.notifications`

Dodać w `core.notifications` mały helper, który atomowo rezerwuje wysyłkę powiadomienia dla danego klucza źródła.

Mechanizm powinien korzystać z `django.core.cache.cache.add(key, value, timeout)`, a nie z sekwencji `get()` i `set()`.

`cache.add()` zapewnia, że przy równoczesnym zdarzeniu obsługiwanym przez kilka workerów tylko jeden worker uzyska prawo do wysyłki.

Proponowane zachowanie helpera:

1. Zbudować pełny klucz throttlingu.
2. Wywołać atomowe `cache.add()` z TTL 90 minut.
3. Zwrócić `True`, jeśli wpis został utworzony i powiadomienie można wysłać.
4. Zwrócić `False`, jeśli klucz już istnieje i powiadomienie należy pominąć.
5. Przy błędzie backendu cache zalogować ostrzeżenie i zwrócić `True` zgodnie z zasadą fail-open.

### 2. Namespace instancji Wikikracja

Redis jest wspólny dla trzynastu instancji, dlatego klucz nie może składać się wyłącznie ze źródła i typu zdarzenia.

Proponowany format:

```text
notification-throttle:{instance}:{source}:{event}
```

Przykład:

```text
notification-throttle:example.org:post:123:updated
```

Jako identyfikator instancji należy wykorzystać domenę bieżącej instancji z `django_site`, ponieważ jest już częścią istniejącej konfiguracji aplikacji i rozróżnia wdrożenia bez dodawania nowego parametru środowiskowego.

Jeżeli pobranie domeny wymaga dostępu do bazy w miejscu, w którym może to powodować problemy, należy zamiast tego użyć istniejącego `settings.SITE_DOMAIN`, z bezpiecznym i stabilnym fallbackiem. Wybór powinien zachować tę samą wartość dla wszystkich workerów danej instancji.

### 3. Integracja z dispatcherem

Rozszerzyć `_dispatch_notification` o opcjonalny parametr techniczny, np. `throttle_key` albo `notification_source`.

Parametr powinien:

- zostać zużyty wyłącznie po stronie serwera;
- nie trafić do payloadu FCM ani WebSocket;
- nie zmienić zachowania istniejących wywołań, które nie korzystają z throttlingu;
- być sprawdzany przed utworzeniem payloadu i uruchomieniem wysyłki push/WebSocket.

Jeżeli throttling zablokuje powiadomienie, dispatcher nie powinien uruchamiać żadnego z tych dwóch kanałów. Ewentualne niezależne wysyłanie e-maila powinno zachować dotychczasowe zachowanie, ponieważ e-mail nie należy do zakresu throttlingu.

### 4. Zastosowanie do źródeł powiadomień

Każdy odbiornik sygnału, który ma podlegać throttlingowi, powinien przekazać jawny klucz źródła i typu zdarzenia.

Dla dokumentów przykładowe klucze to:

- `post:{id}:created`
- `post:{id}:updated`
- `post:{id}:visibility-changed`
- `post:{id}:archived`
- `post:{id}:published`

Ważne zdarzenia statusowe powinny mieć osobne klucze. Dzięki temu zwykła edycja nie zablokuje np. archiwizacji lub ponownego opublikowania dokumentu.

Pierwsza publikacja nowego obiektu powinna korzystać z klucza typu `created` lub `published`, a nie z ogólnego klucza obiektu.

Podczas implementacji należy przejrzeć wszystkie odbiorniki sygnałów w `core.notifications` i przypisać klucze tylko do rzeczywistych źródeł zdarzeń. Nie należy deduplikować powiadomień na podstawie samego tekstu, tytułu ani tagu przeglądarkowego.

## Zakres plików

Najbardziej prawdopodobne miejsca zmian:

- `core/notifications.py` — helper, konfiguracja parametru oraz centralne sprawdzanie throttlingu;
- `core/test_notifications.py` — testy mechanizmu, atomowości i integracji z dispatcherem;
- odbiorniki sygnałów, które będą przekazywać klucze źródeł, w szczególności miejsca obsługujące dokumenty;
- ustawienia projektu — domyślne 90 minut, jeżeli wartość nie będzie trzymana wyłącznie jako stała modułu.

Nie przewiduje się:

- migracji bazy danych;
- nowego modelu powiadomień;
- osobnej tabeli deduplikacji;
- osobnego Redisa dla każdej instancji;
- zmian w kontraktach payloadów wysyłanych do klientów.

## Konfiguracja czasu

Dodać jedną wartość konfiguracyjną z domyślną wartością 90 minut, np.:

```python
NOTIFICATION_THROTTLE_SECONDS = 90 * 60
```

Wartość powinna być używana jako TTL wpisu cache. Nie należy kodować liczby `5400` w wielu miejscach.

## Zachowanie przy awarii

Mechanizm ma działać w trybie fail-open:

- błąd połączenia z Redis/cache nie może zablokować ważnego powiadomienia;
- błąd powinien zostać zalogowany bez ujawniania danych wrażliwych;
- wysłanie bez aktywnego throttlingu może chwilowo dopuścić duplikat, ale nie powoduje utraty komunikatu.

## Testy

W `core/test_notifications.py` należy dodać testy obejmujące:

1. pierwsze powiadomienie dla klucza jest wysyłane;
2. drugie powiadomienie z tym samym kluczem jest pomijane;
3. TTL wynosi 90 minut lub wartość skonfigurowaną w ustawieniach;
4. po wygaśnięciu TTL powiadomienie może zostać wysłane ponownie;
5. różne źródła nie blokują się wzajemnie;
6. różne typy zdarzeń tego samego obiektu nie blokują się wzajemnie;
7. namespace dwóch instancji powoduje niezależne limity;
8. push i WebSocket są pomijane razem dla zablokowanego klucza;
9. parametr techniczny throttlingu nie trafia do payloadu;
10. błąd cache uruchamia fail-open;
11. równoczesna próba używa atomowej operacji cache zamiast `get()` + `set()`;
12. pierwsza publikacja nowego źródła nadal wysyła powiadomienie;
13. istotne zmiany statusu korzystające z osobnych kluczy nadal są wysyłane.

Jeżeli zmiana obejmie odbiorniki board, dodać także testy potwierdzające mapowanie zdarzeń dokumentu na właściwe klucze.

## Kolejność realizacji

1. Potwierdzić sposób uzyskiwania stabilnego identyfikatora instancji — preferowana domena instancji.
2. Dodać konfigurację TTL i helper atomowego claimowania klucza.
3. Rozszerzyć centralny dispatcher o opcjonalny throttling.
4. Dodać klucze do odbiorników źródeł powiadomień.
5. Dodać testy jednostkowe i integracyjne ograniczone do zmienionego przepływu.
6. Uruchomić wersję `.venv` i testy dotyczące `core.test_notifications` oraz zmienionych odbiorników.
7. Sprawdzić, że istniejące payloady i kanały bez throttlingu zachowują dotychczasowe działanie.

## Kryteria akceptacji

- Wielokrotna edycja tego samego dokumentu generuje najwyżej jedno powiadomienie push/WebSocket w ciągu 90 minut na danej instancji.
- Ta sama edycja na dwóch różnych instancjach nie powoduje wzajemnego blokowania.
- Dwa workery jednej instancji nie wysyłają tego samego powiadomienia równocześnie.
- Niezależne typy zdarzeń nie są tłumione przez wspólny, zbyt szeroki klucz.
- Awaria Redis nie powoduje utraty powiadomień.
- Nie jest wymagana zmiana schematu bazy danych.
