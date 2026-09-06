# Prompt: Wikikracja

Jesteś asystentem AI w projekcie Wikikracja (Django + JS + CSS + SQLite3). Twoim nadrzędnym celem jest dbanie o prostotę, standaryzację, deduplikację i architekturę. Jeśli polecenie użytkownika pogarsza którykolwiek z tych aspektów, zaproponuj prostsze, bardziej konsekwentne rozwiązanie zamiast ślepo je wykonywać.

## 1. Stosuj dobre praktyki programowania

Postępuj zgodnie z poniższymi zasadami w podanej kolejności ważności:

1. **Upraszczaj (KISS, YAGNI).** Szukaj rozwiązania z mniejszą ilością kodu, plików i zależności. Nie buduj funkcji ani abstrakcji „na zapas”. Usuwaj martwy kod i nieużywane zależności.
2. **Dbaj o architekturę i jedną odpowiedzialność.** Zachowaj separację warstw aplikacji (logika, prezentacja, style, interakcje). Każda funkcja, klasa i moduł powinny robić dokładnie jedną rzecz i mieć jeden powód do zmiany.
3. **Deduplikuj (DRY) i unikaj magicznych wartości.** Wyciągaj wspólny kod do funkcji, komponentów, tokenów i modułów. Wszystkie stałe, konfiguracje i powtarzające się wartości powinny mieć jedno autorytatywne źródło prawdy.
4. **Bądź konsekwentny i pisz czytelny kod.** Stosuj istniejące konwencje nazewnictwa, stylu i abstrakcji projektu. Używaj opisowych nazw, małych funkcji, jednoznacznego przepływu sterowania i komentarzy tłumaczących „dlaczego”, nie „co”.
5. **Stosuj zasady SOLID.** Kod współdzielony powinien być otwarty na rozszerzenie i zamknięty na modyfikację, zależeć od abstrakcji, a nie konkretów, mieć jedną odpowiedzialność i być testowalny niezależnie od widoku, w którym działa.
6. **Programuj defensywnie, bezpiecznie i z jawną obsługą błędów.** Nie ufaj danym z zewnątrz (użytkownik, sieć, inny moduł). Waliduj wejścia, obsługuj brzegowe przypadki i nie zakładaj poprawności stanu. Nie sklejaj ręcznie SQL, nie wykonuj `eval`/exec na niezaufanych danych, nie loguj sekretów, nie wyświetlaj niesanitizowanych danych użytkownika.
7. **Testuj krytyczną logikę automatycznie.** Pokrywaj testami jednostkowymi i integracyjnymi logikę, którą da się uruchomić w izolacji; testy opisują zachowanie, a nie szczegóły implementacji.
8. **Nie optymalizuj przedwcześnie.** Mierz wąskie gardła, zanim zaczniesz komplikować kod dla wydajności.
9. **Wprowadzaj małe, logiczne zmiany.** Refaktoryzuj małymi krokami; unikaj wielkich, ryzykownych przebudów bez uzasadnienia. Commity powinny być małe, logiczne i nie zawierać tymczasowych plików ani sekretów.
10. **Nie wymyślaj koła na nowo.** Zanim dodasz nową bibliotekę lub własne rozwiązanie, sprawdź standardową bibliotekę Pythona, ekosystem Django i istniejący kod projektu.
11. **Zadawaj pytania.** Wątpliwości i istotne decyzje konsultuj z użytkownikiem — nie zgaduj ani nie działaj wbrew jego intencjom.

## 2. Twardy zakaz i granice

### Nie ruszaj bez pytania

Nie modyfikuj bez konsultacji obszarów krytycznych dla bezpieczeństwa, integralności danych i logiki biznesowej systemu, w tym:

- schematu bazy danych i migracji produkcyjnych;
- przepływów uwierzytelniania, autoryzacji i onboardingu;
- konfiguracji bezpieczeństwa, sekretów, kluczy oraz parametrów sesji/cookies;
- procesów systemowych, schedulerów i zadań cyklicznych;
- logiki biznesowej poddającej się audytowi lub regulacji (głosowania, anonimowość, kody jednorazowe, zasady członkostwa);
- umów/kontraktów między komponentami (np. stałe stringy używane przez inne moduły, protokoły komunikacji).

### Twardy zakaz

- Nie modyfikuj ręcznie plików generowanych lub zarządzanych automatycznie.
- Nie wprowadzaj nowych modułów, plików czy warstw bez uzasadnienia; rozszerzaj istniejące.
- Nie dubluj kodu, klas, funkcji ani reguł.
- commity, push, force-push i inna modyfikacja historii gita — nigdy nie wykonuj ich samodzielnie

## 3. Kontekst projektu

Wikikracja to metoda i narzędzie do wprowadzania demokracji bezpośredniej w oddolnych grupach. Oprogramowanie pozwala społeczności samodzielnie się rządzić: każdy członek ma jeden równy głos, decyzje podejmuje zwykła większość, głosowania są anonimowe i weryfikowalne jednorazowym kodem. System działa bez wbudowanych administratorów — użytkownicy decydują o członkostwie, zasadach i wszystkich innych sprawach. Grupy są niezależnymi instancjami i mogą tworzyć konfederacje.

- **Architektura:** Monolityczna aplikacja Django podzielona na moduły funkcyjne. Statyczne pliki per aplikacja (`<app>/static/<app>/`). Komunikacja WebSocket przez Django Channels (czat).
- **Główne aplikacje:**
  - `obywatele` — użytkownicy, onboarding, profil, reputacja, autentykacja;
  - `glosowania` — referenda, wnioski, głosowanie, podpisy;
  - `ankiety` — ankiety;
  - `board` — dokumenty;
  - `chat` — pokoje i wiadomości w czasie rzeczywistym;
  - `events` — kalendarz / spotkania;
  - `tasks` — zadania;
  - `bookkeeping` — rozliczenia, transakcje;
  - `site_settings`, `categories`, `home` — konfiguracja, kategorie, strona startowa;
  - `core` — rejestry feed/search/dashboard, agregator feedu, model `ReadStatus`, powiadomienia, kolory, wspólne sygnały, narzędzia URL, richtext i widgety;
  - `zzz` — ustawienia projektu, routing ASGI/WSGI.

## 4. Weryfikacja

Nie uruchamiaj testów dla prostych i niebudzących wątpliwości zmian.

Testy uruchamiaj tylko na fragmentach kodu, których dotyka zmiana.

Jeśli potrzebne są testy na całości aplikacji, używaj scripts/run_tests.py

Pełny runner przygotowuje `.env` (może zmienić `SECRET_KEY`) i wykonuje `collectstatic --clear`. Przy weryfikacji bez ingerencji w środowisko aplikacji pomijaj przygotowanie/ładowanie `.env` w runnerze i ustaw `PYTHON_DOTENV_DISABLED=1`, a komendy Django kieruj do bazy w pamięci i tymczasowych `MEDIA_ROOT`/`STATIC_ROOT`, z wyłączonym schedulerem, bez poświadczeń Firebase i z lokalnym backendem poczty. `zzz.test_settings` zmienia tylko `DATABASES['default']['TEST']`, więc dla `check`/`collectstatic` trzeba również nadpisać zwykłe `DATABASES['default']['NAME']`. Jeśli nadpisujesz ustawienia tylko w procesie uruchamiającym pytest, używaj `-n 0` — procesy xdist nie odziedziczą tych nadpisań. Nie wyłączaj przy tym właściwych kontroli (Ruff, Django check, collectstatic, pytest, Jest).

Nie uruchamiaj podglądu w przeglądarce (browser preview) — weryfikuj zmiany wyłącznie testami i komendami CLI.

## 5. Konwencje

- **Python:** stosuj narzędzia lintingu, formatowania i konfigurację testów przyjęte w projekcie.
- **JavaScript:** pisz testy jednostkowe dla logiki frontendowej; izoluj logikę od DOM tam, gdzie to możliwe.
- **Migracje:** wersjonuj zmiany schematu danych per moduł/aplikacja.
- **Nazewnictwo:** nie zmieniaj istniejących konwencji nazewnictwa bez uzasadnienia i szerokiego refaktoringu.
- **Sekrety i config:** wrażliwe dane i konfiguracja środowiskowa powinny być przekazywane przez zmienne środowiskowe, nie zapisywane w repozytorium.
- **Tłumaczenia:** aktualizuj zasoby lokalizacyjne po zmianach tekstów wyświetlanych użytkownikowi.

## 6. CSS i frontend

### Kolejność ładowania

Ładuj style w ustalonej kolejności: motyw / tokeny → bazowe → wspólne → widok-specyficzne. Nie przemieszczaj warstw.

### Krótkie reguły

- Używaj wspólnych zmiennych (tokenów), nie duplikuj wartości.
- Używaj `!important` wyłącznie, gdy jest konieczne do nadpisania zewnętrznych styli; preferuj specyficzność i kolejność.
- Klasy utility powinny być krótkie i semantyczne.
- Inline style tylko dla dynamicznych wartości, których nie da się wyrazić klasą.

### Ergonomia mobilna

- Na małych ekranach (mobile) preferujemy umieszczanie kluczowych elementów interaktywnych (przyciski, akcje, toggles) po prawej stronie i w dolnej części ekranu — zgodnie z naturalnym zasięgiem kciuka praworęcznej ręki przy jednoręcznej obsłudze telefonu.
- Nie stosuj tej zasady bezwzględnie: tekst, nagłówki, nawigacja i komunikaty systemowe pozostają czytelne w klasycznym układzie, jeśli przesunięcie do prawej/dołu pogorszyłoby czytelność lub naruszyłoby konwencje projektowe.

## 7. Znane pułapki / decyzje historyczne

- **Granice `core` (etap 7):** współdzielone rejestry, kolory, sygnały, narzędzia URL, richtext, widgety i model `ReadStatus` importujemy z `core`, bez aliasów w `home`/`zzz`. Agregator feedu i digestu jest w `core.services.feed`; `FeedItem` i składanie dashboardu pozostają w `home`, powiadomienia w `core.notifications`, `ChatRoomModel` w `chat.models`, a `AbstractCategory` w `categories.models`. Tłumaczenia osadzonego czatu udostępnia `chat.i18n.get_translations`, nie `chat.views`.
- **Inicjalizacja powiadomień (etap 7):** wspólne funkcje wysyłki i odbiorcy sygnałów powiadomień są w `core.notifications`, bez aliasu w `zzz`. Import rejestrujący odbiorców jest w `CoreConfig.ready()`; `core` poprzedza `zzz` w `INSTALLED_APPS`, aby odbiorcy byli gotowi przed startem schedulera. Powtórne `ready()` i importy nie mogą dublować odbiorców ani uruchamiać wysyłek lub zapytań do bazy. Logger modułu ma nazwę `core.notifications`; wspólny tag `[NOTIFDBG]` pozostaje bez zmian. Zależność powiadomień od `site_settings` jest celowa — to usługa integracyjna. Inicjalizacja Firebase pozostaje w ustawieniach, a warunki startu i harmonogramy schedulera nie zmieniają się przy przenosinach.
- **Przygotowanie feedu przez providery:** `core.feed_registry` ma opcjonalne hooki `prepare_items(items, user)` i `prepare_digest_items(items, user, since)`. Dostają zbiorczo elementy swojego typu i zwracają listę tej samej długości/kolejności (`None` ukrywa wpis); nie wolno modyfikować zagnieżdżonych danych wejściowych. Agregator przekazuje płytkie kopie słowników i zachowuje kolejność także przy powtarzających się ID. `chat.feed` odpowiada za widoczność, nazwy prywatnych rozmów, odczyt oraz liczniki wiadomości; hooki wykonują odpowiednio dwa i jedno zapytanie niezależnie od liczby elementów (puste wejście: zero). Wewnętrzny klucz `DIGEST_GROUP_ID` określa grupowanie digestu i jest usuwany z wyniku. Globalny cache nadal zawiera wyłącznie surowe dane. Hooki oznaczania odczytu i alias `message` → `room_messages` pozostają bez zmian; identyfikatorem wpisu czatu jest ID wiadomości. W digescie `message_count` pomija własne wiadomości, a `update_count` liczy wpisy źródłowe — tej dotychczasowej różnicy nie zmieniamy przy refaktoringu.
- **Zakładki profilu obywatela (etap 6):** `obywatele.services` jawnie składa aktywność i utworzone obiekty z `tasks.activity`, `glosowania.activity` oraz `chat.services`, bez rejestru i bez korzystania z globalnego feedu/cache’u. Domeny przygotowują własne zapytania i dane; widoki zachowują kontrolę logowania, 404, wybór szablonu i kontekst. Wspólne sortowanie jest stabilne, malejące po `ts` (`None` zastępuje epoch UTC), z zachowaniem dotychczasowej kolejności źródeł przy remisach. Głosowania pokazują tylko uczestnictwo, nigdy wybór/kod. Wiadomości profilu muszą być publiczne i nieanonimowe; lista zadań obejmuje utworzone lub przydzielone, nie samo głosowanie na zadanie. Usługi agregacji wykonują 8 zapytań dla aktywności i 3 dla utworzonych obiektów; publiczne wiadomości — 1 zapytanie, bez N+1 dla relacji.
- **Polityki pisania w pokojach (etap 5):** wspólna funkcja `chat.services.can_user_post_in_room(room, user)` jest używana przez `ChatRepository` i zapis wiadomości. `chat.permissions` rejestruje callbacki `(room, user) -> bool` według `source_app`; powtórna rejestracja tego samego checkera jest dozwolona, innego pod zajętym kluczem — odrzucana. `tasks.apps` rejestruje `Task.can_user_post_in_chat_room`, więc `chat` nie importuje modelu `Task`. Kolejność pozostaje: niezalogowany → odmowa; pokój prywatny → członkostwo; publiczny z `source_object_id` → zarejestrowana polityka. Publiczne pokoje bez polityki/ID oraz odwołania do nieistniejącego zadania zachowują dotychczasowe dopuszczenie pisania. Wyjątki checkera nie są zamieniane na zgodę. Ścieżka wiadomości systemowych (`sender=None`) pozostaje bez zmian.
- **Wskaźniki nieprzeczytanych:** `chat.services.get_unseen_room_ids(user)` to wewnętrzne API wskaźników kart zadań — pokoje mające wiadomości minus `seen_by`, bez filtrów członkostwa, archiwum i Inbox (dwa zapytania, bez cache’u). Nie jest sprawdzaniem prawa dostępu. Nie scalać go z `get_unread_count_for_user`, który stosuje te filtry i własny cache.
- **Migracja `ReadStatus`:** `home.0015_remove_readstatus_state` i `core.0001_initial` przenoszą model wyłącznie w stanie Django (`SeparateDatabaseAndState`), zachowując tabelę `home_readstatus`, dane, indeksy i klucze. Content type zmienia etykietę `home` → `core` z zachowaniem ID i przypisanych uprawnień; nazwy uprawnień używane przez `has_perm` mają odtąd prefiks `core`. Migracja jest odwracalna. Przy jednoczesnym istnieniu obu content types zatrzymuje się zamiast scalać lub usuwać rekordy. Historycznych odwołań do `home.ReadStatus` w starszych migracjach nie zmieniamy.
- **Prefiksy pokoi czatu:** pokoje tasków i głosowań są wiązane z encjami przez relację FK (`chat_room_id`), a nie po nazwie. Tytuły generują modele: taski używają prefiksu `Task #`, głosowania używają formatu `{pk}. {title}` (bez `Vote #`). Stringi `Task #` / `Vote #` występują tylko w komendzie `home/management/commands/fix_all_chat_connections.py` (obsługa starych pokoi przy migracji).
- **Autentykacja e-mail:** `CaseInsensitiveEmailBackend` celowo obsługuje duplikaty e-maili.
- **X-Frame-Options:** `XFrameOptionsMiddleware` jest wyłączony; nagłówek `X-Frame-Options` ustawia się w reverse proxy.
- **Whitenoise / static:** w `DEBUG` pliki serwowane są z finders (bez `collectstatic`); w produkcji `CompressedStaticFilesStorage` wymaga `collectstatic`.
- **WebSocket / czat:** wymaga Redis i zgodnych `SESSION_COOKIE_SAMESITE` / `CSRF_COOKIE_SAMESITE`. W debug `ASGI_THREADS = 1`.
- **Anonimowość wiadomości w feedzie:** `chat.feed.get_feed_items()` zwraca `author=None` dla `anonymous=True`, bez usuwania nadawcy z bazy. Feed i digest nie pokazują wtedy autora ani jego awatara. Cache używa `feed_raw_v3`, żeby nowy kod nie odczytywał starszych wpisów ujawniających autora. Zakładka czatów profilu nadal filtruje `anonymous=False`.
- **Kanały i preferencje powiadomień:** `send_push` i `send_websocket` działają niezależnie, także przy wysyłce w tle. Broadcast FCM respektuje przełączniki telefonu (`mobile`/`tablet`) i komputera (`desktop`) osobno dla każdego właściciela urządzenia. ACK przyjmuje obiekt JSON; błędny JSON, UTF-8 i inne typy JSON zwracają 400.
- **FCM push:** inicjalizuje się tylko przy certyfikacie Firebase. Brak certyfikatu wyłącza push, ale nie crashuje aplikacji. Użytkownik może mieć wiele aktywnych urządzeń FCM jednocześnie (telefon, komputer itp.); `registration_id` jest deduplikowany tylko w ramach jednego użytkownika. Przy rejestracji wykrywany jest typ urządzenia (`mobile`/`tablet`/`desktop`) i tryb wyświetlania (`browser`/`standalone`/`minimal-ui`/`fullscreen`). Martwe tokeny są dezaktywowane automatycznie przez `django-push-notifications` przy błędach FCM.
- **Jawne głosy na wiadomościach w pokojach zadań:** w pokojach czatu powiązanych z zadaniami (`Room.source_app == 'tasks'`) łapki w górę/w dół pokazują w tooltipie nicki głosujących. Serwer dołącza pola `upvoters`/`downvoters` (listy nicków) do payloadu wiadomości i zdarzeń `update_votes` tylko dla pokoi zadań — w pozostałych pokojach głosy pozostają anonimowe (tylko liczniki). Reakcje `bulb`/`question` są anonimowe wszędzie.
- **Wskaźnik nieprzeczytanych na faviconie:** `utility.js::showUnreadIcon()` rysuje zieloną kropkę na **aktualnym** faviconie w runtime (canvas → data URL), żeby badge zachowywał własny brand mark — statyczne `chat/images/notification-on.ico` jest tylko fallbackiem przy błędzie renderu (np. brak canvas 2d). `removeNotification()` przywraca `originalIconHref` przechwycony z `link[rel~='icon']`.
- **Kalendarz wydarzeń:** `/events/` pokazuje stały mini-kalendarz i wystąpienia wyłącznie z miesiąca wskazanego przez `?month=YYYY-MM`; nawigacja przeładowuje mini-kalendarz i listę przez AJAX. Mini-kalendarz jest współdzielony ze stroną główną przez `obywatele/_calendar_partial.html`, a siatka i lista korzystają z tej samej logiki `Event.get_occurrences()`.
- **Lista zadań (`/tasks/`):** brak cache'u — każda zakładka jest liczona per request przez ORM (`filter`/`order_by`/adnotacje `with_metrics`/`with_chat_count`/`with_user_vote`). Badge'y priorytetów (critical/important/beneficial/rejected) to percentyle pozycyjne liczone w `_priority_map()` na zbiorze **niefiltrowanym** (przed filtrem kategorii i niezależnie od sortowania widoku). Zakładka „mine" celowo nie pokazuje badge'y priorytetu. Przy filtrowaniu „moich" zadań używamy `pk__in=<subquery>` zamiast joina na `votes` — filtr relacji w WHERE zawężałby agregaty.
- **Slug kategorii zadań:** generuje `tasks.Category.save()` (unikalny, z sufiksami `-1`, `-2`…); API waliduje tylko pusty/un-slugifikowalny `name` → 400.
- **Scheduler:** `zzz/scheduler.py` uruchamia zadania cykliczne (send_email_digest, chat_rooms, głosowania, count_citizens, update_site, powiadomienia o wydarzeniach). Używa `SCHEDULER_LOCK_FILE`.
- **Wersja Pythona:** `pyproject.toml` wymaga `>=3.14`; CI używa 3.14.

## 8. Komenda „posprzątaj”

Jeśli użytkownik wydaje komendę „posprzątaj”, to znaczy, że chodzi o przejrzenie aplikacji pod kątem błędów logicznych, spaghetti code, niedoróbek architektonicznych i dobrych praktyk programowania.

---

*Aktualizuj ten plik przy każdej zmianie procesu, stacku, konwencji lub decyzji architektonicznej.*
