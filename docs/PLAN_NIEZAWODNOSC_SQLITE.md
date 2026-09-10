# Plan: niezawodność i wielodostęp do SQLite3

## Cel

Zwiększyć odporność aplikacji Wikikracja na równoczesne odczyty i zapisy przy zachowaniu SQLite3 jako jedynego silnika bazy danych.

Plan nie zakłada migracji na PostgreSQL ani zmian zasad głosowania, anonimowości, kodów jednorazowych lub innych reguł biznesowych.

## Stan początkowy

- Baza jest plikiem `db/db.sqlite3`.
- Django ma `OPTIONS['timeout'] = 60`.
- Przy tworzeniu połączenia ustawiany jest tryb `WAL`.
- Scheduler ma blokadę wątkową `_db_lock`, która działa tylko w obrębie jednego procesu.
- Scheduler ma osobną blokadę plikową ograniczającą liczbę jego instancji.
- Ścieżka oddawania głosu ma retry dla przejściowego `database is locked`.
- Dokumentacja zawiera historyczną instrukcję kopiowania SQLite, ale aktualna procedura używa SQLite Backup API i kontroli integralności.
- `select_for_update()` nie zapewnia na SQLite takiej ochrony przed konkurencją jak na PostgreSQL.

## Zasady realizacji

1. Każdy etap musi mieć osobny cel, test i kryterium wycofania.
2. Nie zmieniać schematu danych bez osobnej analizy i backupu.
3. Nie zwiększać bezkrytycznie timeoutu — długie czekanie może tylko ukryć problem.
4. Nie wykonywać operacji serwisowych na produkcyjnej bazie bez sprawdzonego backupu i planu przywrócenia.
5. Nie używać blokad procesowych jako jedynej ochrony, jeśli aplikacja może działać w wielu procesach.
6. Dla ścieżek głosowania i innych operacji audytowalnych preferować poprawność i jawny błąd nad cichą utratą lub powtórzeniem zapisu.

## Status wdrożenia

Wykonane i pozostawione w kodzie:

- [x] Narzędzie `scripts/sqlite_maintenance.py` do backupu przez SQLite Backup API, kontroli integralności, checkpointu WAL i jawnie włączanego `VACUUM` po backupie.
- [x] Backup używa 60-sekundowego timeoutu oraz kopiuje bazę porcjami z krótkim oczekiwaniem między stronami.
- [x] Narzędzie nie nadpisuje istniejącego backupu bez jawnego usunięcia pliku docelowego.
- [x] `TRUNCATE` checkpoint wymaga jawnego potwierdzenia.
- [x] Dokumentacja operacyjna backupu, restore i checkpointu.
- [x] Udokumentowana strategia timeoutu głosowania: spinner, komunikat, ponowny odczyt statusu i brak automatycznego drugiego POST-a.

Celowo wycofane przed produkcją z powodu ryzyka dla trwających głosowań,
Redis, obecności i schedulera:

- [ ] Wspólne pragmy SQLite poza istniejącym WAL.
- [ ] Wspólny retry aktualizacji obecności.
- [ ] Dodatkowa diagnostyka runtime retry.
- [ ] Zmiana międzyprocesowej blokady schedulera.

Do wykonania osobno, po pomiarach:

- [ ] Audyt wszystkich długich transakcji i efektów zewnętrznych.
- [ ] Test obciążeniowy wielu procesów HTTP, WebSocketów i schedulera.
- [ ] Formalne ograniczenie liczby workerów i opis produkcyjnego modelu uruchomienia.
- [ ] Monitoring liczby blokad, czasu transakcji i rozmiaru WAL.
- [ ] Regularny automatyczny test odtworzenia backupu.

---

## Bramka przed produkcją: GO / NO-GO

Kod i testy są gotowe do przygotowania wdrożenia, ale samo wdrożenie produkcyjne
może otrzymać status **GO** dopiero po potwierdzeniu poniższych warunków na
serwerze produkcyjnym:

- [ ] `SQLITE_DATABASE_PATH` wskazuje bazę w kontenerze, a `SQLITE_BACKUP_DIR` wskazuje trwały, zamontowany volume.
- [ ] `SQLITE_BACKUP_RETENTION_DAYS` jest ustawione zgodnie z polityką backupów.
- [ ] `db/db.sqlite3` znajduje się na lokalnym systemie plików, nie na NFS/SMB.
- [ ] Znana jest liczba procesów HTTP/ASGI zapisujących do pliku.
- [ ] Działa dokładnie jeden scheduler dla tej bazy.
- [ ] Liczba workerów jest zgodna z zaakceptowanym limitem dla SQLite.
- [ ] Backup wykonany przez `scripts/sqlite_maintenance.py backup` został odtworzony na osobnym pliku.
- [ ] Odtworzona kopia przechodzi `integrity-check`, `manage.py check` i smoke test.
- [ ] Sprawdzono wolne miejsce na dysku z zapasem na bazę, WAL, backup i logi.
- [ ] Ustalono sposób monitorowania `database is locked`, rozmiaru WAL i czasu zadań schedulera.
- [ ] Redis oraz bufor głosowań mają osobną procedurę backupu/odtworzenia albo zaakceptowano ich odrębne ryzyko.
- [ ] **DO ZROBIENIA PRZEZ CIEBIE:** na systemie backupowym ustawić proces kopiujący ukończone pliki `.sqlite3` z katalogu backupów na zewnętrzny NAS; pliki tymczasowe `.part` ignorować, jeśli zostaną wprowadzone.
- [ ] Jest procedura zatrzymania aplikacji, schedulera i odtworzenia bazy bez użycia starych plików `-wal`/`-shm`.

Brak któregokolwiek z punktów oznacza **NO-GO operacyjnie**, nawet jeśli testy
aplikacji przechodzą. Testy potwierdzają poprawność kodu, ale nie potwierdzają
konfiguracji konkretnego serwera, systemu plików ani procesu wdrożeniowego.

## Mapa zapisów SQLite według czynności użytkownika

Mapa obejmuje bezpośrednie miejsca zapisu w kodzie aplikacji, z pominięciem testów
i migracji. Generyczne `CreateView`, `UpdateView` i `DeleteView` są wymienione
jawnie, mimo że zapis wykonuje odziedziczona metoda Django. Sygnały i metody modeli
mogą powodować dodatkowe zapisy pośrednie.

### 1. Referenda, wnioski i głosowania

- `glosowania.views.dodaj` — INSERT wniosku/propozycji.
- `glosowania.views.edit` — INSERT wersji oraz UPDATE treści wniosku.
- `glosowania.views.details` — INSERT podpisu autora, DELETE podpisu, UPDATE licznika podpisów.
- `glosowania.views._cast_vote` — INSERT faktu oddania głosu; buforowanie treści głosu odbywa się poza SQLite w Redis.
- `glosowania.views.details` — INSERT/UPDATE/DELETE argumentów pod wnioskiem.
- `glosowania.views.parameters_edit` i `glosowania.views.brand_mark_edit` — UPDATE parametrów lub propozycji znaku.
- `glosowania.management.commands.vote.Command.handle` — przejścia statusów, INSERT kodów głosów, DELETE faktów głosowania po utracie bufora, UPDATE wyników i decyzji powiązanych.
- `glosowania.signals` — usuwanie powiązanego pokoju czatu przy usunięciu decyzji.

### 2. Ankiety

- `ankiety.views._cast_vote` — DELETE poprzednich głosów i INSERT nowych głosów ankiety.
- `ankiety.views.survey_create` — INSERT ankiety i opcji.
- `ankiety.views.survey_edit` — UPDATE ankiety, UPDATE/INSERT/DELETE opcji.
- `ankiety.views.survey_delete` — DELETE ankiety wraz z zależnościami.
- `ankiety.forms.SurveyForm.create_options` — UPDATE kolejności opcji, DELETE usuniętych opcji, `bulk_create` nowych opcji.

### 3. Czat i wiadomości

- `chat.views.add_room`, `chat.views.open_dm` — INSERT pokoi lub reaktywacja/UPDATE pokoju.
- `chat.views.rename_room` — UPDATE nazwy pokoju.
- `chat.views.guest_message` i `chat.services._create_message` — INSERT wiadomości.
- `chat.services.ChatRepository.edit_message_and_history` — INSERT historii edycji i UPDATE wiadomości.
- `chat.services.ChatRepository.save_attachments` / `_save_attachments_sync` — INSERT załączników.
- `chat.services.ChatRepository.remove_attachments` — DELETE załączników.
- `chat.services.ChatRepository.add_vote` / `remove_vote` — INSERT, UPDATE lub DELETE głosu na wiadomość.
- `chat.services.ChatRepository.toggle_reaction` — UPDATE reakcji wiadomości.
- `chat.services.ChatRepository.mark_message_read` / `mark_messages_read_bulk` — INSERT statusów odczytu.
- `chat.feed.mark_message_as_read` / `mark_message_as_unread` — INSERT lub DELETE statusu odczytu.
- `chat.signals` — UPDATE metadanych pokoju, INSERT pokoi systemowych i wiadomości powitalnych, DELETE pokoi prywatnych.
- `chat.management.commands.chat_rooms` — UPDATE/DELETE/INSERT pokoi wykonywane przez scheduler.
- `chat.push_api.register` / `unregister` / `ack` — INSERT/UPDATE/DELETE urządzeń push oraz UPDATE obecności.

### 4. Obecność i aktywność użytkownika

- `core.presence.record_presence` — monotoniczny UPDATE `last_presence_at` i źródła obecności.
- `obywatele.middleware.UpdateLastSeenMiddleware` — okresowy UPDATE `last_login`.
- `core.presence.record_login_presence` — zapis obecności po logowaniu.
- `chat.consumers.ChatConsumer.record_presence` / `presence_heartbeat` — UPDATE obecności wywołany połączeniem WebSocket lub heartbeat.
- Odbiorcy sygnałów aktywności obywatela — INSERT rekordów `CitizenActivity`.

### 5. Konto, onboarding i profil obywatela

- `obywatele.forms.CustomSignupForm.save` — INSERT użytkownika, profilu, adresu e-mail i danych onboardingu.
- `obywatele.views.dodaj` — INSERT kandydata/profilu i powiązanych ocen.
- `obywatele.views.my_profile`, `candidate_edit`, `set_user_language`, `toggle_notification`, `upload_avatar` — UPDATE użytkownika lub profilu.
- `obywatele.views.parameters` i `change_email` / `change_username` — UPDATE ustawień konta i danych logowania.
- `obywatele.views.request_deletion` / `cancel_deletion` — INSERT lub DELETE żądania usunięcia konta.
- `obywatele.views.poczekalnia` — INSERT/UPDATE ocen kandydatów.
- `obywatele.management.commands.count_citizens` — UPDATE reputacji, aktywacji i blokad, DELETE nieaktywnych użytkowników oraz czyszczenie zależności.
- `obywatele.signals` — INSERT aktywności obywateli i aktywności blokady.

### 6. Zadania

- `tasks.views.TaskCreateView.form_valid` — INSERT zadania i początkowego głosu twórcy.
- `tasks.views.TaskEditView` oraz `TaskCloseView.form_valid` — UPDATE zadania.
- `tasks.views.approve_helper`, `remove_helper`, `toggle_helper` — UPDATE relacji zatwierdzonych pomocników.
- `tasks.views.take_task` / `resign_task` — UPDATE przypisania zadania.
- `tasks.views.vote_task` — INSERT/UPDATE/DELETE głosu i czasem UPDATE statusu zadania.
- `tasks.views.reopen_task` — UPDATE statusu.
- `tasks.views.evaluate_task` — INSERT/UPDATE/DELETE oceny wykonania.
- `tasks.views.delete_task` — DELETE zadania.
- `tasks.views.TaskCategoryAPI` / `TaskCategoryEditAPI` — INSERT/UPDATE/DELETE kategorii.
- `tasks.signals` — usuwanie powiązanego pokoju czatu.

### 7. Dokumenty i załączniki

- `board.views.PostFormViewMixin.form_valid` — INSERT lub UPDATE dokumentu oraz INSERT załączników.
- `board.views.delete_post` — DELETE dokumentu.
- `board.views.delete_attachment` — DELETE załącznika.
- `board.models.Post.delete` — dodatkowe usuwanie zależności dokumentu.

### 8. Kalendarz i wydarzenia

- `events.views.EventCreateView` — INSERT wydarzenia.
- `events.views.EventUpdateView` — UPDATE wydarzenia.
- `events.views.EventDeleteView` — DELETE wydarzenia.
- `events.forms.EventForm.save` — normalizacja i zapis wydarzenia.

### 9. Finanse i rozliczenia

- `bookkeeping.views.AssetCreateView` / `AssetUpdateView` / `AssetDeleteView` — INSERT/UPDATE/DELETE aktywów.
- `bookkeeping.views.CategoryCreateView` / `CategoryUpdateView` / `CategoryDeleteView` — INSERT/UPDATE/DELETE kategorii.
- `bookkeeping.views.PartnerCreateView` / `PartnerUpdateView` / `PartnerDeleteView` — INSERT/UPDATE/DELETE partnerów.
- `bookkeeping.views.TransactionCreateView.post` — INSERT transakcji.
- `bookkeeping.views.TransactionUpdateView` — UPDATE transakcji.
- `bookkeeping.views.TransactionDeleteView` — DELETE transakcji.
- `bookkeeping.views.ProtectedDeleteView.post` — kontrola zależności i DELETE obiektu, gdy nie jest używany.

### 10. Administracja i ustawienia grupy

- `home.views.add_quick_link`, `edit_quick_link`, `reorder_quick_links`, `delete_quick_link` — INSERT/UPDATE/DELETE szybkich linków.
- `home.views.change_password` — UPDATE danych uwierzytelniania.
- `site_settings.SiteSettings.get` / `get_or_create` — INSERT ustawień przy pierwszym użyciu.
- `site_settings.params.set_parameter` — UPDATE parametrów grupy.
- `site_settings.params.apply_brand_mark` — UPDATE znaku/brandingu i zapis plików pochodnych.
- `site_settings.params.update_site_from_env` — INSERT lub UPDATE domeny i nazwy witryny.

### 11. Operacje systemowe i powiadomienia

- `home.management.commands.send_email_digest.Command.run` — UPDATE czasu ostatniego digestu.
- `glosowania.management.commands.vote.Command.handle` — opisany wyżej główny ciężki zapis schedulera.
- `obywatele.management.commands.count_citizens.Command` — opisane wyżej masowe UPDATE/DELETE.
- `core.notifications` — zwykle wysyłka zewnętrzna; należy sprawdzić odbiorców sygnałów, które dodatkowo zapisują urządzenia, aktywność lub stan powiadomień.

Ta mapa jest punktem wyjścia do audytu długości transakcji. Najwyższy priorytet
mają: `glosowania.management.commands.vote`, `ankiety.views._cast_vote`,
`tasks.views.vote_task`, zapis obecności, `chat.services._create_message` oraz
masowe komendy schedulera.

## VACUUM po backupie

`VACUUM` nie jest lekarstwem na `database is locked` i nie zwiększa liczby
równoczesnych piszących. Przebudowuje plik bazy, odzyskuje wolne strony i może
zmniejszyć jego rozmiar po dużej liczbie DELETE.

Wykonywać go tylko jako osobną operację serwisową:

1. wykonać i zweryfikować backup przez SQLite Backup API;
2. zatrzymać aplikację, scheduler i inne procesy zapisujące do pliku;
3. upewnić się, że na dysku jest zapas miejsca na dodatkową kopię/plik tymczasowy;
4. wykonać `VACUUM` poza transakcją;
5. uruchomić `quick_check` i `integrity_check`;
6. dopiero potem uruchomić aplikację.

Na aktywnej produkcyjnej bazie `VACUUM` może sam wywołać `database is locked`,
blokować ruch przez długi czas i wymagać znacznie więcej miejsca. Dlatego opcja
`--vacuum-after` jest jawna i powinna być uruchamiana wyłącznie w uzgodnionym
oknie serwisowym o 04:00, gdy zapisy aplikacji i scheduler są zatrzymane lub
zablokowane. Backup jest wykonywany przed `VACUUM`, więc nieudany `VACUUM` nie
usuwa kopii bezpieczeństwa.

## Obsługa timeoutu głosowania: plan UX i backendu

- [ ] Po kliknięciu „Tak” lub „Nie” natychmiast wyłączyć oba przyciski.
- [ ] Pokazać spinner oraz komunikat „Zapisywanie głosu…”, z `aria-busy="true"`.
- [ ] Nie wysyłać automatycznie drugiego POST-a po timeoutcie.
- [ ] Po zakończeniu żądania przywrócić stan formularza, także po powrocie z cache przeglądarki (`pageshow`).
- [ ] Przy końcowym `database is locked` obsłużyć błąd po stronie Django i wykonać redirect do szczegółów referendum zamiast 500.
- [ ] Po błędzie ponownie odczytać, czy `KtoJuzGlosowal` zawiera użytkownika, ponieważ timeout HTTP nie dowodzi, że commit się nie udał.
- [ ] Pokazać komunikat rozróżniający: głos potwierdzony, głos niepotwierdzony albo chwilowa niedostępność.
- [ ] Nie ponawiać automatycznie operacji, która mogła już zapisać fakt głosowania lub wysłać dane do Redis.
- [ ] Dodać testy formularza, komunikatu timeoutu, stanu przycisków i braku podwójnego POST-a.

Spinner ma informować o oczekiwaniu, ale nie może anulować ani dublować zapisu.
Jeżeli frontendowy timeout nastąpi przed odpowiedzią serwera, backend może nadal
kończyć operację; status głosu musi być rozstrzygany przez ponowny odczyt, nie
przez sam fakt zerwania połączenia.

---

## Etap 0 — inwentaryzacja i pomiary

**Ryzyko: bardzo niskie**  
**Wpływ na użytkowników: brak**

### Zadania

- Spisać wszystkie procesy korzystające z bazy:
  - worker HTTP/ASGI;
  - obsługa WebSocketów;
  - scheduler APScheduler;
  - komendy zarządzające;
  - zadania uruchamiane ręcznie i w CI.
- Zidentyfikować wszystkie miejsca obsługi `transaction.atomic()` i zapisu w pętlach.
- Zidentyfikować wszystkie miejsca łapiące `OperationalError` oraz tekst `database is locked`.
- Zmierzyć i zapisać:
  - liczbę błędów blokady na godzinę/dobę;
  - czas trwania najdłuższych transakcji;
  - rozmiar `db.sqlite3`, `db.sqlite3-wal` i `db.sqlite3-shm`;
  - czas trwania zadań schedulera;
  - liczbę równoległych procesów aplikacji.
- Potwierdzić, że baza znajduje się na lokalnym systemie plików, a nie na NFS/SMB lub współdzielonym wolumenie bez gwarancji poprawnych blokad plików.

### Kryterium zakończenia

Powstaje mapa procesów i miejsc zapisu oraz bazowy raport obciążenia. Na tym etapie nie zmieniamy zachowania aplikacji.

---

## Etap 1 — bezpieczny backup i kontrola integralności

**Ryzyko: niskie**  
**Wpływ na użytkowników: brak, poza krótkim obciążeniem odczytem**

### Zadania

- Zastąpić dokumentacyjne `cp db.sqlite3 backup.sqlite3` procedurą wykorzystującą SQLite `.backup` lub API backupu SQLite.
- Nie kopiować pojedynczego pliku `db.sqlite3` bez uwzględnienia aktywnego WAL.
- Po wykonaniu backupu uruchamiać na kopii:

  ```sql
  PRAGMA quick_check;
  PRAGMA integrity_check;
  ```

- Ustalić retencję backupów i miejsce przechowywania poza katalogiem aplikacji.
- Przetestować odtworzenie backupu do tymczasowego pliku i uruchomienie na nim `manage.py check` oraz odczytu podstawowych danych.
- Udokumentować procedurę awaryjnego zatrzymania schedulerów przed operacją przywracania.

### Kryterium zakończenia

Można odtworzyć działającą kopię bazy bez ręcznego kopiowania plików WAL. Backup i restore są sprawdzane automatycznie lub według powtarzalnej procedury.

### Rollback

Brak zmian w działającej bazie. Wycofanie dotyczy wyłącznie skryptu/procedury backupowej.

---

## Etap 2 — jawna i testowalna konfiguracja SQLite

**Ryzyko: niskie**  
**Wpływ na użytkowników: możliwa zmiana wydajności, bez zmiany modelu danych**

### Zadania

- Wydzielić konfigurację SQLite w czytelne stałe zamiast pojedynczego długiego literału `DATABASES`.
- Zachować `timeout=60`, a jego wartość uczynić konfigurowalną przez środowisko z bezpiecznym limitem.
- Przy tworzeniu połączenia ustawiać i logować tylko bezpieczne pragmy:
  - `journal_mode=WAL`;
  - `foreign_keys=ON`;
  - `busy_timeout` zgodny z timeoutem Django.
- Rozważyć `synchronous=NORMAL` dopiero po pomiarze i po akceptacji kompromisu trwałości. Nie ustawiać `synchronous=OFF`.
- Zapewnić, że handler `connection_created` nie rejestruje się wielokrotnie przy wielokrotnym ładowaniu aplikacji.
- Dodać test sprawdzający konfigurację nowego połączenia SQLite.

### Kryterium zakończenia

Każde nowe połączenie ma przewidywalne ustawienia, a ich działanie jest sprawdzone testem. Brak pogorszenia integralności w testach migracji i testach głosowań.

### Rollback

Wycofanie zmian w konfiguracji połączenia i restart procesów aplikacji.

---

## Etap 3 — obserwowalność blokad i WAL

**Ryzyko: niskie**  
**Wpływ na użytkowników: brak lub minimalny narzut logowania**

### Zadania

- Wprowadzić jeden wspólny mechanizm rozpoznawania i logowania blokady SQLite.
- Logować metadane bez danych wrażliwych:
  - operację/moduł;
  - nazwę procesu;
  - numer próby retry;
  - czas oczekiwania;
  - czas transakcji;
  - rozmiar plików WAL.
- Nie logować kodów głosowania, treści anonimowych głosów, tokenów ani sekretów.
- Dodać metrykę lub licznik dla końcowych błędów `database is locked`.
- Monitorować wzrost `db.sqlite3-wal` i ustalić bezpieczny próg alarmowy.
- Przygotować kontrolowaną procedurę checkpointu WAL:

  ```sql
  PRAGMA wal_checkpoint(PASSIVE);
  ```

  `TRUNCATE` wykonywać tylko w procedurze serwisowej, po sprawdzeniu aktywnych połączeń.

### Kryterium zakończenia

Da się wskazać, który proces i która operacja powoduje blokadę, bez analizowania niepełnych logów HTTP.

### Rollback

Wyłączenie dodatkowego logowania/metryk bez zmian w danych.

---

## Etap 4 — wspólne, ograniczone retry dla przejściowych blokad

**Ryzyko: niskie do średniego**  
**Wpływ na użytkowników: krótsze oczekiwanie zamiast błędu 500, możliwe powtórzenie operacji**

### Zadania

- Zdefiniować wspólną politykę retry tylko dla błędu `database is locked`:
  - mała liczba prób;
  - krótki, rosnący backoff;
  - maksymalny czas całkowity;
  - ponowienie całej transakcji, nie pojedynczego zapytania.
- Nie ponawiać automatycznie błędów integralności, walidacji, braku rekordu ani innych `OperationalError` niezwiązanych z blokadą.
- Nie obejmować retry operacji z nieodwracalnym efektem zewnętrznym bez idempotencji, np. wysyłki push lub wiadomości do Redis.
- Dla głosowania zachować dotychczasową atomowość i testować, że retry nie tworzy drugiego znacznika głosu ani drugiego wpisu w buforze.
- Dodać testy dla:
  - blokady przy pierwszej próbie i sukcesu przy drugiej;
  - wyczerpania prób i kontrolowanego błędu;
  - braku retry dla innego `OperationalError`;
  - braku podwójnych efektów ubocznych.

### Kryterium zakończenia

Każda objęta retry operacja ma test idempotencji lub jawnie pozostaje poza wspólnym retry. Nie ma nieskończonego czekania ani ukrywania trwałej awarii.

### Rollback

Wyłączenie retry w danym miejscu lub przywrócenie poprzedniej implementacji bez zmian schematu.

---

## Etap 5 — skrócenie i uporządkowanie transakcji

**Ryzyko: średnie**  
**Wpływ na użytkowników: możliwe zmiany kolejności zapisu i obsługi błędów**

### Zadania

- Przejrzeć wszystkie długie transakcje i usunąć z ich wnętrza:
  - ciężkie obliczenia Python;
  - renderowanie;
  - zewnętrzne wywołania HTTP;
  - Redis, FCM, e-mail i WebSocket;
  - niepotrzebne odczyty listowe.
- Ograniczyć transakcje do minimalnego odczytu warunku i zapisu danych.
- Przenieść efekty zewnętrzne poza transakcję tylko tam, gdzie można zagwarantować spójność przez idempotencję, outbox lub bezpieczny retry.
- Nie traktować `select_for_update()` jako pełnego mechanizmu blokowania na SQLite.
- Dla operacji konkurencyjnych oprzeć poprawność na unikalnych ograniczeniach i obsłudze konfliktu, a nie wyłącznie na schemacie „sprawdź, potem zapisz”.
- Szczególnie ostrożnie przeanalizować głosowania, ponieważ zapis znacznika uczestnictwa i anonimowego kodu ma wymagania audytowe.

### Kryterium zakończenia

Każda zmieniona transakcja ma test scenariusza konkurencyjnego, test rollbacku i test efektu zewnętrznego. Nie zmieniają się zasady biznesowe.

### Rollback

Etap wdrażać małymi zmianami per moduł. Cofnięcie powinno dotyczyć pojedynczego modułu, nie całej warstwy transakcyjnej.

---

## Etap 6 — serializacja zapisów procesów wewnętrznych

**Ryzyko: średnie do wysokiego**  
**Wpływ na użytkowników: możliwe opóźnienia zadań i zmiana harmonogramów**

### Zadania

- Rozdzielić blokadę schedulera od blokady bazy i jasno opisać ich zakres.
- Zapewnić, że zadania schedulera zapisujące dużo danych nie wykonują się równolegle w obrębie procesu ani między procesami.
- Jeśli potrzebna jest blokada międzyprocesowa, użyć mechanizmu plikowego z poprawnym zachowaniem na systemie docelowym i timeoutem, zamiast `threading.Lock` jako jedynej ochrony.
- Nie uruchamiać wielu niezależnych schedulerów wskazujących na ten sam plik bazy.
- Rozważyć kolejkę pojedynczego writer’a dla ciężkich zadań, ale dopiero po pomiarze, aby nie stworzyć nowej warstwy bez potrzeby.
- Ustalić, które zapisy użytkowników mogą działać równolegle z zadaniami tła, a które wymagają odłożenia.

### Kryterium zakończenia

W testowym uruchomieniu wieloprocesowym nie występują równoległe instancje ciężkich zadań tła, a opóźnienie HTTP pozostaje w zaakceptowanym limicie.

### Rollback

Możliwość wyłączenia nowych blokad przez konfigurację oraz powrót do poprzedniego harmonogramu bez usuwania danych.

---

## Etap 7 — ograniczenie modelu uruchomieniowego SQLite

**Ryzyko: wysokie**  
**Wpływ na dostępność usługi i wydajność**

### Zadania

- Ustalić oficjalny produkcyjny model uruchomienia:
  - jeden plik bazy na lokalnym dysku;
  - brak współdzielenia pliku przez wiele hostów;
  - kontrolowana liczba procesów zapisujących;
  - jeden aktywny scheduler;
  - jawna procedura restartu i backupu.
- Ograniczyć liczbę workerów, jeśli pomiary pokażą, że konkurencja zapisów jest główną przyczyną blokad.
- Nie uruchamiać aplikacji z konfiguracją, w której wiele kontenerów zapisuje do tego samego pliku SQLite przez współdzielony wolumen.
- Zweryfikować zachowanie po restarcie w trakcie aktywnego WAL i po nieoczekiwanym zakończeniu procesu.
- Wykonać test obciążeniowy obejmujący jednocześnie HTTP, WebSockety, obecność, scheduler i głosowania.

### Kryterium zakończenia

Model uruchomieniowy jest zapisany w dokumentacji, przetestowany na środowisku zbliżonym do produkcji i ma określone limity obciążenia.

### Rollback

Powrót do poprzedniej liczby workerów i poprzedniego harmonogramu. Jeśli baza jest podejrzana po awarii, najpierw wykonać kontrolę integralności i przywrócić ostatni poprawny backup.

---

## Etap 8 — procedury awaryjne i testy odtworzeniowe

**Ryzyko: wysokie operacyjnie**  
**Wpływ na dostępność podczas ćwiczeń lub awarii**

### Zadania

- Przygotować runbook dla:
  - rosnącego WAL;
  - utrzymującej się blokady;
  - błędu `database disk image is malformed`;
  - braku miejsca na dysku;
  - przerwanego checkpointu;
  - odtworzenia backupu.
- Regularnie wykonywać test odtworzenia na osobnym pliku/kopii.
- Sprawdzać integralność przed i po operacjach serwisowych.
- Ustalić, kiedy zatrzymać aplikację zamiast ryzykować kolejne zapisy.
- Dokumentować maksymalną akceptowalną utratę danych oraz czas odtworzenia.
- Wykonać kontrolowany test awarii procesu w środowisku testowym, nigdy przez celowe uszkadzanie produkcyjnego pliku.

### Kryterium zakończenia

Inna osoba niż autor procedury może odtworzyć działającą bazę i uruchomić aplikację według runbooka.

### Rollback

Procedury awaryjne nie zmieniają kodu produkcyjnego. Każda operacja na produkcji wymaga potwierdzenia i sprawdzonego backupu.

---

## Kolejność wdrażania

1. Inwentaryzacja i pomiary.
2. Bezpieczny backup oraz kontrola integralności.
3. Jawna konfiguracja SQLite.
4. Obserwowalność blokad i WAL.
5. Wspólne, ograniczone retry.
6. Skrócenie transakcji.
7. Serializacja zapisów zadań wewnętrznych.
8. Ograniczenie modelu uruchomieniowego.
9. Procedury awaryjne i regularne testy odtworzeniowe.

Nie należy rozpoczynać etapów 5–8 bez wykonania etapu 1 i 2. Bez pomiarów oraz sprawdzonego backupu trudno odróżnić poprawę od maskowania problemu i nie ma bezpiecznego sposobu wycofania awarii.

## Kryteria sukcesu całego planu

- Baza pozostaje SQLite3 i działa na lokalnym, wspieranym systemie plików.
- Brak niekontrolowanych błędów `database is locked` w scenariuszu obciążenia referencyjnego.
- Retry nie powoduje podwójnych zapisów, podwójnych głosów ani podwójnych efektów zewnętrznych.
- Backup aktywnej bazy można odtworzyć i przejść nim podstawowe kontrole Django.
- Rozmiar WAL, blokady i czas transakcji są obserwowalne.
- Scheduler nie uruchamia konkurencyjnych ciężkich zadań zapisujących.
- Każda zmiana wpływająca na głosowania ma test regresyjny i osobną akceptację przed wdrożeniem.
