## 2026-10-28: Diagnostyka bledow usuwania kont

- **Zmienione obszary:** `obywatele.management.commands.count_citizens` oraz testy usuwania kont.
- **Co sie zmienilo:** Sprzatanie nieaktywnych kont pomija uzytkownikow z `DeletionRequest`, pozostawiajac ich wylacznie sciezce realizujacej prosbe po terminie. Bledy usuwania kont nieaktywnych i zadanych przez uzytkownika uzywaja `log.exception`, dzieki czemu logi zawieraja traceback.
- **Testy:** Dodano regresje pomijania konta z prosba oraz sprawdzenia, ze oba bledy usuwania zachowuja traceback w logu.
- **Uzasadnienie:** Jedno konto nie powinno byc probowane przez dwa niezalezne mechanizmy w tym samym przebiegu, a traceback pomoze wskazac konkretna operacje naruszajaca FK.
- **Spodziewany efekt:** Brak powtorzonej proby usuniecia konta z wnioskiem oraz latwiejsza diagnoza przyszlych bledow FK bez zmiany semantyki terminu prosby.

# LOG_AI

## 2026-10-24: Usuwanie wszystkich obrazow podczas edycji czatu

- **Przyczyna:** przycisk czyszczenia podgladu usuwal istniejace obrazy tylko z DOM; nie dodawal ich nazw do listy `removed_attachments`, wiec zapis pozostawial je przy wiadomosci.
- **Zmiana:** `clearFiles()` oznacza teraz wszystkie widoczne, istniejace zalaczniki jako usuniete w aktywnym trybie edycji przed wyczyszczeniem podgladu.
- **Testy:** dodano regresje DOM API potwierdzajaca, ze czyszczenie podgladu przekazuje nazwe istniejacego obrazu do zapisu.
- **Spodziewany efekt:** przycisk usuwania wszystkich obrazow zapisuje ich usuniecie z wiadomosci.

## 2026-10-24: Stabilizacja edycji wiadomosci czatu

- **Przyczyna:** embedded chat odczytywal edytowana tresc i czas z pol `message`/`latest_timestamp`, podczas gdy serwer wysyla `text`/`timestamp`; powodowalo to wyczyszczenie tresci oraz `NaN:NaN`. Edytory nie obslugiwaly rowniez zmian zalacznikow w pelnym i osadzonym czacie.
- **Zmiana:** oba edytory synchronizuja podglady z wybranymi plikami, oznaczaja usuniete zalaczniki i wysylaja zmiany obrazow. Embedded chat aktualizuje widok z pol serwerowego payloadu, a interfejs nie nadpisuje tekstu ani czasu wartosciami brakujacymi lub niepoprawnymi. Poprawiono usuwanie koncowych pustych linii `<br>` po sanitizacji.
- **Testy:** dodano regresje backendu potwierdzajaca, ze edycja samych zalacznikow zachowuje tekst i nie zapisuje wpisu historii tekstu, test odpornosci DOM API oraz E2E dodawania i usuwania obrazu.
- **Spodziewany efekt:** obraz mozna dodac lub usunac podczas edycji w obu wariantach czatu, a tekst wiadomosci pozostaje widoczny po zapisie.

## 2026-10-21: Usuwanie HTML z powiadomień o wydarzeniach

- **Przyczyna:** powiadomienia push otrzymywały HTML z opisu wydarzenia jako zwykły tekst, przez co Windows wyświetlał tagi i encje.
- **Zmiana:** opisy i gotowe treści powiadomień są konwertowane istniejącym helperem `plain_text`, który usuwa znaczniki, dekoduje encje i zachowuje podziały `<br>`/akapitów jako nowe linie.
- **Testy:** dodano regresje dla treści przygotowanej przez scheduler oraz opisu budowanego bezpośrednio w handlerze.
- **Spodziewany efekt:** powiadomienia systemowe pokazują czytelny tekst bez HTML, z zachowanym formatowaniem wierszy.

## 2026-10-20: Kafelek mapy społeczności na pulpicie

- **Przyczyna:** pulpit nie udostępniał szybkiego podglądu istniejącej Mapy społeczności.
- **Zmiana:** dodano kafelek 1×1 w trzeciej pozycji, korzystający ze wspólnego endpointu mapy i oddalony o jeden poziom. Kliknięcie podglądu otwiera pełną mapę; kliknięcia w kontrolki i atrybucję Leaflet zachowują ich działanie. Kafelek pokazuje wyłącznie mapę z markerami — bez etykiet, popupów, list i stopki. Atrybucja dostawcy pozostała widoczna, a jej tekst zmniejszono do 10 px.
- **Weryfikacja:** testy renderowania kafelka i trybu mapy bez szczegółów, build CSS, regression scan i UI guard. Uchwyt sortowania jest zakotwiczony nad warstwami Leaflet, mapa wypełnia wysokość kafelka, a pełna mapa nie zasłania mobilnego menu.

## 2026-10-20: Poprawki błędów CI dla GitHub Pages i testu motywu

- **Przyczyna:** Jekyll interpretował wzmiankę o tagu Django `load` w tym pliku jako własny tag Liquid, a test E2E oczekiwał `dark`, chociaż aplikacja renderuje motyw ciemny jako `tokyo-night`.
- **Zmiana:** opis tagów Django nie zawiera już składni Liquid, a test przełącznika akceptuje rzeczywistą nazwę motywu.
- **Weryfikacja:** sprawdzono brak składni Liquid w logu i poprawność diffu.

## 2026-10-20: Poprawna semantyka ARIA w linkach sortowania

- **Przyczyna:** `aria-pressed` nie jest obsługiwane przez elementy `<a>`; wzorzec występował w przykładzie standardów i wspólnym toolbarze.
- **Zmiana:** aktywny link sortowania używa teraz `aria-current="true"`, a nieaktywne linki nie deklarują bieżącego elementu.
- **Weryfikacja:** sprawdzono przykład dokumentacji i wspólny partial toolbaru; test widoku potwierdza stan aktywnego sortowania, a test strony ustawień potwierdza położenie metadanych wewnątrz `<head>`.

## 2026-10-20: Ładowanie motywu z preferencji profilu

- **Przyczyna:** inicjalizacja przed renderem brała motyw wyłącznie z `localStorage`, a globalny przełącznik wysyłał do serwera `tokyo-night` zamiast zapisanego wariantu `dark`.
- **Zmiana:** dla zalogowanych użytkowników serwerowa preferencja profilu jest źródłem motywu już przed załadowaniem CSS; przełącznik zapisuje do bazy wartość zgodną z modelem. Tagi `load` Django są umieszczone wewnątrz `<head>`, żeby narzędzia HTML nie interpretowały ich jako treści przed `<!DOCTYPE html>`.
- **Weryfikacja:** test renderowania ustawień z zapisaną preferencją oraz test zapisu wariantu ciemnego.

## 2026-10-20: Tailwind skanuje tylko źródła JS aplikacji

- **Przyczyna:** glob `./**/static/**/*.js` obejmował również ignorowany katalog `static/` z wynikiem `collectstatic`. Stary, scalony plik `community-map.js` utrzymywał nieużywaną klasę `tw-bg-accent` lokalnie, ale nie w czystym CI.
- **Zmiana:** zawężono glob do `./*/static/**/*.js`, czyli źródłowych zasobów aplikacji, bez generowanego katalogu root.
- **Weryfikacja:** `npm run build:css` usuwa teraz nieużywaną klasę i daje wynik zgodny ze źródłami.

## 2026-10-20: Stały kolor zasobu na mapie

- **Przyczyna:** utility `tw-bg-success` używa `--badge-approved-color`, którego wartość różni się między motywami.
- **Zmiana:** znacznik zasobu korzysta bezpośrednio ze wspólnego, niezmiennego między motywami tokenu `--color-success`.
- **Testy:** test Jest sprawdza klasę tokenu znacznika zasobu.

## 2026-10-20: Podkład mapy zależny od motywu

- **Zmiana:** w motywie ciemnym filtrowana jest wyłącznie warstwa kafelków Leaflet; jasny motyw pozostawia oryginalny podkład. Znaczniki, kontrolki i atrybucja nie są przyciemniane. Motyw przełącza się natychmiast wraz ze zmianą atrybutu `data-theme`.
- **Testy:** kontrola renderowania mapy, build CSS, regression scan i UI guard.

## 2026-10-20: Kontrast niebieskiego znacznika osoby

- **Zmiana:** jaśniejszy niebieski `info` zastąpiono w znaczniku osoby ciemnym tokenem `citizen-color-9` i białą ikoną. Kolory partnera i zasobu pozostają bez zmian.
- **Testy:** regresja sprawdza przypisanie ciemnoniebieskiego znacznika osobie.

## 2026-10-20: Oddzielne znaczniki dla nakładających się typów

- **Zmiana:** mapa nie łączy już obywateli, partnerów i zasobów w jeden mieszany znacznik. Nakładające się ikony są rozsuwane minimalnie w pikselach bieżącego zoomu; każdy zachowuje osobny typ i popup. Po zmianie zoomu układ jest przeliczany.
- **Testy:** dodano regresję nakładających się obywatela, partnera i zasobu oraz niezmienionych pozycji dla niezachodzących punktów.

## 2026-10-20: Geokodowanie punktów miejskich i lista krajów partnera

- **Zmiana mapy:** lokalizacja z samym krajem i miastem korzysta z najlepszego wyniku geokodera dla osady; wyszukiwanie bez ulicy ogranicza liczbę wyników do jednego. Pełny adres nadal używa precyzyjnego dopasowania, a w razie braku wyniku wraca do miasta.
- **Zmiana formularza:** kraj partnera jest wybierany z katalogu krajów, domyślnie Polska; zapisane wartości ISO i nazwy są odtwarzane, a historyczne `Polska` mapuje się na `PL`.
- **Weryfikacja:** testy wyboru kraju partnera, rozpoznawania `Polska` oraz geokodowania punktu Kielc bez ulicy i numeru.

## 2026-10-20: Kraj w formularzach ludzi, zasobów i partnerów

- **Przyczyna:** profil wysyła kraj jako kod ISO, ale formularz Django inicjalizował wybór kluczem obcym (liczbą). Brak dopasowanej opcji w przeglądarce pokazywał pierwszy kraj na liście, Afganistan.
- **Zmiana:** formularze profilu i onboardingu wybierają kod kraju zapisanego w bazie (lub `PL`, gdy go nie ma). Formularze zasobów i partnerów zachowują zapisany kraj; brak kraju w nowym lub edytowanym wpisie domyślnie daje Polskę z katalogu `Country`, bez zmiany schematu ani istniejących rekordów.
- **Weryfikacja:** testy inicjalizacji i zapisu formularzy, Ruff, Django check i kontrole UI.

## 2026-10-20: Znaczniki zasobów na mapie społeczności

- **Zmiana:** mapa zbiera aktywne oferty i potrzeby z kanonicznego `resources.Entity`, gdy mają własny kraj i miasto oraz są wspólnotowe lub przypisane do aktywnego członka. Zasoby otrzymują znacznik i odnośnik do katalogu; jednostki finansowe, wpisy zamknięte i bez lokalizacji pozostają wykluczone.
- **Prywatność:** zasoby są geokodowane i opisywane wyłącznie na poziomie miasta; adres zasobu i lokalizacja właściciela nie są udostępniane. Publiczny payload nadal zawiera tylko unikalne współrzędne.
- **Diagnoza produkcji:** dopisano do instrukcji wdrożenia sposób sprawdzenia odpowiedzi endpointu i cache. Sam kod nie włącza geokodowania: przy `MAP_GEOCODING_ENABLED=False` i pustym Redisie żadne punkty nadal się nie pojawią. Zewnętrzny ruch wymaga osobnej decyzji operatora.
- **Weryfikacja:** testy mapy po stronie Django i Jest, Ruff, build CSS, skan regresji i UI guard.

## 2026-10-18: Zachowanie fokusu po wyszukiwaniu transakcji

- **Co się zmieniło:** przy wysłaniu formularza wyszukiwania Enterem zapisywana jest pozycja kursora; po załadowaniu wyników fokus i pozycja kursora wracają do pola.
- **Weryfikacja:** dodano test odtwarzania fokusu po przeładowaniu wyników.

## 2026-10-18: Wyszukiwanie transakcji po Enter z dopasowaniem OR

- **Co się zmieniło:** wyszukiwanie listy transakcji uruchamia się przez Enter. Wpisane słowa są osobnymi warunkami OR względem rodzaju, daty, partnera, kategorii, aktywa (kod, nazwa i symbol), kwoty, autora (login, imię i nazwisko) oraz notatki.
- **Weryfikacja:** dodano regresję dopasowującą dwa różne słowa do dwóch transakcji.

## 2026-10-18: Zarządzanie kategoriami bez osobnego kroku

- **Zmienione obszary:** stepper bookkeeping oraz regresja API listy kategorii.
- **Co się zmieniło:** usunięto kategorię ze steppera; zarządzanie pozostaje dostępne z listy transakcji. Poprawiono nazwę relacji reverse używaną do zliczania transakcji w API, która powodowała 500 przy pobieraniu kategorii.
- **Spodziewany efekt:** krótsza nawigacja bez utraty dotychczasowych adresów kategorii ani ich API.

## 2026-10-18: Uproszczenie filtrów listy transakcji

- **Zmienione obszary:** formularz, wyszukiwanie listy transakcji oraz testy.
- **Co się zmieniło:** wyszukiwanie dopasowuje partnera, kategorię, rodzaj, kwotę i datę. Usunięto selektor rodzaju oraz przyciski „Filtruj” i „Wyczyść”; sortowanie, kategorie i widok pozostają we wspólnym toolbarze.
- **Spodziewany efekt:** szybsze wyszukiwanie bez dodatkowych kontrolek, z polem mieszczącym się w jednym rzędzie toolbaru, gdy pozwala na to szerokość ekranu.

## 2026-10-18: Konsolidacja dokumentacji zasobów

- **Zmiana:** po zakończeniu cutoverów usunięto robocze plany zasobów i cutoverów. Trwałe reguły modelu i prywatności są w `SECURITY_EXCEPTIONS.md`, wymagania dostawców mapy oraz procedury kopii/odtworzenia w `DEPLOYMENT_INSTRUCTIONS.md`, a historię, preflight i ograniczenia rollbacku zachowują wpisy tego dziennika.
- **Zakres:** zakończone etapy zachowuje ten log; wycofane przez użytkownika propozycje nie są już listą otwartych zadań. Nie zmieniano kodu ani schematu.

## 2026-10-18: Zamknięcie planu mapy społeczności

- **Zmiana:** uznano plan mapy za wykonany i usunięto `docs/ongoing/PLAN_MAPA.md`. Zasady zakresu danych, widoczności i prywatności mapy są w `SECURITY_EXCEPTIONS.md`; konfiguracja oraz ograniczenia dostawców są w `DEPLOYMENT_INSTRUCTIONS.md`.
- **Zakres:** potwierdzono przyjęte założenia dostawców dla bieżącego MVP; przed zwiększeniem ruchu należy ponownie sprawdzić aktualne warunki usług i przewidywane użycie. Nie zmieniano kodu ani schematu.

## 2026-10-18: Ograniczenie zakresu planu zasobów

- **Zmiana zakresu:** usunięto z `PLAN_ZASOBY_UŻYTKOWNIKÓW.md` wskazane przez użytkownika, odłożone pola i funkcje. Nie zmieniano schematu ani logiki aplikacji w tym kroku.
- **Pozostały zakres:** prywatne dopasowanie aktywnych ofert do aktywnych potrzeb pozostaje wdrożone; sugestie/powiadomienia dla oferentów i przypomnienia nie należą do aktualnej wersji. Read-only audyt migracji potwierdził, że archiwum historycznych pól nie istnieje w schemacie: `0047`–`0048` przeniosły wartości i usunęły źródłowe kolumny, a `0055` usuwa `ResourceItem` bez reverse. Pełne odtworzenie wymaga backupu sprzed migracji; jego dostępności nie sprawdzano.

## 2026-10-18: Dopasowanie aktywnych ofert do potrzeb

- **Zmienione obszary:** usługa dopasowań `resources`, ekran zarządzania zasobami, częściowa karta wpisu, tłumaczenia i testy.
- **Co się zmieniło:** właściciel potrzeby widzi na ekranie zarządzania aktywne, publicznie widoczne oferty z taką samą nazwą po normalizacji Unicode, wielkości liter i białych znaków. Community-owned potrzeby są widoczne członkom; zamknięte wpisy i wpisy przypisane nieaktywnym profilom nie trafiają do sugestii. To wyłącznie lokalna sugestia — bez powiadomień.
- **Prywatność:** karta dopasowanej oferty nie pokazuje autora ani akcji zarządzania; profil aktualnie przypisanego członka pozostaje linkiem kontaktowym zgodnym z katalogiem.
- **Zakres dopasowania:** pierwsza wersja używa wyłącznie identycznej znormalizowanej nazwy. Nie stosuje dopasowania opisów, lokalizacji, promienia ani fuzzy matching.
- **Weryfikacja:** 86 testów widoków/encj/mapy/dopasowań oraz 72 testy migracji/resources/usług przechodzą. Tłumaczenia skompilowane; Ruff, Django check, `makemigrations --check`, build CSS, regression scan i UI guard przechodzą. Playwright nie był uruchamiany bez `E2E_BASE_URL`.

## 2026-10-18: Cutover PhysicalAsset i ResourceListing do Entity

- **Zmienione obszary:** fizyczny CRUD i formularz, agregacja mapy, zarządzanie ofertami/potrzebami, sygnały profilu, `LegacyEntityReference`, migracja `bookkeeping.0041`, testy i plany mapy/zasobów.
- **Co się zmieniło:** usunięto runtime modele `bookkeeping.PhysicalAsset` i `bookkeeping.ResourceListing` oraz dual-write. Fizyczne formularze i mapa korzystają wyłącznie z `Entity`; zarządzanie ofertami/potrzebami aktualizuje encje bez shadow rows. Stare URL-e i markery mapy nadal rozwiązują dawne ID przez `LegacyEntityReference`; nowe aktywa fizyczne mają trasy kanoniczne.
- **Integralność danych:** migracja dopisuje brakujące mapowania, zachowuje pełne lokalizacje i pola wpisów oraz zatrzymuje się przed usunięciem tabel przy błędnych lokalizacjach, rozbieżności danych lub osieroconych referencjach. Nie dopisuje historycznych autorów/właścicieli. `source_profile_id` przechowuje dawny profil shadow row wyłącznie na potrzeby rollbacku; bieżące przypisanie wspólnotowe pozostaje w `Entity`. Daty istniejących mapowanych encji pozostają autorytatywne, a daty niesparowanych wpisów są kopiowane.
- **Kaskada i prywatność:** `pre_delete` profilu usuwa wyłącznie przypisane mu, nie-wspólnotowe encje z legacy referencją; zasoby wspólnotowe pozostają. Mapa zachowuje dotychczasowy payload i nie pokazuje autora ani przypisania.
- **Odtworzenie:** rollback odtwarza stare wiersze oraz URL referencje bez wymyślania profilu. Jeśli historyczny profil wpisu wspólnotowego został już usunięty, pełne odtworzenie wymaga backupu SQLite. Agent nie uruchamiał migracji; później operator uruchomił `start_dev.py --full`. Read-only kontrola `db/db.sqlite3` potwierdziła zastosowanie `bookkeeping.0040`/`0041`, `resources.0007` i brak dawnych tabel. Produkcja nie była sprawdzana.
- **Weryfikacja:** 82 testy widoków, encji, mapy i migracji oraz 69 testów migracji/resources/usług przechodzą. `makemigrations --check`, Django check i Ruff przechodzą. CSS build, regression scan i UI guard przechodzą. Playwright nie był uruchamiany bez `E2E_BASE_URL`.

## 2026-10-17: Cutover finansów z Asset do Entity

- **Zmienione obszary:** model transakcji i formularze, CRUD jednostek finansowych, raporty/salda, feed/powiadomienia, seed demo, testy i migracja `bookkeeping.0040`.
- **Co się zmieniło:** `Transaction.entity` jest jedynym wymaganym FK, a `bookkeeping.Asset` nie istnieje już w modelu runtime. Migracja usuwa tabelę shadow oraz stary FK po preflight zgodności kodu, nazwy, symbolu, precyzji, waluty, domyślności i mapowań transakcji.
- **Bezpieczeństwo danych i kompatybilność:** preflight wymaga dokładnie jednego mapowania każdej jednostki legacy do finansowej encji oraz zgodności `Transaction.entity` z jednostką wynikającą ze starego FK `asset`; brak lub konflikt zatrzymuje migrację przed zmianą schematu, bez automatycznego rozstrzygania ani nadpisywania danych. Kwoty i istniejące transakcje pozostają niezmienione. Migracja wstecz odtwarza shadow rows i FK z zachowaniem PK; nowe encje otrzymują mapowane legacy ID. Stare URL-e nadal rozwiązują istniejące ID przez `LegacyEntityReference`; nowe jednostki mają kanoniczne URL-e encji. Agent nie uruchamiał migracji; późniejszy read-only odczyt po `start_dev.py --full` potwierdził `bookkeeping.0040` w lokalnym `db/db.sqlite3`; produkcja nie była sprawdzana.
- **Pozostałe reguły finansowe:** transakcja nadal chroni używaną jednostkę przez `PROTECT`; zapis odrzuca encję niefinansową; kod, waluta, precyzja i pojedyncza jednostka domyślna pozostają w `resources.Entity`.
- **Weryfikacja:** 32 testy migracji `bookkeeping/resources`, 100 testów modeli/usług/widoków bookkeeping i 163 testy cross-cutting przeszły. `makemigrations --check`, Django check, Ruff check/format, kompilacja tłumaczeń, build CSS, regression scan i UI guard przeszły.

## 2026-10-17: Wspólne wyszukiwanie encji zasobów

- **Zmienione obszary:** katalog `/bookkeeping/resource/`, współdzielona usługa zapytań `resources`, filtry UI oraz testy.
- **Co się zmieniło:** katalog może przeszukiwać encje finansowe, fizyczne i oferty/potrzeby po typie, nazwie/opisie, mieście/kraju/województwie, stanie i zakresie przypisania. Domyślny widok ofert i potrzeb pozostaje zgodny wstecznie.
- **Prywatność i uprawnienia:** wyniki fizyczne pokazują wyłącznie miasto i kraj, nigdy ulicę ani numer domu; autor nie jest ujawniany. Zamknięte oferty/potrzeby widzi wyłącznie osoba uprawniona do zarządzania nimi. Sugestie nazw pozostają ograniczone do typów zasobów.
- **Weryfikacja:** 54 testy `bookkeeping.tests.test_views`, testy Jest wyszukiwarki, Django check, Ruff, kompilacja polskich tłumaczeń, build CSS, regression scan i UI guard przechodzą.
- **Spodziewany efekt:** jeden katalog umożliwia wspólne wyszukiwanie typów `resources.Entity` bez dublowania modeli ani ujawniania szczegółowych lokalizacji.

## 2026-10-17: Katalog i CRUD zasobów na Entity

- **Zmienione obszary:** katalog publiczny, zarządzanie zasobami, filtry lokalizacji i właściciela oraz akcje archiwizacji/usuwania.
- **Co się zmieniło:** Katalog i nowy CRUD czytają/zapisują `resources.Entity`; formularz pozwala autorowi wybrać aktywnego członka albo całą wspólnotę. Publiczne filtrowanie nadal rozdziela oferty od potrzeb i respektuje lokalizację przypisanego członka.
- **Kompatybilność:** Stare URL-e `bookkeeping:resource_*` rozwiązują legacy PK przez `LegacyEntityReference`. Historyczne wpisy `ResourceListing` są synchronizowane; usunięcie starego wpisu/profilu usuwa jego encję członkowską, a zasób wspólnotowy pozostaje.
- **Uprawnienia:** Autor i przypisany członek mogą zarządzać treścią; przypisanie może zmieniać autor, a przy historycznym wpisie bez autora — dotychczasowy właściciel. Zasób wspólnotowy może zarządzać aktywny członek instancji.
- **Weryfikacja:** Przeszło 128 testów bookkeeping/resources/dashboard; Ruff, Django check i kontrola migracji przechodzą. CSS build, regression scan i UI guard przechodzą.
- **Zakres przejściowy:** `ResourceListing` pozostaje jako adapter dla starych rekordów i URL-i; wspólne wyszukiwanie wszystkich typów `Entity` oraz usunięcie modeli legacy są kolejnymi etapami.

## 2026-10-17: Synchronizacja ResourceListing z Entity

- **Zmienione obszary:** zapis ofert/potrzeb, archiwizacja, usuwanie wpisów oraz usuwanie profilu.
- **Co się zmieniło:** Dotychczasowe tworzenie, edycja i zamykanie `ResourceListing` aktualizują również przypisaną `Entity`; nowe wpisy dostają autora, a bieżący profil jest przypisaniem. Autor skopiowanych historycznych rekordów nadal pozostaje nieznany.
- **Usuwanie:** Odbiornik `post_delete` usuwa encję legacy, gdy źródłowy wpis znika — także przy kaskadowym usunięciu profilu — zachowując dotychczasowy `on_delete=CASCADE`.
- **Zakres przejściowy:** Katalog i formularze nadal czytają `ResourceListing`; pełne przełączenie widoczności, transferu przypisania do członka/społeczności i starych URL-i pozostaje następnym etapem.
- **Weryfikacja:** 124 testy bookkeeping/resources/dashboard przechodzą; Ruff, Django check i kontrola migracji przechodzą.

## 2026-10-17: CRUD jednostek finansowych przez Entity

- **Zmienione obszary:** formularz, lista, szczegóły, aktualizacja i usuwanie jednostek finansowych.
- **Co się zmieniło:** Lista oraz formularze tworzenia i edycji pracują na `resources.Entity`. Stare ścieżki URL przyjmują legacy PK i odnajdują encję przez `LegacyEntityReference`.
- **Zgodność:** Przy tworzeniu i edycji utrzymywany jest shadow `bookkeeping.Asset`, potrzebny jeszcze dla legacy FK transakcji i starych adresów. Usunięcie pod starym URL usuwa shadow i encję atomowo; używane jednostki nadal chroni `PROTECT`.
- **Weryfikacja:** 123 testy bookkeeping/resources/dashboard przechodzą; Ruff, Django check i kontrola migracji przechodzą. CSS build, regression scan i UI guard przechodzą.
- **Zakres przejściowy:** Model `Asset` i `Transaction.asset` pozostają do czasu końcowego audytu dual-write, relacji i kompatybilnych URL-i.

## 2026-10-17: Odczyt finansów przez Entity

- **Zmienione obszary:** formularz transakcji, agregacje sald i raportów, pulpit, feed oraz prezentacja transakcji.
- **Co się zmieniło:** Formularz wybiera `Entity`, a salda, pivot raportu, pulpit, feed i widoki transakcji czytają dane finansowe z tego samego modelu. Zapis mapuje wybraną encję z powrotem na stare `Asset` przez `LegacyEntityReference`, dzięki czemu dotychczasowy FK pozostaje spójny.
- **Zachowana semantyka:** Nie zmieniono sumowania wpływów/wydatków, filtrów, sortowania jednostki domyślnej, dokładności kwot ani ochrony przed usuwaniem aktywa użytego w transakcji.
- **Weryfikacja:** 102 testy dotkniętych modeli, usług, widoków, dashboardu i migracji przechodzą; Ruff, Django check, kontrola migracji, build CSS, regression scan i UI guard przechodzą.
- **Zakres przejściowy:** Legacy `Transaction.asset` i zarządzanie `bookkeeping.Asset` pozostają dla zgodności. Ich usunięcie wymaga osobnego końcowego cutoveru.

## 2026-10-17: Dual-write aktywów finansowych i transakcji

- **Zmienione obszary:** synchronizacja finansowego `Asset`, zapis `Transaction` i testy CRUD/finansów.
- **Co się zmieniło:** CRUD jednostek finansowych synchronizuje `Entity` przy tworzeniu, edycji i usuwaniu. Zapis `Transaction` ustawia nowe `entity_id` na podstawie legacy `asset`, również dla transakcji tworzonych przez dotychczasowy interfejs.
- **Ochrona zgodności:** Stary FK `Transaction.asset`, formularze, raporty i usługi pozostają aktywne; transakcje nadal chronią używaną jednostkę. Ustawienie domyślne jest synchronizowane z zachowaniem istniejącej reguły pojedynczej jednostki.
- **Weryfikacja:** 116 testów wybranych z modeli, usług, widoków i migracji przechodzi; Django check, kontrola migracji i Ruff przechodzą.
- **Spodziewany efekt:** Nowe i edytowane dane finansowe są gotowe do późniejszego odczytu z `Entity`, bez jednoczesnego przełączania raportów i rozliczeń.

## 2026-10-17: Wstępne powiązanie transakcji z Entity

- **Zmienione obszary:** model `Transaction`, migracje `bookkeeping.0038`–`0039` i testy migracji.
- **Co się zmieniło:** Dodano nullable FK `Transaction.entity` do finansowej encji i jednorazowo wypełniono go przez mapowanie starego `Asset`/PK. Migracja zatrzymuje się, jeśli nie potrafi znaleźć encji dla któregokolwiek aktywa transakcji.
- **Bezpieczeństwo finansów:** Istniejący FK `Transaction.asset`, kwoty i zachowanie dotychczasowych usług pozostają bez zmian. Migracja odwrotna czyści wyłącznie nowe powiązanie.
- **Zakres przejściowy:** Dotychczasowy kod tworzący transakcje jeszcze nie uzupełnia `entity`; trzeba wdrożyć dual-write albo przełączyć formularze i usługi przed uczynieniem pola wymaganym.
- **Weryfikacja:** 26 testów dotkniętych migracji i encji przechodzi, w tym brak mapowania, rollback, zachowanie kwoty i starego FK; Ruff, Django check i kontrola migracji przechodzą.
- **Spodziewany efekt:** Każda istniejąca transakcja ma sprawdzalne powiązanie z Entity, bez odcięcia aktualnej ścieżki finansowej.

## 2026-10-17: Kopia finansowych Asset do Entity

- **Zmienione obszary:** ograniczenia unikalności zasobów, migracja finansowych `Asset` oraz testy danych i relacji.
- **Co się zmieniło:** Jednostki finansowe są kopiowane do `resources.Entity` z kodem, nazwą, symbolem, precyzją, flagą waluty i ustawieniem domyślnym. Mapowanie starego modelu/PK rozróżnia ich identyfikatory od zasobów i aktywów fizycznych.
- **Bezpieczeństwo finansów:** Transakcje nadal wskazują starą tabelę `Asset`; migracja ich nie przepisuje ani nie usuwa danych źródłowych. Test potwierdza zachowanie relacji i kwoty.
- **Zakres przejściowy:** Formularze, raporty i usługi finansowe nadal używają `bookkeeping.Asset`. Przełączenie klucza `Transaction.asset` pozostaje osobnym etapem.
- **Weryfikacja:** 21 testów `resources` przechodzi, w tym trzy migracje danych w przód/wstecz; Ruff, Django check i kontrola migracji przechodzą.
- **Spodziewany efekt:** Dane wszystkich trzech starych modeli mają addytywne kopie w `Entity`; dotychczasowe CRUD i rozliczenia działają bez zmian.

## 2026-10-17: Kopia ResourceListing do Entity

- **Zmienione obszary:** ograniczenia unikalności encji, migracja `bookkeeping.ResourceListing` oraz testy migracji.
- **Co się zmieniło:** Istniejące wpisy ofert/potrzeb są kopiowane do `resources.Entity` z typem, opisem, statusem zamknięcia, datami i bieżącym profilem jako przypisanym członkiem. Mapowanie modelu/PK zachowuje tożsamość źródła; historyczny autor pozostaje nieznany.
- **Integralność:** Unikalność nazwy bez rozróżniania wielkości liter obowiązuje w obrębie przypisanego członka i typu, a dla współwłasności społeczności — w obrębie typu. Migracja zachowuje tabelę źródłową i jest odwracalna.
- **Zakres przejściowy:** Katalog i CRUD nadal używają `ResourceListing`; kopia `Entity` nie jest jeszcze udostępniana jako druga lista. Przed cutoverem trzeba synchronizować zmiany legacy oraz zachować dotychczasowe usuwanie wpisów przy usunięciu profilu.
- **Weryfikacja:** 19 testów `resources` przechodzi, w tym migracje fizycznych aktywów i wpisów w przód/wstecz; Ruff i kontrola migracji przechodzą.
- **Spodziewany efekt:** Dane ofert i potrzeb mają kopię w wspólnym modelu, bez zmiany aktualnego katalogu ani polityki usuwania kont.

## 2026-10-17: Cutover fizycznych aktywów i mapy

- **Zmienione obszary:** formularz i widoki fizycznych aktywów, synchronizacja `resources.Entity`, agregacja mapy, tłumaczenia i testy.
- **Co się zmieniło:** Nowe fizyczne aktywo zapisuje równolegle stary rekord i encję z autorem oraz jawnym przypisaniem do aktywnego członka albo całej społeczności w jednej transakcji. Aktualizacja synchronizuje pola lokalizacji; przypisanie może zmienić tylko autor encji.
- **Mapa:** Rekordy z mapowaniem są renderowane z `Entity`; rekordy legacy bez mapowania pozostają fallbackiem. Link do szczegółów nadal korzysta ze starego PK, a autor i przypisanie nie trafiają do payloadu.
- **Zakres przejściowy:** Stara tabela nie została usunięta. Zwykli zalogowani zachowują dotychczasową edycję pól aktywa, ale pola przypisania nie są dostępne osobom innym niż autor.
- **Weryfikacja:** 36 wybranych testów dotkniętych modułów, Django check, kontrola migracji, Ruff, build CSS, regression scan, UI guard i kompilacja tłumaczeń przeszły.
- **Spodziewany efekt:** Mapa i nowe zapisy korzystają z `Entity`, stare linki i rekordy bez mapowania nadal działają, a przyszłe odcięcie tabeli legacy pozostaje osobnym etapem.

## 2026-10-17: Migracja fizycznych aktywów do Entity

- **Zmienione obszary:** model mapowania `resources.LegacyEntityReference`, migracja danych oraz testy migracji.
- **Co się zmieniło:** Istniejące `bookkeeping.PhysicalAsset` są kopiowane do `resources.Entity` typu `physical_asset` wraz z krajem i pełnymi polami adresowymi. Mapowanie `(model źródłowy, PK)` zachowuje identyfikator potrzebny do kompatybilności; stary rekord pozostaje bez zmian.
- **Integralność danych:** Migracja zatrzymuje się na pustej miejscowości zamiast tworzyć niewalidowalną encję. Nie przypisuje historycznych autora ani właściciela; migracja odwrotna usuwa wyłącznie skopiowane encje.
- **Bezpieczne przełączenie:** Mapa nadal czyta `PhysicalAsset`, ponieważ bieżące formularze zapisują stary model i nie zbierają autora ani przypisania. Przełączenie źródła mapy nastąpi po dostosowaniu zapisu, by nowe i edytowane obiekty nie znikały ani nie miały wymyślonej własności.
- **Weryfikacja:** 15 testów `resources` przechodzi, w tym migracja w przód/wstecz i kolizje PK między modelami; Ruff, kontrola migracji i `git diff --check` przechodzą.
- **Spodziewany efekt:** Dane fizycznych aktywów mają bezpieczną kopię w nowym modelu, bez zmiany obecnego UI, mapy ani tabel źródłowych.

## 2026-10-17: Pierwszy etap wspólnego modelu Entity

- **Zmienione obszary:** nowa aplikacja `resources`, konfiguracja Django i test discovery.
- **Co się zmieniło:** Dodano `resources.Entity` z typami finansowym, fizycznym i ofertowo-potrzebowym, autorem, przypisaniem członkowi lub całej społeczności oraz walidacją pól specyficznych dla typów. Własność wspólnotowa jest flagą instancji, nie rekordem `auth.Group`; usunięcie przypisanego profilu nie usuwa encji.
- **Integralność finansów:** Zachowano kod, symbol, jednostkę domyślną i jej zachowanie awaryjne (najstarsza jednostka). Ograniczenia bazy pilnują pojedynczej jednostki domyślnej, poprawnego przypisania i wymaganej lokalizacji aktywa fizycznego.
- **Zakres migracji:** Utworzono wyłącznie nową tabelę. Stare modele, dane, transakcje, raporty i mapa pozostają nietknięte do kolejnych etapów.
- **Weryfikacja:** 12 testów `resources` przechodzi; Django check, Ruff, kontrola migracji (`makemigrations --check --dry-run`) i `git diff --check` przechodzą.
- **Spodziewany efekt:** Istnieje przetestowany fundament pod etapowe przenoszenie danych i konsumentów bez zmiany bieżącego zachowania aplikacji.

## 2026-10-17: Zmiana etykiety modułu w menu

- **Zmienione obszary:** główna nawigacja.
- **Co się zmieniło:** Etykieta pozycji prowadzącej do modułu rozliczeń używa teraz istniejącego tłumaczenia `Resources` („Zasoby”) zamiast `Finance`.
- **Spodziewany efekt:** Menu główne i bieżąca nazwa modułu pokazują „Zasoby”; adres i działanie linku pozostają bez zmian.

## 2026-10-17: Naprawa uwierzytelniania kafelków mapy

- **Przyczyna:** Stadia zwracała 401, a OSM blokował kafelki. Django używa globalnej polityki `same-origin`, więc przeglądarka pomijała Referer przy żądaniach międzydomenowych.
- **Zmiana:** Warstwa Leaflet ustawia `referrerPolicy: 'origin'` tylko dla obrazów kafelków. Dostawca otrzymuje origin strony (host/port), bez ścieżki ani query; globalne ustawienia bezpieczeństwa pozostają niezmienione. W `DEBUG=True` domyślnie używamy Stadia Alidade Smooth (dopuszczone keyless na localhost); produkcja zachowuje domyślny OSM. URL i atrybucja są konfigurowalne.
- **Weryfikacja:** Ustawienia wyboru providera sprawdzono w odizolowanych procesach dla `DEBUG=True` i `False`; test Jest sprawdza politykę Referer warstwy. Nie wykonywano żądań kafelków ani geokodera.

## 2026-10-17: Integracja Leaflet i mapy społeczności

- **Zmienione obszary:** widoki/routes mapy, stepper obywateli, Leaflet/webpack-free CSS build, geokodowanie, konfiguracja providerów, Docker, szablony oraz testy.
- **Co się zmieniło:** Dodano publiczną stronę `/obywatele/mapa/` i endpoint danych. Strona członka używa steppera; strona gościa nie zawiera steppera ani danych o typach. Punkty gościa są nieklikalne i zawierają wyłącznie unikalne współrzędne; widok aktywnego użytkownika pokazuje grupowane typy, popupy i listę nieoznaczonych lokalizacji. Leaflet jest lokalnym assetem bundlowanym w Tailwind; mapa używa konfigurowalnych kafelków HTTPS i widocznej atrybucji OSM.
- **Geokodowanie:** Nominatim dostaje wyłącznie kraj, miasto oraz opcjonalnie ulicę/numer domu; adres szczegółowy jest uznawany tylko po dokładnym dopasowaniu, w innym razie używany jest punkt miasta. Cache przechowuje sukces przez 30 dni, błąd przez 15 minut, a współdzielony limiter wymusza 1,1 s między żądaniami. Goście korzystają tylko z cache; `MAP_GEOCODING_ENABLED` jest domyślnie `False`, dopóki nie potwierdzimy ruchu i liczby lokalizacji.
- **Warunki dostawcy:** Sprawdzono oficjalną politykę kafelków OSM i Nominatim; nie wykonano żądań geokodera ani kafelków. Przed włączeniem geokodowania trzeba jeszcze ocenić przewidywaną liczbę zapytań.
- **Weryfikacja:** 14 testów Django mapy/adresu i 3 testy Jest, Django check, kontrola migracji, collectstatic do katalogu tymczasowego, Ruff, kompilacja tłumaczeń, build CSS, regression scan i UI guard przeszły. Playwright nie był uruchamiany, bo pełny runner modyfikuje `.env` i wykonuje `collectstatic --clear`.
- **Uwaga o zależnościach:** `npm install leaflet` zgłosił 32 wysokie podatności w całym drzewie npm; nie uruchamiano automatycznego upgrade'u zależności poza zakresem mapy.
- **Spodziewany efekt:** Mapa działa bez ujawniania danych lokalizacyjnych gościom poza współrzędnymi; ruch geokodera pozostaje wyłączony do chwili potwierdzenia skali.

## 2026-10-17: Poprawa semantyki list adresowych w szczegółach

- **Zmienione obszary:** szablony szczegółów obywatela, partnera i aktywa fizycznego.
- **Co się zmieniło:** Listy `<dl>` są renderowane bez białych znaków między elementami; warunek aktywnego konta znajduje się wewnątrz wartości `<dd>`, a nie bezpośrednio w `<dl>`. Nieaktywni użytkownicy widzą kreskę zamiast numeru mieszkania.
- **Weryfikacja:** Cztery testy widoków szczegółów, build CSS, UI guard i regression scan przeszły.
- **Pozostałe ostrzeżenia:** Ostrzeżenia Edge Tools z `home.html` dotyczą surowych bloków Django wewnątrz list; ten plik nie został zmieniony.

## 2026-10-17: Agregacja lokalizacji mapy i adresy szczegółów

- **Zmienione obszary:** szczegóły profilu obywatela, nowy serwis `obywatele.map_data`, testy i checklistę planu mapy.
- **Co się zmieniło:** Szczegóły profilu pokazują kraj, ulicę i numer domu; numer mieszkania jest widoczny tylko dla aktywnego konta. Serwis zbiera dozwolone pola aktywnych obywateli, partnerów i aktywów fizycznych, dokładnie normalizuje kraj partnera oraz normalizuje miasto wyłącznie do porównań. Budowniczy payloadu oddziela gościnne unikalne współrzędne od grupowanych markerów i nieoznaczonych wpisów dla aktywnych użytkowników.
- **Granice zakresu:** Geokoder nie jest jeszcze podłączony, a payload nie jest wystawiony przez trasę mapy. Funkcja przyjmuje resolver współrzędnych, co pozwala testować prywatność i grupowanie bez połączeń sieciowych. Nie wyszukiwano ani nie wywoływano publicznego Nominatim.
- **Weryfikacja:** 3 testy agregacji/payloadu oraz 2 testy szczegółów adresu przeszły; wcześniej przeszło 88 testów bookkeeping. Django check, kontrola migracji, Ruff, build CSS, regression scan i UI guard przeszły.
- **Spodziewany efekt:** Kolejna warstwa mapy otrzymuje małe, allowlistowane rekordy z ustalonym podziałem gość/członek i bez kontaktów ani danych finansowych.

## 2026-10-17: Model danych i CRUD aktywów fizycznych mapy

- **Zmienione obszary:** modele i migracja `bookkeeping`, formularze partnera i aktywa fizycznego, widoki, routing, stepper, szablony, testy oraz plan mapy.
- **Co się zmieniło:** Dodano odrębny `PhysicalAsset` z wymaganym krajem i miastem oraz opcjonalnym adresem szczegółowym, wraz z listą, stroną szczegółów, tworzeniem i edycją. `Partner` otrzymał analogiczne pola ulicy, numeru domu i mieszkania; dotychczasowy tekst `Partner.address` pozostaje bez zmian i nie jest automatycznie parsowany. Szczegóły obywatela pokazują teraz kraj i adres strukturalny, a numer mieszkania tylko przy aktywnym koncie.
- **Dostęp i separacja:** Widoki fizycznych aktywów korzystają z istniejących uprawnień bookkeeping. Numer mieszkania pokazuje się wyłącznie aktywnemu użytkownikowi. Finansowy model `Asset` oraz transakcje nie zostały zmienione.
- **Weryfikacja:** 88 testów bookkeeping, Ruff check/format, Django check, kontrola spójności migracji, kompilacja tłumaczeń, build CSS, regression scan i UI guard przeszły.
- **Spodziewany efekt:** Partnerzy i fizyczne aktywa mogą przechowywać dane lokalizacyjne potrzebne do późniejszej agregacji mapy bez mieszania nieruchomości z jednostkami finansowymi.

## 2026-10-17: Start realizacji planu mapy — lokalizacja profilu

- **Zmienione obszary:** model i migracja profilu obywatela, katalog krajów, formularze i szablony ustawień/onboardingu/zaproszeń/edycji kandydata, dokumentacja onboardingu, testy oraz plan mapy.
- **Co się zmieniło:** Profil przechowuje kraj z katalogu `Country` (domyślnie Polska) oraz opcjonalną ulicę, numer domu i numer mieszkania. Migracja uzupełnia kraje istniejących profili na podstawie regionu albo przypisuje Polskę oraz zasila katalog kodami ISO z `pycountry`. Formularze ustawień, onboardingu i zaproszenia zapisują te pola; wybór regionu pozostaje opcjonalny i ograniczony do kraju profilu.
- **Granice zakresu:** Nie dodano jeszcze modelu fizycznych aktywów, pól lokalizacji partnerów, geokodowania, publicznego API ani widoku mapy. Adres profilu nie jest na tym etapie ujawniany w widokach publicznych.
- **Weryfikacja:** 27 wybranych testów widoków/formularzy przeszło. Ruff check/format, Django check, kontrola spójności migracji, kompilacja tłumaczeń, build CSS, regression scan i UI guard przeszły.
- **Spodziewany efekt:** Dane profilu mają spójne źródło kraju i miejsce na szczegóły adresowe, potrzebne do dalszej agregacji mapy, bez łączenia kraju lokalizacji z `phone_country`.

## 2026-10-17: Akceptacja obywateli na aktywnej liście

- **Zmienione obszary:** przygotowanie danych w widoku obywateli, lista i siatka aktywnych użytkowników, testy i tłumaczenia.
- **Co się zmieniło:** Lista zbiorczo odczytuje ocenę bieżącego użytkownika dla aktywnych obywateli i pokazuje wspólny badge akceptacji, sprzeciwu lub neutralnego stosunku. Odczyt nie tworzy ani nie zmienia ocen, a ich wartość jest interpretowana po znaku.
- **Testy:** Dodano test stanów dodatniego, ujemnego i neutralnego, w tym braku własnej oceny.
- **Spodziewany efekt:** Na liście aktywnych obywateli użytkownik widzi swoją ocenę w obu układach, bez wpływu na reputację lub logikę członkostwa.

## 2026-10-17: Poprawki po przeglądzie katalogu zasobów

- **Zmienione obszary:** filtrowanie i paginacja katalogu `bookkeeping`, karta zarządzania, testy widoków, plan zasobów oraz wygenerowany CSS.
- **Co się zmieniło:** Filtr `profile` odrzuca niepoprawne i przekraczające zakres identyfikatory zamiast kończyć żądanie błędem 500. Liczniki ofert i potrzeb dotyczą całego filtrowanego zbioru, a na stronach bez danego rodzaju wpisu nie pojawia się fałszywy komunikat o braku wyników. Akcje wpisu zawijają się i przechodzą pod opisem na małym ekranie; puste sekcje używają neutralnego tekstu o braku wpisów.
- **Decyzja produktowa:** Sam filtr miejscowości nadal pokazuje także osoby bez żadnej oferty lub potrzeby, w oddzielnej sekcji. Zachowanie jest potwierdzone testem i opisane w planie.
- **Weryfikacja:** 15 testów `ResourceListingViewTests`, Ruff check/format, build CSS, regression scan, UI guard i `git diff --check` przeszły. Nie uruchamiano ponownie pełnego runnera; ostatnio zatrzymał się na niezwiązanym teście `board`, więc Playwright pozostaje niesprawdzony.
- **Spodziewany efekt:** Katalog nie kończy się błędem na błędnym filtrze, poprawnie opisuje wielostronicowe wyniki i jest czytelniejszy na telefonach bez zmiany widoczności osób filtrowanych po mieście.

## 2026-10-17: Ręczne zamykanie wpisów zasobów

- **Zmienione obszary:** model i migracja `bookkeeping.ResourceListing`, widoki oraz formularz zarządzania, testy i plan zasobów.
- **Co się zmieniło:** Dodano `is_closed`, domyślnie `False`; właściciel może zamknąć lub przywrócić wpis. Katalog pokazuje tylko aktywne wpisy, a strona zarządzania rozdziela aktywne i zamknięte. Zamknięcie nie usuwa danych i nie wygasa automatycznie.
- **Bezpieczeństwo i dane:** Tylko właściciel może zamykać, przywracać, edytować i usuwać wpis. Migracja `bookkeeping.0036` zachowuje dotychczasowe wpisy jako aktywne.
- **Weryfikacja:** 35 testów dotkniętych widoków, migracji, dashboardu i profilu przeszło. CSS build, regression scan, UI guard, Ruff, Django check, kompilacja tłumaczeń i collectstatic przeszły. Pełny pytest: 1356 testów przeszło, jeden niezwiązany test `tests/test_board.py::test_system_post_visible_to_authenticated_users_regardless_of_author_or_private_flag` zawiódł (302 zamiast 404). Playwright nie został uruchomiony, bo runner zatrzymał się na tym błędzie; `E2E_BASE_URL` nie jest skonfigurowany.
- **Spodziewany efekt:** Właściciel może wycofać nieaktualną ofertę z katalogu bez kasowania jej i przywrócić ją później.

## 2026-10-17: Przeniesienie ofert i potrzeb użytkowników do bookkeeping

- **Zmienione obszary:** modele i migracje `bookkeeping`/`obywatele`, katalog oraz formularz zasobów, ustawienia profilu, lista i szczegóły obywateli, nawigacja, dashboard, testy, wyjątki bezpieczeństwa i plany funkcji.
- **Co się zmieniło:** `ResourceListing` w `bookkeeping` przechowuje cztery dotychczasowe typy wpisów wraz z nazwą, opisem, właścicielem i znacznikami czasu. Migracja kopiuje rekordy z `obywatele.ResourceAssignment`, zachowując identyfikatory i dane, a następnie usuwa stary model. Stare adresy przekierowują do nowych widoków. Własne wpisy nadal może edytować i usuwać wyłącznie ich właściciel.
- **UI i granice domen:** katalog i formularz są w Finanse; profil osobisty zawiera tylko odnośnik do zarządzania wpisami. Listy i szczegóły obywateli również pokazują odnośnik, a nie treść wpisów. `ResourceListing` pozostaje oddzielony od finansowego `Asset`, transakcji i fizycznych markerów mapy; aktualizowano spójnie `PLAN_ZASOBY_UŻYTKOWNIKÓW.md` i `PLAN_MAPA.md`.
- **Testy:** 33 testy widoków, formularzy, dashboardu i migracji przeszły. Build CSS, regression scan, UI guard, Ruff, Django check, kompilacja tłumaczeń, collectstatic i 315 testów Jest przeszły. Pełny pytest: 1354 testy przeszły, jeden niezwiązany test `tests/test_board.py::test_system_post_visible_to_authenticated_users_regardless_of_author_or_private_flag` zawiódł (anonimowe żądanie otrzymało 302 zamiast 404). Runner zakończył się na pytest, więc Playwright nie został uruchomiony; `E2E_BASE_URL` nie jest skonfigurowany.
- **Spodziewany efekt:** użytkownicy dodają i przeglądają oferty oraz potrzeby w bookkeeping, a profil nie duplikuje ich treści. Dotychczasowe wpisy są zachowane w nowym modelu bez zmiany właściciela ani uprawnień.

## 2026-10-17: Synchronizacja planów mapy i zasobów

- **Zmienione pliki:** `docs/ongoing/PLAN_MAPA.md` oraz `docs/ongoing/PLAN_ZASOBY_UŻYTKOWNIKÓW.md`.
- **Co się zmieniło:** Plany wskazują teraz wspólny `ProfileForm` jako miejsce przyszłych pól lokalizacji profilu. Mapa obsługuje kraj, szczegółowy adres i geokodowanie; katalog zasobów pozostaje przy filtrach miejscowości i województwa i nie ujawnia dokładnego adresu ani telefonu.
- **Granice zakresu:** Wpisy ofert i potrzeb `ResourceAssignment` nie są markerami mapy. Fizyczne aktywa mapy pozostają odrębnymi rekordami `bookkeeping`, niezależnymi od finansowego `Asset` i zasobów użytkowników. Lokalizacja profilu na mapie nie stanowi zasięgu oferty.
- **Spodziewany efekt:** Realizacja obu planów nie dubluje formularzy ani źródeł danych i zachowuje rozdział zasad widoczności mapy oraz katalogu zasobów.

## 2026-10-17: Oddzielenie edycji profilu od zarządzania zasobami

- **Zmienione obszary:** widoki i szablony `obywatele`, testy widoków oraz plan zasobów.
- **Co się zmieniło:** edycja `ProfileForm` jest dostępna w ustawieniach profilu (`/obywatele/settings/?edit=details`), a `/obywatele/my_assets/` służy wyłącznie do zarządzania wpisami zasobów. Widok ustawień prezentuje dane profilu i zasoby w osobnych sekcjach. Zapis danych profilu aktualizuje nazwę użytkownika i profil w jednej transakcji.
- **Decyzja projektowa:** wspólny słownik zasobów został pominięty zgodnie z decyzją użytkownika; wpisy zachowują swobodne nazwy.
- **Testy:** dodano testy osobnego formularza profilu, walidacji, uprawnień i braku zapisu profilu z widoku zasobów.
- **Weryfikacja:** 17 testów dotkniętych widoków przeszło. Build CSS, regression scan, UI guard, Ruff, Django check, kompilacja tłumaczeń i collectstatic przeszły. Pełny pytest: 1351 testów przeszło, jeden niezwiązany test `tests/test_board.py::test_system_post_visible_to_authenticated_users_regardless_of_author_or_private_flag` zawiódł (anonimowe żądanie otrzymało przekierowanie logowania zamiast 404). Osobny Jest: 315 testów przeszło. Playwright nie został uruchomiony: pełny runner zatrzymał się na błędzie pytest, a `E2E_BASE_URL` nie jest skonfigurowany.
- **Spodziewany efekt:** użytkownik edytuje dane kontaktowe i profil niezależnie od wpisów zasobów, bez zmiany modelu zasobów ani dodawania nowego endpointu.

## 2026-10-15: Kanoniczne maile i normalizacja instancji produkcyjnych

- **Zmienione obszary:** sygnały `obywatele`, komenda i skrypt operacyjny oraz testy `obywatele`.
- **Co się zmieniło:** sygnały `pre_save` zapisują e-maile `User` i `EmailAddress` małymi literami; menedżery allauth również kanonizują zmieniane adresy. Po tej kanonizacji usunięto własne formularze resetu/kodu i własny etap weryfikacji — standardowe wyszukiwanie allauth wystarcza. Komenda `normalize_email_case` domyślnie tylko audytuje; blokuje kolizje między kontami i scali wyłącznie duplikaty tego samego konta z jednym zweryfikowanym głównym adresem oraz niezweryfikowanymi, niegłównymi kopiami bez rekordów `EmailConfirmation`. Zapis wymaga `--apply --confirm` i jest transakcyjny. Skrypt `scripts/normalize_email_case_all_instances.sh` sprawdza HTTP deploymenty instancji, wykonuje audyt na wszystkich przed zapisem i wymaga potwierdzenia backupów.
- **Uzasadnienie:** normalizacja wyłącznie w formularzach nie chroniła zapisów przez admina ani bezpośrednie `save()`. Historyczne dane wymagają osobnej, kontrolowanej normalizacji na każdej izolowanej bazie produkcyjnej; konflikty adresów muszą zatrzymać całą fazę audytu przed zmianą którejkolwiek instancji.
- **Bezpieczeństwo operacyjne:** nie uruchamiano skryptu na produkcji. Wykonanie `--apply` jest osobną decyzją operatora; najpierw trzeba przejrzeć dry-run i wykonać backup każdej instancji. Aktualizacja jest transakcyjna per baza i idempotentna do bezpiecznego ponowienia po częściowym błędzie, ale nie stanowi globalnej transakcji między instancjami. Normalizacja nie wysyła ponownie potwierdzeń; oczekujące linki dla niezaufanych adresów mogą wymagać ponownej wysyłki.
- **Weryfikacja:** 18 testów auth/e-mail i komendy, Django check, Ruff check/format, `git diff --check` i `bash -n scripts/normalize_email_case_all_instances.sh` przeszły przez `.venv`; testy używały bazy testowej w pamięci. Produkcyjnego skryptu nie uruchamiano.
- **Spodziewany efekt:** adresy wprowadzane lub zmieniane przez standardowe ścieżki aplikacji są przechowywane małymi literami; wszystkie istniejące instancje można audytować zbiorczo i naprawić bez automatycznego rozstrzygania kolizji.

## 2026-10-15: Odporne logowanie i reset e-maili na wielkość liter

- **Zmienione obszary:** backend logowania, formularze i etap weryfikacji e-maila django-allauth, formularze zaproszeń/rejestracji oraz testy `obywatele`.
- **Co się zmieniło:** logowanie hasłem przyjmuje pole `email` przekazywane przez allauth; wyszukiwanie przy resecie hasła i żądaniu kodu dopasowuje bez uwzględniania wielkości liter w `User.email` i `EmailAddress.email`. Etap weryfikacji allauth również rozpoznaje zweryfikowane adresy zapisane z inną wielkością liter. Nowe konta z formularzy zaproszeń i rejestracji zapisują e-mail małymi literami.
- **Uzasadnienie:** allauth normalizował wpisany adres do małych liter, ale wykonywał dokładne zapytania. W efekcie istniało konto i zweryfikowany e-mail, lecz hasło mogło nie zostać uwierzytelnione, a po odzyskaniu dostępu weryfikacja mogła przekierować użytkownika do onboardingu bez tokenu.
- **Weryfikacja:** 10 testów `DebugSkipAuthTest`, `LoginByCodePageTest` i `CaseInsensitiveEmailResetTest`, Django check, Ruff check/format oraz `git diff --check` przeszły. Testy działały przez `.venv` na bazie testowej w pamięci, z lokalnym backendem poczty i wyłączonym schedulerem.
- **Spodziewany efekt:** logowanie hasłem, reset hasła i logowanie kodem akceptują adres niezależnie od wielkości liter; zaakceptowane logowanie nie trafia błędnie do potwierdzenia e-maila; nowe adresy są zapisywane w postaci kanonicznej.

## 2026-10-11: Anonimizacja autora w zdarzeniu edycji czatu

- **Zmienione obszary:** payload WebSocket `chat.edit` i testy `chat`.
- **Co się zmieniło:** dla anonimowych wiadomości zdarzenie edycji zachowuje dotychczasowy zestaw pól, ale wysyła `user_id: null`, `username: "Anonymous"` i `display_name: "Anonymous"`. Edycje wiadomości nieanonimowych nadal zawierają dane autora.
- **Uzasadnienie:** handler `chat.edit` pomijał serializer chroniący anonimowość i ujawniał odbiorcom pokoju ID oraz nazwę konta autora.
- **Weryfikacja:** nowy test regresyjny odtwarzał ujawnienie przed poprawką; 21 testów `chat/tests/test_command_handlers.py`, Ruff check/format oraz `git diff --check` przeszły.
- **Spodziewany efekt:** uczestnicy pokoju nie otrzymują tożsamości autora anonimowej wiadomości w aktualizacji jej treści lub załączników.

## 2026-10-11: Logowanie kodem e-mail bez hasła

- **Zmienione obszary:** konfiguracja django-allauth, szablony logowania i formularzy kodu, testy `obywatele`.
- **Co się zmieniło:** włączono opcjonalne logowanie kodem jednorazowym wysyłanym na e-mail i skrócono go z 8 do 6 niejednoznacznych liter w układzie 3-3. Na dotychczasowym ekranie pozostaje logowanie hasłem, a użytkownik może wybrać osobny formularz prośby o kod i formularz jego potwierdzenia. Formularze korzystają ze wspólnego wyglądu Tailwind i standardowych tłumaczeń allauth; rejestracja/onboarding pozostały bez zmian.
- **Bezpieczeństwo:** pozostawiono domyślne limity allauth: 3 próby i 3 minuty ważności. Test integracyjny potwierdza, że samo zgłoszenie kodu nie loguje użytkownika, a poprawny kod loguje go dopiero po potwierdzeniu.
- **Weryfikacja:** po skróceniu kodu przeszły 3 testy logowania kodem, Django check, Ruff check/format i `git diff --check`; wcześniej przeszły też build CSS, regression scan i UI guard. Pełny runner: 1277 testów pytest przeszło, 2 zawiodły — `ProfileFormErrorViewTest.test_change_username_renders_form_for_authenticated_user` (powtarza się także samodzielnie) oraz `TaskCreateViewTest.test_get_returns_form` (przechodzi samodzielnie; awaria równoległa dotyczyła współdzielonego pliku favicon). Playwright: 35 zaliczonych, 16 pominiętych.
- **Spodziewany efekt:** osoby mające problem z resetowaniem hasła mogą logować się bez hasła, odbierając kod na e-mail; jego poprawne wpisanie potwierdza dostęp do skrzynki. Dotychczasowe logowanie hasłem pozostaje dostępne.

## 2026-10-10: Zakończenie naprawy nazw i cyklu życia pokoi czatu

- **Zmienione obszary:** klasyfikacja DM, feed i powiadomienia czatu, cykl życia pokoi, audyt/naprawa danych, ograniczenia relacji i testy `chat` oraz integracji.
- **Co się zmieniło:** `public` oznacza wyłącznie dostęp; pokoje źródłowe są rozpoznawane po `source_app`, a prawdziwe DM-y są bez źródła i mają dwóch członków. Ograniczenia bazy chronią unikalne powiązania pokoi z obiektami. Nowo przyjęci członkowie są dodawani do istniejących pokojów dokumentów, również archiwalnych. Pokoje źródłowe mogą być archiwizowane, ale scheduler ich nie usuwa.
- **Naprawa danych i decyzje:** audyt `repair_discussion_rooms --audit` jest tylko do odczytu. Kontrolowana naprawa po przeglądzie raportu i potwierdzeniu backupu uzupełniła jednoznaczne braki; nie usuwano wiadomości ani niejednoznacznych pokojów. Członkostwa nieaktywnych kont pozostają zachowane, ponieważ konto może zostać przywrócone. Jednoosobowe DM-y pozostają do ręcznej oceny; nie są automatycznie kasowane.
- **Audyt wdrożonych instancji przekazany przez użytkownika:** sprawdzono 13/13 podów, 9 bez uwag. Pozostałe 4 zgłosiły 11 członkostw nieaktywnych kont w pokojach dokumentów (`instance-12`: 3, `instance-6`: 8) oraz 24 prywatne DM-y z 0–1 członkiem (`instance-3`: 6, `instance-6`: 17, `instance-8`: 1). Wśród DM-ów było 21 pokoi z jednym członkiem i 3 bez członków. Audyt nie zmienił danych. Ostrzeżenia o nieaktywnych członkach są zgodne z przyjętą polityką.
- **Puste DM-y:** niechronione prywatne pokoje bez członków są usuwane wraz z historią po `delete_inactive_user_after` dniach (obecnie 30). Retencja liczona jest od nowszej z dat ostatniej aktywności i wiadomości; usunięcie ostatniego członka odświeża znacznik aktywności. Pokoje publiczne, źródłowe, systemowe, federacyjne, Inbox i chronione są wykluczone. Ta zmiana kodu została wprowadzona po przekazanym audycie i zacznie działać po wdrożeniu nowej wersji. Stare pokoje `instance-6` #133/#147/#148 i `instance-8` #79 są kandydatami do usunięcia przy pierwszym przebiegu schedulera, jeśli ich ostatnia wiadomość również przekracza retencję.
- **Weryfikacja:** 10 testów cyklu życia `chat_rooms`, Ruff check/format i `git diff --check` przeszły. Testy obejmują retencję i kaskadowe usunięcie historii, odliczanie od odejścia ostatniego członka, świeżą aktywność oraz wykluczenia typów pokoi.
- **Spodziewany efekt:** rozdzielone reguły dostępu i rodzaju pokoju, zachowana historia aktywnych lub niejednoznacznych DM-ów oraz automatyczne porządkowanie tylko starych, całkowicie pustych DM-ów.

## 2026-10-10: Aktualizacja zależności zgłoszonych przez Dependabot

- **Zmienione obszary:** `requirements.txt`, generowany przez npm `package-lock.json` oraz testy sanityzacji HTML.
- **Co się zmieniło:** podniesiono Bleach do 6.4.0 i Daphne do 4.2.2, a pośrednie zależności narzędzi JS: `form-data` do 4.0.6, `js-yaml` do 3.15.2 i `brace-expansion` do 1.1.21. Dwa testy regresji sprawdzają odrzucanie zamaskowanych Unicode schematów URL w linku oraz atrybucie `formaction` TinyMCE; oba odtwarzały problem przed aktualizacją Bleach.
- **Uzasadnienie:** poprawione wydania usuwają wskazane podatności bez zmiany głównych narzędzi testowych ani kontraktów aplikacji. Alert Bleach dotyczący `parse_email=True` nie dotyczy obecnego wywołania `bleach.linkify`, które używa domyślnego `False`.
- **Weryfikacja:** 44 testy Pythona (sanityzacja i WebSocket), 307 testów Jest, Django check, `pip check`, Ruff check/format i kontrola białych znaków w zmienionych plikach przeszły. `npm audit` nadal pokazuje 40 innych problemów w drzewie narzędzi deweloperskich; zgłasza `js-yaml` pośrednio przez jego zależność `argparse`, a nie przez cztery naprawiane tutaj alerty `js-yaml`.
- **Spodziewany efekt:** zależności używają poprawionych wersji, a sanityzacja odrzuca niebezpieczne schematy URL maskowane znakiem Unicode.

## 2026-10-10: Przewijanie czatu do wiadomości z aktywności

- **Zmienione obszary:** linki feedu `chat`, router i API WebSocketu czatu, pobieranie wiadomości w `ChatRepository`, testy feedu i czatu.
- **Co się zmieniło:** każde zdarzenie wiadomości w aktywności prowadzi do `#room_id=…&message_id=…`. Komenda dołączania może opcjonalnie przyjąć ID wiadomości; repozytorium pobiera maksymalnie 100 wiadomości wokół niej w kolejności chronologicznej, a przy brzegu pokoju uzupełnia porcję z drugiej strony. Nieistniejący lub obcy ID nie ujawnia wiadomości z innego pokoju i powoduje zwykłe pobranie ostatnich wiadomości. Zachowano istniejące przewijanie i podświetlenie, pomijając próbę przewijania przy pojedynczej wiadomości realtime przed historią.
- **Cache:** podbito `FEED_CACHE_KEY` do `feed_raw_v6`, aby cache nie zwracał starych linków bez `message_id`.
- **Weryfikacja:** pełne 1212 testów Pythona i 307 testów Jest, pełny Ruff check/format, Django check, compilemessages, build CSS, regression scan i UI guard przeszły. Pre-push runnera nie uruchamiano, bo wykonuje `collectstatic --clear` i przygotowuje `.env`; te kroki pominięto w bezpiecznej weryfikacji lokalnej. Playwright nie jest częścią pre-push (`--no-playwright`).
- **Spodziewany efekt:** kliknięcie zdarzenia wiadomości otwiera właściwy pokój, ładuje porcję obejmującą wskazany wpis, przewija do niego i podświetla go.

## 2026-10-10: Bookmarki zdarzeń w aktywności głosowań

- **Zmienione obszary:** feed `glosowania`, rejestr providerów i usługa bookmarków `core`, widok aktywności, obsługa JS, testy i migracja stanu modelu `FeedBookmark`.
- **Co się zmieniło:** wpis głosowania nadal używa klucza `decision` + ID głosowania, a każdy argument dostaje osobny klucz `decision_argument` + ID argumentu. Odczyt pozostaje przypisany do głosowania. Lista bookmarków na pulpicie, filtr aktywności i przyciski korzystają z identyfikatora bookmarka konkretnego zdarzenia. Starsze zapisane głosowania są pobierane przez hook providera tylko na potrzeby widoków bookmarków, bez rozszerzania zwykłego 90-dniowego feedu. Zwiększono wersję klucza cache surowego feedu.
- **Migracja:** rozszerzono choices `FeedBookmark.content_type`; `sqlmigrate` potwierdza brak SQL zmieniającego tabelę lub dane.
- **Uzasadnienie:** wspólny identyfikator głosowania powodował, że bookmark jednego argumentu oznaczał wszystkie zdarzenia związane z tym głosowaniem. Dawny rekord nie wskazuje konkretnego argumentu, więc pozostaje bookmarkiem samego głosowania, widocznym także po wyjściu tego wpisu z okna feedu.
- **Weryfikacja:** 111 testów feedu, aktywności, digestu i dashboardu, 8 testów Jest aktywności, Django check, Ruff, kontrola migracji i `sqlmigrate`, build CSS, regression scan, UI guard i `git diff --check` przeszły. Testy obejmują niezależność bookmarków argumentów, starsze głosowania, filtr odczytu oraz brak daty modyfikacji.
- **Spodziewany efekt:** można niezależnie zapisać bookmark dla zdarzenia głosowania oraz każdego argumentu; dotychczasowe bookmarki pozostają dostępne bez zgadywania, który argument był pierwotnie oznaczony.

## 2026-10-08: Zapis ważnego dokumentu nie zamyka transakcji SQLite

- **Zmiana:** powiadomienie w pokoju „Ważne” jest wysyłane przez `transaction.on_commit()` zamiast wewnątrz transakcji `Post.save()`. Sygnał zachowuje dotychczasowe argumenty; przy wycofaniu transakcji wiadomość nie powstaje.
- **Powód:** `database_sync_to_async` w usłudze czatu zamykało plikowe połączenie SQLite podczas zapisu ważnego dokumentu, powodując HTTP 500 (`Cannot operate on a closed database`).
- **Testy:** dodano test edycji przez formularz na plikowej bazie SQLite odtwarzający wyjątek przed zmianą oraz test braku wiadomości po wycofaniu transakcji. Istniejące testy historii ważnych dokumentów wykonują teraz rzeczywisty commit.
- **Weryfikacja:** 64 testy `board` przeszły na bazie w pamięci, a 6 testów ważnych dokumentów na plikowej SQLite; Django check, Ruff i `git diff --check` przeszły. Na Windowsie teardown testów z plikową SQLite zgłasza ostrzeżenie o zajętym pliku po zakończeniu testów.
- **Spodziewany efekt:** zapis ważnego dokumentu kończy się poprawnie, a wiadomość na czacie trafia dopiero po zatwierdzeniu danych.

## 2026-10-08: Samodzielny audyt pokoi na podach przed migracją

- **Zmienione obszary:** nowy `scripts/audit_discussion_rooms_pods.sh`; procedura bezpiecznej kolejności audytu i wdrożenia jest zachowana w sekcji finalizacji naprawy pokoi czatu powyżej.
- **Powód:** wdrożenie nowego obrazu automatycznie uruchamia migracje, więc audyt danych musi działać bez aktualizacji aplikacji.
- **Działanie:** skrypt Bash uruchamiany ręcznie na serwerze odpytuje 13 wskazanych podów przez `microk8s kubectl exec -i`, przekazując przez stdin samodzielny kod Python/SQLite. Baza jest otwierana tylko do odczytu, bez importu Django i bez migracji. Raport rozróżnia blokery nowych ograniczeń od pozostałych uwag, kontynuuje po błędzie jednego poda i podaje zbiorczy wynik. Nie naprawia danych.
- **Weryfikacja lokalna:** `bash -n` oraz próby na izolowanej starej strukturze SQLite: stan czysty, zduplikowany klucz źródła i współdzielony pokój, uwaga o brakującej relacji.
- **Wynik audytu przed wdrożeniem przekazany przez użytkownika:** 13/13 podów sprawdzonych, 0 blokerów, 0 błędów odczytu. Pozostało 28 uwag: sześć członkostw nieaktywnych kont w czterech pokojach dokumentów `instance-12` oraz 24 pokoje prywatne z 0–1 członkiem (`instance-3`: 6, `instance-6`: 17, `instance-8`: 1). Audyt nie zmienił danych. To wynik historyczny sprzed migracji; późniejszy audyt po wdrożeniu i aktualna interpretacja uwag są opisane w sekcji finalizacji powyżej.

## 2026-10-08: Rozdzielenie rodzaju i dostępu do pokojów czatu

- **Zmienione obszary:** `chat` (modele, feed, powiadomienia, sygnały, widoki, komenda archiwizacji i narzędzie audytu/naprawy), testy `chat` oraz feedu, aktywności i digestu w `home`.
- **Co się zmieniło:** `public` nadal określa dostęp, a wspólna reguła oparta o istniejące `source_app` odróżnia pokoje treści od DM. Feed, digest i push zachowują tytuł źródłowy dla grupowych dokumentów; nazwy ankiet są oczyszczane przy wyświetlaniu. Wyszukiwanie, obecność i widoki DM wymagają pokoju bez źródła z dokładnie dwiema osobami; kolizja tytułu nie przejmuje już obcego pokoju. Usuwanie konta kasuje wyłącznie prawdziwe DM, nowi obywatele dostają członkostwo w grupowych i archiwalnych czatach dokumentów, a scheduler może archiwizować pokoje źródłowe, lecz ich nie usuwa ani nie zamienia nieaktywnego członka w powód usunięcia.
- **Dane historyczne:** `repair_discussion_rooms --audit` jest tylko do odczytu. Po przeglądzie i jawnym potwierdzeniu backupu `--repair-source-data` dodał 4 członków do `board #87`, uzupełnił metadane 5 pokoi zadań i później dodał 12 brakujących członkostw w `instance-12`. Wcześniejszy audyt 13 podów: 9 czystych; w `instance-12` pozostał niejednoznaczny `board #24` i sześć członkostw nieaktywnych kont w czterech pokojach; w `instance-3`, `instance-6` i `instance-8` pozostały 24 prywatne pokoje z 0–1 członkiem. Użytkownik zdecydował zachować członkostwa nieaktywnych osób i nie usuwać niejednoznacznych DM. Nie usunięto pokojów ani wiadomości.
- **Uzasadnienie:** `public=False` opisywało ograniczenie dostępu, ale było mylone z prywatną rozmową 1:1; skutkowało to błędnym tytułem aktywności oraz ryzykiem pomylenia, archiwizacji lub usunięcia pokoi dokumentów.
- **Weryfikacja:** 332 testy dotyczące czatu, feedu, aktywności, digestu i dokumentów przeszły; Ruff, Django check, `makemigrations --check --dry-run --noinput` (brak zmian migracji) oraz `git diff --check` przeszły. Wykonano audyt 13 wdrożonych podów przed naprawą i ponownie po niej; raport końcowy zawiera wyżej opisane pozostałości do ręcznej oceny. Nie uruchamiano pełnego E2E.
- **Spodziewany efekt:** Pokoje dokumentów zachowują własne tytuły i dane; działania specyficzne dla DM nie obejmują już pokoju grupowego z błędnej interpretacji `public=False`.

## 2026-10-08: Ograniczenia integralności powiązań pokoi źródłowych

- **Zmienione obszary:** model `chat.Room`, wspólny `ChatRoomModel`, obsługa sygnałów tworzenia/usuwania, preflight `repair_discussion_rooms`, migracje aplikacji `chat`, `board`, `tasks`, `glosowania` i `ankiety` oraz testy cyklu życia.
- **Co się zmieniło:** Baza wymusza unikalny klucz `(source_app, source_object_id)` i zabrania identyfikatora źródła bez aplikacji. Opcjonalne FK obiektu do pokoju stały się OneToOne z `on_delete=PROTECT`. Wspólny handler odłącza FK transakcyjnie przed usunięciem pokoju przy usuwaniu obiektu źródłowego; bezpośrednie usunięcie pokoju przez ORM jest blokowane. Zapis obiektu przerywa się, gdy istniejący FK wskazuje pokój o innym źródle, a ścieżka `bulk_create` odrzuca błędny prelink.
- **Migracje:** wygenerowano `chat.0030`, `board.0024`, `tasks.0013`, `glosowania.0029` i `ankiety.0005`. Nie zastosowano ich na wdrożonych bazach. Przed rolloutem trzeba uruchomić samodzielny audyt relacji (w tym duplikatów `chat_room_id`) na każdej instancji, przejrzeć konflikty i wykonać backup; dopiero potem wdrożyć kod z migracjami i powtórzyć audyt. Po zakończeniu testów użytkownik utworzył nowy pusty pokój dla `board #24` (bez odtwarzania wiadomości).
- **Weryfikacja:** 559 testów dotkniętych modułów przeszło; Ruff, Django check, `makemigrations --check --dry-run --noinput` oraz `git diff --check` przeszły. Testy obejmują wymuszenie unikalności, kolizje powiązań, chronione usuwanie oraz zachowanie pozostałych source apps.
- **Uzasadnienie:** Metadane źródła i FK obiektu były dwoma niezależnymi, opcjonalnymi zapisami. Ograniczenia oraz fail-closed obsługa ograniczają duplikaty, przypadkowe współdzielenie i ciche przepięcie istniejącego pokoju.
- **Spodziewany efekt:** Pokój źródłowy ma najwyżej jeden właścicielski obiekt w ramach aplikacji, jego tożsamość nie może się dublować, a ORM nie usunie podpiętego pokoju bez jawnego cyklu usuwania źródła.
- **Uzupełnienie preflight:** `repair_discussion_rooms --audit` sprawdza duplikaty `(source_app, source_object_id)` także dla nieznanych aplikacji oraz współdzielenie pokojów między wszystkimi aplikacjami nawet przy `--app`. Audyt pozostaje tylko do odczytu, a lokalne sprawdzanie członkostw nadal respektuje `--app`. Testy komendy: 14 zaliczonych w izolowanej bazie w pamięci.

## 2026-10-05: Wyraźne oznaczenie wzmianek w pushu i digescie

- **Zmienione obszary:** `chat.notifications`, `home.management.commands.send_email_digest` oraz testy tych dwóch kanałów.
- **Co się zmieniło:** Tytuł istniejącego powiadomienia o wzmiance i tytuł pozycji czatu w digescie HTML/tekstowym rozpoczyna się od `[wzmianka o Tobie]` (z użyciem już przetłumaczonego tekstu). W digescie etykieta została przeniesiona z małego metadopisku do widocznego tytułu.
- **Uzasadnienie:** Push FCM dla `chat.mention` już działał, ale miał taki sam tytuł jak zwykła wiadomość. Wspólna kolejka, godzinny limit i ustawienia użytkownika pozostają bez zmian zgodnie z decyzją użytkownika; czekające powiadomienie nadal może zostać zastąpione najnowszą wiadomością z pokoju. Nie powstaje dodatkowy e-mail ani drugi push.
- **Weryfikacja:** 29 testów czatu i kolejki oraz 33 testy digestu, Django check, Ruff, build CSS, regression scan, UI guard i `git diff --check`. Wykorzystano istniejący przetłumaczony tekst `mentioned you`, więc nie dodano nowych kluczy tłumaczeń.
- **Spodziewany efekt:** Odbiorca widzi, że został zawołany, zarówno w istniejącym powiadomieniu push, jak i w e-mailowym podsumowaniu.

## 2026-10-05: Jednoznaczne podpowiedzi wzmianek na czacie

- **Zmienione obszary:** endpoint i testy widoków czatu, wspólna logika edytorów głównego i osadzonego czatu.
- **Co się zmieniło:** Wpisanie `@` i fragmentu imienia, nazwiska lub loginu może pokazać jedną podpowiedź uczestnika pokoju. Podpowiedź pojawia się wyłącznie przy jednym dopasowaniu i można ją wybrać Tabem lub kliknięciem; do wiadomości trafia istniejący format `@username`.
- **Uzasadnienie:** Wykorzystuje obecny mechanizm powiadomień o wzmiankach, nie zmienia formatu wiadomości ani schematu danych; brak automatycznego wyboru przy kilku trafieniach chroni przed omyłkowym zawołaniem innej osoby.
- **Weryfikacja:** Testy widoków czatu i Jest dla czatu, Django check, Ruff, build CSS, regression scan oraz UI guard. Uruchomienie testów odświeżyło również `locale/pl/LC_MESSAGES/django.po`; plik pozostawiono zgodnie z decyzją użytkownika.
- **Poprawka kursora:** Po zatwierdzeniu podpowiedzi Tabem lub kliknięciem edytor odzyskuje fokus, a kursor trafia na koniec wstawionego `@username `, nie przed wzmiankę. Testy JS sprawdzają oba sposoby zatwierdzenia oraz pozycję zaznaczenia.
- **Separator po wzmiance:** Zwykłą spację na końcu wstawionego węzła zastąpiono spacją niełamliwą, żeby edytor HTML nie zwijał jej przy dalszym pisaniu. Testy sprawdzają zachowanie separatora i wykrywanie wzmianki przez serwer także po serializacji jako `&nbsp;`.
- **Spodziewany efekt:** Szybsze i bezpieczniejsze wołanie osób także w czatach osadzonych bez rozwijanej listy.

## 2026-10-03: Uproszczenie instrukcji uruchamiania i helpera Compose

- **Zmienione obszary:** `docs/DEPLOYMENT_INSTRUCTIONS.md`, `scripts/build_docker_localy_on_windows.ps1`, `scripts/start_dev.py`.
- **Co się zmieniło:** Skrócono lokalny setup, usunięto odwołanie do skasowanego `start_dev.sh` i instrukcję importowania fixture’ów. Windowsowy helper tworzy `.env` z przykładu, sprawdza Docker Compose v2, zatrzymuje lokalne kontenery, buduje obraz, wykonuje migracje i uruchamia usługi; reset bazy wymaga wpisania `RESET`. Opis `start_dev.py` dopasowano do rzeczywistego serwera Django.
- **Uzasadnienie:** Dokumentacja zawierała powielone kroki i nieaktualne informacje o Redisie, migracjach oraz skryptach; helper nie uruchamiał migracji i obie gałęzie startowały w trybie odłączonym.
- **Weryfikacja:** Parser PowerShella zaakceptował zmieniony skrypt. Testów aplikacji nie uruchamiano; zmiany dotyczą instrukcji i lokalnego helpera.
- **Spodziewany efekt:** Powtarzalniejszy start Compose i mniej ręcznych kroków przy lokalnym uruchomieniu; produkcyjny rollout nadal pozostaje zarządzany przez CI i Flux.

## 2026-09-30: Zabezpieczenia SQLite przed migracją do MariaDB

- **Zmienione obszary:** `core/sqlite.py`, `glosowania` (oddawanie głosu), `scripts/sqlite_maintenance.py`, `scripts/sqlite_contention_test.py`, konfiguracja SQLite, scheduler oraz instrukcje operacyjne.
- **Co się zmieniło:** Dodano bezpieczny backup przez SQLite Backup API z kontrolą integralności, checkpointem WAL i opcjonalnym `VACUUM` po backupie; istniejący plik backupu nie jest nadpisywany bez jawnego usunięcia, a checkpoint `TRUNCATE` wymaga potwierdzenia. Dodano test współbieżności na kopii/tymczasowej bazie z pomiarem blokad i WAL/SHM. Połączenia używają wspólnych pragm SQLite (`WAL`, `foreign_keys`, `busy_timeout`), retry pozostaje ograniczone i ma diagnostykę bez danych wrażliwych, a scheduler ma międzyprocesową blokadę dla Linux i Windows. Końcowy błąd blokady przy głosowaniu daje bezpieczny redirect i komunikat zamiast 500; interfejs blokuje podwójne wysłanie i nie ponawia POST-a automatycznie.
- **Wyniki zachowane do porównania:** W historycznych testach 16 writerów po 5000 operacji odnotowano 74882 zapisy i 5118 blokad przy timeout 0,1 s oraz 79312 zapisów i 688 blokad przy timeout 1 s. Test pilota na docelowym PVC uzyskał 999/1000 zapisów i jedną blokadę; kopia przeszła kontrole integralności. Są to baseline'y testów/pilota, nie bieżące potwierdzenie bezpieczeństwa całego klastra.
- **Decyzje i ograniczenia:** Zabezpieczenia SQLite pozostają wymagane do cutoveru i ewentualnego rollbacku; ich usunięcie jest odroczone do Etapu 7 `PLAN_MIGRACJI_MARIADB.md`. Przed operacją produkcyjną nadal trzeba potwierdzić aktualny backup, integralność, filesystem/blokady, wolne miejsce i monitoring. Nie uruchamiać `VACUUM` równolegle z aktywną bazą.
- **Uzasadnienie:** Ograniczenia współbieżności SQLite wymagają odrębnego modelu operacyjnego; zachowanie kontrolowanego backupu i bezpiecznej ścieżki głosowania chroni dane do czasu przejścia na MariaDB.
- **Weryfikacja:** W planie odnotowano testy obciążeniowe, kontrolę integralności i smoke testy restartów pilota. Nie wykonywałem ich ponownie przy porządkowaniu dokumentacji.
- **Spodziewany efekt:** Obecne instancje mogą pozostać na SQLite z zachowaniem ograniczeń i procedur, a wyniki pomiarów służą jako punkt odniesienia dla migracji bez traktowania historycznego statusu jako bieżącego GO.

## 2026-09-30: Status aktywności na podstawie push i aktywności aplikacji

- **Zmienione obszary:** `core.presence`, aplikacje `obywatele` i `chat`, model profilu i migracja, wspólny avatar/UI, dashboard aktywności oraz testy i dokumentacja UI.
- **Co się zmieniło:** Dodano indeksowany znacznik czasu i źródło ostatniego sygnału (`app`/`push`) na poziomie użytkownika. Sygnały aplikacji obejmują logowanie, heartbeat, widoczność karty, interakcje i WebSocket; kliknięcia i wpisywanie są ograniczone do zapisu najwyżej raz na 5 minut. Obecność push aktualizuje wyłącznie uwierzytelniony użytkownik po ACK `shown` po pokazaniu powiadomienia; `skipped` i `error` nie aktualizują statusu. Zapis jest monotoniczny, nie przechowuje tokenów FCM, a zmiany są rozgłaszane przez istniejący WebSocket. Status ma konfigurowalne progi: zielony do 15 minut, żółty do 7 dni, czerwony przy starszym lub brakującym sygnale.
- **UI i dashboard:** Wspólny partial avatara pokazuje dostępny kropkowy wskaźnik z opisem źródła i czasu; dotknięcie otwiera popover. Wzorzec działa w listach, siatkach, profilach, aktywności, dokumentach, głosowaniach, zadaniach, dashboardzie i prywatnym czacie. Kafelek aktywności pokazuje podział świeżości sygnałów dla ostatnich 30 dni, procent i liczby oraz prowadzi do listy z filtrem; opiera się wyłącznie na `last_presence_at`.
- **Decyzje i ograniczenia:** Status jest heurystyką ostatniego wiarygodnego sygnału, nie dowodem obecności człowieka. Nie opiera się na samym `last_login`, aktywnym tokenie ani wysłaniu push. Model przechowuje tylko najnowszy sygnał, dlatego historia dzienna i heatmapa 30-dniowa pozostają poza zakresem.
- **Uzasadnienie:** Jeden wskaźnik ma informować o ostatniej potwierdzonej aktywności także osób bez push, bez utożsamiania rejestracji tokena lub próby wysłania z faktycznym odbiorem powiadomienia.
- **Weryfikacja:** Zgodnie z planem przeszły testy dotkniętych obszarów backendu i frontendu, Django check, linting, test migracji, build CSS, regression scan i UI guard. Test listy obywateli sprawdza, że liczba zapytań nie rośnie proporcjonalnie do liczby użytkowników.
- **Spodziewany efekt:** Użytkownicy widzą przy avatarach aktualny, opisany status wynikający z najnowszego sygnału z dowolnego urządzenia; aktywność może być raportowana zarówno z aplikacji, jak i z potwierdzonego odbioru push.

## 2026-09-30: Refaktoryzacja architektury między aplikacjami

- **Zmienione obszary:** `chat`, `glosowania`, `tasks`, `board`, `home`, `zzz`, aplikacje dostarczające dane do dashboardu i wyszukiwania oraz powiązane migracje i testy.
- **Co się zmieniło:**
  - Czat komunikuje się z `glosowania`, `tasks` i `board` przez sygnały domenowe (`chat_room_requested`, `chat_message_requested`) zamiast bezpośredniego tworzenia wiadomości/pokoi lub wywoływania usług czatu. `Room` przechowuje `source_app` i `source_object_id`; backfill istniejących rekordów rozdzielono na migracje `tasks` i `glosowania`, aby uniknąć cyklicznej zależności. Widoki i komendy grupują pokoje po `source_app`, a naprawa połączeń używa `django.apps` zamiast importów modeli `Task`/`Decyzja`. `Room.clean_title()` usuwa techniczne prefiksy tytułów przy wyświetlaniu. Testy błędnego tworzenia pokoju mockują teraz `chat.signals.Room.objects.create`.
  - Feed, dashboard i wyszukiwanie korzystają z rejestrów providerów `core.feed_registry`, `core.dashboard_registry` i `core.search_registry`; aplikacje-właściciele rejestrują providery w `AppConfig.ready()`. `core.services.feed` agreguje i cache’uje elementy feedu, a aplikacje-właściciele podpinają unieważnianie cache’u do zmian swoich modeli. Rejestr feedu obsługuje także hooki oznaczania jako przeczytane/nieprzeczytane oraz przygotowania elementów i digestu; czat implementuje własne hooki w `chat.feed`, bez specjalnego przypadku w `home.views.py`. `home.services.dashboard` składa kontekst widoku z providerów oraz elementów należących do `home` (prezentacja feedu, quick links i `DASHBOARD_MODULES`). Widoki używają tych usług i `core.search_registry` zamiast importować modele domenowe do agregowania dashboardu, feedu i wyszukiwania.
  - Wspólne widgety przeniesiono z `home/widgets.py` do `zzz/widgets.py`, a `citizen_color_class`/`citizen_color` do `zzz/templatetags/citizen_filters.py`; zaktualizowano zależne importy i szablon avatara.
  - Powiadomienia scentralizowano przez sygnały domenowe w `zzz/signals.py` i odbiorców w `zzz/notifications.py`, które wybierają kanał FCM, WebSocket lub email. Ręczne wywołania zastąpiono emisją zdarzeń; obsługę pokoi 1-to-1 oraz chatowe sprzątanie po usunięciu obywatela wydzielono do `chat/signals.py`. Obsłużono też błędy `DatabaseError` przy dostępie do odbiorców push i broadcastach, żeby blokada SQLite nie kończyła pracy tła nieobsłużonym wyjątkiem.
  - `count_citizens` rozdziela liczenie reputacji/aktywację od operacji czatu, a `chat_messages` grupuje pokoje dynamicznie po `source_app` z fallbackiem `public`/`private`.
- **Decyzje i ograniczenia:** Przeniesienie `FeedItem` i `ReadStatus` z `home/models.py` do `core` pozostawiono poza zakresem — wymagałoby nowej aplikacji i migracji schematu.
- **Uzasadnienie:** Zmiany zmniejszają sprzężenie między aplikacjami i skupiają obsługę integracji w jawnych kontraktach, rejestrach oraz odbiorcach zdarzeń.
- **Weryfikacja:** Według wykonanych raportów przeszły `manage.py check`, `makemigrations --check --dry-run`, Ruff (`check` i `format --check`), 461 testów pytest oraz 97 testów Jest.
- **Spodziewany efekt:** Moduły zależą od jawnych kontraktów i rejestrów zamiast bezpośrednio od modeli i efektów ubocznych innych aplikacji; dokumentacja planu została zastąpiona tym podsumowaniem wykonanych prac.

## 2026-09-30: Inbox wyłączony z digestu e-mailowego

- **Zmienione pliki:** `chat/feed.py`, `home/test_email_digest.py`, `docs/LOG_AI.md`.
- **Co się zmieniło:** Liczenie wiadomości do digestu pomija pokoje oznaczone jako Inbox zarówno flagą `is_inbox`, jak i kluczem systemowym `inbox`. Test digestu pokrywa oba znaczniki; publiczny Inbox pozostaje dostępny w aktywności.
- **Uzasadnienie:** Wspólne źródło aktywności zaczęło uwzględniać publiczny Inbox, przez co wiadomości gości trafiały także do digestu e-mailowego, który nie powinien zawierać tego kanału.
- **Weryfikacja:** Pełna bramka lokalna bez Playwrighta przeszła: Ruff, regression scan, UI guard, Django check, kontrola buildu Tailwind, 1107 testów pytest i 299 testów Jest. Po rozszerzeniu regresji testy `home/test_email_digest.py` i `home/test_activity.py` przeszły (43 testy). `collectstatic --clear` sprawdzono tylko w trybie `--dry-run`, a `compilemessages` pominięto, by nie czyścić ignorowanego katalogu `static/` ani nie nadpisywać skompilowanych katalogów tłumaczeń bez osobnej zgody.
- **Spodziewany efekt:** Aktywność nadal pokazuje wiadomości z publicznego Inboxa, a digest e-mailowy je pomija.

## 2026-09-30: Krocząca lista wydarzeń i responsywna siatka

- **Zmienione obszary:** `events` (widok, szablon, testy), wspólny CSS Tailwind, standard UI, polskie tłumaczenia i ten log.
- **Co się zmieniło:** Lista wydarzeń obejmuje daty od początku miesiąca wybranego w mini-kalendarzu do 31 dni naprzód. Kliknięcie dnia filtruje listę do dokładnie tego dnia i przekazuje tę datę do formularza nowego wydarzenia. Nowe wydarzenie domyślnie zaczyna się o 12:00 w bieżącym dniu lokalnym. Siatka kart dobiera kolumny do szerokości kontenera, a dzisiejszy dzień z wydarzeniem zachowuje kontrastowy tekst.
- **Uzasadnienie:** Ograniczenie historii do ostatnich 5 dni ukrywało starsze wydarzenia wybranego miesiąca, a kolor tekstu dnia z wydarzeniem nadpisywał kontrast dnia bieżącego; siatka mogła też wymuszać przepełnienie poziome.
- **Weryfikacja:** 17 testów `events/tests/test_views.py`, Ruff, Django check, kompilacja tłumaczeń, regression scan, UI guard i `git diff --check` przeszły. Playwright nie został uruchomiony: brak lokalnego `.env.local` z dedykowanym kontem E2E, a pełny runner przygotowuje `.env` i wykonuje `collectstatic --clear`.
- **Spodziewany efekt:** Wydarzenia od początku wybranego miesiąca są widoczne razem z najbliższymi 31 dniami, kliknięcie daty zawęża je do jednego dnia, dzień bieżący pozostaje czytelny, a karty zawijają się do szerokości ekranu.

## 2026-09-29: Aktywność usunięcia konta, Inbox i filtr finansów

- **Zmienione obszary:** `obywatele` (aktywność i prośby usunięcia konta), `chat.feed`, aktywność `home`, provider `bookkeeping`, testy, polski katalog tłumaczeń i ten log.
- **Co się zmieniło:** Złożenie prośby tworzy ogólny wpis `CitizenActivity` bez powodu; pozostaje on po anulowaniu prośby, a znika wraz z usunięciem konta. Aktywność czatu obejmuje teraz pełną treść wiadomości z publicznego Inboxa. Dodano filtr „Finance” i unieważnianie cache’u po utworzeniu/usunięciu transakcji.
- **Migracja:** Zaktualizowano stan choices `CitizenActivity.activity_type`; nie zmienia to fizycznej kolumny bazy.
- **Audyt dokumentów:** Bieżący model nie ma widoczności „prywatny”. Pozostała wzmianka w `LOG_AI.md` opisuje historyczny stan z datowanego wpisu; nie zmieniano historii ani odniesień do prywatnych pokoi czatu.
- **Uzasadnienie:** Zmiany odpowiadają na prośbę o widoczność tych wpisów i filtr finansowy, zachowując powód usunięcia poza publicznym feedem.
- **Spodziewany efekt:** Prośba o usunięcie, wiadomości Inboxa i transakcje są widoczne w aktywności zgodnie z wybranym zakresem.

## 2026-09-29: Inicjały nadawcy w powiadomieniach czatu

- **Zmienione pliki:** `chat/notifications.py`, `chat/tests/test_consumers.py`, `chat/tests/test_services.py`, `docs/LOG_AI.md`.
- **Co się zmieniło:** Powiadomienia czatu używają inicjałów nadawcy w treści oraz w nazwie pokoju prywatnego; wiadomości anonimowe nadal pokazują wyłącznie „Anonymous”.
- **Uzasadnienie:** Ten sam payload trafia do powiadomień WebSocket i FCM, wyświetlanych na komputerze oraz telefonie. Zmiana wspólnego źródła usuwa pełne imię i nazwisko z obu kanałów.
- **Testy:** Dodano regresję inicjałów dla prywatnego powiadomienia o wzmiance oraz kontrolę zachowania anonimowości.
- **Spodziewany efekt:** Na wszystkich urządzeniach nadawca jest rozpoznawalny po inicjałach, bez ujawniania pełnego imienia i nazwiska.

## 2026-09-29: Licznik pozycji zasobów w stepperze obywateli

- **Zmienione pliki:** `obywatele/templatetags/profile_tags.py`, `obywatele/tests/test_views.py`, `docs/LOG_AI.md`.
- **Co się zmieniło:** Krok „Zasoby” pokazuje liczbę aktywnych przypisań zasobów wszystkich typów: do oddania, do pożyczenia, do sprzedania i potrzeb. Każdy rekord przypisania jest liczony jako jedna pozycja, zgodnie z modelem bez pola ilości.
- **Uzasadnienie:** Użytkownik poprosił o łączną liczbę pojedynczych pozycji z wszystkich czterech kategorii; liczenie przypisań pomija pozycje nieaktywnego profilu i nie zależy od filtrów widoku.
- **Testy:** Dodano regresję sprawdzającą wszystkie typy, filtr widoku oraz wykluczenie nieaktywnego właściciela.
- **Spodziewany efekt:** Licznik „Zasoby” pokazuje sumę widocznych pozycji wszystkich aktywnych obywateli.

## 2026-09-29: Liczniki obywateli i kandydatów w stepperze

- **Zmienione pliki:** `obywatele/templatetags/profile_tags.py`, `obywatele/tests/test_views.py`, `docs/LOG_AI.md`.
- **Co się zmieniło:** Stepper obywateli przekazuje liczbę aktywnych kont oraz nieaktywnych kont z profilem kandydata, zliczonych jednym agregatem ORM. Dodano test renderowania obu wartości.
- **Uzasadnienie:** Wspólny partial steppera już obsługuje liczniki, ale builder obywateli nie dostarczał danych.
- **Spodziewany efekt:** Przy zakładkach „Obywatele” i „Kandydaci” widać aktualną liczbę elementów z odpowiadających im list.

## 2026-09-27: Odporne testy wyszukiwania zasobow na aktywny jezyk

- **Zmieniony plik:** `obywatele/tests/test_views.py`.
- **Co sie zmienilo:** Test widoku zasobow porownuje naglowki `Offers` i `Needs` przez istniejaca funkcje tlumaczen zamiast oczekiwac angielskich tekstow niezaleznie od aktywnego jezyka.
- **Uzasadnienie:** Pelny runner kompiluje katalogi tlumaczen przed pytestem, a domyslnym jezykiem instancji jest polski. Wtedy poprawnie przetlumaczony interfejs zwracal `Oferty` i `Potrzeby`, co ujawnialo bledne, jezykowo zalezne asercje testu.
- **Testy:** Przeszedl test regresyjny wyszukiwania zasobow, wszystkie 1087 testow pytest, wszystkie 294 testy Jest oraz 35 uruchomionych scenariuszy Playwright (14 pozostalo pominietych zgodnie z konfiguracja projektow).
- **Spodziewany efekt:** Test zachowuje sprawdzanie obecnosci naglowkow i przechodzi zarowno dla polskiego, jak i angielskiego aktywnego jezyka.

## 2026-09-16: Synchronizacja własnego statusu aktywności bez zakłócania odpowiedzi WebSocket

- **Zmienione pliki:** `chat/consumers.py`, `tests/test_websocket.py`.
- **Co się zmieniło:** Początkowa odpowiedź WebSocket zawiera razem z `unread_count` także własny `presence_update`, jeśli zapis aktywności zmienił stan. Broadcast do pozostałych klientów odbywa się przed dołączeniem nowego połączenia do grupy `presence`, a klient dołącza do niej zawsze po wysłaniu odpowiedzi początkowej.
- **Uzasadnienie:** Dołączenie klienta do grupy przed pierwszym broadcastem aktualizowało jego zieloną kropkę, ale zostawiało niezależny komunikat `presence_update` przed odpowiedzią na pierwszą komendę czatu. Z kolei całkowite pominięcie członkostwa bieżącego klienta usuwało mu przyszłe aktualizacje obecności. Połączenie obu danych w jednym pakiecie zachowuje zieloną kropkę i deterministyczną kolejność odpowiedzi.
- **Testy:** Dodano regresję własnego statusu oraz broadcastu statusu do już połączonego klienta.
- **Spodziewany efekt:** Własna i cudza obecność w czacie pozostają aktualne, bez pojawiania się niezamówionego komunikatu przed odpowiedzią `join`/`error`.

## 2026-09-16: Własny status aktywności w czacie

- **Zmieniony plik:** `chat/consumers.py`.
- **Co się zmieniło:** Połączenie WebSocket dołącza do grupy `presence` przed zapisaniem i rozgłoszeniem pierwszego sygnału aktywności.
- **Uzasadnienie:** Wcześniej pierwszy broadcast był wysyłany zanim własny klient dołączył do grupy, więc pozostawał przy starym, często czerwonym statusie, mimo że lista osób otrzymywała aktualną aktywność.
- **Spodziewany efekt:** Status zalogowanej osoby w czacie odświeża się od razu po nawiązaniu połączenia, tak samo jak status innych użytkowników.

## 2026-09-15: Audyt kompatybilności ze starymi urządzeniami — bez zmian w kodzie

- **Status:** Tylko udokumentowane znalezisko; nie wprowadzono żadnych zmian w kodzie, konfiguracji ani zależnościach.
- **Problem:** Na starych fizycznych urządzeniach anonimowy Burger Menu może być niewidoczny i nie reagować. Przycisk zależy od JavaScriptowego dropdownu, który używa m.in. `Element.closest()`, `const`/`let` i `Object.assign()`, a sama ikona jest dostarczana przez zewnętrzny Font Awesome 7. Menu jest ukryte przez CSS (`display: none`) do czasu dodania klasy `tw-show`, więc awaria JS blokuje całą zawartość menu.
- **Szersze znalezisko:** `home/static/home/js/app.js` zawiera optional chaining, a czat i część funkcji współdzielonych używają nowoczesnej składni JavaScript, modułów ES, `async`/`await`, `fetch()`, `URLSearchParams`, `AbortController`, obserwatorów DOM i innych API. Starsza przeglądarka może odrzucić cały plik podczas parsowania, przez co przestaną działać m.in. motyw, mobilny sidebar, PagePrefs, filtry, część akcji aktywności, modale, zakładki i czat.
- **Warstwa wizualna:** CSS opiera się na custom properties, Flexbox/Grid, `gap`, `position: sticky` i miejscami `:has()`. Font Awesome 7 używa nowocześniejszych mechanizmów CSS i może dodatkowo nie załadować się na starym urządzeniu albo przy problemach z CDN, co ukrywa także inne ikony w aplikacji.
- **Brak kompatybilności:** Projekt nie ma obecnie Babela, `browserslist`, polyfilli ani osobnego pakietu legacy; JavaScript jest dostarczany bezpośrednio jako źródłowy kod, a część skryptów jako `type="module"`.
- **Wniosek:** Najprostsza docelowa strategia to zapewnić anonimowym akcjom (logowanie, rejestracja, kontakt, język) działanie z samego HTML jako progressive enhancement, a następnie — jeśli zostanie określona minimalna wersja urządzeń — dodać wspólny build legacy, polyfille oraz fallback CSS/ikon. Sama ręczna zamiana pojedynczych konstrukcji JS nie rozwiąże problemów CSS, CDN, modułów, WebSocketów ani push.
- **Decyzja:** Na tym etapie niczego nie naprawiamy; wpis zachowuje diagnozę i kierunek ewentualnego przyszłego zadania.

## 2026-09-15: Gmail-odporny nagłówek codziennego digestu

- **Zmienione pliki:** `home/templates/emails/digest.html`, `home/test_email_digest.py`.
- **Co się zmieniło:** Nagłówek digestu zastąpiono panelem `<div>` wzorowanym na działającym panelu podsumowania: ma jasne, kontrastowe tło, większą nazwę strony i ciemną typografię. Usunięto zależność od tła komórki tabeli, `bgcolor` oraz inline CSS.
- **Uzasadnienie:** Gmail nadal renderował obszar nagłówka jako biały, przez co biały tytuł i nazwa strony były niewidoczne. Panel typu `div`, tak jak istniejący panel podsumowania, jest faktycznie widoczny w odebranej wiadomości.
- **Spodziewany efekt:** W Gmailu nazwa strony i tekst „Activity digest” są widoczne na jasnofioletowym panelu bez zielonego akcentu; motyw ciemny zachowuje własny wariant tła.

## 2026-09-14: Zachowanie pełnego formatowania artykułów TinyMCE

- **Zmienione pliki:** `core/richtext.py`, `zzz/tests/test_richtext.py`.
- **Co się zmieniło:** Usunięto whitelistę tagów, atrybutów i właściwości CSS dla treści TinyMCE. Sanitizer zachowuje dowolny HTML/CSS użyty w artykule, usuwając tylko elementy wykonywalne: bloki `<script>`, event handlery, niebezpieczne URL-e oraz niebezpieczne URL-e w CSS. Dodano regresję opartą o responsywny layout z `flex`, `gap`, `flex-basis` i gradientem.
- **Uzasadnienie:** Poprzednia whitelist wycinała legalne właściwości layoutu (`flex`, `flex-wrap`, `gap`, `justify-content`, `background`), przez co artykuł na stronie tracił responsywność i formatowanie widoczne w edytorze.
- **Spodziewany efekt:** Artykuł zachowuje układ, odstępy, tła, gradienty, responsywne kolumny i niestandardowe elementy HTML z edytora, przy zachowaniu blokady wykonania skryptu.

## 2026-09-14: Naprawa pełnego pipeline'u testów

- **Zmienione pliki:** `tests/test_board.py`, `tests/test_sqlite_business_concurrency.py`.
- **Co się zmieniło:** Asercje komunikatów pokoju „Ważne” uwzględniają aktywne tłumaczenie zamiast zakładać język angielski. Testy współbieżności dostały brakujące importy, przekazują zwykłą wartość głosu do procesów potomnych oraz bezpiecznie zamykają tymczasowe bazy SQLite na Windows.
- **Uzasadnienie:** Pełny runner ujawnił 7 błędów: 3 wynikające z lokalizacji `pl` oraz 4 związane z inicjalizacją modeli w procesach `spawn` i blokadą pliku SQLite podczas sprzątania.
- **Weryfikacja:** pełny pipeline zakończył się powodzeniem: 1001 testów pytest, 285 testów Jest oraz 35 testów Playwright (14 pominiętych), a także Ruff, Django check, collectstatic, skan regresji i kontrola buildu Tailwind.

## 2026-09-14: Cztery stany widoczności dokumentów

- **Zmienione obszary:** `board`, synchronizacja pokoi `chat`, aktywność i wyszukiwanie dokumentów, tłumaczenia oraz testy.
- **Co się zmieniło:** Zastąpiono trzy flagi widoczności jednym polem `Post.visibility` ze stanami „Tylko ja”, „Grupa”, „Publiczny” i „Archiwum”. Dodano migrację zachowującą dotychczasowe znaczenie flag, z priorytetem archiwum, prywatności i publiczności oraz wymuszeniem publiczności i ważności dokumentów systemowych.
- **Uprawnienia:** Tylko autor może ustawić dokument jako prywatny; prywatny dokument jest czytelny i edytowalny wyłącznie dla autora. Dokumenty grupowe są widoczne dla zalogowanych członków, publiczne także dla gości, a archiwalne są tylko do odczytu i przywracają się do grupy.
- **Czat i aktywność:** Prywatne i archiwalne dokumenty nie trafiają do aktywności. Historia pokoju „Ważne” nie jest usuwana; wyłączenie znacznika „Ważne” oraz zmiany widoczności ważnego dokumentu publikują komunikaty statusu, także przy ponownym udostępnieniu.
- **UI:** Opcje widoczności są prezentowane inline, metadane kart siatki mają kolejność: ikona użytkownika, autor, data, a autor systemowy korzysta ze wspólnego partialu `home/_brand_mark.html`, który pobiera logo ustawione w parametrach systemowych przez głosowanie.
- **Spodziewany efekt:** Znika ujawnianie prywatnych dokumentów w aktywności, zapis prywatności nie kończy się błędem 404, a dokumenty systemowe zachowują publiczny i ważny charakter przy zapisie `updated_by`.

## 2026-09-14: Usunięcie tekstowych dzieci z list błędów formularzy

- **Zmienione pliki:** `obywatele/templates/obywatele/my_assets.html`, `obywatele/templates/obywatele/onboarding_details.html`.
- **Co się zmieniło:** Pętle renderujące błędy formularzy zostały złożone bezpośrednio wewnątrz elementów `<ul>`, bez białych znaków będących tekstowymi dziećmi listy.
- **Uzasadnienie:** Narzędzia Microsoft Edge zgłaszały ostrzeżenie HTML, ponieważ `<ul>` miał bezpośrednie dzieci tekstowe obok dozwolonych elementów `<li>`.
- **Spodziewany efekt:** Ostrzeżenia walidatora znikają, a lista błędów zachowuje dotychczasową treść i działanie.

## 2026-09-12: Wyrównanie kategorii czatu do prawej

- **Zmieniony plik:** `home/static/home/css/tailwind.css`.
- **Co się zmieniło:** Zawartość przycisków kategorii czatu jest wyrównana do prawej strony niezależnie od szerokości ekranu; usunięto redundantne nadpisanie mobilne.
- **Uzasadnienie:** Użytkownik poprosił o dosunięcie nagłówków kategorii do prawej strony przy zachowaniu kolejności licznika, nazwy i strzałki.
- **Spodziewany efekt:** Nagłówki wszystkich kategorii czatu są skupione przy prawej krawędzi panelu.

## 2026-09-12: Kolejność elementów nagłówków kategorii czatu

- **Zmienione pliki:** `chat/templates/chat/chat.html`, `home/static/home/css/tailwind.css`.
- **Co się zmieniło:** Nazwy kategorii zostały opakowane w elementy flex, a strzałki otrzymały stałą kolejność po nazwie. Licznik nieprzeczytanych pozostaje przed nazwą dzięki istniejącemu porządkowi CSS.
- **Uzasadnienie:** Nagłówki kategorii powinny być czytelne i spójne: patrząc od prawej, strzałka stanu, nazwa kategorii, a następnie po lewej liczba nieprzeczytanych wiadomości.
- **Spodziewany efekt:** Na desktopie i urządzeniach mobilnych przyciski kategorii mają kolejność wizualną: licznik, nazwa, strzałka od lewej do prawej.

## 2026-09-12: Nawigacja Previous/Next na szczegółach ankiet, transakcji, wydarzeń i dokumentów

- **Zmienione obszary:** `core.utils`, wspólny partial `home/templates/home/includes/detail_navigation.html`, aplikacje `ankiety`, `bookkeeping`, `events` i `board` oraz ich testy.
- **Co się zmieniło:** Dodano wspólny builder URL-i nawigacji oraz wspólny partial renderujący ikonowe guziki „Previous”/„Next”. Widoki szczegółów wyliczają sąsiadów w kolejności bieżącej listy, zachowują parametry wyszukiwania, sortowania, zakładki, kategorii i miesiąca, a na krańcach listy renderują nieaktywne guziki z `aria-disabled`. Linki z list przekazują ten sam kontekst do szczegółu.
- **Wydarzenia:** linki zawierają także identyfikator wystąpienia, dzięki czemu nawigacja może przejść przez każde wystąpienie wydarzenia cyklicznego bez zapętlenia na tym samym URL-u.
- **Ujednolicenie:** logika sąsiadów i markup UI nie są kopiowane między modułami; listy dokumentów korzystają z wyodrębnionej wspólnej logiki sortowania i filtrowania także przy budowaniu nawigacji.
- **Testy:** Dodano testy zachowania kolejności, zachowania kontekstu i stanów brzegowych dla ankiet, transakcji, wydarzeń oraz dokumentów.
- **Uzasadnienie:** Użytkownik może przechodzić między elementami bez powrotu do listy i bez utraty aktywnego widoku, a wspólny komponent ogranicza rozbieżności dostępności i wyglądu.
- **Spodziewany efekt:** Spójne guziki Previous/Next na czterech typach szczegółów, poprawna nawigacja przez filtrowane listy i wystąpienia kalendarza oraz prostsze utrzymanie wspólnego wzorca.

## 2026-09-11: Uatrakcyjnienie porannego digestu e-mail

- **Zmienione pliki:** `home/templates/emails/digest.html`, `home/test_email_digest.py`.
- **Co się zmieniło:** Odświeżono wizualną hierarchię digestu: nagłówek otrzymał wyraźniejszą etykietę i typografię, wprowadzono panel wprowadzenia, karty aktywności z akcentem oraz responsywne odstępy. Zachowano bez zmian markup, tekst i adres guzika „Zarządzaj powiadomieniami e-mail”.
- **Testy:** Test wysyłki digestu sprawdza obecność nowych elementów wizualnych oraz niezmieniony kontrakt guzika i adresu ustawień.
- **Uzasadnienie:** E-mail wysyłany o 08:00 powinien szybciej prowadzić wzrok do najważniejszych aktywności i dobrze działać na urządzeniach mobilnych, bez ryzyka naruszenia działającej akcji zarządzania powiadomieniami.
- **Spodziewany efekt:** Czytelniejszy, bardziej nowoczesny digest HTML w jasnym i ciemnym motywie oraz na małych ekranach; wersja tekstowa i działanie guzika pozostają bez zmian.

## 2026-09-09: Dodanie obowiązku dokumentowania zmian w `docs/LOG_AI.md`

- **Zmieniony plik:** `AGENTS.md`
- **Co się zmieniło:** W `AGENTS.md` dodano nową sekcję `## 9. Dokumentowanie zmian`, która nakazuje, aby po każdym zadaniu rejestrować w `docs/LOG_AI.md` wszystkie wprowadzone zmiany kodu wraz z uzasadnieniem, opisem tego, co się zmieniło, oraz spodziewanym efektem.
- **Uzasadnienie:** Projekt potrzebował jednolitego źródła informacji o modyfikacjach wprowadzanych przez asystenta AI. Dzięki temu decyzje są przejrzyste, a ich historia dostępna do audytu, debugowania i dalszego rozwoju.
- **Spodziewany efekt:** Po każdym zadaniu asystent będzie aktualizował `docs/LOG_AI.md`, co poprawi transparentność prac i dostarczy kontekstu dla przyszłych zmian.
- **Plik logu:** Powstał ten dokument (`docs/LOG_AI.md`) jako pierwszy zapis zgodny z nową regułą.

## 2026-09-11: Audyt zmian UI dokumentów i liczników czatu

- **Zmienione obszary:** `board`, `chat.services`, listy i szczegóły `tasks`/`glosowania`, wspólny CSS oraz `docs/UI_STANDARDS.html`.
- **Co się zmieniło:** Dokumenty przechowują osobno twórcę (`author`) i ostatnią osobę aktualizującą (`updated_by`), a migracja `board.0017_post_updated_by` dodaje nullable FK bez zgadywania danych historycznych. Formularze zachowują pierwotnego autora i zapisują wykonawcę każdej edycji, także dokumentu systemowego.
- **Liczniki czatu:** `chat.services.get_unread_message_counts_for_rooms()` zbiorczo liczy wiadomości bez `MessageReadBy` dla bieżącego użytkownika. Widoki dokumentów, głosowań i działań przekazują jeden policzony słownik do kart zamiast wykonywać zapytania w szablonach; wskaźnik `get_unseen_room_ids()` pozostaje oddzielnym kontraktem opartym o `Room.seen_by`.
- **UI i architektura:** Widok siatki dokumentów pokazuje datę i autora utworzenia oraz datę i osobę aktualizującą. Jednorazowe klasy CSS dokumentów zastąpiono istniejącymi utility `tw-*`, a standard czatu i kart zapisano w `docs/UI_STANDARDS.html`.
- **Testy:** Dodano sprawdzenie częściowo przeczytanego pokoju oraz zachowania autora i `updated_by` przy zwykłej i systemowej edycji dokumentu.
- **Uzasadnienie:** Rozdzielenie odpowiedzialności usuwa niepoprawne nadpisywanie autora, centralizuje obliczanie liczników, eliminuje N+1 w szablonach i zachowuje odrębne znaczenie `MessageReadBy` oraz `Room.seen_by`.
- **Spodziewany efekt:** Poprawne dane audytowe dokumentów, dokładne liczniki nieprzeczytanych wiadomości i prostsza, spójna implementacja zgodna z zasadami KISS, DRY i wspólnego pipeline’u UI.

## 2026-09-11: Oznaczenie wiadomości nieprzeczytanych przy wejściu do czatu

- **Zmienione obszary:** payload historii w `chat.services`, renderowanie historii w `chat.js`, wspólny arkusz Tailwind, safelista i `docs/UI_STANDARDS.html`.
- **Co się zmieniło:** Historia pokoju zwraca `read_by_current_user` obliczone przed zbiorczym oznaczeniem wiadomości jako przeczytanych. Frontend nadaje wiadomościom bez wcześniejszego `MessageReadBy` klasę `tw-chat-message--unread-on-entry` i dopiero potem wysyła `messages-mark-read-bulk`.
- **UI:** Wiadomość otrzymuje subtelne tło i lewy akcent bez zmiany wymiarów. Stan pozostaje widoczny podczas bieżącej wizyty i znika po ponownym wejściu, gdy istnieje już `MessageReadBy`.
- **Przypadek brzegowy:** Pojedyncza wiadomość historyczna korzysta ze ścieżki batch, a ścieżka real-time jest wybierana wyłącznie dla wiadomości z `new=true`; dzięki temu pojedyncza historia jest oznaczana i zapisywana jako przeczytana tak samo jak większy batch.
- **Testy:** Test usługi czatu sprawdza oba stany `read_by_current_user`; uruchomiono pełny zestaw 249 testów Jest.
- **Spodziewany efekt:** Użytkownik po wejściu do pokoju widzi, które wiadomości były nowe, bez utrzymywania dodatkowego stanu w bazie i bez zmiany istniejącego protokołu oznaczania odczytu.

## 2026-09-11: Liczniki wiadomości przy obywatelach i na liście pokoi

- **Zmienione obszary:** lista i szczegóły obywateli, widok i szablon listy pokoi czatu, model `Room`, wspólny CSS oraz `docs/UI_STANDARDS.html`.
- **Co się zmieniło:** Istniejące pokoje 1:1 są zbiorczo mapowane na obywateli, a `get_unread_message_counts_for_rooms()` dostarcza dokładne liczniki wiadomości bez `MessageReadBy`. Te same liczniki są przypisywane wszystkim grupom pokoi na stronie czatu.
- **Deduplikacja UI:** Dodano wspólny komponent `.tw-chat-count` i zastosowano go także w dokumentach, działaniach i głosowaniach zamiast lokalnego formatowania liczby.
- **Wydajność:** `Room.find_private_rooms_for_user_pairs()` korzysta z prefetchu członków i stałej liczby zapytań; liczniki są liczone jednym zapytaniem dla całego widoku, bez N+1.
- **Testy:** Dodano test częściowo przeczytanej rozmowy prywatnej przy obywatelu oraz test dokładnego licznika na liście pokoi.
- **Spodziewany efekt:** Użytkownik widzi tę samą, dokładną liczbę nieprzeczytanych wiadomości przy osobie, na kartach modułów i na liście pokoi czatu.

## 2026-09-11: Wzmocnienie granicy wiadomości nieprzeczytanych

- **Problem:** Pierwotne tło mieszało 45% koloru akcentowego z tłem karty i było praktycznie niewidoczne w części motywów.
- **Co się zmieniło:** Przed pierwszą wiadomością nieprzeczytaną przy wejściu dodano separator „Unread”, a wszystkie wiadomości bez wcześniejszego `MessageReadBy` otrzymują pełne tło `accent-muted` i mocniejszy lewy akcent.
- **Logika:** Wspólna funkcja frontendowa `wasUnreadOnEntry()` steruje zarówno separatorem, jak i klasą wiadomości. Wiadomości czasu rzeczywistego nie są zaliczane do historycznej grupy nieprzeczytanych.
- **UI:** Dodano wspólną klasę `.tw-chat-unread-divider`, safelistę Tailwind i zaktualizowano `docs/UI_STANDARDS.html`.
- **Spodziewany efekt:** Po wejściu do pokoju użytkownik natychmiast widzi granicę nowych wiadomości oraz każdą wiadomość, która nie była wcześniej przeczytana.

## 2026-09-11: Sumy nieprzeczytanych wiadomości w działach czatu

- **Zmienione obszary:** `chat.views`, nagłówki kategorii w `chat/chat.html`, wspólny komponent licznika i `docs/UI_STANDARDS.html`.
- **Co się zmieniło:** Po zbiorczym policzeniu wiadomości bez `MessageReadBy` widok sumuje wartości dla działów Public, Activities, Referendums, Documents i Private, obejmując pokoje aktywne oraz archiwalne.
- **Architektura:** Sumowanie wykorzystuje obiekty pokoi już pobrane do renderowania i nie wykonuje dodatkowych zapytań. Słownik `chat_section_unread_counts` jest jedynym źródłem danych dla nagłówków.
- **UI:** Statyczny wariant `.tw-chat-count--section` umieszcza sumę bezpośrednio po nazwie działu i jest ukrywany dla zera.
- **Testy:** Test widoku czatu sprawdza sumę trzech nieprzeczytanych wiadomości z dwóch pokoi oraz osobny licznik pokoju.
- **Spodziewany efekt:** Użytkownik może ocenić liczbę nowych wiadomości w każdym obszarze jeszcze przed rozwinięciem działu.
