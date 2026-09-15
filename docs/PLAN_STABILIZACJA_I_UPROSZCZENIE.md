# Plan stabilizacji i uproszczenia Wikikracji

## Cel

Doprowadzić całą aplikację do stanu, w którym:

- najważniejsze przepływy działają powtarzalnie i są chronione testami;
- każda informacja i konfiguracja ma jedno źródło prawdy;
- moduły mają jasną odpowiedzialność i niewiele zależności;
- usuwamy martwy, zdublowany i nieużywany kod zamiast dodawać kolejne warstwy;
- problemy są widoczne w logach, metrykach albo testach, zanim trafią do użytkownika;
- wdrożenie, backup, odtworzenie i rollback są opisane oraz sprawdzalne;
- UI korzysta z jednego wspólnego systemu komponentów i stylów.

To jest plan nadrzędny. Szczegółowe prace opisane już w osobnych dokumentach pozostają w tych dokumentach; tutaj są tylko powiązane z właściwym etapem, aby nie tworzyć drugiego, rozbieżnego backlogu.

## Zasady realizacji

1. **Najpierw pomiar i test, potem refaktoryzacja.** Nie upraszczamy kodu na podstawie przypuszczeń.
2. **Małe, odwracalne kroki.** Każdy podetap musi być możliwy do zweryfikowania i wycofania osobno.
3. **Zachowanie przed strukturą.** Refaktoryzacja nie zmienia zasad głosowania, anonimowości, kodów jednorazowych, członkostwa ani autoryzacji.
4. **KISS i YAGNI.** Nie dodajemy frameworków, rejestrów, abstrakcji ani konfiguracji bez konkretnego problemu i testu, który uzasadnia ich koszt.
5. **Jedna odpowiedzialność.** Widoki obsługują HTTP, usługi logikę domenową, modele integralność danych, a frontend interakcję i prezentację.
6. **Nie usuwamy danych ani historii migracji pochopnie.** Zmiany schematu, migracje produkcyjne i dane audytowalne wymagają osobnej analizy, backupu i konsultacji.
7. **Brak cichych obejść.** Błąd krytycznego zapisu ma być jawny; retry stosujemy tylko tam, gdzie operacja jest bezpieczna i idempotentna.
8. **Jedna implementacja wzorca.** Przed dodaniem rozwiązania sprawdzamy istniejące rejestry, usługi, partiale, komponenty UI i narzędzia.
9. **Nie optymalizujemy bez baseline'u.** Wydajność poprawiamy dopiero po pomiarze czasu, liczby zapytań, blokad albo rozmiaru zasobu.
10. **Każdy etap kończy się bramką.** Nie przechodzimy dalej, jeśli testy, checki lub kryteria akceptacji nie są spełnione.

## Stan wyjściowy i istniejące źródła prawdy

Wikikracja jest monolitem Django z modułami `obywatele`, `glosowania`, `ankiety`, `board`, `chat`, `events`, `tasks`, `bookkeeping`, `site_settings`, `categories`, `home`, `core` i `zzz`. Używa między innymi Django Channels/Daphne, Redis, SQLite w środowisku deweloperskim i w bieżącym wdrożeniu Kubernetes, Tailwind CSS, Jest, pytest i Ruff.

Istnieją już podstawowe bramki jakościowe: Ruff, Django check, pytest, Jest, kontrola wygenerowanego Tailwind CSS, skan regresji CSS, UI guard oraz Playwright. Plan zakłada ich uporządkowanie i konsekwentne używanie, a nie tworzenie drugiego systemu kontroli.

Powiązane dokumenty:

- `docs/PLAN_refaktoryzacja_architektury.md` — granice modułów, rejestry i dekompozycja zależności;
- `docs/PLAN_refaktoryzacja_home.md` — historyczny coupling `home` i plan jego ograniczania;
- `docs/PLAN_NIEZAWODNOSC_SQLITE.md` — backupy, blokady, transakcje, scheduler i model jednego writera;
- `docs/UI_STANDARDS.html`, `docs/UI_DEVELOPMENT_GUIDE.md`, `docs/TAILWIND_UI_GUIDE.md` — wspólny system UI;
- `scripts/run_tests.py` i `scripts/pre_push_tests.py` — odpowiednio pełna i zmieniona-zakresowo weryfikacja.

Nie modyfikować `docs/TODO.md`; jest osobistą listą użytkownika. Ten dokument jest planem technicznym aplikacji.

## Status etapów

- [ ] Faza 0 — zamrożenie zakresu i baseline
- [ ] Faza 1 — powtarzalne środowisko i bramki jakości
- [ ] Faza 2 — niezawodność danych, transakcji i procesów
- [ ] Faza 3 — uproszczenie architektury backendu
- [ ] Faza 4 — ochrona przepływów krytycznych
- [ ] Faza 5 — uproszczenie frontendu i UI
- [ ] Faza 6 — redukcja martwego kodu i zależności
- [ ] Faza 7 — obserwowalność i operacje
- [ ] Faza 8 — utrwalenie prostoty

Status etapu zaznaczamy dopiero po przejściu jego bramki. Zadania można zaznaczać niezależnie, ale nie oznacza to ukończenia całej fazy.

## Faza 0 — zamrożenie zakresu i baseline

Cel: ustalić, co naprawdę działa, co jest krytyczne i z jakiego stanu startujemy. W tej fazie nie wykonujemy szerokiego refaktoru.

- [ ] Ustalić listę przepływów krytycznych i ich właścicieli:
  - [ ] logowanie, wylogowanie, reset hasła i onboarding;
  - [ ] członkostwo, akceptacja, blokowanie i usuwanie obywatela;
  - [ ] utworzenie, podpisanie i oddanie głosu oraz weryfikacja kodem;
  - [ ] anonimowość i audytowalność głosowania;
  - [ ] czat, uprawnienia do pokoju, reconnect i wiadomości;
  - [ ] powiadomienia, digest i oznaczanie odczytu;
  - [ ] zadania, wydarzenia, dokumenty, ankiety i rozliczenia;
  - [ ] backup, start aplikacji, scheduler, migracje i healthchecki.
- [ ] Spisać mapę uruchomieniową: HTTP/ASGI, WebSocket, Redis, baza, scheduler, worker powiadomień i zadania zarządzające.
- [ ] Spisać mapę danych: modele, właściciel danych, zapisujący kod, efekty uboczne i wymagany poziom audytu.
- [ ] Zmierzyć baseline testów: czas, liczba testów, flaky tests, błędy środowiskowe i wymagane usługi.
- [ ] Zmierzyć baseline działania aplikacji: czas startu, błędy 4xx/5xx, błędy WebSocket, `database is locked`, czas zadań schedulera i rozmiar WAL.
- [ ] Zidentyfikować funkcje, endpointy, szablony, pliki JS/CSS, komendy i zależności podejrzane o brak użycia — bez ich usuwania na tym etapie.
- [ ] Oznaczyć obszary wymagające konsultacji przed zmianą: migracje i dane, uwierzytelnianie, uprawnienia, scheduler, głosowania, anonimowość, kody jednorazowe i kontrakty między modułami.
- [ ] Ustalić dla każdego dalszego zadania: dowód potrzeby, zakres, kryterium akceptacji, test i sposób wycofania.

**Bramka F0:** istnieje aktualna mapa systemu, baseline testów i lista przepływów krytycznych; nie ma zadania typu „refaktoryzuj wszystko” bez mierzalnego kryterium.

## Faza 1 — powtarzalne środowisko i bramki jakości

Cel: każdy deweloper i CI uruchamiają te same kontrole, a błąd środowiska nie jest mylony z błędem aplikacji.

- [ ] Ujednolicić instrukcję uruchamiania na Windows/Linux/CI wokół repozytoryjnego `.venv` i Node 22.
- [ ] Ustalić jeden kanoniczny zestaw komend dla: lintingu, formatowania, Django check, migracji, collectstatic, testów Python, Jest, CSS, skanów i E2E.
- [ ] Zweryfikować, że CI i lokalne skrypty mają zgodne wersje narzędzi oraz identyczne wymagania środowiskowe.
- [ ] Rozdzielić szybkie kontrole zmienionego zakresu od pełnej bramki; nie ukrywać pominiętych kontroli.
- [ ] Zapewnić deterministyczne ustawienia dla testów wymagających nadpisania bazy, `MEDIA_ROOT`, `STATIC_ROOT`, poczty, schedulera i Firebase.
- [ ] Ustalić politykę testów równoległych: `-n 0` przy procesowych nadpisaniach ustawień oraz osobne testy współbieżności tam, gdzie równoległość jest przedmiotem testu.
- [ ] Ograniczyć Playwright do dedykowanego konta E2E z `E2E_EMAIL` i `E2E_PASSWORD`; nie używać kont developerskich, administracyjnych ani prywatnych.
- [ ] Dodać do CI kontrolę brakujących sekretów i usług bez wypisywania ich wartości.
- [ ] Ustalić, które ostrzeżenia logów są oczekiwane, a które oznaczają regresję; usunąć szum dopiero po potwierdzeniu przyczyny.

**Bramka F1:** od czystego checkoutu można jednoznacznie uruchomić właściwe kontrole; wynik każdej kontroli jest czytelny, powtarzalny i nie zależy od przypadkowego lokalnego stanu.

## Faza 2 — niezawodność danych, transakcji i procesów

Cel: chronić integralność danych i przewidywalność operacji bez zmiany reguł biznesowych.

- [ ] Dokończyć otwarte zadania z `docs/PLAN_NIEZAWODNOSC_SQLITE.md`:
  - [ ] audyt długich transakcji i efektów zewnętrznych wykonywanych w transakcji;
  - [ ] globalny monitoring blokad, czasu transakcji i rozmiaru WAL;
  - [ ] test obciążeniowy HTTP, WebSocketów, schedulera i głosowania na docelowym modelu uruchomienia;
  - [ ] formalne ograniczenie liczby procesów zapisujących do SQLite;
  - [ ] procedury backupu, integralności, odtworzenia i awarii;
  - [ ] testy restartu oraz monitorowanie schedulera, Redis i ścieżki głosowania.
- [ ] Sprawdzić wszystkie operacje zapisu pod kątem atomowości, powtórzenia żądania i częściowego wykonania.
- [ ] Zostawić retry wyłącznie przy błędach przejściowych i operacjach bezpiecznych do powtórzenia; głosowanie i inne zapisy audytowalne muszą mieć jawny wynik.
- [ ] Uporządkować granice `transaction.atomic()`: krótki zapis w bazie, efekty zewnętrzne po zatwierdzeniu albo jawny mechanizm kompensacji.
- [ ] Zweryfikować idempotencję sygnałów, powiadomień, komend zarządzających i zadań schedulera.
- [ ] Sprawdzić backup na kopii i wykonać kontrolowane odtworzenie, bez operowania na jedynej produkcyjnej kopii.
- [ ] Nie skalować SQLite poza zaakceptowany model jednego kontrolowanego writera; ewentualną zmianę silnika traktować jako osobną decyzję architektoniczną.

**Bramka F2:** krytyczne zapisy mają testy integralności i konkurencji, backup można odtworzyć, a liczba procesów i retry jest jawnie określona.

## Faza 3 — uproszczenie architektury backendu

Cel: zmniejszyć sprzężenie i liczbę miejsc, w których ukryta jest logika.

- [ ] Zaktualizować mapę zależności importów między aplikacjami i wskazać cykle, importy modeli w widokach oraz moduły o zbyt wielu odpowiedzialnościach.
- [ ] Ustalić właściciela każdej domeny i publiczne, minimalne kontrakty między domenami.
- [ ] Dokończyć tylko uzasadnione elementy istniejącego planu architektury; nie tworzyć kolejnego rejestru, jeśli obecny kontrakt wystarcza.
- [ ] Utrzymać `core` jako miejsce rzeczywiście współdzielonych mechanizmów, bez przenoszenia logiki domenowej tylko po to, aby skrócić import.
- [ ] Utrzymać cienkie widoki: request/permission/form → wywołanie usługi → response/template.
- [ ] Wydzielać logikę z widoków tylko wtedy, gdy ma własną odpowiedzialność, test lub więcej niż jeden konsument.
- [ ] Usunąć bezpośrednie importy modeli innych domen tam, gdzie istnieje już stabilny kontrakt, provider lub sygnał.
- [ ] Ujednolicić obsługę błędów i komunikatów użytkownika; nie maskować wyjątków ogólnym `except` bez logowania i kryterium odzyskania.
- [ ] Zredukować side-effecty w `AppConfig.ready()`: importy rejestrujące mogą być idempotentne i nie mogą wykonywać zapytań ani wysyłać danych przy każdym starcie.
- [ ] Zweryfikować granice usług wyszukiwania, dashboardu, feedu, powiadomień, czatu i profilu zgodnie z istniejącymi decyzjami architektonicznymi.
- [ ] Po każdej zmianie zależności wykonać test importu, Django check i testy domen, których kontrakt dotyczy.

**Bramka F3:** nowe zależności przechodzą przez jeden jawny kontrakt, widoki nie zawierają ukrytej logiki domenowej, a liczba wyjątków architektonicznych jest udokumentowana i maleje.

## Faza 4 — ochrona przepływów krytycznych

Cel: stabilizować zachowanie bez naruszania zasad systemu.

- [ ] Dla każdego przepływu z Fazy 0 utworzyć test charakterystyki przed refaktorem.
- [ ] Dodać testy graniczne dla braku danych, ponownego żądania, timeoutu, błędu Redis, blokady SQLite, zerwanego WebSocketu i nieaktualnego formularza.
- [ ] Zweryfikować uprawnienia na poziomie widoku, usługi i zapisu; nie polegać wyłącznie na ukryciu przycisku w UI.
- [ ] Zweryfikować, że logi, feed, digest, profil i powiadomienia nie ujawniają danych anonimowych ani danych spoza zakresu użytkownika.
- [ ] Utrzymać niezmienione kontrakty głosowania, anonimowości, jednorazowych kodów, członkostwa i autoryzacji; każdą propozycję zmiany konsultować osobno.
- [ ] Przetestować synchronizację stanu czatu: reconnect, rejoin, kolejkę wiadomości, timeouty, singleton WebSocketu i izolację błędu handlera.
- [ ] Przetestować powiadomienia niezależnie dla kanałów WebSocket, push i e-mail oraz bez aktywnej konfiguracji Firebase.
- [ ] Utrzymać E2E tylko dla najważniejszych ścieżek użytkownika; resztę pokrywać tańszymi testami jednostkowymi i integracyjnymi.
- [ ] Przy każdym wykrytym błędzie dodać najpierw minimalny test regresji, potem poprawkę.

**Bramka F4:** przepływy krytyczne mają testy zachowania i błędów brzegowych; żadna poprawka stabilizacyjna nie zmienia zasad biznesowych bez osobnej decyzji.

## Faza 5 — uproszczenie frontendu i UI

Cel: zmniejszyć liczbę wariantów UI, kodu JS i źródeł stylów.

- [ ] Utrzymać jeden produkcyjny pipeline `tailwind.css` → `tailwind.build.css`; nie edytować ręcznie pliku generowanego.
- [ ] Zinwentaryzować klasy Bootstrap, modułowe arkusze, inline styles, duplikaty partiali i jednorazowe komponenty.
- [ ] Migrować powtarzalne elementy do istniejących `tw-*`, partiali `home/templates/home/includes/`, `home/templates/tw/` i wspólnych modułów JS.
- [ ] Nie dodawać nowych klas bez prefiksu `tw-`, poza krótkotrwałymi, semantycznymi hookami JS.
- [ ] Usuwać duplikaty po sprawdzeniu wszystkich użyć, a nie przez masową zamianę tekstu.
- [ ] Ujednolicić formularze, alerty, badge, karty, toolbary, tabele, empty states, modale, dropdowny, ikony i widoki list/siatek.
- [ ] Rozdzielić logikę JS od DOM tam, gdzie pozwala to na test jednostkowy; zachować jeden kontrakt wspólnego WebSocketu.
- [ ] Dodać testy dla nowych lub zmienionych interakcji i sprawdzić dostępność klawiaturą, focus, komunikaty błędów oraz mobile.
- [ ] Po każdej zmianie UI uruchomić `npm run build:css`, `scripts/regression_scan.py` i `scripts/ui_guard.py`, gdy dotyczy.
- [ ] Aktualizować `docs/UI_STANDARDS.html` i przewodniki tylko wtedy, gdy powstaje lub zmienia się wspólny wzorzec.

**Bramka F5:** istnieje jedno źródło stylów, nie przybywa wyjątków UI, zmienione interakcje mają testy, a kontrola wygenerowanego CSS przechodzi.

## Faza 6 — redukcja martwego kodu i zależności

Cel: zmniejszyć powierzchnię aplikacji dopiero po udowodnieniu, że element jest nieużywany.

- [ ] Dla każdego kandydata potwierdzić brak użycia w Pythonie, URL-ach, szablonach, JS, sygnałach, komendach, migracjach, CI i konfiguracji wdrożeniowej.
- [ ] Oznaczyć elementy jako: używane, historyczne, publiczny kontrakt, tymczasowe albo bez użycia.
- [ ] Usunąć nieużywane zależności Python/Node dopiero po sprawdzeniu importów, lockfile, CI i środowiska produkcyjnego.
- [ ] Usunąć nieużywane endpointy, template tags, helpery, duplikaty providerów i martwe ścieżki kodu małymi seriami.
- [ ] Nie usuwać migracji historycznych; ewentualne squashowanie lub porządkowanie migracji wymaga osobnego planu i backupu.
- [ ] Zastąpić powielone stałe i konfiguracje jednym źródłem prawdy, bez zmiany publicznych kontraktów.
- [ ] Uporządkować dokumentację, tłumaczenia i nazwy tylko po ustaleniu wpływu na URL-e, dane, importy i użytkowników.
- [ ] Po każdym usunięciu wykonać testy konsumentów oraz skan nieużywanych referencji.

**Bramka F6:** kod i zależności są mniejsze, a każda usunięta rzecz ma dowód braku użycia i przechodzący test regresji.

## Faza 7 — obserwowalność i operacje

Cel: szybko rozpoznać awarię, odróżnić jej przyczynę i bezpiecznie przywrócić usługę.

- [ ] Zdefiniować minimalne metryki i alerty: 5xx, błędy logowania, błędy WebSocket, `database is locked`, czas zapisu głosu, czas schedulera, błędy powiadomień, Redis, WAL i backupów.
- [ ] Ujednolicić nazwy loggerów, poziomy logowania i identyfikatory korelacji bez logowania sekretów, kodów jednorazowych ani danych anonimowych.
- [ ] Dodać lub zweryfikować healthchecki rozdzielające liveness od gotowości oraz sprawdzające tylko niezbędne zależności.
- [ ] Opisać runbooki: start, zatrzymanie, migracja, backup, restore, rollback, blokada SQLite, awaria Redis, awaria schedulera i odnowienie sekretów.
- [ ] Zweryfikować, że scheduler, worker powiadomień i HTTP mają jednoznaczne role oraz nie uruchamiają się przypadkiem podwójnie.
- [ ] Wykonać ćwiczenie odtworzenia backupu i udokumentować wynik, czas oraz ograniczenia.
- [ ] Zdefiniować kryteria GO/NO-GO przed wdrożeniem oraz smoke test po wdrożeniu.

**Bramka F7:** operator może na podstawie logów i runbooka rozpoznać awarię, odtworzyć dane na kopii i wykonać bezpieczny rollback.

## Faza 8 — utrwalenie prostoty

Cel: nie odtworzyć długu po zakończeniu jednorazowej stabilizacji.

- [ ] Dodać checklistę Definition of Done do zmian backendu, frontendu, danych i wdrożenia.
- [ ] Wymagać wskazania właściciela danych, kontraktu, testu i kryterium usunięcia dla każdej nowej abstrakcji.
- [ ] Wymagać uzasadnienia dla nowej zależności, konfiguracji, klasy CSS, sygnału, schedulera i publicznego endpointu.
- [ ] Raz na cykl przeglądać zadania z tego planu, otwarte wyjątki architektoniczne i metryki stabilności.
- [ ] Aktualizować ten dokument po ukończeniu etapu; nie zaznaczać zadania jako wykonane bez dowodu w postaci testu, pomiaru, dokumentu albo decyzji.
- [ ] Po zakończeniu każdej zmiany kodu dopisać wpis do `docs/LOG_AI.md`, zgodnie z zasadami projektu.

**Bramka F8:** nowe zmiany nie omijają bramek jakości, a dokumentacja odzwierciedla aktualny stan systemu.

## Kanoniczne bramki weryfikacyjne

Przed uruchomieniem komend sprawdzić wersję repozytoryjnego interpretera:

```powershell
.venv\Scripts\python.exe --version
```

Zakres zmienionej aplikacji:

```powershell
.venv\Scripts\python.exe -m pytest -q -n 0 <ścieżki-testów>
.venv\Scripts\python.exe -m ruff check <zmienione-ścieżki>
.venv\Scripts\python.exe -m ruff format --check <zmienione-ścieżki>
```

Zmiany UI dodatkowo:

```powershell
npm run build:css
.venv\Scripts\python.exe scripts\regression_scan.py
.venv\Scripts\python.exe scripts\ui_guard.py
npm test -- --runInBand
```

Pełna bramka aplikacji, gdy zakres tego wymaga:

```powershell
.venv\Scripts\python.exe scripts\run_tests.py
```

Pełna bramka musi używać dedykowanego konta E2E i nie może być zastępowana interaktywnym podglądem przeglądarki. Przy weryfikacji izolowanej od środowiska należy stosować zasady z `AGENTS.md`, w szczególności `PYTHON_DOTENV_DISABLED=1`, bazę w pamięci, tymczasowe katalogi i `-n 0` przy procesowych nadpisaniach ustawień.

## Definition of Done dla każdego zadania

- [ ] Problem i zakres są opisane jednym zdaniem.
- [ ] Zmiana ma jeden właścicielski moduł i nie dodaje niepotrzebnej warstwy.
- [ ] Istnieje test regresji albo uzasadnienie, dlaczego test nie ma sensu.
- [ ] Zostały sprawdzone uprawnienia, dane wrażliwe, retry, transakcje i efekty uboczne.
- [ ] Dla UI użyto istniejącego wzorca i właściwego pipeline'u CSS.
- [ ] Przeszły właściwe testy, lint, format, checki i skany.
- [ ] Dokumentacja, tłumaczenia i runbooki są aktualne, jeśli zmiana ich dotyczy.
- [ ] Zmiana jest mała, odwracalna i nie zawiera sekretów ani plików tymczasowych.
- [ ] `docs/LOG_AI.md` zawiera wpis, jeśli zmieniono kod.

## Kryterium zakończenia całego planu

Plan można uznać za zakończony dopiero, gdy wszystkie poniższe punkty są spełnione:

- [ ] Krytyczne przepływy mają stabilne testy automatyczne i przechodzą testy ręczne po wdrożeniu.
- [ ] CI i lokalna weryfikacja korzystają z tego samego, opisanego zestawu bramek.
- [ ] Nie ma nieudokumentowanych zależności między domenami ani niekontrolowanych efektów w `ready()`, sygnałach i schedulerze.
- [ ] Model bazy, liczba writerów, backup, restore, monitoring i rollback są sprawdzone operacyjnie.
- [ ] Frontend ma jedno źródło stylów, wspólne komponenty i testowane interakcje.
- [ ] Usunięto potwierdzony martwy kod i zbędne zależności bez naruszenia kontraktów.
- [ ] Metryki pokazują brak regresji stabilności, a każdy pozostały wyjątek jest świadomą decyzją opisaną w dokumentacji.
