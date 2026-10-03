# Plan przebudowy działu zasobów i pomocy

## 1. Cel

Przebudować dział `/obywatele/assets/` oraz powiązany formularz `/obywatele/my_assets/` z przeszukiwarki tekstowych pól profilu w katalog **ofert i potrzeb pomocy**.

Użytkownik powinien móc przede wszystkim:

- znaleźć osobę, która oferuje potrzebną pomoc;
- dodać własną ofertę pomocy;
- zgłosić własną potrzebę;
- przejść z wyniku wyszukiwania do profilu osoby i skontaktować się z nią;
- korzystać ze wspólnego, standaryzowanego słownika umiejętności i zasobów.

Jednostką katalogu będzie oferta albo potrzeba, a nie cały profil obywatela.

## 2. Ustalone decyzje projektowe

- [ ] Imię, nazwisko, miejscowość, województwo oraz komunikator/telefon wydzielić do osobnego formularza „Podstawowe dane kontaktowe” w ustawieniach profilu.
- [ ] Formularz pomocy będzie obsługiwał wiele osobnych wpisów, a nie jedno duże pole tekstowe.
- [ ] W pierwszej wersji obsługiwane będą cztery typy wpisów:
  - [ ] pomoc lub umiejętność;
  - [ ] rzecz do oddania;
  - [ ] rzecz do pożyczenia;
  - [ ] potrzeba pomocy lub zasobu.
- [ ] Jeden wpis może mieć przypisanych wiele pozycji ze słownika.
- [ ] Każdy wpis może zawierać krótki opis, dostępność, formę pomocy i warunki.
- [ ] Wpisy i lokalizacja będą widoczne wyłącznie dla zalogowanych członków.
- [ ] Pierwsza wersja lokalizacji wykorzysta miejscowość/województwo oraz zasięg, np. zdalnie, miejscowość, gmina, województwo lub cała Polska.
- [ ] Po znalezieniu wpisu użytkownik przechodzi do profilu osoby; nie wprowadzamy na tym etapie osobnego pośredniego systemu akceptowania kontaktu.
- [ ] Wpisy będą zamykane ręcznie przez właściciela. Automatyczne wygaszanie nie jest częścią pierwszej wersji.
- [ ] Każdy użytkownik może dodać nową pozycję do słownika, ale zapis podobnej pozycji zostaje zablokowany przez dynamiczne wyszukiwanie podobnych nazw.
- [ ] Stare dane pozostaną przejściowo w osobnej sekcji archiwalnej, tylko do odczytu i z możliwością całkowitego usunięcia przez użytkownika.
- [ ] Migracja starych danych będzie stopniowa. System może proponować nowe wpisy na podstawie starej treści, ale użytkownik zatwierdza propozycje.

## 3. Etap 1 — rozdzielenie danych podstawowych

- [ ] Zaprojektować osobny formularz podstawowych danych kontaktowych.
- [ ] Przenieść do niego imię i nazwisko, miejscowość, województwo oraz komunikator/telefon.
- [ ] Ustalić docelową nawigację między profilem podstawowym a formularzem pomocy.
- [ ] Zachować dotychczasowe adresy URL lub przygotować bezpieczne przekierowania.
- [ ] Nie usuwać jeszcze żadnych istniejących pól ani danych użytkowników.
- [ ] Zaktualizować widok profilu tak, aby dane podstawowe i zasoby były wyraźnie rozdzielone.
- [ ] Dodać testy zapisu i odczytu danych podstawowych.

## 4. Etap 2 — model słownika i wpisów

- [ ] Zaprojektować model kontrolowanego słownika umiejętności, usług i zasobów.
- [ ] Przewidzieć nazwę wyświetlaną, opis, typ/kategorię nadrzędną oraz warianty wyszukiwania.
- [ ] Zaprojektować model oferty pomocy.
- [ ] Zaprojektować model potrzeby pomocy.
- [ ] Dodać relację wiele-do-wielu między wpisem a pozycjami słownika.
- [ ] Dodać status wpisu, co najmniej aktywny i zamknięty.
- [ ] Dodać pola opisu, dostępności, formy pomocy i warunków.
- [ ] Dodać zasięg lokalizacyjny bez zapisywania dokładnego adresu domowego.
- [ ] Przygotować migracje oraz testy ograniczeń integralności.

## 5. Etap 3 — słownik i ochrona przed duplikatami

- [ ] Przygotować pierwszą, małą listę kategorii i pozycji, np. pomoc informatyczna, transport, naprawy, edukacja i opieka.
- [ ] Zaimplementować dynamiczne wyszukiwanie podobnych pozycji podczas dodawania nowej.
- [ ] Zablokować zapis, gdy nowa nazwa jest zbyt podobna do istniejącej.
- [ ] Przed blokadą pokazać użytkownikowi znalezione podobne pozycje i umożliwić ich wybór.
- [ ] Ustalić reguły normalizacji nazw, między innymi wielkości liter, białych znaków i podstawowych wariantów językowych.
- [ ] Dodać ochronę przed wyścigiem dwóch równoczesnych zapisów tej samej pozycji.
- [ ] Przygotować mechanizm późniejszego scalania lub korekty pozycji słownika, jeśli mimo zabezpieczeń powstanie duplikat.

## 6. Etap 4 — nowy formularz pomocy

- [ ] Zastąpić ręczne pola tekstowe ekranem zarządzania osobnymi wpisami.
- [ ] Dodać przycisk „Dodaj ofertę pomocy”.
- [ ] Dodać przycisk „Dodaj potrzebę”.
- [ ] Pozwolić wybrać wiele pozycji ze słownika.
- [ ] Dodać wybór typu zasobu: pomoc/umiejętność, rzecz do oddania, rzecz do pożyczenia lub potrzeba.
- [ ] Dodać opis, dostępność, formę pomocy, warunki i zasięg.
- [ ] Dodać możliwość edycji i ręcznego zamknięcia wpisu.
- [ ] Pokazywać aktywne i zamknięte wpisy w osobnych sekcjach.
- [ ] Zastosować wspólne komponenty UI i standardowy toolbar zamiast tworzyć modułowe, jednorazowe style.
- [ ] Dodać testy formularzy, walidacji i uprawnień.

## 7. Etap 5 — archiwum starych danych i migracja stopniowa

- [ ] Wyświetlić dotychczasowe pola tekstowe w osobnej sekcji „Stare dane”.
- [ ] Ustawić te pola jako tylko do odczytu.
- [ ] Dodać osobne usuwanie treści każdego starego pola.
- [ ] Nie przepisywać ani nie usuwać danych automatycznie podczas wdrożenia.
- [ ] Przygotować mechanizm analizy starego tekstu i proponowania pozycji słownika.
- [ ] Pokazywać propozycje użytkownikowi przed utworzeniem nowych wpisów.
- [ ] Pozwolić użytkownikowi odrzucić, poprawić albo zatwierdzić każdą propozycję.
- [ ] Po zatwierdzeniu zachować stare pole do czasu ręcznego usunięcia przez użytkownika.
- [ ] Rejestrować wyłącznie informacje potrzebne do bezpiecznej migracji; nie ujawniać starej treści innym użytkownikom po jej usunięciu.
- [ ] Przygotować testy, że migracja nie powoduje utraty istniejących danych.

## 8. Etap 6 — katalog i wyszukiwanie pomocy

- [ ] Zastąpić szeroką tabelę obywateli katalogiem ofert i potrzeb.
- [ ] Dodać dwa główne wejścia: „Znajdź pomoc” oraz „Dodaj ofertę pomocy”.
- [ ] Wyszukiwanie oprzeć na pozycjach słownika, a nie na dowolnych fragmentach pól tekstowych.
- [ ] Dodać filtry typu wpisu, kategorii, formy pomocy, dostępności i zasięgu.
- [ ] Pokazywać wyniki jako karty zawierające rodzaj pomocy, lokalizację/zasięg, dostępność i aktualność.
- [ ] Dodać przejście do profilu osoby z wyniku wyszukiwania.
- [ ] Zachować możliwość wyszukania ofert zdalnych niezależnie od miejscowości.
- [ ] Dodać sortowanie według trafności, aktualności oraz — po wdrożeniu danych przestrzennych — odległości.
- [ ] Dodać testy filtrów, widoczności i wyników wyszukiwania.

## 9. Etap 7 — dopasowania i dalszy rozwój

- [ ] Pokazywać użytkownikowi oferty pasujące do aktywnych potrzeb.
- [ ] Pokazywać osobom oferującym pomoc nowe pasujące potrzeby, jeśli użytkownik wyrazi na to zgodę.
- [ ] Dodać przypomnienie o potwierdzeniu aktualności wpisu bez automatycznego zamykania w pierwszej wersji.
- [ ] Rozważyć powiadomienia o nowych dopasowaniach.
- [ ] Rozważyć przybliżone współrzędne i wyszukiwanie po promieniu dopiero po sprawdzeniu użyteczności lokalizacji miejskiej.
- [ ] Rozważyć mapę dopiero po wdrożeniu ochrony prywatności lokalizacji i potwierdzeniu realnej potrzeby.

## 10. Zasady bezpieczeństwa i prywatności

- [ ] Dane i wpisy widzą wyłącznie zalogowani członkowie.
- [ ] Nie ujawniać dokładnego adresu ani dokładnego punktu zamieszkania.
- [ ] Nie ujawniać numeru telefonu automatycznie na liście wyników.
- [ ] Wszystkie operacje edycji i usuwania ograniczyć do właściciela wpisu lub odpowiednio uprawnionej osoby.
- [ ] Walidować typ wpisu, pozycje słownika i zakres lokalizacyjny po stronie serwera.
- [ ] Zabezpieczyć tworzenie pozycji słownika przed duplikatami również na poziomie bazy danych.
- [ ] Nie wykonywać destrukcyjnej migracji istniejących danych.

## 11. Kryteria zakończenia pierwszej wersji

- [ ] Użytkownik może oddzielnie edytować podstawowe dane kontaktowe.
- [ ] Użytkownik może utworzyć wiele ofert i potrzeb.
- [ ] Każdy wpis używa pozycji ze wspólnego słownika.
- [ ] Użytkownik może ręcznie zamknąć wpis.
- [ ] Stare dane są zachowane, tylko do odczytu i możliwe do usunięcia.
- [ ] System proponuje migrację starej treści, ale nie usuwa jej bez decyzji użytkownika.
- [ ] Członek może znaleźć ofertę po ustandaryzowanej kategorii i przejść do profilu osoby.
- [ ] Podstawowe filtry lokalizacji działają bez ujawniania dokładnego miejsca zamieszkania.
- [ ] Logika migracji, uprawnień, słownika i wyszukiwania jest pokryta odpowiednimi testami.
