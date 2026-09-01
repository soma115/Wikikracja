- ikony w "Pierwsze kroki" są niepotrzebne

- w głosowaniu nad logiem powinno dać się kliknąć logo żeby je powiększyć

- Kolory w kandydatach przy ocenach (zielony, żółty, czerwony)

- Ukrywaj puste kafelki na Pulpit. 

- aktywnosc/ trzeba odświeżać ręcznie żeby zobaczyć co faktycznie jest przeczytane a co nie

- Czat do dokumentów

- jedna osoba dodaje umiejętność/zainteresowanie/hobby, pozostałe osoby mogą wybrać te rzeczy z listy.

- nie dostaję powiadomień na telefon. Może jak są na komputerze to nie ma na telefonie?


- Powiadomienia email, domyślnie raz dziennie, możliwość zmiany częstotliwości - raz na dzień, tydzień, miesiąc, nigdy:
  - Głosowania
  - Osoby
  - Czat
  - Wydarzenia
  - Dokumenty
  - Ankiety
  - Zadania
  - Finanse
Powiadomienia Push tak jak teraz - każde oddzielnie, dodać więcej typów.
E-maile z powiadomieniami są wysyłane według harmonogramu w scheduler.py:
Czat — dwa razy dziennie: o 12:01 i 18:01 (@C:\Users\Robert\code\gitops\wikikracja\zzz\scheduler.py:48-50, ikracja\chat\management\commands\chat_messages.py" lines="20-21" />).
Głosowania — raz dziennie: o 08:05 (scheduler.py:56-58, vote.py:21-22).
Wydarzenia — co minutę, gdy w danej minucie zaczyna się jakieś wydarzenie (scheduler.py:68-69, services.py:34-41).
Poza tym niektóre powiadomienia (np. o nowym obywatelu/prośbie o członkostwo, o nowej propozycji) są wysyłane natychmiastowo z poziomu formularzy/widoków, a nie cyklicznie.


- testy są bardzo wolne. Może da się je jakoś zdeduplikować żeby je przyspieszyć? Raczej wszystkie są potrzebne.

- W aktywnosc/ w powiadomieniach z czatu widać starą wiadomość zamiast najnowszej. Sprawdź skąd się bierze ten problem. A. zawsze widać 5 wiadomości ale nie wiem jak to inaczej zorganizować.

- Jedno największe możliwe bezpieczne uproszczenie w kodzie, plikach i katalogach.

- prosty i szybki mechanizm do zbierania statystyk na temat tego, które opcje w aplikacji są używane a które nie

Bookkeeping zajmuje część strony na szerokość a pozostałe moduły całą stronę. Zrób tak żeby bookkeeping też zajmował całą szerokość strony. 

- Możliwość dodawania specyficznie: x.com, fb, insta, itd.

Refaktoryzacje:
- board > documents
- events > calendar
- glosowania > voting
- obywatele > citizens



# OGÓLNE
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

# ZADANIA (TASKS)
- W Zadaniach suma punktów Sukces/Porażka jest podwojona.
- Zadania: termin zakończenia
- Zadania: co blokuje wykonanie
- Design szczegółów zadania do poprawienia (wygląd strony szczegółów)
- Opis do Tasks: Pomysł przechodzi do działu "W realizacji" jeśli zaistnieją 2 warunki: - ktoś wziął na siebie realizację projektu - zwolenników realizacji jest o 2 więcej niż przeciwników.
- Filtr, który pokazuje tylko moje zadania
- Kategorie przypisywane do Zadań i Ludzi. Kategorie: pisanie, ludzie, programowanie, grafika, finanse, itp. Kategorie powinno dać się: tworzyć, przypisać, zmieniać nazwę i filtrować.
- Task jaki eksperyment: hipoteza, test, wynik. Spodziewamy efekt, eksperymenty, rzeczywisty efekt.

# CHAT
- Chat: Mniej powiadomień / konfigurowalna częstotliwość — tylko tam gdzie się wypowiedziałem; każdy sam ustawia jak często chce otrzymywać wiadomości.
- Czat: powiadomienia przychodzą wielokrotnie na Windows - trzeba to jakoś ograniczyć.

## Błędy
- Nie działa na Safari. ReferenceError: can't find variable TRANSLATION. Automate cross browser testing.
- Expandable messages: napis "… pokaż więcej" nakłada się na ostatnią linię tekstu (biały tekst widoczny pod hintem). Trzeba dopracować pozycjonowanie/stacking — element DOM `.expandable-hint` jest absolutnie pozycjonowany ale tekst body przebija przez tło.

## Funkcjonalności
- Zmiana nazwy pokoju (tylko Publiczne)
- Jeśli Zadanie zostaje zamknięte to pokój powinien zostać zarchiwizowany od razu
- Kolejne wiadomości od tej samej osoby: bez ramek
- Wyszukiwarka do czatu (albo całej strony)
- Czaty pod ogłoszeniami, przepisami, zadaniami i głosowaniami
- Szeregowanie wypowiedzi po ocenie
- Przypomnij wszystkim o danej wiadomości w danej dacie. Każdy może to włączyć.
- Wiadomość do wszystkich / do całej grupy — chaty z najwyżej punktowanymi wypowiedziami; ludzie piszą do grupy, grupy piszą do siebie.
- Możliwość oznaczania wypowiedzi jako predykcji. Data przypomnienia albo wydarzenie po którym będzie można sprawdzić predykcję.

# EMAILE
- Język w emailach ustawiony na sztywno — niezależnie od przeglądarki wysyłającego; emaile nie są tłumaczone na angielski.
- Funkcja wysyłająca emaile powtarza się 6 razy. Może moduł z multithreading? https://anymail.dev/en/v12.0/tips/django_templates/
- Opcja wyłączenia powiadomień email (Unsubscribe)
- Konfigurowalna częstotliwość wysyłania powiadomień o nowych zdarzeniach (czat, referenda, prośba o dołączenie)
- Lepsze wyjaśnienie do emaili z powiadomieniami (głosowania i czat oddzielnie)
- Poprawki w tłumaczeniach języka (niespójności/brakujące tłumaczenia w UI)
- Dodać informację, że podanie emaila jest niezbędne żeby otrzymać hasło
- Dodać komunikat jeśli użytkownik odzyskuje hasło ale nie ma ustawionego emaila

# GŁOSOWANIA

## Błędy
- Jeśli czas trwania referendum jest ustawiony na 3 dni, to referendum w rzeczywistości trwa 4 dni

## Funkcjonalności
- Głosowania cykliczne/stałe nad parametrami systemu (ile podpisów pod wnioskiem, czas trwania dyskusji, próg akceptacji, z kim chcemy być w konfederacji, wysokość zrzutki, archiwizacja pokoi)
- Podświetlanie guzików kiedy jest trwające referendum
- Opis przy dodawaniu nowego przepisu: Co się dzieje; Jaki jest mechanizm; Jak to zmienić; Jakie będą konsekwencje
- Wersjonowanie Przepisów

# BOOKKEEPING
- Dodać waluty
- Mechanizm do opłacania składki
- Umowy, kontrakty i płatności między użytkownikami: ja pożyczam tobie / ja przechowuję tobie; kto, komu, ile, kiedy, za co. Squash: jeśli A wisi B, B wisi C, C wisi A 100zł to wszystko się zeruje. Rozliczenia gotówkowe / Śledzenie przekazywania przedmiotów. Podpisywanie kontraktu jeśli obie strony są w grupie lub grupa coś kupuje (zatwierdzanie wydatku). Potwierdzenie zwykłych płatności leży w sprzeczności z umowami — chyba że umowę/transakcję wpisze ta strona, która otrzymuje płatność.
- Okresowe składki. Opłaty roczne, miesięczne, jednorazowe
- Wysyłanie okresowych emaili z przypomnieniami o płatnościach
- Oprogramować powiadomienia o składce

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

## Stan kont / Raporty
- Składka powinna być widoczna na koncie grupy
- Odnotowywać kto dodał, zmienił i skasował wpis

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

## Okresowe kredytowanie i debetowanie
- Miejsce użytkowania / dostępności
- Właściciel (jedna osoba, wielu, wszyscy)
- Potwierdzanie własności/użytkowania przez obie strony (podczas przekazywania)
- Obecny użytkownik ← naliczanie opłaty za czas użytkowania
- Parametry oferty/potrzeb: ilość, cena za sztukę, miejsce, cena za wynajem

# OGŁOSZENIA / BOARD
- Wersjonowanie Ogłoszeń. Powinna być możliwość głosowania na wersję. Kolejne wersje powinny tworzyć drzewko. Tzn. nowa modyfikacja powinna być zlinkowana do poprzedniej wersji. Głosowanie na wersje powinno umożliwiać podgląd dwóch wersji obok siebie. Podgląd powinien pokazywać różnice w wersjach.
- Dodać komentarze pod artykułami (albo czat room)
- Powiadomienia email przy zmianie treści artykułu (tylko przy okazji innych wiadomości)
- Edytowanie ogłoszeń tylko przez autora
- Zmiana autora jeśli ktoś zostanie wyrzucony z grupy
- Ocenianie artykułów. Najniżej oceniane trafiają do ukrytego archiwum.
- Przewijanie artykułów na blogu
- Ogłoszenia: opcja "wyświetl na pulpicie użytkowników" wtedy pojawia się na pulpicie.
- Ogłoszenia: data ważności (po tej dacie ogłoszenie się archiwizuje)

# OBYWATELE
- Do profilu użytkownika możliwość wyboru ról/zadań (it, marketing, księgowość, administracja)
- Walidacja czyści formularz jeśli pierwsze pole jest nieprawidłowe (przy zapraszaniu nowej osoby)
- Dodaj opcję kasowania własnego konta i wszystkich danych użytkownika. Powinna być możliwość samodzielnego usunięcia z grupy ale też powinien być okres karencji po którym potwierdza się chęć odejścia. W okresie karencji będziemy mieli szansę zapytać co jest nie tak.
- Temat grace period (okres karencji) pojawił się też przy normalnym usuwaniu użytkowników oraz przy czasowej banicji (jako konsekwencja złamania przepisu). Może da się upiec 3 pieczenie przy jednym ogniu.
- Podczas zakładania konta powinny się wyświetlić aktualne zasady i trzeba je zaakceptować. Zgoda na warunki przed przystąpieniem do grupy (grupa jawna/tajna do custom_settings)
- Okres próbny: wszystkie głosowania są zablokowane, finanse i emaile do ludzi nie są widoczne
- Banowanie użytkowników na określony czas. Stany usera: zbanowany czasowo, zbanowany na stałe, członek honorowy bez prawa głosu (obserwator)
- Ochrona czasowa. Banowanie poprzedzić możliwością rozmowy z osobą
- Ograniczenie praw osobom, które mają być wyrzucone
- Tłumaczenie nie działa: `templates/allauth/account/messages/email_confirmation_sent.txt`
- Próg akceptacji (chwilowy i przegłosowany)
- Potwierdzenie konta za pomocą SMSa
- Dodać losowanie osoby sprawującej daną funkcję
- Zmianę emaila, nazwiska i użytkownika przenieść do jednego formularza
- Możliwość dodawania własnych pól w Zasobach
- Link "obywatele" zmienić na "ludzie"
- Akceptacja/odrzucenie bez wchodzenia w profil osoby: https://www.reddit.com/r/django/comments/b3ow2b/_/

# HOME
- Imię, nazwisko, username from email, miasto
- GROUP_IS_PUBLIC oprogramować
- Formularz zapisywania się nie zapisuje danych
- Zrób obrazek po polsku pokazujący kolejne kroki zapisywania się do grupy
- "Ostatnie logowanie" nie działa jeśli ktoś się nie wylogował. Powinno być ostatnie kliknięcie.
- Wybór języka powinien być możliwy na stronie startowej bez zalogowania. Powinien być pamiętany i możliwy do zmiany podczas całego procesu zakładania nowego konta.

# LIBRARY
- Dodać ocenianie książek (rating stars + recenzja/opis)
- Autor i tytuł zamiast obrazka zastępczego
- Tagi
- Wiki: assets - załączanie dowolnej ilości plików + galeria + okładka + autor + gatunek + czas wygasania + player audio/wideo + kto obecnie przechowuje (potwierdzenie od nadawcy i odbiorcy)

# KALENDARZ / EVENTS
- Powiadomienie o spotkaniu. Wysyłka SMS'ów bezpośrednio z Wikikracji.

# ROLE I UPRAWNIENIA
- Legislator: opis kompetencji
- Administrator: superuser + opis kompetencji, konfiguracja systemu wedle wytycznych
- Sędzia: read only + opis kompetencji, weryfikacja czy przepisy są realizowane
- Senator: tworzenie przepisów, we współpracy z administratorem i sędzią
- Skarbnik: trzyma kasę i magazyn (potrzebna rola przed płatnościami)
- Prawa nadawane po wyborach
- Wyłączyć edycję przepisów przez administratora
- Doprowadzić do tego żeby superuser był zbędny (eliminacja tego co jest w After installation)
- Pozbyć się linka admin

# BEZPIECZEŃSTWO
- settings.SECURE_SSL_HOST
- Secure Cookies - rozdział security z 2 scoops
- https://docs.djangoproject.com/en/dev/ref/clickjacking/ → https://www.ponycheckup.com/result/
- fail2ban
- Czy można z powrotem włączyć apparmor? (proxy, wiki, jitsi)
- Włączyć FireWall na wszystkich domowych maszynach
- Powiadomienie o nowym logowaniu (np. z nowego urządzenia)
- Wyświetlać końcówkę adresu IP z którego loguje się użytkownik

# UI / UX
- Na komórce nie widać kto jest obecny (pogrubienie)
- Light and Dark mode https://youtu.be/n3lcjY4Mm00
- Burger menu na dół i sticky
- Tłumaczenie: "No file chosen" / "Choose File" https://stackoverflow.com/questions/14340519/html-input-file-how-to-translate-choose-file-and-no-file-chosen
- PiotrCOHOTO może pomóc z wyglądem
- Dodać opis Wikikracji wszędzie gdzie się da. Uwzględnić emocje i błędy poznawcze.
- Formularz kontaktowy - napisz do grupy

# KOMUNIKACJA
- Kalendarz. Powiadomienia WhatsApp o spotkaniu
- signal-cli do wysyłania wiadomości
- Powiadomienia i głosowania SMS
- Django-WebRtc
- Automatyczny newsletter. Moduł do zapisywania ważnych wydarzeń i wysyłania zbiorczej informacji raz na tydzień.
- Okresowy automatyczny export wyników głosowań oraz listy użytkowników + wysyłka na email

# INNE
- Oferuje/potrzebuje do oddzielnej tabelki ← wiele do wielu → Obywatel
- Firma do oddzielnej tabelki ← wiele do wielu → Obywatel
- Generowanie userów na podstawie listy mieszkańców/emaili/numerów mieszkań. Kod zapraszający z konta osoby zapraszającej. https://django-registration.readthedocs.io/en/3.1.1/
- Przy zakładaniu konta dla grupy podaj zakres adresów np. Wrzeciono 57A / 1-30
- Refactoring - przetłumaczyć zmienne na angielski
- PWA: https://web.dev/what-are-pwas/ https://beeware.org/
- System reputacji oparty na predykcjach - kto trafniej przewiduje przyszłe wydarzenia zyskuje punkty, przyznanie się do błędu zatrzymuje utratę punktów.
- Podpowiedzi z możliwymi przepisami i biznesami do zrobienia

## Przydatne komendy
docker compose up --build -d - r
docker compose restart

Get-ChildItem -Path . -Recurse -Filter __pycache__ -Directory | Remove-Item -Recurse -Force

------------------------------------------------------------

# NIE BĘDZIE ZROBIONE
- Flutter - aplikacja na Androida i iOS
- Riot/Matrix integration - trzeba by tworzyć oddzielne konta na Riot dla użytkowników
- Pogrubić login w emailu - to jest w module venv
- Nasz człowiek w parlamencie
