# Plan przebudowy działu zasobów i pomocy

## Stan wdrożenia

Obecny katalog jest wdrożony w `bookkeeping`; wszystkie trzy typy zasobów korzystają już z `resources.Entity`.

- Jednostki finansowe (`financial_asset`), aktywa fizyczne (`physical_asset`) oraz oferty/potrzeby (`resource`) są przechowywane w `resources.Entity`; reguły księgowe pozostają w `bookkeeping`.
- Runtime modele `bookkeeping.Asset`, `bookkeeping.PhysicalAsset` i `bookkeeping.ResourceListing` oraz ich dual-write zostały usunięte. Użytkownik później uruchomił `start_dev.py --full`; read-only sprawdzenie `db/db.sqlite3` potwierdziło `0040`/`0041` oraz brak dawnych tabel. Stan produkcji nie był sprawdzany.
- `LegacyEntityReference` zachowuje stare URL-e finansowe, fizyczne i zasobów oraz linki mapy. Dla dawnych wspólnotowych shadow rows `source_profile_id` jest wyłącznie snapshotem do rollbacku, nie bieżącym przypisaniem.
- Wpisy można dodawać, edytować i usuwać. Nazwa jest unikalna bez rozróżniania wielkości liter w obrębie użytkownika i typu.
- Katalog `/bookkeeping/resource/` jest dostępny po zalogowaniu. Wyszukuje po nazwie i filtruje po typie, miejscowości oraz województwie; pokazuje oferty i potrzeby z odnośnikiem do profilu.
- Formularz i lista własnych wpisów są pod `/bookkeeping/resource/manage/`; ich obsługa zachowuje dotychczasowe uprawnienia właściciela. Sugestie nazw działają w katalogu, nie w formularzu.
- Wspólny słownik został świadomie odrzucony. Wpisy mają ręczny stan aktywny/zamknięty bez automatycznego wygaszania; `bookkeeping.0036` pozostawia istniejące wpisy aktywne. Nie mają zakresu lokalizacji ani archiwum starych pól. Dane profilu są edytowane osobno w ustawieniach.
- Z profilu użytkownika prowadzi tylko odnośnik do zarządzania wpisami w Finanse. Stare adresy zasobów w `obywatele` przekierowują do nowych widoków.
- Oferty i potrzeby nie są markerami mapy; tylko `Entity` typu `physical_asset` trafia na mapę zgodnie z `docs/ongoing/PLAN_MAPA.md`.
- Migracje `0047`–`0048` przeniosły stare pola profilu do wpisów i usunęły stare kolumny; `0055` rozdzieliła wpisy od słownika. Migracja `bookkeeping.0035` przenosi wpisy do `bookkeeping.ResourceListing`, a `obywatele.0056` usuwa stary model po skopiowaniu danych.

Etapy 1–7 poniżej dokumentują dotychczasowe wdrożenie i jego dalszy rozwój; nie oznaczają już docelowej granicy modelu. Etap 8 zastępuje założenia o trzech osobnych modelach i opisuje migrację do `resources.Entity`. Nie odtwarzamy usuniętych pól ani nie dodajemy archiwum bez osobnej decyzji i potwierdzenia dostępności danych źródłowych.

## Powiązanie z planem mapy

- Obecny katalog używa miejscowości i województwa z profilu; nie wyświetla ulicy, numeru domu, numeru mieszkania ani telefonu. Po scaleniu nadal nie ujawnia szczegółowego adresu ani telefonu.
- Kraj, szczegółowe pola adresowe, geokodowanie i ich widoczność na mapie należą do `docs/ongoing/PLAN_MAPA.md`. Nie dodawać tych pól ponownie ani nie traktować adresu profilu jako zasięgu oferty.
- Docelowo oferty/potrzeby i fizyczne aktywa są typami `resources.Entity`; tylko encje typu `physical_asset` trafiają na mapę. Jednostki finansowe również korzystają z encji, ale nie są mapowane.
- Rozszerzenia formularza profilu w planie mapy powinny korzystać z istniejącego `ProfileForm` w ustawieniach oraz formularza onboardingu; nie tworzyć równoległego formularza kontaktowego dla zasobów.

## 1. Cel

Docelowo rozwijać w aplikacji `resources` wspólny katalog encji, łączący jednostki finansowe (`Asset`), fizyczne aktywa (`PhysicalAsset`) oraz wpisy ofert i potrzeb (`ResourceListing`). Każda encja ma typ, wspólne dane potrzebne do wyszukiwania oraz zachowane reguły właściwe dla jej rodzaju. Istniejące widoki i URL-e pozostają kompatybilne w trakcie etapowego przełączenia.

Użytkownik powinien móc przede wszystkim:

- znaleźć osobę, która oferuje potrzebną pomoc;
- dodać własną ofertę pomocy;
- zgłosić własną potrzebę;
- wyszukiwać i filtrować encje według typu, nazwy, opisu, lokalizacji i bieżącego przypisania;
- przejść z wyniku wyszukiwania do profilu osoby i skontaktować się z nią;
- odróżnić autora rekordu od aktualnej osoby lub społeczności, której przypisano zasób.

Jednostką wyników jest pojedyncza encja. Oferty i potrzeby zachowują swobodne nazwy oraz istniejące typy; nie wprowadzać wspólnego słownika bez osobnej potrzeby. Wyszukiwanie wyłącznie po lokalizacji nadal może pokazywać osobno aktywnych obywateli bez wpisów.

## Docelowy model encji i własności

- `resources.Entity` jest wspólnym, wyszukiwalnym rekordem z typem, nazwą, opisem, autorem, bieżącym przypisaniem oraz znacznikami czasu.
- Typ encji rozróżnia co najmniej jednostkę finansową, fizyczne aktywo i wpis oferty/potrzeby. Pola specyficzne dla typu i ich ograniczenia pozostają właściwe dla domeny; nie dopuścić do przypadkowego wypełniania niezgodnych pól.
- Autor oznacza osobę, która utworzyła wpis; bieżące przypisanie oznacza aktualnego posiadacza/odpowiedzialnego i może być zmieniane osobno. Autor może przypisać encję innemu aktywnemu członkowi społeczności.
- Wariant A dla wspólnej własności: przypisanie ma zakres `community`, oznaczający całą społeczność tej instancji, albo wskazuje pojedynczego członka. Nie dodawać modelu nazwanych grup ani nie używać `auth.Group` do własności.
- Walidować, że wybrane przypisanie jest jednoznaczne: dokładnie członek albo społeczność. Jednostki finansowe będące konfiguracją księgową nie wymagają przypisania członkowi ani społeczności.
- Nowe encje tworzone przez członków wymagają autora. Dla historycznych rekordów bez wiarygodnej informacji o autorze lub właścicielu zachować nieznany stan zamiast dopisywać fikcyjne dane; autor systemowych jednostek finansowych może pozostać pusty.
- Ustalić uprawnienia zmiany, zamknięcia i usunięcia encji: autor może ustawić początkowe przypisanie; operacje wykonywane później muszą respektować bieżące przypisanie i dotychczasowe ograniczenia edycji wpisów.

## 2. Ustalone decyzje projektowe i stan

- [x] Edycja danych profilu jest oddzielona od zarządzania zasobami; profil zawiera wyłącznie odnośnik do zarządzania wpisami w `bookkeeping`.
- [x] Formularz obsługuje wiele osobnych wpisów.
- [x] Dostępne typy to: rzecz do oddania, rzecz do pożyczenia, rzecz na sprzedaż i potrzeba.
- [x] Wspólny słownik nie jest potrzebny; wpis przechowuje jedną swobodną nazwę tekstową.
- [x] Wpis może zawierać krótki opis.
- [x] Katalog wymaga zalogowania; wyniki obejmują wyłącznie aktywne profile.
- [x] Katalog `bookkeeping` pozostaje przy filtrach miejscowości i województwa; szczegółową lokalizację profilu obsługuje osobno plan mapy.
- [x] Sam filtr lokalizacji pokazuje osoby z wybranej miejscowości/województwa nawet wtedy, gdy nie wystawiły żadnego wpisu.
- [x] Wynik prowadzi do profilu osoby; kontakt odbywa się poza katalogiem.
- [x] Właściciel może ręcznie zamknąć i ponownie otworzyć wpis; zamknięte wpisy nie pojawiają się w katalogu ofert.
- [x] Wspólny słownik i globalna kontrola podobieństwa nazw są poza zakresem; unikalność obowiązuje dla tego samego użytkownika i typu.
- [x] Stare pola zostały przeniesione do wpisów migracją i usunięte; nie utworzono archiwum ani migracji zatwierdzanej przez użytkownika.

## 3. Etap 1 - rozdzielenie danych podstawowych

- [x] Użyć istniejącego `ProfileForm` jako osobnego formularza edycji profilu w ustawieniach.
- [x] Oddzielić edycję imienia i nazwiska, miejscowości, województwa, telefonu i sposobu kontaktu od zarządzania wpisami; pozostałe pola profilu są w tym samym formularzu.
- [x] Rozdzielić nawigację: ustawienia profilu prowadzą do edycji danych i osobno do zarządzania zasobami.
- [x] Zachować stare adresy zasobów jako przekierowania do widoków w `bookkeeping`; edycja danych profilu pozostaje w `/obywatele/settings/`.
- [x] Stare pola usunięto migracją `0048` po przeniesieniu ich wartości do wpisów migracją `0047`; nie ma osobnych kolumn archiwalnych.
- [x] Widok ustawień pokazuje dane profilu oraz odnośnik do zarządzania zasobami, bez wyświetlania wpisów.
- [x] Testy obejmują odczyt i zapis danych profilu w nowym przepływie.

## 4. Etap 2 - model wpisów w bookkeeping

- [x] Model `bookkeeping.ResourceListing` przechowuje osobny wpis z nazwą, opisem, typem i właścicielem (`obywatele.Uzytkownik`).
- [x] Oferta i potrzeba są typami wpisu, a nie osobnymi modelami.
- [x] Integralność nazwy zabezpiecza ograniczenie unikalności (nazwa bez rozróżniania wielkości liter, właściciel, typ).
- [x] Wspólny słownik odrzucono jako niepotrzebny; wpis pozostaje niezależny i ma jedną nazwę tekstową.
- [x] Wpisy zostały przeniesione z `obywatele.ResourceAssignment` migracją danych z zachowaniem identyfikatorów, właścicieli, opisów i znaczników czasu; migracja jest odwracalna.
- [x] `ResourceListing.is_closed` rozróżnia wpisy aktywne i zamknięte; migracja ustawia istniejące wpisy jako aktywne.
- [x] Migracja `bookkeeping.0036` dodaje zamknięcie bez zmiany istniejącego właściciela i pozostałych danych wpisu.

## 5. Etap 3 - wyszukiwanie nazw i duplikaty

- [x] Kategorie i wspólny słownik nie są potrzebne w przyjętym wariancie.
- [x] Wyszukiwarka katalogu podpowiada pasujące nazwy istniejących wpisów.
- [x] Formularz normalizuje białe znaki; model blokuje duplikat nazwy bez rozróżniania wielkości liter u tego samego właściciela i typu.
- [x] Nie stosujemy kontroli podobieństwa ani scalania nazw między użytkownikami; wspólny słownik i globalna unikalność nie są potrzebne.

## 6. Etap 4 - formularz wpisów

- [x] Formularz i katalog są częścią `bookkeeping`; profil prowadzi do osobnej strony zarządzania wpisami.
- [x] Właściciel może edytować i usuwać własny wpis; operacje na cudzym wpisie są niedostępne.
- [x] Właściciel może ręcznie zamykać i przywracać wpisy; zarządzanie pokazuje aktywne i zamknięte osobno, a katalog udostępnia tylko aktywne.
- [x] Widok korzysta ze wspólnych klas i komponentów UI.
- [x] Istnieją testy tworzenia, edycji, usuwania, walidacji i zachowania uprawnień właściciela.

## 7. Etap 5 - obsługa historycznych danych

- [x] Migracja `0047` przeniosła niepuste stare pola do wpisów; migracja `0048` usunęła stare pola z modelu profilu.
- [x] Migracja `0055` rozdzieliła wpisy na niezależne rekordy z własną nazwą i opisem, bez wspólnego `ResourceItem`.
- [x] Migracje `bookkeeping.0034`–`0035` utworzyły `ResourceListing` i przeniosły dane; `bookkeeping.0036` dodała ręczny status, a `obywatele.0056` usuwa stary model dopiero po transferze.
- Archiwum historycznych pól nie istnieje w aplikacji: migracje `0047`–`0048` przeniosły wartości do wpisów i usunęły źródłowe kolumny, a `0055` usunęła wspólny `ResourceItem` bez bezpiecznego reverse. Odtworzenie wymaga zweryfikowanego backupu sprzed migracji i osobnej decyzji; backupu nie sprawdzano.
- [x] Ogólna procedura tworzenia backupu i odtwarzania SQLite jest udokumentowana w `docs/DEPLOYMENT_INSTRUCTIONS.md`; przed migracją produkcyjną wymaga aktualnego, zweryfikowanego backupu i użycia właściwego runbooka. Nie wykonywano backupu ani restore w ramach tego cutoveru.

## 8. Etap 6 - katalog i wyszukiwanie

- [x] Katalog ofert i potrzeb jest częścią `bookkeeping` i nie miesza się z finansowym rejestrem `Asset`.
- [x] Dostępne są wyszukiwanie po nazwie oraz filtry typu, miejscowości i województwa.
- [x] Filtr samej lokalizacji pokazuje oddzielnie osoby bez wpisów; nie miesza ich z kartami ofert i potrzeb.
- [x] Wyszukiwanie korzysta z nazwy wpisu; filtry kategorii nie są potrzebne bez słownika.
- [x] Karty pokazują typ wpisu, opis, właściciela i lokalizację; kontakt prowadzi przez profil.
- [x] Widok katalogu ma paginację i testy wyszukiwania, filtrów, widoczności oraz wyników; liczniki ofert i potrzeb odnoszą się do całego filtrowanego zbioru.

## 9. Etap 7 — dopasowania i dalszy rozwój

- [x] Pokazywać użytkownikowi aktywne, publicznie widoczne oferty pasujące do jego aktywnych potrzeb; pierwsza wersja porównuje nazwy bez rozróżniania wielkości liter i nadmiarowych spacji.
- [x] Mapa społeczności ma osobny zakres i harmonogram w `docs/ongoing/PLAN_MAPA.md`; pozostaje osobnym widokiem, choć docelowo korzysta z `resources.Entity` typu `physical_asset`.

## 10. Zasady bezpieczeństwa i prywatności

- [x] Widoki katalogu i zarządzania wpisami wymagają zalogowania.
- [x] Katalog pokazuje miejscowość/województwo, nie dokładny adres ani numer telefonu.
- [x] Edycja, zamykanie, przywracanie i usuwanie są ograniczone do właściciela wpisu.
- [x] Serwer waliduje typ wpisu; ograniczenie bazy danych zapobiega duplikatom u jednego właściciela dla danego typu.
- [x] Nie ma wspólnego słownika, więc walidacja jego pozycji nie dotyczy obecnego wariantu.
- [x] Stare pola zostały usunięte migracją po przeniesieniu ich wartości do wpisów; nie planować kolejnych destrukcyjnych migracji bez uzgodnienia i weryfikacji danych.

## 11. Kryteria obecnej wersji katalogu

- [x] Użytkownik może utworzyć, edytować i usuwać wiele wpisów czterech typów.
- [x] Wpis ma nazwę i opcjonalny opis; katalog ma wyszukiwanie po nazwie i filtry lokalizacji.
- [x] Zalogowany użytkownik może przejść z wpisu do profilu autora bez ujawniania numeru telefonu w wynikach.
- [x] Testy obejmują formularze, uprawnienia, filtry, widoczność i wyniki katalogu.
- [x] Użytkownik edytuje dane profilu osobno; w profilu widzi tylko odnośnik do wpisów w `bookkeeping`.
- [x] Wpisy można ręcznie zamykać i ponownie otwierać.
- [x] Archiwum historycznych pól pozostaje poza obecną wersją; po migracji nie ma osobnej kopii tych wartości w schemacie.
- [x] Wspólny słownik został świadomie wyłączony z zakresu.

## Etap docelowy — scalenie modeli w resources

- [x] Utworzyć aplikację `resources` i wspólny model `Entity`; zdefiniować typy encji, pola wspólne i walidację pól specyficznych dla typu.
- [x] Rozdzielić autora od bieżącego przypisania. Nowe wpisy otrzymują autora; autor może przypisać zasób innemu aktywnemu członkowi.
- [x] Wdrożyć wariant A własności wspólnej: zakres przypisania `community` oznacza całą społeczność instancji; nie tworzyć nazwanych grup ani nie używać `auth.Group`.
- [x] Zachować oferty i potrzeby (`give`, `borrow`, `sale`, `need`), opis, stan zamknięcia, znaczniki czasu i unikalność nazw dla przypisania członek/społeczność.
- [x] Skopiować istniejące fizyczne aktywa addytywną migracją do `resources.Entity`; zachować kraj, miejscowość i szczegóły adresu oraz zapisać mapowanie starego modelu/PK. Nie wymyślać autora ani przypisania dla danych historycznych.
- [x] Skopiować `ResourceListing` addytywną migracją z typem, opisem, archiwum, datami, przypisanym profilem i mapowaniem starego modelu/PK. Nie dopisywać autora, którego źródło danych nie potwierdza.
- [x] Przenieść fizyczne aktywa do typu `physical_asset`, zachowując adres i reguły mapy z `PLAN_MAPA.md`; nie ujawniać autora ani przypisania w payloadzie mapy.
- [x] Przełączyć fizyczne formularze tworzenia/edycji bezpośrednio na `Entity`. Nowy rekord otrzymuje autora i jawne przypisanie; tylko autor może później zmienić przypisanie, a historyczny autor pozostaje nieznany. Stare fizyczne URL-e zachowuje `LegacyEntityReference`.
- [x] Przełączyć agregację mapy na wszystkie encje `physical_asset`, zachować stare linki szczegółów przez `LegacyEntityReference` i usunąć fallback do modelu legacy po preflight.
- [x] Usunąć dual-write i runtime `ResourceListing`; zachować stare URL-e przez `LegacyEntityReference` oraz dotychczasową kaskadę wpisów legacy członka przez sygnał usuwający przypisaną, nie-wspólnotową encję. Wspólnotowe zasoby pozostają niezależne od dawnego profilu.
- [x] Skopiować finansowy `Asset` jako typ jednostki finansowej. Zachować kod, symbol, precyzję, domyślną jednostkę i ograniczenia integralności; nie przypisywać waluty członkowi ani społeczności. Relacje transakcji nadal wskazują na starą tabelę.
- [x] Dodać nullable `Transaction.entity` i wypełnić je z mapowania finansowego `Asset`; przerwać migrację, jeśli transakcyjnemu aktywu brakuje encji. Zachować dotychczasowy FK `Transaction.asset`.
- [x] Skopiować dane addytywnymi migracjami z mapowaniem `(stary model, stary PK) -> Entity PK`, ponieważ identyfikatory tabel mogą się powtarzać. Nie usuwać tabel źródłowych w tej fazie.
- [x] Utrzymywać kopię jednostki finansowej przy tworzeniu/edycji/usuwaniu przez CRUD i uzupełniać `Transaction.entity` przy zapisie transakcji; pozostawić `Transaction.asset` jako dotychczasowe źródło odczytu na czas przejściowy.
- [x] Przełączyć formularz/listę/szczegóły transakcji, feed, saldo, pulpit i raporty na finansowe `Entity`; zachować starą trasę szczegółów i FK `Transaction.asset` jako przejściową kompatybilność.
- [x] Przełączyć listę, szczegóły oraz tworzenie i edycję jednostek finansowych na `Entity`; mapować stare URL-e przez `LegacyEntityReference`, a legacy `Asset` zachować jako shadow dla istniejących FK i tras.
- [x] Przy usuwaniu jednostki przez stary URL usuwać shadow i encję w jednej transakcji; transakcje nadal blokują usunięcie przez FK `PROTECT`.
- [x] Usunąć legacy FK `Transaction.asset` i model `bookkeeping.Asset` po audycie dual-write oraz zgodności danych; `Transaction.entity` jest wymagane, a stare adresy jednostek finansowych nadal rozwiązują `LegacyEntityReference`.
- [x] Dla starych `ResourceListing` zachować profil jako bieżące przypisanie; autor pozostaje nieznany, bo źródło danych nie potwierdza historii utworzenia ani transferów.
- [x] Dla starych aktywów fizycznych bez danych o autorze/właścicielu nie dopisywać fikcyjnych użytkowników. Właściciela wspólnotowego ustawiać tylko po potwierdzeniu, że rekord reprezentuje własność całej społeczności.
- [x] Przełączyć katalog oraz tworzenie/edycję/archiwizację zasobów na `Entity`; obsłużyć autora, przypisanie do członka lub wspólnoty, legacy URL-e oraz kaskadowe usuwanie starych wpisów członkowskich.
- [x] Udostępnić wspólne wyszukiwanie i filtrowanie po typie, nazwie, opisie, lokalizacji, stanie i przypisaniu. Katalog obejmuje jednostki finansowe, fizyczne aktywa i oferty/potrzeby; nie wyświetla szczegółowych adresów ani autorów. Zamknięte oferty/potrzeby są widoczne wyłącznie autorowi, przypisanemu członkowi albo członkowi przeglądającemu zasób wspólnotowy.
- [x] Dodać testy migracji i zgodności kopii: brak utraty rekordów/relacji źródłowych, mapowanie kolidujących PK, zachowanie pól waluty, domyślności i transakcji oraz przypisania zasobów.
- [x] Po audycie odwołań, preflight zgodności i testach rollbacku usunąć `PhysicalAsset`, `ResourceListing` oraz ich dual-write; `LegacyEntityReference` pozostaje wyłącznie dla starych URL-i/mapy, a `source_profile_id` zachowuje historyczny shadow owner do rollbacku.
