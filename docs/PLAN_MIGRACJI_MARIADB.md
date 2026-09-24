# Plan migracji Wikikracji z SQLite do MariaDB

## Cel i zakres

Celem jest:

- zwiększenie niezawodności Wikikracji;
- zwiększenie skalowalności Wikikracji;
- uproszczenie całego systemu przez usunięcie warstw i zabezpieczeń
  potrzebnych wyłącznie z powodu SQLite;
- umożliwienie niezależnego przenoszenia każdej instancji.

W szczególności migracja ma usunąć ograniczenia wynikające z przechowywania
bazy jako współdzielonego pliku SQLite, bez upraszczania kosztem integralności
danych, anonimowości lub możliwości odtworzenia instancji.
Migracja ma zachować zachowanie biznesowe aplikacji, w szczególności:

- anonimowość i weryfikowalność głosów;
- jeden głos obywatela w referendum;
- kody jednorazowe ujawniane dopiero po zakończeniu referendum;
- niezależność instancji Wikikracji;
- Django Channels, kolejki powiadomień i cache w Redis.

Ten plan nie zakłada przeniesienia bufora anonimowych głosów do MariaDB.
Treść głosu (`code` i wybór) nadal pozostaje w Redis do chwili zamknięcia
referendum. MariaDB przechowuje fakt oddania głosu, ale nie może stać się
miejscem natychmiastowego zapisu osoby i treści tego samego głosu.

### Co oznacza uproszczenie systemu

Uproszczenie nie oznacza minimalnej liczby podów za wszelką cenę. Własny Redis
na instancję zwiększy liczbę małych workloadów, ale usunie współdzielenie stanu
i związane z nim wyjątki. Główne uproszczenia docelowe to:

- usunięcie WAL, `busy_timeout`, retry na `database is locked` i diagnostyki
  plików SQLite;
- usunięcie ograniczenia jednego writera oraz zależności bazy od PVC i blokad
  filesystemu;
- zastąpienie backupu plików SQLite backupem każdej bazy MariaDB;
- usunięcie blokady plikowej schedulera lub zastąpienie jej nazwaną blokadą
  `GET_LOCK()` w MariaDB;
- ujednolicenie konfiguracji i procedur przenoszenia instancji;
- wyraźne oddzielenie danych trwałych (MariaDB i media) od efemerycznego
  stanu Redis.

Nie upraszczamy przez usunięcie Redis, schedulera, workera ani zabezpieczeń
anonimowości, ponieważ pełnią one niezależne funkcje biznesowe i operacyjne.

## Stan wyjściowy

- Django używa SQLite `db/db.sqlite3`.
- Każda instancja ma własny plik bazy na PVC `ReadWriteOnce`.
- HTTP, scheduler i worker powiadomień korzystają z tego samego PVC.
- Każda instancja ma jedną replikę HTTP, schedulera i workera.
- SQLite wymaga WAL, `busy_timeout`, retry na `database is locked` oraz
  ograniczenia liczby writerów.
- Scheduler APScheduler działa jako osobny Deployment na instancję.
- Redis jest współdzielony przez instancje, ale każda z nich używa osobnej
  logicznej bazy i prefiksu kanałów.
- Redis przechowuje także anonimowy bufor głosów, kolejkę powiadomień,
  kanały WebSocket i stan obecności.
- Backup produkcyjny kopiuje bazy SQLite i media z PVC na NAS przez Kubernetes
  CronJob.

Dokumentacja SQLite pozostaje użyteczna jako opis stanu bieżącego i planu
przejściowego: `docs/PLAN_NIEZAWODNOSC_SQLITE.md`.

## Docelowa architektura

### MariaDB

**Każda instancja Wikikracji ma własną, osobną instancję MariaDB** — osobny
serwer, StatefulSet albo inny niezależnie zarządzany deployment. Wspólny
serwer lub klaster MariaDB dla wielu instancji nie jest wariantem docelowym:

```text
Wikikracja instance 1 ── MariaDB instance-1
Wikikracja instance 2 ── MariaDB instance-2
Wikikracja instance 3 ── MariaDB instance-3
Wikikracja instance N ── MariaDB instance-N
```

Nie używamy wspólnego modelu z `instance_id`, wspólnej bazy ani wspólnego
serwera MariaDB dla wielu instancji. Osobna instancja MariaDB, osobny Redis,
media, konfiguracja i sekrety są warunkiem pełnej niezależności i możliwości
przeniesienia jednej instancji bez eksportowania lub odłączania pozostałych.

W razie przeniesienia instancji wykonuje się backup jej bazy MariaDB, a nie
wspólnego systemu wieloinstancyjnego. Kosztem tej decyzji jest większa liczba
usług do utrzymania; plan musi więc obejmować automatyzację provisioningu,
backupów, aktualizacji i monitoringu per instancja.

### Redis

Docelowo **każda instancja Wikikracji ma własny, efemeryczny Redis**, z własnym
Service, Deploymentem, konfiguracją i limitami zasobów. Redis nie ma własnego
PVC ani innego trwałego storage'u i nie jest backupowany:

```text
Wikikracja instance 1 ── MariaDB wikikracja_instance_1
                      └─ Redis redis-instance-1
Wikikracja instance 2 ── MariaDB wikikracja_instance_2
                      └─ Redis redis-instance-2
Wikikracja instance N ── MariaDB wikikracja_instance_N
                      └─ Redis redis-instance-N
```

Nie używamy współdzielonego `redis-1` ani osobnych logicznych baz Redis jako
modelu docelowego. Osobny Redis izoluje bufor anonimowych głosów, Channels,
kolejkę powiadomień, cache i obecność. Wszystkie te dane są efemeryczne; po
przeniesieniu instancji uruchamiany jest nowy Redis, bez odtwarzania jego
zawartości.

Redis zachowuje dotychczasową odpowiedzialność:

- bufor anonimowych głosów;
- atomowe deduplikowanie operacji oddania głosu;
- atomowe przejęcie bufora po zamknięciu referendum;
- Channels i komunikacja WebSocket;
- kolejka powiadomień;
- cache i obecność.

Migracja do MariaDB nie może zmienić kolejności zapisu głosu:

1. MariaDB zapisuje fakt, że obywatel zagłosował;
2. Redis zapisuje kod i wybór bez identyfikatora obywatela;
3. po zamknięciu referendum bufor jest atomowo przejmowany i mieszany;
4. dopiero wtedy wynik i kody trafiają do MariaDB;
5. bufor jest usuwany dopiero po zatwierdzeniu transakcji MariaDB.

Redis pozostaje celowo efemeryczny. Restart, utrata poda lub przeniesienie
instancji może usunąć jego zawartość, w tym bufor aktywnych głosów. Dlatego
przenoszenie, restore i planowane restarty instancji są dozwolone wyłącznie po
zakończeniu wszystkich aktywnych referendów. Nie wolno uznać MariaDB za
zamiennik tego bufora ani dodawać Redisowi trwałego storage'u w ramach tej
migracji.

To ograniczenie dotyczy planowanych operacji. Nie usuwa istniejącego
mechanizmu awaryjnego: jeśli po awarii Redisa liczba rekordów w buforze nie
zgadza się z liczbą zarejestrowanych głosujących, system nie liczy częściowego
wyniku. Czyści listę faktów oddania głosu, unieważnia wydane kody, zwiększa
licznik restartów i rozpoczyna referendum od nowa na pełny okres. Ten restart
referendum pozostaje wymaganym zabezpieczeniem integralności głosowania.

### Procesy aplikacji

Początkowo pozostają osobne procesy per instancja:

```text
HTTP/ASGI ───────────────┐
scheduler APScheduler ───┼─ MariaDB wikikracja_instance_N
chat-notifications-worker ┘  Redis redis-instance-N
```

Każdy z tych procesów korzysta wyłącznie z zasobów swojej instancji. Nie może
istnieć wspólny Redis runtime ani wspólna baza danych aplikacyjnych dla dwóch
instancji. Migracja bazy nie wymaga jednoczesnego usuwania APScheduler ani
workera. Po przejściu na MariaDB można niezależnie rozważyć zwiększenie
replik HTTP oraz zastąpienie blokady plikowej schedulera nazwaną blokadą
`GET_LOCK()`, po osobnej weryfikacji czasu życia blokady i połączenia.

### Przenośny pakiet instancji

Celem jest pełny, samodzielny pakiet jednej instancji, możliwy do uruchomienia
w innym klastrze lub na innym hoście. Pakiet obejmuje:

- osobną instancję MariaDB wraz z backupem i procedurą restore;
- manifesty HTTP, schedulera, workera i efemerycznego Redisa;
- dane media oraz procedurę ich eksportu/importu;
- ConfigMapy, mapowanie domen, konfigurację TLS i procedurę DNS;
- sekrety instancji przekazywane bezpiecznym kanałem, poza repozytorium;
- instrukcję uruchomienia, migracji, smoke testu i rollbacku.

Redis w takim pakiecie jest nową, pustą instancją. Nie jest eksportowany ani
odtwarzany jako dane trwałe. Przeniesienie jest dozwolone wyłącznie bez
aktywnego referendum. Wspólne repozytorium obrazu lub wspólny system Flux może
pozostać elementem platformy operatorskiej, ale nie może być wymagany przez
dane ani runtime jednej instancji w sposób uniemożliwiający jej przeniesienie.

## Zasady bezpieczeństwa i integralności

1. Nie migrować, restartować ani przenosić instancji, gdy ma aktywne
   referendum lub bufor głosów wymagający zachowania.
2. Nie zapisywać treści głosu do MariaDB wcześniej niż obecnie.
3. Nie usuwać danych ani PVC przed wykonaniem i sprawdzeniem backupu.
4. Każda instancja musi mieć osobny rollback danych i konfiguracji.
5. Każdy etap musi mieć kryterium GO/NO-GO oraz sprawdzalny rollback.
6. Retry pozostaje dozwolony dla błędów sieciowych, deadlocków MariaDB i
   idempotentnych operacji, ale nie może powodować powtórnego oddania głosu,
   wysłania e-maila ani push notification.
7. Sekrety MariaDB muszą być dostarczane przez środowisko/Secret, nigdy z
   repozytorium ani z logów.
8. Migracja nie zmienia reguł autoryzacji, członkostwa, anonimowości ani
   audytowalnej logiki głosowań.

## Etapy realizacji

### Etap 0 — decyzja infrastrukturalna i inwentaryzacja

- [ ] Wybrać sposób uruchomienia osobnej instancji MariaDB dla każdej instancji
  Wikikracji: osobny host, StatefulSet, operator albo zarządzana usługa.
- [ ] Wybrać wersję MariaDB wspieraną przez używaną wersję Django oraz ustalić
  jednolite ustawienia InnoDB, `utf8mb4`, collation, strefy czasowej i trybu
  ścisłego SQL.
- [ ] Określić wymagania RPO/RTO, retencję backupów i procedurę odtworzenia
  osobnej bazy MariaDB każdej instancji.
- [ ] Potwierdzić, że wspólny serwer/klaster MariaDB dla wielu instancji
  Wikikracji jest poza zakresem docelowej architektury.
- [ ] Zaprojektować jeden oddzielny, efemeryczny Redis na instancję:
  Service, Deployment, limity i politykę restartu; bez PVC, backupu i
  odtwarzania zawartości.
- [ ] Ustalić procedurę przenoszenia/restartu instancji wymagającą braku
  aktywnych referendów.
- [ ] Zmierzyć rozmiar każdej bazy MariaDB i bieżące użycie Redis, liczbę
  tabel, największe struktury oraz czas odczytu/zapisu.
- [ ] Zidentyfikować operacje z efektami zewnętrznymi w transakcjach:
  e-maile, push, Redis, WebSockety i sygnały Django.
- [ ] Zidentyfikować aktywne referenda i ustalić, które muszą pozostać otwarte
  podczas migracji.

**Kryterium wyjścia:** zatwierdzony projekt MariaDB, polityka Redis i
udokumentowane RPO/RTO dla każdej instancji.

### Etap 1 — przygotowanie aplikacji do MariaDB

- [ ] Dodać backend `django.db.backends.mysql` jako jedyny wspierany backend
  produkcyjny, stagingowy i lokalny.
- [ ] Wprowadzić konfigurację przez zmienne środowiskowe, np. host, port,
  nazwa bazy, użytkownik, hasło, SSL i limity połączeń.
- [ ] Skonfigurować `utf8mb4`, uzgodnioną collation, tryb ścisły SQL oraz poziom
  izolacji wspierający oczekiwane zachowanie transakcji Django.
- [ ] Dodać wspierany przez Django sterownik `mysqlclient` do
  `requirements.txt` oraz lock/build verification zgodną z polityką projektu.
- [ ] Usunąć zależność ustawień od `SQLITE_DATABASE_PATH`, `SQLITE_TIMEOUT`
  i produkcyjnych pragm SQLite.
- [ ] Zaktualizować development, testy, Docker Compose i CI tak, aby używały
  tej samej głównej wersji MariaDB; nie utrzymywać równoległej ścieżki SQLite.
- [ ] Sprawdzić wszystkie surowe zapytania SQL, funkcje SQLite, `PRAGMA`, typy
  pól, długości indeksów, constraints, wartości domyślne i zachowanie dat/czasów.
- [ ] Sprawdzić różnice collation i porównań tekstu, w szczególności wielkość
  liter, polskie znaki oraz unikalność identyfikatorów i adresów e-mail.
- [ ] Zastąpić logowanie `wal_size` i retry `database is locked` metrykami oraz
  obsługą deadlocków, timeoutów blokad i zerwanych połączeń MariaDB.

**Kryterium wyjścia:** aplikacja uruchamia testy Django na MariaDB i przechodzi
`check`, migracje oraz testy krytycznych modułów.

### Etap 2 — schemat i migracja danych

- [ ] Utworzyć osobną pustą bazę i konto MariaDB dla każdej testowanej
  instancji, z minimalnymi uprawnieniami ograniczonymi do jej bazy.
- [ ] Utworzyć osobny Redis dla każdej testowanej instancji oraz sprawdzić,
  że aplikacja nie może połączyć się z Redisem innej instancji.
- [ ] Wykonać `manage.py migrate` na pustej bazie MariaDB każdej instancji.
- [ ] Przygotować narzędzie migracji danych SQLite → MariaDB, preferując
  eksport/import kontrolowany przez Django nad ręcznym kopiowaniem pliku.
- [ ] Zachować klucze główne, kolejność zależności, relacje, statusy,
  daty/czasy, załączniki i dane audytowalne.
- [ ] Ustawić wartości `AUTO_INCREMENT` po imporcie i sprawdzić przyszłe inserty.
- [ ] Zweryfikować `utf8mb4`, rich text, duże pola, wartości binarne, pliki media
  i rekordy usunięte logicznie.
- [ ] Sprawdzić, czy wszystkie tabele używają InnoDB oraz czy constraints,
  indeksy unikalne i klucze obce zostały rzeczywiście utworzone.
- [ ] Porównać liczbę i sumy kontrolne rekordów dla każdej aplikacji Django.
- [ ] Wykonać test logowania, profilu, czatu, ankiet, zadań, finansów,
  dokumentów, wydarzeń i głosowań.

**Kryterium wyjścia:** kopia testowa jest funkcjonalnie równoważna z SQLite,
a różnice są opisane i zaakceptowane.

### Etap 3 — testy współbieżności i anonimowości

- [ ] Uruchomić równoległe zapisy HTTP na MariaDB bez sztucznego limitu
  jednego writera.
- [ ] Testować konkurencyjne głosowanie tego samego obywatela i potwierdzić,
  że constraint oraz transakcja tworzą najwyżej jeden fakt oddania głosu.
- [ ] Testować równoczesne głosowania wielu obywateli.
- [ ] Testować `select_for_update()` na MariaDB dla głosowania, ankiet,
  zadań i przetwarzania referendum, w tym zakres blokad przy używanym poziomie
  izolacji, deadlocki i timeouty oczekiwania.
- [ ] Testować restart HTTP, workera i schedulera w cyklu bufora głosów oraz
  potwierdzić, że planowany restart/przeniesienie Redisa jest blokowane, gdy
  bufor aktywnego referendum wymaga zachowania.
- [ ] Potwierdzić, że MariaDB nie zawiera pary pozwalającej skorelować
  obywatela z treścią głosu przed zamknięciem referendum.
- [ ] Potwierdzić atomowe `claim`, shuffle, bulk insert i acknowledge bufora.
- [ ] Przetestować utratę Redis i zachowanie aplikacji zgodnie z wybraną
  polityką odzyskiwania; nigdy nie liczyć częściowego wyniku.

**Kryterium wyjścia:** testy nie wykazują podwójnego głosu, utraty danych,
przedwczesnego ujawnienia wyniku ani ponownego wykonania efektów zewnętrznych.

### Etap 4 — środowisko staging i backup MariaDB

- [ ] Utworzyć staging z taką samą wersją MariaDB, konfiguracją połączeń
  oraz osobnym, efemerycznym Redisem dla każdej instancji.
- [ ] Wprowadzić spójny backup każdej bazy MariaDB (`mariadb-dump` albo
  `mariadb-backup`, zależnie od RPO/RTO), retencję i monitoring świeżości.
  Redis nie jest backupowany.
- [ ] Przetestować restore kompletnej instancji do tej samej wersji MariaDB:
  bazy, kont i uprawnień, mediów, konfiguracji i sekretów oraz uruchomienie
  pustego Redisa.
- [ ] Przetestować przeniesienie jednej instancji do odrębnego namespace/hosta
  bez uruchamiania ani rekonfigurowania pozostałych instancji.
- [ ] Zastąpić dokumentację SQLite backupu dokumentacją MariaDB, ale nadal
  backupować media niezależnie.
- [ ] Zmierzyć czas backupu, restore, migracji i niedostępności aplikacji.
- [ ] Zweryfikować alarmy: brak backupu, nieudany backup, brak miejsca,
  niedostępność MariaDB, zbyt wiele połączeń, deadlocki i wolne zapytania.

**Kryterium wyjścia:** odtworzenie stagingu z backupu jest powtarzalne i mieści
się w zaakceptowanym RTO.

### Etap 5 — migracja pilota jednej instancji

- [ ] Wybrać instancję pilota o niskim ryzyku i uzgodnić okno migracyjne.
- [ ] Wykonać świeży backup SQLite i mediów instancji pilota; Redis nie jest
  backupowany.
- [ ] Utworzyć osobny, efemeryczny Redis dla instancji pilota, bez
  współdzielenia z innymi instancjami.
- [ ] Zatrzymać zapisy aplikacji zgodnie z runbookiem, nie usuwając danych.
- [ ] Potwierdzić brak aktywnych referendów; migracja, restart i przeniesienie
  instancji są niedozwolone, gdy istnieje bufor głosów wymagający zachowania.
- [ ] Utworzyć oddzielną bazę MariaDB dla instancji pilota i wykonać import.
- [ ] Uruchomić `migrate --plan` oraz wymagane migracje na MariaDB.
- [ ] Przełączyć tylko instancję pilota na jej bazę MariaDB i jej Redis.
- [ ] Wykonać smoke test logowania, WebSocketów, czatu, powiadomień,
  głosowania, kodu weryfikacyjnego i schedulera.
- [ ] Przez uzgodniony okres obserwować błędy, opóźnienia, deadlocki, liczbę
  połączeń i zużycie zasobów.

**Kryterium wyjścia:** pilot działa bez regresji, a rollback został przećwiczony
na kopii lub środowisku staging.

### Etap 6 — migracja pozostałych instancji

Dla każdej instancji wykonywać osobny, powtarzalny runbook. Instancja musi
otrzymać własny komplet zasobów, bez współdzielenia bazy MariaDB ani Redisa
z instancją już zmigrowaną:

- [ ] backup i weryfikacja backupu;
- [ ] sprawdzenie stanu referendum i bufora Redis;
- [ ] utworzenie oddzielnej bazy i konta MariaDB z minimalnymi uprawnieniami;
- [ ] utworzenie oddzielnego, efemerycznego Redisa i Service instancji, bez
  PVC;
- [ ] import danych i weryfikacja liczników;
- [ ] zmiana Secret/ConfigMap z backendem MariaDB i adresem Redis instancji;
- [ ] uruchomienie migracyjnego Job-a;
- [ ] uruchomienie HTTP, schedulera i workera;
- [ ] smoke test oraz porównanie liczby użytkowników i kluczowych rekordów;
- [ ] obserwacja logów i metryk przez ustalony okres;
- [ ] oznaczenie instancji jako zakończonej dopiero po osobnej kontroli.

Kolejność musi pozwalać na zatrzymanie procesu po jednej instancji bez blokowania
pozostałych.

### Etap 7 — uproszczenie infrastruktury po migracji

Dopiero po migracji wszystkich instancji i okresie obserwacji:

- [ ] usunąć `SQLITE_DATABASE_PATH`, `SQLITE_TIMEOUT`, konfigurację WAL,
  `busy_timeout` i `PRAGMA` z produkcyjnego kodu;
- [ ] usunąć retry specyficzne dla `database is locked`;
- [ ] usunąć `core/sqlite.py`, `sqlite_maintenance.py` i testy contention,
  jeśli nie są już używane przez wspierane środowisko;
- [ ] zastąpić blokadę plikową schedulera nazwaną blokadą `GET_LOCK()` po
  sprawdzeniu jej zachowania przy utracie połączenia albo pozostawić blokadę
  plikową do czasu osobnej decyzji o schedulerze;
- [ ] usunąć montowanie PVC bazy do HTTP, schedulera i workera;
- [ ] rozważyć `RollingUpdate` i więcej niż jedną replikę HTTP;
- [ ] zachować osobny storage mediów i osobny, efemeryczny Redis dla każdej
  instancji;
- [ ] usunąć wspólny `redis-1` dopiero po migracji i weryfikacji ostatniej
  instancji;
- [ ] zastąpić CronJob backupu SQLite osobnym backupem każdej bazy MariaDB
  oraz mediów; Redis nie jest backupowany;
- [ ] usunąć nieaktualne instrukcje restore SQLite z dokumentacji.

Redisowy bufor głosów, Redis Channels, kolejka powiadomień i ich monitoring
pozostają. Zmienia się tylko model: każdy z tych elementów działa w Redisie
należącym wyłącznie do jednej instancji.

## Strategia rollbacku

Rollback musi być możliwy na dwóch poziomach:

### Rollback przed przełączeniem ruchu

- pozostawić starą instancję SQLite wyłączoną lub gotową do kontrolowanego
  uruchomienia;
- nie usuwać PVC, backupu MariaDB ani konfiguracji osobnego Redisa
  instancji;
- przywrócić poprzednią konfigurację Flux, obraz i endpointy wyłącznie tej
  instancji;
- uruchomić pusty Redis instancji i potwierdzić, że nie ma aktywnego
  referendum wymagającego zachowania bufora;
- nie przełączać ani nie odtwarzać zasobów innych instancji.

### Rollback po rozpoczęciu zapisu do MariaDB

Nie wolno po prostu przełączyć aplikacji z powrotem na SQLite, jeśli MariaDB
przyjął nowe zapisy. Należy wtedy albo:

1. wycofać ruch i odtworzyć MariaDB z właściwego backupu/snapshotu; albo
2. wykonać kontrolowaną migrację przyrostową MariaDB → SQLite.

Drugi wariant jest trudniejszy i nie może być domyślną procedurą awaryjną.
Przed produkcją należy przećwiczyć pierwszy wariant i jasno określić punkt,
do którego rollback jest bezstratny.

## Kryteria zakończenia projektu

Migrację uznajemy za zakończoną dopiero, gdy:

- [ ] uproszczenia SQLite-specyficzne są wdrożone albo mają udokumentowane
  uzasadnienie pozostawienia;
- [ ] wszystkie aktywne instancje używają MariaDB;
- [ ] każda instancja ma własną, oddzielną bazę MariaDB, konto i poświadczenia;
- [ ] każda instancja ma własny, efemeryczny Redis, Service i poświadczenia,
  bez PVC;
- [ ] żadna instancja nie korzysta z bazy MariaDB ani Redisa innej instancji;
- [ ] pojedynczą instancję można wyeksportować i uruchomić w innym miejscu bez
  eksportowania, rekonfigurowania lub zatrzymywania pozostałych, o ile nie ma
  aktywnego referendum wymagającego zachowania bufora Redis;
- [ ] każda instancja ma izolowany backup/restore MariaDB i mediów, a Redis
  może być odtworzony jako pusty;
- [ ] import i restore zostały przetestowane;
- [ ] testy współbieżności przechodzą bez błędów SQLite;
- [ ] głosowania zachowują obecną anonimowość i weryfikowalność;
- [ ] Redisowy bufor głosów pozostaje używany, a operacje na instancji są
  blokowane do czasu zakończenia aktywnych referendów;
- [ ] nie występują podwójne głosy, częściowe wyniki ani przedwczesne kody;
- [ ] backup i restore mediów są niezależnie sprawdzone;
- [ ] monitoring obejmuje MariaDB, Redis, worker, scheduler i backupy;
- [ ] dokumentacja wdrożenia, rollbacku i obsługi awarii jest aktualna;
- [ ] usunięto wyłącznie elementy SQLite, które nie są już używane;
- [ ] APScheduler i worker zostały ocenione osobno, bez mieszania ich z
  migracją silnika bazy.

## Powiązane dokumenty i źródła prawdy

- `docs/PLAN_NIEZAWODNOSC_SQLITE.md` — stan obecny i zabezpieczenia SQLite;
- `docs/dokumentacja/DEPLOYMENT_INSTRUCTIONS.md` — uruchamianie aplikacji i
  aktualna architektura runtime;
- `flux-cluster/docs/PLAN_MIGRACJI_INSTANCJI_WIKIKRACJA.md` — kolejność i
  model warstw Flux per instancja;
- `flux-cluster/docs/BACKUP_STRATEGY.md` — obecna strategia backupu SQLite,
  która wymaga zastąpienia po przełączeniu na MariaDB;
- `glosowania/vote_buffer.py` — implementacja i kontrakt anonimowego bufora
  głosów;
- `zzz/settings_base.py` — obecna konfiguracja backendu bazy.
