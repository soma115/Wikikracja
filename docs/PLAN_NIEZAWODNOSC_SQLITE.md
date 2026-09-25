# Plan: niezawodność i wielodostęp do SQLite3

## Cel

Zwiększyć odporność aplikacji Wikikracja na równoczesne odczyty i zapisy przy zachowaniu SQLite3 jako jedynego silnika bazy danych.

Plan nie zakłada migracji na MariaDB ani zmian zasad głosowania, anonimowości, kodów jednorazowych lub innych reguł biznesowych.

Plan docelowej migracji do MariaDB znajduje się w `docs/PLAN_MIGRACJI_MARIADB.md`.
Ten dokument opisuje stan SQLite, który należy utrzymać do czasu zakończenia
migracji oraz wykorzystać jako źródło wymagań dla rollbacku.

## Stan początkowy

- Baza jest plikiem `db/db.sqlite3`.
- Django ma `OPTIONS['timeout'] = 60`.
- Przy tworzeniu połączenia ustawiany jest tryb `WAL`.
- Scheduler ma blokadę wątkową `_db_lock`, która działa tylko w obrębie jednego procesu.
- Scheduler ma osobną blokadę plikową ograniczającą liczbę jego instancji.
- Ścieżka oddawania głosu ma retry dla przejściowego `database is locked`.
- Dokumentacja zawiera historyczną instrukcję kopiowania SQLite, ale aktualna procedura używa SQLite Backup API i kontroli integralności.
- `select_for_update()` nie zapewnia na SQLite takiej ochrony przed konkurencją jak na MariaDB z InnoDB.

## Zasady realizacji

1. Każdy etap musi mieć osobny cel, test i kryterium wycofania.
2. Nie zmieniać schematu danych bez osobnej analizy i backupu.
3. Nie zwiększać bezkrytycznie timeoutu — długie czekanie może tylko ukryć problem.
4. Nie wykonywać operacji serwisowych na produkcyjnej bazie bez sprawdzonego backupu i planu przywrócenia.
5. Nie używać blokad procesowych jako jedynej ochrony, jeśli aplikacja może działać w wielu procesach.
6. Dla ścieżek głosowania i innych operacji audytowalnych preferować poprawność i jawny błąd nad cichą utratą lub powtórzeniem zapisu.

## Aktualny zakres realizacji

Podstawowa ochrona ścieżki oddawania głosu oraz rozdzielenie procesów
produkcyjnych są zaimplementowane. Plan pozostaje otwarty wyłącznie dla prac
pomiarowych, audytowych i operacyjnych — nie oznacza to, że bieżący klaster
należy skalować ponad przyjęty model jednego writera SQLite na instancję.

- [x] Retry dla przejściowego `database is locked` w głosowaniu.
- [x] Wycofanie transakcji po nieudanym zapisie.
- [x] Redirect zamiast błędu 500 po końcowej blokadzie SQLite.
- [x] Ponowny odczyt, czy głos został zapisany.
- [x] Komunikat dla użytkownika o konieczności ponowienia próby.
- [x] Spinner i blokada podwójnego wysłania formularza.
- [x] Przywracanie stanu spinnera po powrocie strony z cache (`pageshow`).
- [x] HTTP, migracje, scheduler i worker powiadomień są osobnymi procesami
      Kubernetes.
- [x] Każda aktywna instancja ma własny PVC SQLite i po jednej replice HTTP,
      schedulera oraz workera.

## Status wdrożenia

Wykonane i pozostawione w kodzie:

- [x] Narzędzie `scripts/sqlite_maintenance.py` do backupu przez SQLite Backup API, kontroli integralności, checkpointu WAL i jawnie włączanego `VACUUM` po backupie.
- [x] Backup używa 60-sekundowego timeoutu oraz kopiuje bazę porcjami z krótkim oczekiwaniem między stronami.
- [x] Narzędzie nie nadpisuje istniejącego backupu bez jawnego usunięcia pliku docelowego.
- [x] `TRUNCATE` checkpoint wymaga jawnego potwierdzenia.
- [x] Dokumentacja operacyjna backupu, kontroli integralności i checkpointu.
- [x] Udokumentowana strategia timeoutu głosowania: spinner, komunikat, ponowny odczyt statusu i brak automatycznego drugiego POST-a.
- [x] Skrypt `scripts/sqlite_contention_test.py` do bezpiecznego testu na tymczasowej bazie/kopii, z writerami, backupem i opcjonalnym `VACUUM`.
- [x] Skrypt raportuje liczbę blokad, czas testu, przepustowość, czas backupu oraz szczytowy i końcowy rozmiar WAL/SHM.
- [x] Wspólne pragmy SQLite: WAL, `foreign_keys=ON` i `busy_timeout` zgodny z timeoutem.
- [x] Wspólny, ograniczony retry aktualizacji obecności.
- [x] Dodatkowa diagnostyka runtime retry bez danych wrażliwych.
- [x] Międzyprocesowa blokada schedulera z obsługą Linux i Windows.

Do wykonania osobno, po pomiarach i z weryfikacją na klastrze:

- [ ] Audyt wszystkich długich transakcji i efektów zewnętrznych.
- [ ] Test obciążeniowy HTTP, WebSocketów, schedulera, workera, Redis i backupu na docelowym storage.
- [ ] Formalne potwierdzenie limitu procesów zapisujących do SQLite po każdym typie restartu i rollout’u.
- [ ] Niezależna metryka końcowych blokad, czasu transakcji i rozmiaru WAL oraz progi alertów.

## Status etapów planu

- [x] Etap 0 — inwentaryzacja miejsc zapisu i mapa `INSERT`/`UPDATE`/`DELETE`.
- [x] Etap 1 — narzędzie backupu przez SQLite Backup API i kontrola integralności.
- [x] Etap 2a — konfiguracja ścieżki bazy i katalogu backupów przez zmienne `SQLITE_*`.
- [x] Etap 2b — jawny timeout backupu 60 sekund i kopiowanie porcjami.
- [x] Etap 2c — kontrolowany `VACUUM` po backupie przez `--vacuum-after`.
- [ ] Etap 3 — pełny monitoring blokad, czasu transakcji i rozmiaru WAL.
- [x] Etap 4a — retry głosowania 3/6/12 sekund.
- [x] Etap 4c — spinner, blokada podwójnego POST-a i bezpieczny redirect po końcowym locku głosowania.
- [ ] Etap 4b — globalna polityka retry dla innych operacji bez efektów ubocznych.
- [ ] Etap 5 — audyt i skrócenie wszystkich długich transakcji.
- [x] Etap 6 — międzyprocesowa serializacja zadań schedulera.
- [ ] Etap 7 — test obciążeniowy i formalny model liczby workerów.
- [ ] Etap 8 — procedury awaryjne oraz produkcyjny monitoring.

## Wyniki testów obciążeniowych SQLite

- [x] Test 4 writerów × 250 operacji, timeout 0,1 s, backup online: 1000 udanych zapisów, 0 blokad, backup i integralność poprawne; szczytowy WAL 1,07 MB, SHM 32 KB.
- [x] Test 8 writerów × 1000 operacji, timeout 0,1 s, backup online: 8000 udanych zapisów, 0 blokad, backup i integralność poprawne.
- [x] Test 16 writerów × 5000 operacji, timeout 0,1 s, backup online: 74882 udane zapisy, 5118 blokad, 0 innych błędów, backup i integralność poprawne.
- [x] Test 16 writerów × 5000 operacji, timeout 1,0 s, backup online: 79312 udanych zapisów, 688 blokad, 0 innych błędów, backup i integralność poprawne; czas testu 127,43 s.
- [x] Test z równoległym `VACUUM`: `VACUUM` otrzymał `database is locked`, co potwierdza konieczność okna serwisowego.
- [x] Test docelowego PVC na `k8s` — 4 writerów × 250 operacji: 999 udanych zapisów, 1 `database_locked`, 0 innych błędów; kopia testowa przeszła `quick_check` i `integrity_check`.
- [x] Dla pilota `instance-1` po restarcie HTTP zachowano `journal_mode=WAL`, a `quick_check` i `integrity_check` aktywnej bazy przeszły.
- [x] Dla pilota `instance-1` osobne restarty schedulera i workera zakończyły się uruchomieniem podów `1/1`, zachowaniem integralności SQLite i bez błędów w logach.
- [x] Ręczny smoke test pilota po restartach: logowanie, powiadomienia i podstrony aplikacji działały poprawnie.

Powyższe wyniki są wynikami testów pilota, a nie bieżącym odczytem stanu każdego poda. Aktualna deklaracja klastra obejmuje instancje `1`, `2`, `3` i `5–14`.

Wyniki są zależne od obciążenia i systemu, dlatego nie są jeszcze podstawą
do zmiany timeoutu produkcyjnego ani do globalnego retry. Służą jako baseline
do kolejnych pomiarów.

---

## Bramka przed produkcją: GO / NO-GO

Kod, manifesty i częściowa weryfikacja live są gotowe, ale status **GO** dla
bieżącego klastra nadal wymaga domknięcia kontroli operacyjnych. Poniższy stan
live pochodzi ze zrzutu przekazanego 2026-09-15; nie jest automatycznie aktualny
po kolejnych rolloutach.

**Potwierdzone w repozytorium i zrzucie live:**

- [x] `SQLITE_DATABASE_PATH` wskazuje `/app/db/db.sqlite3` w PVC każdej instancji.
- [x] Migracje są osobnymi Jobami, a HTTP, scheduler i worker są rozdzielone.
- [x] Wszystkie aktywne instancje mają gotowy HTTP, scheduler i worker; każdy
      Deployment ma jedną dostępną replikę.
- [x] Wszystkie migration Joby są `Complete`; Job instance-1 nazywa się
      `wikikracja-instance-1-migrate`, a pozostałe używają wariantu
      `wikikracja-instance-N-migrate-new`.
- [x] Wszystkie PVC są `Bound`, mają `1Gi`, `RWO` i StorageClass
      `microk8s-hostpath`.
- [x] Redis `redis-1` działa `1/1` na `k8s`.
- [x] Flux Kustomizations są `Ready=True`; aplikacyjne warstwy używają rewizji
      `main@sha1:48dc738c`.
- [x] Wszystkie wyświetlone workloady Wikikracji używają obrazu
      `ghcr.io/soma115/wikikracja:main-20260915113429`.
- [x] W zrzucie widoczny jest zakończony Job `backup-to-nas`.

**Warunki GO nadal wymagające potwierdzenia:**

- [ ] Potwierdzić, że nie ma drugiego writera podczas rollout’u, restartu i
      odtwarzania oraz wykonać test blokad SQLite na aktywnym storage.
- [ ] Potwierdzić typ i semantykę filesystemu pod `microk8s-hostpath`, w tym
      zachowanie blokad `flock`/`fcntl` oraz WAL/SHM.
- [ ] Potwierdzić transfer ostatniego backupu na NAS, jego integralność i retencję;
      status `Completed` Joba nie jest dowodem poprawnego transferu.
- [ ] Sprawdzić wolne miejsce na bazę, WAL, media, staging backupu i logi.
- [ ] Potwierdzić monitoring blokad SQLite, WAL, schedulerów, Redis i backupów.
- [ ] Wykonać smoke test logowania, czatu, głosowania i schedulera po restartach.

Brak któregokolwiek warunku live oznacza **NO-GO operacyjnie**, nawet jeśli testy
aplikacji, render manifestów i status Flux przechodzą.

## Zadania wdrożeniowe na klastrze Kubernetes

Kubernetes może uruchamiać Wikikrację z SQLite tylko w modelu jednego kontrolowanego
writer’a. Nie wolno skalować aplikacji do wielu podów zapisujących do tego samego
pliku SQLite ani montować bazy przez NFS/SMB lub storage bez gwarancji poprawnych
blokad plikowych.

### Aktualna konfiguracja klastra

- Namespace: `wikikracja`.
- Aktywne instancje: `1`, `2`, `3` i `5–14`; instancja `4` nie jest wdrożona.
- Obraz: `ghcr.io/soma115/wikikracja`, sortowalny tag `main-<timestamp>`
  zarządzany przez Flux Image Automation.
- Każda instancja ma własny PVC `wikikracja-instance-N-data`, żądanie `1Gi`
  i `ReadWriteOnce`; deklarowane zasoby HTTP to request `100m` CPU / `128Mi`
  RAM oraz limit `2000m` CPU / `512Mi` RAM.
- Każda instancja ma dokładnie po jednej replice HTTP, schedulera i workera
  powiadomień. Wszystkie te pody są przypinane do węzła `k8s`.
- Wspólny Redis to Deployment `redis-1` (`redis:7-alpine`), jedna replika,
  `emptyDir`, również na `k8s`. Instancje używają osobnych logicznych baz Redis
  `1`, `2`, `3` i `5–14`.
- HTTP używa Traefik `IngressRoute`, przekierowania HTTP → HTTPS i resolvera
  `letsencrypt`. Domeny i aliasy wynikają z ConfigMap oraz manifestów
  `wikikracja-instance-N.yaml`; nie należy kopiować historycznej domeny
  `w1.wikikracja.pl`.
- Migracje są osobnymi Jobami i są zależnością odpowiedniego runtime Flux;
  instance-1 używa Joba `wikikracja-instance-1-migrate`, a instancje 2, 3 i 5–14
  używają nazw `wikikracja-instance-N-migrate-new`.
- Backup wszystkich aktywnych PVC wykonuje `backup-to-nas` codziennie o `04:10`
  UTC, z retencją `180` dni, na `robert@nas:44999:/volume1/NetBackup/wiki`.
- Zrzut live potwierdza, że wszystkie PVC są `Bound`, mają `1Gi`, `RWO` i
  StorageClass `microk8s-hostpath`; wszystkie obserwowane pody Wikikracji i Redis
  działają na `k8s`.
- Zrzut live potwierdza status `Ready` warstw Flux, gotowość Deploymentów oraz
  ukończenie migracji dla wszystkich aktywnych instancji.

StorageClass i binding PVC są potwierdzone z klastra, ale sam zrzut `get pvc` nie
potwierdza typu filesystemu, poprawności blokad SQLite ani integralności backupu.
`emptyDir` Redis jest buforem/cache i nie jest backupowany jako trwała baza
aplikacji.

Źródła manifestów:

- `clusters/apps/kustomization.yaml`
- `clusters/apps/wikikracja-base/`
- `clusters/apps/wikikracja-shared/backup-to-nas-cronjob.yaml`
- `clusters/apps/wikikracja-migrations-1/` for instance-1 and
  `clusters/apps/wikikracja-migrations-N/` for instances 2, 3 and 5–14
- `clusters/apps/wikikracja-instance-N/` for each active instance
- `clusters/infrastructure/image-automation.yaml`

The paths above are relative to the `flux-cluster` repository.

Przed uznaniem wdrożenia Kubernetes za gotowe należy rozdzielić stan
manifestów od stanu live.

**Potwierdzone w manifestach:**

- [x] Jest osobny layer base z namespace, wspólną konfiguracją, Redis i PVC.
- [x] Jest osobny layer shared z middleware i backupem NAS.
- [x] Każda aktywna instancja ma osobny Job migracji oraz osobną warstwę runtime.
- [x] HTTP ma `replicas: 1` i `strategy: Recreate`, a scheduler i worker mają po
      jednej replice i również `strategy: Recreate`.
- [x] HTTP ma wyłączony scheduler; scheduler jest uruchamiany wyłącznie przez
      `python manage.py run_scheduler` z `SCHEDULER_ENABLED=true`.
- [x] Worker jest uruchamiany wyłącznie przez
      `python manage.py run_chat_notifications_worker`.
- [x] Wszystkie komponenty instancji montują jej własny PVC pod `/app/db`;
      HTTP i procesy pomocnicze korzystają z tej samej bazy instancji.
- [x] `SQLITE_DATABASE_PATH` wskazuje `/app/db/db.sqlite3`.
- [x] Redis jest osobnym Service `redis-1`, a konfiguracja używa osobnych baz
      logicznych i prefiksów kanałów.
- [x] Są endpointy `/healthz/live/` i `/healthz/ready/`, przy czym readiness
      sprawdza SQLite oraz cache/Redis.
- [x] CronJob `backup-to-nas` działa o `04:10` UTC, ma `concurrencyPolicy: Forbid`
      i obejmuje PVC aktywnych instancji w trybie tylko do odczytu.

**Do potwierdzenia na klastrze:**

- [x] Status Flux Kustomizations, Deploymentów i Jobów migracji — zrzut z
      2026-09-15 pokazuje `Ready=True`, gotowe Deploymenty i Joby `Complete`.
- [x] Gotowość osobno HTTP, schedulera i workera dla każdej instancji — każdy
      Deployment ma `1/1` dostępnych replik.
- [x] Status i storageClass/binding PVC — wszystkie są `Bound`, `1Gi`, `RWO`,
      `microk8s-hostpath`.
- [ ] Typ i semantyka filesystemu dla SQLite/WAL/SHM oraz poprawność blokad.
- [ ] Brak drugiego writera podczas rollout’u, restartu i odtwarzania.
- [ ] Test równoległego zapisu SQLite na docelowym storage po restarcie i
      ponownym zamontowaniu PVC.
- [ ] Smoke test głosowania po restarcie schedulera i workera.
- [ ] Ostatni backup NAS, jego integralność, transfer i retencja.
- [ ] Monitoring blokad SQLite, WAL, restartów, schedulera, Redis i backupu.
- [ ] Sposób ochrony przed zwiększeniem replik ponad jednego writera (w tym
      ewentualny `PodDisruptionBudget` i procedura restartu).

### Kryterium zakończenia wdrożenia Kubernetes

Wdrożenie przechodzi test obciążeniowy i restartowy bez równoległych writerów
SQLite, bez konkurencyjnych schedulerów oraz bez niekontrolowanej utraty lub
podwójnego zapisu głosu. Konfiguracja storage, replik, schedulera, Redis,
backupów i monitoringu jest zapisana w manifestach oraz runbooku operatorskim.

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

- [x] Po kliknięciu „Tak” lub „Nie” natychmiast wyłączyć oba przyciski.
- [x] Pokazać spinner oraz komunikat „Zapisywanie głosu…”, z `aria-busy="true"`.
- [x] Nie wysyłać automatycznie drugiego POST-a po timeoutcie.
- [ ] Po zakończeniu żądania przywrócić stan formularza, także po powrocie z cache przeglądarki (`pageshow`).
- [x] Przy końcowym `database is locked` obsłużyć błąd po stronie Django i wykonać redirect do szczegółów referendum zamiast 500.
- [x] Po błędzie ponownie odczytać, czy `KtoJuzGlosowal` zawiera użytkownika, ponieważ timeout HTTP nie dowodzi, że commit się nie udał.
- [x] Pokazać komunikat rozróżniający: głos potwierdzony, głos niepotwierdzony albo chwilowa niedostępność.
- [x] Nie ponawiać automatycznie operacji, która mogła już zapisać fakt głosowania lub wysłać dane do Redis.
- [x] Dodać testy backendu i formularza dla komunikatu timeoutu, stanu przycisków i braku podwójnego POST-a.

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

### Kryterium zakończenia

Backup i kontrola integralności są wykonywane według powtarzalnej procedury.

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

## Etap 8 — procedury awaryjne i monitoring produkcyjny

**Ryzyko: wysokie operacyjnie**  
**Wpływ na dostępność podczas ćwiczeń lub awarii**

### Zadania

- Przygotować runbook dla:
  - rosnącego WAL;
  - utrzymującej się blokady;
  - błędu `database disk image is malformed`;
  - braku miejsca na dysku;
  - przerwanego checkpointu;
- Sprawdzać integralność przed i po operacjach serwisowych.
- Ustalić, kiedy zatrzymać aplikację zamiast ryzykować kolejne zapisy.
- Wykonać kontrolowany test awarii procesu w środowisku testowym, nigdy przez celowe uszkadzanie produkcyjnego pliku.

### Kryterium zakończenia

Inna osoba niż autor procedury może wykonać opisane czynności awaryjne według runbooka.

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
9. Procedury awaryjne i monitoring produkcyjny.

Nie należy rozpoczynać etapów 5–8 bez wykonania etapu 1 i 2. Bez pomiarów oraz sprawdzonego backupu trudno odróżnić poprawę od maskowania problemu i nie ma bezpiecznego sposobu wycofania awarii.

## Kryteria sukcesu całego planu

- Baza pozostaje SQLite3 i działa na lokalnym, wspieranym systemie plików.
- Brak niekontrolowanych błędów `database is locked` w scenariuszu obciążenia referencyjnego.
- Retry nie powoduje podwójnych zapisów, podwójnych głosów ani podwójnych efektów zewnętrznych.
- Backup aktywnej bazy jest wykonywany przez SQLite Backup API i przechodzi kontrolę integralności.
- Rozmiar WAL, blokady i czas transakcji są obserwowalne.
- Scheduler nie uruchamia konkurencyjnych ciężkich zadań zapisujących.
- Każda zmiana wpływająca na głosowania ma test regresyjny i osobną akceptację przed wdrożeniem.

---

# Aktualny status i następne kroki — kanoniczna sekcja operacyjna

Ta sekcja jest podsumowaniem ostatnich zapisanych wyników planu. W razie
rozbieżności z wcześniejszymi, historycznymi checkboxami powyżej obowiązuje ta
sekcja, ale checkboxy dotyczące stanu live nie zastępują bieżącej weryfikacji na
klastrze. Aktualny stan live należy potwierdzić procedurą GO/NO-GO powyżej.

## P0 — spójność SQLite–Redis w głosowaniu

**Status: `[x]` zaimplementowane i przetestowane lokalnie.**

- [x] Redisowy bufor używa idempotencyjnego `operation_id`.
- [x] Ponowienie transakcji nie dodaje drugiego głosu do Redis.
- [x] Bufor jest przenoszony atomowo do claimu przez Lua i usuwany dopiero po potwierdzeniu wyniku SQLite.
- [x] Obsługiwany jest stary format listy Redis podczas migracji kluczy.
- [x] Nieudany zapis SQLite nie pozostawia zaakceptowanego faktu głosowania.
- [x] Niepewny commit SQLite ma pierwszeństwo; retry zachowuje ten sam
      identyfikator operacji.
- [x] Testy fake Redis, testy Django oraz test rzeczywisty z lokalnym Redisem
      przeszły poprawnie.

## P0.2 — rozdzielenie HTTP, migracji i schedulera

**Status: `[x]` zaimplementowane i potwierdzone w zrzucie live z 2026-09-15 dla wszystkich skonfigurowanych instancji 1, 2, 3 i 5–14. Wszystkie warstwy Flux są gotowe, Deploymenty mają `1/1`, a migracje są `Complete`.**

- [x] HTTP uruchamia wyłącznie Daphne.
- [x] Migracje są osobnymi Jobami, bez schedulera.
- [x] Każda zmigrowana instancja ma osobny scheduler `run_scheduler`.
- [x] Scheduler ma `replicas: 1`, lock na PVC i `strategy: Recreate`.
- [x] Każda zmigrowana instancja ma osobny chat notifications worker.
- [x] Flux używa warstw base, shared oraz osobnych migracji i runtime per-instance dla wszystkich aktywnych instancji.
- [x] Zmigrowane instancje używają `redis-1` z osobną logiczną bazą Redis.
- [x] Każda aktywna instancja ma deklaratywnie po jednym HTTP, schedulerze i workerze.
- [x] Historyczne warstwy batch/remaining nie są częścią obecnego modelu i nie mogą być ponownie wprowadzane.

## P0.3 — odtwarzanie danych

- [x] Backup instance-1 został zweryfikowany przez `quick_check` i
      `integrity_check`.
- [x] Backup instance-1 został odtworzony; po restore było 5 użytkowników,
      w tym 5 aktywnych.
- [x] Backup instance-2 został odtworzony; po restore było 6 użytkowników,
      w tym 6 aktywnych.
- [x] Skrypt `flux-cluster/scripts/restore-wikikracja-db.sh` obsługuje
      zatrzymanie aplikacji, walidację, zachowanie starej bazy, migracje i
      ponowne uruchomienie.
- [ ] Po każdym restore wykonać smoke test logowania, czatu, głosowania i
      schedulera.

## P1 — audyt transakcji i testy konkurencji

- [ ] Przeanalizować długie transakcje w:
  - `glosowania.management.commands.vote`;
  - `ankiety.views._cast_vote`;
  - `tasks.views.vote_task`;
  - zapisie wiadomości, reakcji i odczytów czatu;
  - masowych komendach schedulera.
- [ ] Oddzielić efekty zewnętrzne od transakcji SQLite: Redis, push, e-mail,
      WebSocket i zapis plików.
- [ ] Dodać testy konkurencji dla głosowania, ankiet, zadań i obecności.
- [ ] Uruchomić obciążenie HTTP + WebSocket + scheduler + Redis + backup.
- [ ] Powtórzyć test po restarcie poda i na docelowym storage Kubernetes.

### Wyniki testów P1a — zamykanie referendum

Testy wykonane 2026-09-14 potwierdziły:

- [x] awaria po częściowym `VoteCode.bulk_create()` wycofuje wynik SQLite;
- [x] ponowne uruchomienie zamknięcia nie dubluje `VoteCode`;
- [x] awaria jednej decyzji nie wycofuje poprawnego wyniku innej decyzji;
- [x] głosy są przenoszone do retryowalnego claimu Redis i usuwane dopiero po
      trwałym potwierdzeniu commitu SQLite;
- [x] nieudane potwierdzenie claimu jest zapisane w SQLite i ponawiane;
- [x] awarie `apply_parameters()` i `apply_brand_mark()` są zapisane jako
      trwałe efekty oczekujące i ponawiane bez cofania zatwierdzonego wyniku;
- [x] po `data_referendum_stop` nowe głosy są odrzucane przed zapisem do SQLite
      i Redis;
- [x] implementacja claim/ack przeszła test z rzeczywistym Redis 7.

### Wyniki testów P1b — konkurencja ankiet i zadań

Testy wykonane 2026-09-14 na osobnych procesach Django i tymczasowych plikach
SQLite z WAL:

- [x] równoczesna zmiana wyboru tego samego użytkownika w ankiecie pozostawia
      najwyżej jeden głos;
- [x] równoczesne wycofanie i zapisanie głosu nie tworzy duplikatu;
- [x] wielu użytkowników może oddać po jednym głosie na tę samą ankietę;
- [x] równoczesne głosy na jedno zadanie dają deterministyczny wynik agregacji
      i status `REJECTED` przy wyniku `-2`;
- [x] pomiary czasu zapisano jako baseline bez progów CI.

## P1 — ograniczone retry

- [ ] Retry stosować wyłącznie do operacji idempotentnych albo posiadających
      jawny mechanizm deduplikacji.
- [ ] Nie obejmować automatycznym retry e-maili, push, WebSocketów, Redis i
      zapisów plików bez idempotencji.
- [ ] Nie ponawiać innych `OperationalError` jako `database is locked`.
- [ ] Każde retry ma limit prób, backoff i test wyczerpania prób.

## P2 — monitoring i obserwowalność

- [ ] Mierzyć liczbę końcowych `database is locked`.
- [ ] Mierzyć czas transakcji i czas zadań schedulera.
- [ ] Monitorować rozmiar `db.sqlite3-wal` i `db.sqlite3-shm`.
- [ ] Monitorować restart i błędy schedulerów.
- [ ] Monitorować Redis oraz backupy.
- [ ] Powiązać alerty Prometheus/Loki z runbookiem.
- [ ] Nie logować kodów głosowania, anonimowych treści, tokenów ani sekretów.

## P2 — konfiguracja SQLite

- [x] Dodano test rzeczywistego połączenia sprawdzający `WAL`, `foreign_keys`
      i `busy_timeout`.
- [x] Potwierdzić lokalny, wspierany filesystem `ext4` dla bazy, WAL i SHM.
- [ ] Nie włączać `synchronous=OFF`.
- [ ] Nie zwiększać timeoutu ponad 60 sekund bez pomiarów.

### Wyniki P2a — podstawowa obserwowalność

- [x] Wyczerpanie retry SQLite loguje operację, liczbę prób, czas i rozmiar WAL.
- [x] Scheduler loguje czas rozpoczęcia/zakończenia komendy, status i rozmiar WAL.
- [x] Błędy komend schedulera zachowują traceback i końcowy pomiar czasu.
- [x] Flux Loki alertuje o powtarzających się blokadach SQLite i błędach komend schedulera.
- [x] Flux Prometheus ma alerty na stary/nieudany backup oraz zapełnienie PVC danych.
- [x] Zweryfikować reconcile i brak aktywnych alertów na klastrze podczas weryfikacji.
- [ ] Dodać osobny licznik/metrykę końcowych blokad niezależny od logów.

## P3 — bramka GO/NO-GO dla każdej instancji

Przed migracją kolejnej instancji wszystkie poniższe punkty muszą być spełnione:

- [x] Sprawdzony backup każdej instancji.
- [x] Brak aktywnego referendum albo zaakceptowany restart bufora Redis.
- [x] PVC są lokalne, dostępne i mają zapas miejsca.
- [x] Działa dokładnie jeden scheduler dla każdej bazy.
- [x] Działa dokładnie jeden kontrolowany writer SQLite dla każdej instancji.
- [x] Wszystkie migration Joby zakończyły się sukcesem.
- [x] Smoke testy HTTP, logowania, WebSocketów, Redis i głosowania przeszły.
- [x] Jest znany rollback do poprzedniego obrazu i `REDIS_HOST`.
- [x] Po migracji nie ma błędów `no such table`, `no such column` ani
      `database is locked` w krytycznych ścieżkach.

Brak któregokolwiek punktu oznacza **NO-GO** dla danej instancji.

## Kolejność dalszych prac

1. [x] P0 — spójność głosowania SQLite–Redis.
2. [x] P0.2 — fizyczny podział Flux i uruchomienie warstw per-instance.
3. [x] P0.3 — restore instance-1 i instance-2.
4. [ ] P1 — audyt pozostałych długich transakcji.
5. [-] P1 — wykonano testy konkurencji głosowania, ankiet i zadań; pozostaje pełny test HTTP + WebSocket + scheduler + backup.
6. [ ] P1 — ograniczona polityka retry poza głosowaniem i obecnością.
7. [-] P2 — działają logi i alerty blokad, WAL, schedulerów, Redis i backupów; pozostają niezależne metryki i progi.
8. [x] P3 — wszystkie skonfigurowane instancje 1, 2, 3 i 5–14 zmigrowane.

Prace implementacyjne zostają zatrzymane w tym miejscu. Dalszy etap to obserwacja produkcji i ewentualne niezależne metryki Prometheus; nie zmieniać timeoutu SQLite bez nowych pomiarów.
