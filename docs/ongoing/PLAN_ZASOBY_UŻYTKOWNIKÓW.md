# Plan przebudowy działu zasobów i pomocy

## Stan wdrożenia

Katalog zasobów działa już w uproszczonym wariancie, który różni się od pierwotnego projektu:

- `ResourceAssignment` jest osobnym wpisem użytkownika: ma nazwę, opis i jeden z typów: do oddania, do pożyczenia, na sprzedaż albo potrzeba.
- Wpisy można dodawać, edytować i usuwać. Nazwa jest unikalna bez rozróżniania wielkości liter w obrębie użytkownika i typu.
- Katalog jest dostępny po zalogowaniu. Wyszukuje po nazwie i filtruje po typie, miejscowości oraz województwie; pokazuje oferty i potrzeby z odnośnikiem do profilu.
- Sugestie nazw działają w wyszukiwarce katalogu, ale formularz wpisu nie ma autouzupełniania ani kontroli podobieństwa nazw między użytkownikami.
- Wspólny słownik został świadomie odrzucony. Nie ma statusu zamknięcia, zakresu lokalizacji ani archiwum starych pól; dane profilu są już edytowane osobno w ustawieniach.
- Migracja `0047_migrate_legacy_resources` przeniosła stare pola do wpisów, a migracja `0048` usunęła te pola z profilu. Nie zachowano ich jako osobnego, tylko do odczytu archiwum; migracja `0055` dodatkowo rozdzieliła wpisy od wspólnego słownika.

Poniższe etapy opisują stan faktyczny i dalszy kierunek prac. Nie odtwarzamy usuniętych pól ani nie dodajemy archiwum bez osobnej decyzji i potwierdzenia dostępności danych źródłowych. Wspólny słownik został odrzucony jako zbędny.

## 1. Cel

Rozwijać dział `/obywatele/assets/` oraz formularz `/obywatele/my_assets/` jako katalog ofert i potrzeb, zachowując prosty model osobnych wpisów.

Użytkownik powinien móc przede wszystkim:

- znaleźć osobę, która oferuje potrzebną pomoc;
- dodać własną ofertę pomocy;
- zgłosić własną potrzebę;
- przejść z wyniku wyszukiwania do profilu osoby i skontaktować się z nią;
- wyszukiwać wpisy po nazwie, typie i dostępnej lokalizacji.

Jednostką katalogu jest pojedynczy wpis przypisany do profilu, a nie cały profil obywatela. Nazwy wpisów są swobodne; nie używamy wspólnego słownika.

## 2. Ustalone decyzje projektowe i stan

- [x] Edycja danych profilu jest oddzielona od zarządzania zasobami; formularz profilu jest w ustawieniach, a `/obywatele/my_assets/` zarządza wyłącznie wpisami.
- [x] Formularz obsługuje wiele osobnych wpisów.
- [x] Dostępne typy to: rzecz do oddania, rzecz do pożyczenia, rzecz na sprzedaż i potrzeba.
- [x] Wspólny słownik nie jest potrzebny; wpis przechowuje jedną swobodną nazwę tekstową.
- [x] Wpis może zawierać krótki opis; dostępność, formę pomocy i warunki należy rozważyć osobno.
- [x] Katalog wymaga zalogowania; wyniki obejmują wyłącznie aktywne profile.
- [ ] Rozszerzyć lokalizację poza istniejące filtry miejscowości i województwa, jeśli pojawi się uzasadniona potrzeba.
- [x] Wynik prowadzi do profilu osoby; kontakt odbywa się poza katalogiem.
- [ ] Dodać ręczne zamykanie wpisu; obecnie można go edytować lub usunąć.
- [x] Wspólny słownik i globalna kontrola podobieństwa nazw są poza zakresem; unikalność obowiązuje dla tego samego użytkownika i typu.
- [x] Stare pola zostały przeniesione do wpisów migracją i usunięte; nie utworzono archiwum ani migracji zatwierdzanej przez użytkownika.

## 3. Etap 1 - rozdzielenie danych podstawowych

- [x] Użyć istniejącego `ProfileForm` jako osobnego formularza edycji profilu w ustawieniach.
- [x] Przenieść edycję imienia i nazwiska, miejscowości, województwa, telefonu i sposobu kontaktu poza `my_assets.html`; pozostałe pola profilu są w tym samym formularzu.
- [x] Rozdzielić nawigację: ustawienia profilu prowadzą do edycji danych i osobno do zarządzania zasobami.
- [x] Zachować istniejący adres `/obywatele/my_assets/` dla zasobów oraz użyć istniejącego `/obywatele/settings/` do edycji profilu.
- [x] Stare pola usunięto migracją `0048` po przeniesieniu ich wartości do wpisów migracją `0047`; nie ma osobnych kolumn archiwalnych.
- [x] Widok ustawień pokazuje dane profilu i zasoby w osobnych sekcjach.
- [x] Testy obejmują odczyt i zapis danych profilu w nowym przepływie.

## 4. Etap 2 - model wpisów

- [x] Model `ResourceAssignment` przechowuje osobny wpis z nazwą, opisem, typem i właścicielem.
- [x] Oferta i potrzeba są typami wpisu, a nie osobnymi modelami.
- [x] Integralność nazwy zabezpiecza ograniczenie unikalności (nazwa bez rozróżniania wielkości liter, właściciel, typ).
- [x] Wspólny słownik odrzucono jako niepotrzebny; wpis pozostaje niezależny i ma jedną nazwę tekstową.
- [ ] Rozważyć status aktywny/zamknięty oraz pola dostępności, formy pomocy i warunków.
- [ ] Rozważyć zasięg lokalizacyjny bez zapisywania dokładnego adresu domowego.

## 5. Etap 3 - wyszukiwanie nazw i duplikaty

- [x] Kategorie i wspólny słownik nie są potrzebne w przyjętym wariancie.
- [x] Wyszukiwarka katalogu podpowiada pasujące nazwy istniejących wpisów.
- [ ] Dodać podpowiedzi do formularza wpisu tylko wtedy, gdy potwierdzi się taka potrzeba.
- [x] Formularz normalizuje białe znaki; model blokuje duplikat nazwy bez rozróżniania wielkości liter u tego samego właściciela i typu.
- [x] Nie stosujemy kontroli podobieństwa ani scalania nazw między użytkownikami; wspólny słownik i globalna unikalność nie są potrzebne.

## 6. Etap 4 - formularz wpisów

- [x] Formularz zarządza osobnymi wpisami; pozwala wybrać jeden z czterech typów i dodać opis.
- [x] Właściciel może edytować i usuwać własny wpis; operacje na cudzym wpisie są niedostępne.
- [ ] Dodać zamykanie wpisu i podział na aktywne/zamknięte, jeśli zostaną przyjęte jako wymaganie.
- [ ] Dostępność, forma pomocy, warunki i zasięg nie są jeszcze osobnymi polami.
- [x] Widok korzysta ze wspólnych klas i komponentów UI.
- [x] Istnieją testy tworzenia, edycji, usuwania, walidacji i uprawnień.

## 7. Etap 5 - obsługa historycznych danych

- [x] Migracja `0047` przeniosła niepuste stare pola do wpisów; migracja `0048` usunęła stare pola z modelu profilu.
- [x] Migracja `0055` rozdzieliła wpisy na niezależne rekordy z własną nazwą i opisem, bez wspólnego `ResourceItem`.
- [ ] Nie ma archiwum ani zatwierdzania migracji przez użytkownika. Nie odtwarzać archiwum bez potwierdzenia, że stare dane są nadal dostępne i wymagane.
- [ ] Sprawdzić i udokumentować dostępne procedury odtworzenia danych w środowiskach, w których migracje zostały już wykonane.

## 8. Etap 6 - katalog i wyszukiwanie

- [x] Katalog pokazuje osobne wpisy ofert i potrzeb zamiast tabeli profili.
- [x] Dostępne są wyszukiwanie po nazwie oraz filtry typu, miejscowości i województwa.
- [x] Wyszukiwanie korzysta z nazwy wpisu; filtry kategorii nie są potrzebne bez słownika.
- [ ] Filtry formy pomocy, dostępności i zasięgu nie istnieją.
- [x] Karty pokazują typ wpisu, opis, właściciela i lokalizację; kontakt prowadzi przez profil.
- [ ] Zdalny zasięg i sortowanie według trafności/odległości nie są obsługiwane.
- [x] Widok katalogu ma paginację i testy wyszukiwania, filtrów, widoczności oraz wyników.

## 9. Etap 7 — dopasowania i dalszy rozwój

- [ ] Pokazywać użytkownikowi oferty pasujące do aktywnych potrzeb.
- [ ] Pokazywać osobom oferującym pomoc nowe pasujące potrzeby, jeśli użytkownik wyrazi na to zgodę.
- [ ] Dodać przypomnienie o potwierdzeniu aktualności wpisu bez automatycznego zamykania w pierwszej wersji.
- [ ] Rozważyć powiadomienia o nowych dopasowaniach.
- [ ] Rozważyć przybliżone współrzędne i wyszukiwanie po promieniu dopiero po sprawdzeniu użyteczności lokalizacji miejskiej.
- [ ] Rozważyć mapę dopiero po wdrożeniu ochrony prywatności lokalizacji i potwierdzeniu realnej potrzeby.

## 10. Zasady bezpieczeństwa i prywatności

- [x] Widoki katalogu i zarządzania wpisami wymagają zalogowania.
- [x] Katalog pokazuje miejscowość/województwo, nie dokładny adres ani numer telefonu.
- [x] Edycja i usuwanie są ograniczone do właściciela wpisu.
- [x] Serwer waliduje typ wpisu; ograniczenie bazy danych zapobiega duplikatom u jednego właściciela dla danego typu.
- [x] Nie ma wspólnego słownika, więc walidacja jego pozycji nie dotyczy obecnego wariantu.
- [x] Stare pola zostały usunięte migracją po przeniesieniu ich wartości do wpisów; nie planować kolejnych destrukcyjnych migracji bez uzgodnienia i weryfikacji danych.

## 11. Kryteria obecnej wersji katalogu

- [x] Użytkownik może utworzyć, edytować i usuwać wiele wpisów czterech typów.
- [x] Wpis ma nazwę i opcjonalny opis; katalog ma wyszukiwanie po nazwie i filtry lokalizacji.
- [x] Zalogowany użytkownik może przejść z wpisu do profilu autora bez ujawniania numeru telefonu w wynikach.
- [x] Testy obejmują formularze, uprawnienia, filtry, widoczność i wyniki katalogu.
- [x] Użytkownik edytuje dane profilu osobno od wpisów zasobów.
- [ ] Zamykanie wpisów i archiwum historycznych pól pozostają poza obecną wersją.
- [x] Wspólny słownik został świadomie wyłączony z zakresu.
