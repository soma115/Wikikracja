# To są notatki użytkownika, AI nie wolno tutaj zmieniać nic.

Zachowaj standardy tw-* i dąż do unifikację i prostoty.
Pokaż mi co zamierzasz zrobić przed zmianami w kodzie.

# PILNE

Miała miejsce mała awaria. Niezaplanowany restart jednego z elementów infrastruktury (Redis) spowodował zresetowanie kolejki głosowań.

Oznacza to, że obecnie trwające referenda zaczęły się od nowa.

Poproszę o ponowne oddanie głosów:
https://lobbyobywatelskie.wikikracja.pl/glosowania/referendum/

09/09/26 08:30:40 ERROR core.notifications [NOTIFDBG] FCM broadcast failed, notification_id=b449a0acdd7046bc9cfb22ae7645cc28: LegacySettings does not support application_id. To enable multiple application support, use push_notifications.conf.AppSettings.
Traceback (most recent call last):
  File "C:\Users\Robert\code\gitops\wikikracja\core\notifications.py", line 217, in send_fcm_to_all_sync
    result = qs.send_message(message)
  File "C:\Users\Robert\code\gitops\wikikracja\.venv\Lib\site-packages\push_notifications\models.py", line 85, in send_message
    r = fcm_send_message(reg_ids, message, application_id=app_id, **kwargs)
  File "C:\Users\Robert\code\gitops\wikikracja\.venv\Lib\site-packages\push_notifications\gcm.py", line 164, in send_message
    max_recipients = get_manager().get_max_recipients(application_id)
  File "C:\Users\Robert\code\gitops\wikikracja\.venv\Lib\site-packages\push_notifications\conf\legacy.py", line 48, in get_max_recipients
    return self._get_application_settings(application_id, key, msg)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\Robert\code\gitops\wikikracja\.venv\Lib\site-packages\push_notifications\conf\legacy.py", line 34, in _get_application_settings
    raise ImproperlyConfigured(msg)
django.core.exceptions.ImproperlyConfigured: LegacySettings does not support application_id. To enable multiple application support, use push_notifications.conf.AppSettings.

# OGÓLNE
- Zunifikowanie kart listy/siatki – to największa część. Karty głosowań, ankiet, zadań, wydarzeń, dokumentów i obywateli mają różną strukturę i często dedykowaną logikę (np. głosowanie w liście ankiet, koordynator w zadaniach). Można to zrobić na dwa sposoby:
  1. Stworzyć wspólny partial karty z parametrami (tytuł, badge, meta, akcje) i stopniowo przerabiać moduły.
  2. Stopniowo ujednolicać klasy CSS i układ sekcji bez wielkiej abstrakcji.
  Zanim zacznę, chcę żebyś potwierdził preferowany kierunek i ewentualnie zakres modułów. To pozwoli uniknąć spekulatywnego, ryzykownego refaktoringu.
- Przydałaby się strzałka w breadcrumbs na mobile. Czyli zamiast "Ludzie Zasoby" zrób "Ludzie > Zasoby"
- Zbierajmy raz dziennie dane do statystyk. bedzie to wymagało nowej tabeli w bazie. Patrzymy na wszystkie działy, które świadczą o aktywności grupy.
- Prosty i szybki mechanizm do zbierania statystyk na temat tego, które opcje w aplikacji są używane a które nie.
- Działania zniknęły finanse > transakcje. Zmieńmy sposób działania. Niech kliknięcie na transakcję pozwala na wejście w jej szczegóły i tam powinna być edycja i jej usuwanie.
- guziki Przewijania itmów nie są ustandaryzowane i brakuje ich w dokumentach, działaniach, kalendarzu, finansach i ankietach.
- Do formularza wstępnego: Czy jesteś zwolennikiem DB? Czy zgadzasz się na przestrzeganie naszych zasad? (logowanie = zgoda na warunki)
- Zalogowanie się w systemie oznacza zgodę na warunki. Będąc członkiem grupy masz wpływ na przepisy w takim samym stopniu jak każdy inny obywatel.
- Prywatne notatki o człowieku / osobie.
- Dokończyć Fixtures (przepisy, pokoje, ogłoszenia, Start, Footer, Custom email) i dodać je do skryptu instalacyjnego. Start, Footer i Custom emails powinny mieć swój oddzielny dział / znaczniki typu.
- Bookkeeping: reguły cykliczne (składka, abonament z i do nas).
- Backup kontaktów, przepisów, ogłoszeń, itd. Każdy powinien móc zrobić w postaci fixtures i md.
- Wszędzie: Ograniczyć możliwość dodawania treść po to żeby uniknąć manipulacji polegającej na tym, że zły aktor zarzuca grupę dużą ilością głosowań i przemyca w ten sposób niekorzystne dla grupy rozwiązania.
- Mobile: swipe left/right żeby przejść do różnych działów?
- Mapa ze społecznościami. Zlinkować otwarte grupy.
- Pakiet ustaw - powinno dać się zaznaczyć w przepisie, że ten przepis wchodzi w życie razem z innymi przepisami. Może np. dopiero jak wszystkie zbiorą wymagane podpisy.
- Refaktoryzacje:
  - board > documents
  - events > calendar
  - glosowania > voting
  - obywatele > citizens

# AKTYWNOSC

- Na pulpicie kliknięcie w kafelku aktywność na ikonę dzwonka z liczbą nieprzeczytanych przenosi do aktywność i pokazuje tylko nieprzeczytane. I to jest dobrze. 
Natomiast kliknięcie w tym kafelku na tytuł czy też na górną belkę powinno pokazywać całą aktywność, czyli powinno wyłączać filtr nieprzeczytane.

# GÓRNE MENU

- Na komórce etykieta działu w którym się jest zawsze powinna pokazywać się w górnym menu. Ma to być końcówka breadcrumbs np. "Ludzie > Kandydaci"

# PROFIL UŻYTKOWNIKA 

- Umiejętności wybierane z listy i współdzielone z Działaniami. Jedna osoba dodaje umiejętność/zainteresowanie/hobby, pozostałe osoby mogą wybrać te rzeczy z listy.
- Powinniśmy dodać ludziom wybór co do formy kontaktu. Niektórzy ludzie wolą telefon, a inni komunikatory. Niektóre komunikatory używają numeru telefonu, a inne nie. Komunikatory, których używamy, to Facebook, Discord, WhatsApp, Telegram, Signal. Opracuj sprytny formularz w taki sposób, żeby użytkownik mógł wybrać jedną lub wiele form kontaktu i żeby to było intuicyjne. Możliwość dodawania specyficznie m.in.: x.com, fb, insta, itd.

# DOKUMENTY

- Prosta historia edycji dokumentów. Przydałoby się zapisywać przynajmniej kto edytował kiedy i nie wiem ile zostało zmienione. Nie wiem czy przechowywanie wersji dokumentu ma sens.






# ZADANIA (TASKS)
- Corowa część Zadania w realizacji nie może być modyfikowana.
- Task jaki eksperyment: hipoteza, test, wynik. Spodziewamy efekt, eksperymenty, rzeczywisty efekt.
  1. Hipoteza — "Jeśli zrobimy X, stanie się Y" (jedno zdanie)
  2. Metryka sukcesu — konkretna, mierzalna wartość/warunek, po którym poznamy, że hipoteza się potwierdziła
  3. Termin sprawdzenia — data lub punkt, w którym oceniamy wynik. Moment albo sytuacja, w której spodziewane efekty będą już widoczne. (po wyborach, 3 miesiące po konferencji)
  4. Koszt/zasób wejściowy — ile czasu/pieniędzy/osób to pochłonie (żeby było wiadomo, ile można stracić). Czy sukces zależy od osób z zewnątrz.
  5. Wynik i decyzja — pole wypełniane po zakończeniu: co się stało → kontynuować / pivot / zamknąć. Do tego są już guziki.
  To jest właściwie szkielet: hipoteza → jak zmierzymy → kiedy → ile to kosztuje → co z tym zrobimy dalej. Reszta (metodologia, ryzyka, log) może istnieć jako luźne notatki przy projekcie, ale nie musi być osobnym wymaganym polem formularza.
- Statystyki: Ranking koordynatorów
- Zadania: co blokuje wykonanie
- Design szczegółów zadania do poprawienia (wygląd strony szczegółów)
- Kategorie przypisywane do Zadań i Ludzi. Kategorie: pisanie, ludzie, programowanie, grafika, finanse, itp. Kategorie powinno dać się: tworzyć, przypisać, zmieniać nazwę i filtrować.

# CHAT

- sortowanie pokoi po dacie powinno pokazywać pokoje bez daty zawsze na końcu

## Funkcjonalności
- Kolejne wiadomości od tej samej osoby: bez ramek
- Szeregowanie wypowiedzi po ocenie
- Przypomnij wszystkim o danej wiadomości w danej dacie. Każdy może to włączyć.
- Grupy piszą do siebie.
- Możliwość oznaczania wypowiedzi jako predykcji. Data przypomnienia albo wydarzenie po którym będzie można sprawdzić predykcję.

# EMAILE
- Język w emailach ustawiony na sztywno — niezależnie od przeglądarki wysyłającego; emaile nie są tłumaczone na angielski.
- Funkcja wysyłająca emaile powtarza się 3 razy. Może moduł z multithreading? https://anymail.dev/en/v12.0/tips/django_templates/
- Dodać informację, że podanie emaila jest niezbędne żeby otrzymać hasło

# GŁOSOWANIA

## Funkcjonalności
- Podświetlanie guzików kiedy jest trwające referendum
- Opis przy dodawaniu nowego przepisu: Co się dzieje; Jaki jest mechanizm; Jak to zmienić; Jakie będą konsekwencje

# BOOKKEEPING

- Odnotowywać kto dodał, zmienił i skasował wpis. Obecnie tylko autor może edytować transakcję.

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
- Do profilu użytkownika możliwość wyboru ról/zadań (it, marketing, księgowość, administracja)
- Podczas zakładania konta powinny się wyświetlić aktualne zasady i trzeba je zaakceptować. Zgoda na warunki przed przystąpieniem do grupy.
- Potwierdzenie konta za pomocą SMSa
- Dodać losowanie osoby sprawującej daną funkcję
- Możliwość dodawania własnych pól w Zasobach
- Akceptacja/odrzucenie bez wchodzenia w profil osoby: https://www.reddit.com/r/django/comments/b3ow2b/_/

## ZAWIESZENIE CZŁONKOSTWA
- Okres próbny: wszystkie głosowania są zablokowane, finanse i emaile do ludzi nie są widoczne
- Ochrona czasowa. Banowanie poprzedzić możliwością rozmowy z osobą
- Banowanie użytkowników na określony czas. Stany usera: zbanowany czasowo, zbanowany na stałe, członek honorowy bez prawa głosu (obserwator)
- Ograniczenie praw osobom, które mają być wyrzucone
- Temat grace period (okres karencji) pojawił się też przy normalnym usuwaniu użytkowników oraz przy czasowej banicji (jako konsekwencja złamania przepisu). Może da się upiec 3 pieczenie przy jednym ogniu.

# HOME
- "Ostatnie logowanie" nie działa jeśli ktoś się nie wylogował. Powinno być ostatnie kliknięcie.

# LIBRARY
- Dodać ocenianie książek (rating stars + recenzja/opis)

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
- Poprawić działanie mechanizmu pokazującego aktywnych urzytkowników. Może z powiadomień? Tam jest informacja o aktywnej sesji.
- Burger menu na dół i sticky
- Dodać opis Wikikracji wszędzie gdzie się da. Uwzględnić emocje i błędy poznawcze.

# KOMUNIKACJA
- Kalendarz. Powiadomienia WhatsApp o spotkaniu
- signal-cli do wysyłania wiadomości
- Powiadomienia i głosowania SMS
- Django-WebRtc
- Okresowy automatyczny export wyników głosowań oraz listy użytkowników + wysyłka na email

# INNE
- Oferuje/potrzebuje do oddzielnej tabelki ← wiele do wielu → Obywatel
- Generowanie userów na podstawie listy mieszkańców/emaili/numerów mieszkań. Kod zapraszający z konta osoby zapraszającej. https://django-registration.readthedocs.io/en/3.1.1/
- Przy zakładaniu konta dla grupy podaj zakres adresów np. Wrzeciono 57A / 1-30
- System reputacji oparty na predykcjach - kto trafniej przewiduje przyszłe wydarzenia zyskuje punkty, przyznanie się do błędu zatrzymuje utratę punktów.
- Podpowiedzi z możliwymi przepisami i biznesami do zrobienia

## Przydatne komendy

- Znajdź 3 największe możliwości uproszczenia (duplikacja, martwy kod, nadmierna złożoność, zbyt zawiła struktura, możliwe standaryzacje). Przejrzyj całą aplikację a nie tylko największe moduły.
- Przeanalizuj następujący problem, upewnij się, że ewentualne uproszczenia nie zepsują jakiejś funkcjonalności i przygotuj plan naprawy.
- 3 największe możliwe bezpieczne uproszczenie w kodzie, plikach i katalogach.

------------------------------------------------------------

# NIE BĘDZIE ZROBIONE
- Flutter - aplikacja na Androida i iOS
- Riot/Matrix integration - trzeba by tworzyć oddzielne konta na Riot dla użytkowników
- Pogrubić login w emailu - to jest w module venv
- Nasz człowiek w parlamencie
