# To są notatki użytkownika, AI nie wolno tutaj zmieniać nic.

Zachowaj standardy ui i tw-* i dąż do unifikację i prostoty.
Pokaż mi co zamierzasz zrobić przed zmianami w kodzie.

# PILNE

# DROBNE

# OGÓLNE

Unowocześnij:
  http://127.0.0.1:8000/accounts/password/change/
  http://127.0.0.1:8000/obywatele/change_email/
  http://127.0.0.1:8000/obywatele/change_username/

- wersjonowanie dokumentów, Działań. Tylko jedna wersja na dzień. 
- Backup kontaktów, przepisów, ogłoszeń, itd. Każdy powinien móc zrobić w postaci fixtures i md.
- Mapa ze społecznościami. Zlinkować otwarte grupy, partnerów z Finanse, Obywateli. Automatycznie można na podstawie miasta.
- Refaktoryzacje:
  - board > documents
  - events > calendar
  - glosowania > voting
  - obywatele > citizens
- Dokończyć Fixtures (przepisy, pokoje, ogłoszenia, Start, Footer, Custom email) i dodać je do skryptu instalacyjnego. Start, Footer i Custom emails powinny mieć swój oddzielny dział / znaczniki typu.
- Wszędzie: Ograniczyć możliwość dodawania treść po to żeby uniknąć manipulacji polegającej na tym, że zły aktor zarzuca grupę dużą ilością głosowań i przemyca w ten sposób niekorzystne dla grupy rozwiązania.

# AKTYWNOSC

- powiadomienie po dodaniu argumentu za/przeciw do referendum .
- wyszukiwarka do aktywnosc/
- Pokazuj etykiety z modułów działania, dokumenty, głosowania na powiadomieniach w aktywnosc/. Na przykład w głosowaniach - zatwierdzone itd. Te etykiety powinny być też w e-mailach codziennych. Dotyczy to też Kategorii z działań i dokumentów.


# GÓRNE MENU
- Strzałka w breadcrumbs. Czyli zamiast "Ludzie Zasoby" albo "Ludzie zrób "Ludzie > Zasoby". Podobnie jak na dużym i małym ekranie.


# PROFIL UŻYTKOWNIKA 

- Umiejętności wybierane z listy i współdzielone z Działaniami. Jedna osoba dodaje umiejętność/zainteresowanie/hobby, pozostałe osoby mogą wybrać te rzeczy z listy.
- Powinniśmy dodać ludziom wybór co do formy kontaktu. Niektórzy ludzie wolą telefon, a inni komunikatory. Niektóre komunikatory używają numeru telefonu, a inne nie. Komunikatory, których używamy, to Facebook, Discord, WhatsApp, Telegram, Signal. Opracuj sprytny formularz w taki sposób, żeby użytkownik mógł wybrać jedną lub wiele form kontaktu i żeby to było intuicyjne. Możliwość dodawania specyficznie m.in.: x.com, fb, insta, signal, itd.
- Przechodzimy na nicki w postaci - dwie pierwsze litery imienia, dwie pierwsze litery nazwiska. Jeśli ktoś nie wpisał imienia i nazwiska, to nick pozostaje bez zmian.
- Prywatne notatki o człowieku / osobie.
- Proste wysyłanie SMS z Wikikracji z telefonu

# ANKIETY

wiki - ankiety: punkt otwarty i czat

# DOKUMENTY

- Prosta historia edycji dokumentów. Przydałoby się zapisywać przynajmniej kto edytował kiedy i nie wiem ile zostało zmienione. Nie wiem czy przechowywanie wersji dokumentu ma sens.
- Ocenianie Dokumentów, możliwość sortowania po ocenie.

# ZADANIA (TASKS)
- Corowa część Zadania w Realizacji nie może być modyfikowana.

- Task jako eksperyment: hipoteza, test, wynik. Spodziewamy efekt, eksperymenty, rzeczywisty efekt.
  1. Hipoteza — "Jeśli zrobimy X, stanie się Y" (jedno zdanie)
  2. Metryka sukcesu — konkretna, mierzalna wartość/warunek, po którym poznamy, że hipoteza się potwierdziła
  3. Termin sprawdzenia — data lub punkt, w którym oceniamy wynik. Moment albo sytuacja, w której spodziewane efekty będą już widoczne. (po wyborach, 3 miesiące po konferencji)
  4. Koszt/zasób wejściowy — ile czasu/pieniędzy/osób to pochłonie (żeby było wiadomo, ile można stracić). Czy sukces zależy od osób z zewnątrz.
  5. Wynik i decyzja — pole wypełniane po zakończeniu: co się stało → kontynuować / pivot / zamknąć. Do tego są już guziki.
  To jest właściwie szkielet: hipoteza → jak zmierzymy → kiedy → ile to kosztuje → co z tym zrobimy dalej. Reszta (metodologia, ryzyka, log) może istnieć jako luźne notatki przy projekcie, ale nie musi być osobnym wymaganym polem formularza.
  https://claude.ai/share/797289b6-ee29-4f9e-a3d7-4e30f21deb22

- Statystyki: Ranking koordynatorów
- Zadania: co blokuje wykonanie
- Design szczegółów zadania do poprawienia (wygląd strony szczegółów)
- Kategorie przypisywane do Zadań i Ludzi. Kategorie: pisanie, ludzie, programowanie, grafika, finanse, itp. Kategorie powinno dać się: tworzyć, przypisać, zmieniać nazwę i filtrować.

# CHAT

- Są dwa specjalne pokoje na czacie, Inbox i Ważne. To powinny być pokoje systemowe tworzone wraz z instancją aplikacji. Nie powinno dać się ich skasować ani zmienić ich nazw. Oczywiście powinno dać się je tłumaczyć nazwy tych pokoi.Te pokoje powinny wyróżniać się na liście. Nie powinno dać się wyłączyć powiadomień z pokoju Ważne. W pokoju Ważne powinien być slow-mode - dana osoba powinna móc wysłać wiadomość tylko raz dziennie.

- sortowanie pokoi po dacie powinno pokazywać pokoje bez daty zawsze na końcu
- 'pokaż więcej' w wiadomościach czatu powinno być dynamiczne, to znaczy na dużych ekranach powinno pokazywać więcej treści, a na małych ekranach powinno pokazywać mniej treści.

## Funkcjonalności
- Kolejne wiadomości od tej samej osoby: bez ramek
- Szeregowanie wypowiedzi po ocenie
- Przypomnij wszystkim o danej wiadomości w danej dacie. Każdy może to włączyć.
- Grupy piszą do siebie.
- Możliwość oznaczania wypowiedzi jako predykcji. Data przypomnienia albo wydarzenie po którym będzie można sprawdzić predykcję.

# EMAILE

# GŁOSOWANIA

- Za/Przeciw dalej od siebie na telefonie, potwierdź oddanie głosu. Czy na pewno chcesz oddać głos na Tak/Nie. Tej decyzji nie da się wycofać.

## Funkcjonalności
- Podświetlanie guzików kiedy jest trwające referendum
- Opis przy dodawaniu nowego przepisu: Co się dzieje; Jaki jest mechanizm; Jak to zmienić; Jakie będą konsekwencje

# BOOKKEEPING

- Odnotowywać kto dodał, zmienił i skasował wpis. Obecnie tylko autor może edytować transakcję.
- Bookkeeping: reguły cykliczne (składka, abonament z i do nas).

## Okresowe kredytowanie i debetowanie
- Mechanizm do opłacania składki
- Okresowe składki. Opłaty roczne, miesięczne, jednorazowe
- Wysyłanie okresowych emaili z przypomnieniami o płatnościach
- Spięcie z portfelem crypto?

## Umowy i kontrakty
- Umowy, kontrakty i płatności między użytkownikami: ja pożyczam tobie / ja przechowuję tobie; kto, komu, ile, kiedy, za co. Squash: jeśli A wisi B, B wisi C, C wisi A 100zł to wszystko się zeruje. Rozliczenia gotówkowe / Śledzenie przekazywania przedmiotów. Podpisywanie kontraktu jeśli obie strony są w grupie lub grupa coś kupuje (zatwierdzanie wydatku). Potwierdzenie zwykłych płatności leży w sprzeczności z umowami — chyba że umowę/transakcję wpisze ta strona, która otrzymuje płatność.

## Transakcje
- Zobowiązania powinny pojawiać się na koncie przed czasem i w tym momencie powinien być wysyłany email
- Kto wprowadza transakcję, kto stwierdza że kasa wpłynęła, a kto podpisuje?
- Zwykłe płatności grupy: transakcje wprowadza księgowy, ktoś inny potwierdza wpływ kasy.
- Księgowość i magazyn:
  - Filtr na transakcje
  - Okresowy import Członków do Klientów
  - Tworzenie przyszłych transakcji
  - Wysyłanie emaila z rachunkiem
  - Potwierdzanie otrzymania przedmiotu

## Przedmioty / usługi / płatności
Do oddania / na sprzedaż / do wypożyczenia:
- Cena, jednostka (sztuka, dzień)
- Opis, komentarze, pliki, zdjęcia, filmy
- Ogłoszenia komercyjne (płatne) / prywatne i "oddam" (tańsze) / grupowe (ze wspólnej kasy)
- Tagi lub kategorie
- W użyciu od-do / wolne od-do / rezerwacja od-do
- Włączone / wyłączone
- Fungible / non-fungible
- Transakcje credit / debit

## Środki trwałe
- Miejsce użytkowania / dostępności
- Właściciel (jedna osoba, wielu, wszyscy)
- Potwierdzanie własności/użytkowania przez obie strony (podczas przekazywania)
- Obecny użytkownik ← naliczanie opłaty za czas użytkowania
- Parametry oferty/potrzeb: ilość, cena za sztukę, miejsce, cena za wynajem

# DOKUMENTY / OGŁOSZENIA / BOARD
- Wersjonowanie Ogłoszeń. Powinna być możliwość głosowania na wersję. Kolejne wersje powinny tworzyć drzewko. Tzn. nowa modyfikacja powinna być zlinkowana do poprzedniej wersji. Głosowanie na wersje powinno umożliwiać podgląd dwóch wersji obok siebie. Podgląd powinien pokazywać różnice w wersjach.
- Powiadomienia email przy zmianie treści artykułu (tylko przy okazji innych wiadomości)
- Edytowanie ogłoszeń tylko przez autora
- Zmiana autora jeśli ktoś zostanie wyrzucony z grupy
- Ocenianie artykułów. Najniżej oceniane trafiają do ukrytego archiwum.
- Ogłoszenia: data ważności (po tej dacie ogłoszenie się archiwizuje)

# OBYWATELE
- Automatyczne formatowanie numeru telefonu i dodawanie przedrostka plus 48.
- Do profilu użytkownika możliwość wyboru ról/zadań (it, marketing, księgowość, administracja)
- Podczas zakładania konta powinny się wyświetlić aktualne zasady i trzeba je zaakceptować. Zgoda na warunki przed przystąpieniem do grupy.
- Dodać losowanie osoby sprawującej daną funkcję
- Możliwość dodawania własnych pól w Zasobach
- Akceptacja/odrzucenie bez wchodzenia w profil osoby: https://www.reddit.com/r/django/comments/b3ow2b/_/
- Potwierdzenie konta za pomocą SMSa

## ZAWIESZENIE CZŁONKOSTWA
- Okres próbny: wszystkie głosowania są zablokowane, finanse i emaile do ludzi nie są widoczne
- Ochrona czasowa. Banowanie poprzedzić możliwością rozmowy z osobą
- Banowanie użytkowników na określony czas. Stany usera: zbanowany czasowo, zbanowany na stałe, członek honorowy bez prawa głosu (obserwator)
- Ograniczenie praw osobom, które mają być wyrzucone
- Temat grace period (okres karencji) pojawił się też przy normalnym usuwaniu użytkowników oraz przy czasowej banicji (jako konsekwencja złamania przepisu). Może da się upiec 3 pieczenie przy jednym ogniu.

# HOME

# KALENDARZ / EVENTS
- Powiadomienie o spotkaniu. Wysyłka SMS'ów bezpośrednio z Wikikracji.

# ROLE I UPRAWNIENIA
- Administrator: superuser + opis kompetencji, konfiguracja systemu wedle wytycznych
- Sędzia: read only + opis kompetencji, weryfikacja czy przepisy są realizowane
- Senator: tworzenie przepisów, we współpracy z administratorem i sędzią
- Skarbnik: trzyma kasę i magazyn (potrzebna rola przed płatnościami)
- Prawa nadawane po wyborach

# BEZPIECZEŃSTWO
- fail2ban
- Powiadomienie o nowym logowaniu (np. z nowego urządzenia)
- Wyświetlać końcówkę adresu IP z którego loguje się użytkownik

# UI / UX
- Dodać opis Wikikracji wszędzie gdzie się da. Uwzględnić emocje i błędy poznawcze.

# KOMUNIKACJA
- Kalendarz. Powiadomienia WhatsApp o spotkaniu
- signal-cli do wysyłania wiadomości
- Powiadomienia i głosowania SMS
- Django-WebRtc
- Okresowy automatyczny export wyników głosowań oraz listy użytkowników + wysyłka na email
- link z każdego pokoju czatu do jitsi?

# INNE
- Generowanie userów na podstawie listy mieszkańców/emaili/numerów mieszkań. Kod zapraszający z konta osoby zapraszającej. https://django-registration.readthedocs.io/en/3.1.1/
- Przy zakładaniu konta dla grupy podaj zakres adresów np. Wrzeciono 57A / 1-30
- System reputacji oparty na predykcjach - kto trafniej przewiduje przyszłe wydarzenia zyskuje punkty, przyznanie się do błędu zatrzymuje utratę punktów.
- Podpowiedzi z możliwymi przepisami i biznesami do zrobienia

## Przydatne komendy

- Znajdź 3 największe możliwości uproszczenia (duplikacja, martwy kod, nadmierna złożoność, zbyt zawiła struktura, możliwe standaryzacje). Przejrzyj całą aplikację a nie tylko największe moduły.
- Przeanalizuj następujący problem, upewnij się, że ewentualne uproszczenia nie zepsują jakiejś funkcjonalności i przygotuj plan naprawy.

------------------------------------------------------------
# POŹNIEJ
- Prosty i szybki mechanizm do zbierania statystyk na temat tego, które opcje w aplikacji są używane a które nie.

# NIE BĘDZIE ZROBIONE
- Flutter - aplikacja na Androida i iOS
- Riot/Matrix integration - trzeba by tworzyć oddzielne konta na Riot dla użytkowników
- Pogrubić login w emailu - to jest w module venv
- Nasz człowiek w parlamencie