# Plan przebudowy działu zasobów i pomocy

## Stan wdrożenia

Katalog zasobów działa już w uproszczonym wariancie, który różni się od pierwotnego projektu:

- `ResourceListing` w `bookkeeping` jest osobnym wpisem użytkownika: ma nazwę, opis i jeden z typów: do oddania, do pożyczenia, na sprzedaż albo potrzeba. Nie jest finansowym `Asset` ani transakcją.
- Wpisy można dodawać, edytować i usuwać. Nazwa jest unikalna bez rozróżniania wielkości liter w obrębie użytkownika i typu.
- Katalog `/bookkeeping/resource/` jest dostępny po zalogowaniu. Wyszukuje po nazwie i filtruje po typie, miejscowości oraz województwie; pokazuje oferty i potrzeby z odnośnikiem do profilu.
- Formularz i lista własnych wpisów są pod `/bookkeeping/resource/manage/`; ich obsługa zachowuje dotychczasowe uprawnienia właściciela. Sugestie nazw działają w katalogu, nie w formularzu.
- Wspólny słownik został świadomie odrzucony. Wpisy mają ręczny stan aktywny/zamknięty bez automatycznego wygaszania; `bookkeeping.0036` pozostawia istniejące wpisy aktywne. Nie mają zakresu lokalizacji ani archiwum starych pól. Dane profilu są edytowane osobno w ustawieniach.
- Z profilu użytkownika prowadzi tylko odnośnik do zarządzania wpisami w Finanse. Stare adresy zasobów w `obywatele` przekierowują do nowych widoków.
- `ResourceListing` nie jest markerem mapy. Mapa społeczności i fizyczne aktywa pozostają osobnym zakresem w `docs/ongoing/PLAN_MAPA.md`.
- Migracje `0047`–`0048` przeniosły stare pola profilu do wpisów i usunęły stare kolumny; `0055` rozdzieliła wpisy od słownika. Migracja `bookkeeping.0035` przenosi wpisy do `bookkeeping.ResourceListing`, a `obywatele.0056` usuwa stary model po skopiowaniu danych.

Poniższe etapy opisują stan faktyczny i dalszy kierunek prac. Nie odtwarzamy usuniętych pól ani nie dodajemy archiwum bez osobnej decyzji i potwierdzenia dostępności danych źródłowych. Wspólny słownik został odrzucony jako zbędny.

## Powiązanie z planem mapy

- Katalog zasobów nadal używa wyłącznie miejscowości i województwa z profilu; nie wyświetla ulicy, numeru domu, numeru mieszkania ani telefonu.
- Kraj, szczegółowe pola adresowe, geokodowanie i ich widoczność na mapie należą do `docs/ongoing/PLAN_MAPA.md`. Nie dodawać tych pól ponownie ani nie traktować adresu profilu jako zasięgu oferty.
- Wpisy ofert i potrzeb (`bookkeeping.ResourceListing`) nie są fizycznymi aktywami i nie trafiają na mapę w ramach obecnego zakresu. Fizyczne aktywa mapy są odrębnym źródłem danych w `bookkeeping`.
- Rozszerzenia formularza profilu w planie mapy powinny korzystać z istniejącego `ProfileForm` w ustawieniach oraz formularza onboardingu; nie tworzyć równoległego formularza kontaktowego dla zasobów.

## 1. Cel

Rozwijać w `bookkeeping` katalog ofert i potrzeb użytkowników, zachowując prosty model osobnych wpisów. `bookkeeping.Asset` nadal oznacza jednostkę finansową i nie jest używany do tych wpisów.

Użytkownik powinien móc przede wszystkim:

- znaleźć osobę, która oferuje potrzebną pomoc;
- dodać własną ofertę pomocy;
- zgłosić własną potrzebę;
- przejść z wyniku wyszukiwania do profilu osoby i skontaktować się z nią;
- wyszukiwać wpisy po nazwie, typie i dostępnej lokalizacji.

Jednostką wyników ofert i potrzeb jest pojedynczy wpis przypisany do profilu. Wyjątkiem jest wyszukiwanie wyłącznie po lokalizacji: osobna sekcja pokazuje wtedy również aktywnych obywateli bez wpisów. Nazwy wpisów są swobodne; nie używamy wspólnego słownika.

## 2. Ustalone decyzje projektowe i stan

- [x] Edycja danych profilu jest oddzielona od zarządzania zasobami; profil zawiera wyłącznie odnośnik do zarządzania wpisami w `bookkeeping`.
- [x] Formularz obsługuje wiele osobnych wpisów.
- [x] Dostępne typy to: rzecz do oddania, rzecz do pożyczenia, rzecz na sprzedaż i potrzeba.
- [x] Wspólny słownik nie jest potrzebny; wpis przechowuje jedną swobodną nazwę tekstową.
- [x] Wpis może zawierać krótki opis; dostępność, formę pomocy i warunki należy rozważyć osobno.
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
- [ ] Rozważyć osobne pola dostępności, formy pomocy i warunków.
- [ ] Ewentualny zasięg oferty (np. zdalnie lub promień) wymaga osobnej decyzji; pola adresowe i geokodowanie z planu mapy nie oznaczają zasięgu oferty.

## 5. Etap 3 - wyszukiwanie nazw i duplikaty

- [x] Kategorie i wspólny słownik nie są potrzebne w przyjętym wariancie.
- [x] Wyszukiwarka katalogu podpowiada pasujące nazwy istniejących wpisów.
- [ ] Dodać podpowiedzi do formularza wpisu tylko wtedy, gdy potwierdzi się taka potrzeba.
- [x] Formularz normalizuje białe znaki; model blokuje duplikat nazwy bez rozróżniania wielkości liter u tego samego właściciela i typu.
- [x] Nie stosujemy kontroli podobieństwa ani scalania nazw między użytkownikami; wspólny słownik i globalna unikalność nie są potrzebne.

## 6. Etap 4 - formularz wpisów

- [x] Formularz i katalog są częścią `bookkeeping`; profil prowadzi do osobnej strony zarządzania wpisami.
- [x] Właściciel może edytować i usuwać własny wpis; operacje na cudzym wpisie są niedostępne.
- [x] Właściciel może ręcznie zamykać i przywracać wpisy; zarządzanie pokazuje aktywne i zamknięte osobno, a katalog udostępnia tylko aktywne.
- [ ] Dostępność, forma pomocy, warunki i zasięg nie są jeszcze osobnymi polami; brak automatycznego wygaszania.
- [x] Widok korzysta ze wspólnych klas i komponentów UI.
- [x] Istnieją testy tworzenia, edycji, usuwania, walidacji i zachowania uprawnień właściciela.

## 7. Etap 5 - obsługa historycznych danych

- [x] Migracja `0047` przeniosła niepuste stare pola do wpisów; migracja `0048` usunęła stare pola z modelu profilu.
- [x] Migracja `0055` rozdzieliła wpisy na niezależne rekordy z własną nazwą i opisem, bez wspólnego `ResourceItem`.
- [x] Migracje `bookkeeping.0034`–`0035` utworzyły `ResourceListing` i przeniosły dane; `bookkeeping.0036` dodała ręczny status, a `obywatele.0056` usuwa stary model dopiero po transferze.
- [ ] Nie ma archiwum ani zatwierdzania migracji przez użytkownika. Nie odtwarzać archiwum bez potwierdzenia, że stare dane są nadal dostępne i wymagane.
- [ ] Sprawdzić i udokumentować dostępne procedury odtworzenia danych w środowiskach, w których migracje zostały już wykonane.

## 8. Etap 6 - katalog i wyszukiwanie

- [x] Katalog ofert i potrzeb jest częścią `bookkeeping` i nie miesza się z finansowym rejestrem `Asset`.
- [x] Dostępne są wyszukiwanie po nazwie oraz filtry typu, miejscowości i województwa.
- [x] Filtr samej lokalizacji pokazuje oddzielnie osoby bez wpisów; nie miesza ich z kartami ofert i potrzeb.
- [x] Wyszukiwanie korzysta z nazwy wpisu; filtry kategorii nie są potrzebne bez słownika.
- [ ] Filtry formy pomocy, dostępności i zasięgu nie istnieją.
- [x] Karty pokazują typ wpisu, opis, właściciela i lokalizację; kontakt prowadzi przez profil.
- [ ] Zdalny zasięg i sortowanie ofert według trafności/odległości nie są obsługiwane; plan mapy nie wprowadza ich do katalogu zasobów.
- [x] Widok katalogu ma paginację i testy wyszukiwania, filtrów, widoczności oraz wyników; liczniki ofert i potrzeb odnoszą się do całego filtrowanego zbioru.

## 9. Etap 7 — dopasowania i dalszy rozwój

- [ ] Pokazywać użytkownikowi oferty pasujące do aktywnych potrzeb.
- [ ] Pokazywać osobom oferującym pomoc nowe pasujące potrzeby, jeśli użytkownik wyrazi na to zgodę.
- [ ] Dodać przypomnienie o potwierdzeniu aktualności wpisu bez automatycznego zamykania w pierwszej wersji.
- [ ] Rozważyć powiadomienia o nowych dopasowaniach.
- [ ] Rozważyć wyszukiwanie ofert po promieniu dopiero po potwierdzeniu potrzeby; współrzędne mapy profili z planu `PLAN_MAPA.md` nie są automatycznie używane do dopasowywania zasobów.
- [x] Mapa społeczności ma osobny zakres i harmonogram w `docs/ongoing/PLAN_MAPA.md`; nie jest częścią katalogu ofert i potrzeb.

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
- [ ] Archiwum historycznych pól pozostaje poza obecną wersją.
- [x] Wspólny słownik został świadomie wyłączony z zakresu.
