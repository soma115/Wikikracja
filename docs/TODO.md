# OGÓLNE
- Nie wysyłać treści z czatu
- Pokoje w czacie nie rozwijają się jeśli klinie się 2 razy
- Zadania: termin zakończenia
- Zadania: co blokuje wykonanie
- Domyślnie czaty wyciszone, powiadomienia włączają się dopiero jak ktoś się odezwie.
- Chat: Mniej powiadomień - tylko tam gdzie się wypowiedziałem.
- Czat: powiadomienia przychodzą wielokrotnie na Windows - trzeba to jakoś ograniczyć.
- W Zadaniach suma punktów Sukces/Porażka jest podwojona.
- Do formularza wstępnego: Czy jesteś zwolennikiem DB? Czy zgadzasz się na przestrzeganie naszych zasad?
- Do emaila powitalnego dodać https://lobbyobywatelskie.wikikracja.pl/board/view/25/
- Zalogowanie się w systemie oznacza zgodę na warunki. Będąc członkiem grupy masz wpływ na przepisy w takim samym stopniu jak każdy inny obywatel.

- Chat: Przenieś pokoje z Czat do odpowiednich działów do: Zadania, Głosowania, Ludzie
- Bookkeeping: reguły cykliczne: składka, abonament z i do nas
- Dokończyć Fixtures i dodać je do skryptu instalacyjnego. Fixtures z przepisami, pokojami i ogłoszeniami. Start: (publiczna strona startowa dla niezalogowanych) i Footer: (publiczna stopka). Customowy email. Wszystkie te elementy dać do nowego działu.
- Backup kontaktów, przepisów, ogłoszeń, itd. Każdy powinien móc zrobić w postaci fixtures i md.
- Wszędzie: Ograniczyć możliwość dodawania treść po to żeby uniknąć manipulacji polegającej na tym, że zły aktor zarzuca grupę dużą ilością głosowań i przemyca w ten sposób niekorzystne dla grupy rozwiązania.
- Mobile: ? swipe left right żeby przejść do różnych działów
- Mapa ze społecznościami. Zlinkować otwarte grupy.
- Pakiet ustaw - powinno dać się zaznaczyć w przepisie, że ten przepis wchodzi w życie razem z innymi przepisami. Może np. dopiero jak wszystkie zbiorą wymagane podpisy.
- Data ostatniej modyfikacji to 2026-04-17.
  Musi minąć 2 dni od tej daty,
  A ja muszę dodać datę modyfikacji i opis do interfejsu...
- Nie da się usunąć obrazka podczas edycji wiadomości.

# ZADANIA (TASKS)

- Design szczegółów zadania do poprawienia (wygląd strony szczegółów)
- Opis do Tasks: Pomysł przechodzi do działu "W realizacji" jeśli zaistnieją 2 warunki: - ktoś wziął na siebie realizację projektu - zwolenników realizacji jest o 2 więcej niż przeciwników.
- Filtr, który pokazuje tylko moje zadania
- Kategorie przypisywane do Zadań i Ludzi. Kategorie: pisanie, ludzie, programowanie, grafika, finanse, itp. Kategorie powinno dać się: tworzyć, przypisać, zmieniać nazwę i filtrować.
- Task jaki eksperyment: hipoteza, test, wynik. Spodziewamy efekt, eksperymenty, rzeczywisty efekt.

# CHAT

## Błędy

- Nie działa na Safari. ReferenceError: can't find variable TRANSLATION. Automate cross browser testing.
- Expandable messages: napis "… pokaż więcej" nakłada się na ostatnią linię tekstu (biały tekst widoczny pod hintem). Trzeba dopracować pozycjonowanie/stacking — element DOM `.expandable-hint` jest absolutnie pozycjonowany ale tekst body przebija przez tło.

## Funkcjonalności

- Zmiana nazwy pokoju (tylko Publiczne)
- Jeśli Zadanie zostaje zamknięte to pokój powinien zostać zarchiwizowany od razu
- Ankieta powinna być oddzielnym typem wiadomości
- Kolejne wiadomości od tej samej osoby: bez ramek
- Wyszukwiarka do czatu (albo całej strony)
- Czaty pod ogłoszeniami, przepisami, zadaniami i głosowaniami
- Każdy sam ustawia jak często chce otrzymywać wiadomości
- Szeregowanie wypowiedzi po ocenie
- Przypomnij wszystkim o danej wiadomości w danej dacie. Każdy może to włączyć.
- Wiadomość do wszystkich - chaty z najwyżej punktowanymi wypowiedziami
- Możliwość oznaczania wypowiedzi jako predykcji. Data przypomnienia albo wydarzenie po którym będzie można sprawdzić predykcję.

# EMAILE

- Język w emailach ustawiony na sztywno - niezależnie od przeglądarki wysyłającego
- Funkcja wysyłająca emaile powtarza się 6 razy. Może moduł z multithreading? https://anymail.dev/en/v12.0/tips/django_templates/
- Opcja wyłączenia powiadomień email (Unsubscribe)
- Konfigurowalna częstotliwość wysyłania powiadomień o nowych zdarzeniach (czat, referenda, prośba o dołączenie)
- Lepsze wyjaśnienie do emaili z powiadomieniami (głosowania i czat oddzielnie)
- Emaile nie są tłumaczone na angielski
- Poprawki w tłumaczeniach języka (niespójności/brakujące tłumaczenia w UI)
- Dodać tytuł propozycji w emailach (tytuł i treść)
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
- Umowy - ja pożyczam tobie, ja przechowuję tobie.
- Między sobą: kto, komu, ile, kiedy, za co. Squash: jeśli A wisi B, B wisi C, C wisi A 100zł to wszystko się zeruje. Rozliczenia gotówkowe / Śledzenie przekazywania przedmiotów
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
- Podpisywanie kontraktu jeśli obie strony są w grupie
- Podpisywanie kontraktu jeśli grupa coś kupuje (zatwierdzanie wydatku)
- Odnotowywać kto dodał, zmienił i skasował wpis

## Umowy pomiędzy użytkownikami

- Potwierdzenie zwykłych płatności leży w sprzeczności z umowami. W umowach to druga strona potwierdza, że kasa wpłynęła.
- Chyba, że umowę/transakcję wpisze ta strona, która otrzymuje płatność

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
- Parametry oferty/potrzeby: ilość, cena za sztukę, miejsce, cena za wynajem

# OGŁOSZENIA / BOARD

- Wersjonowanie Ogłoszeń. Powinna być możliwość głosowania na wersję. Kolejne wersje powinny tworzyć drzewko. Tzn. nowa modyfikacja powinna być zlinkowana do poprzedniej wersji. Głosowanie na wersje powinno umożliwiać podgląd dwóch wersji obok siebie. Podgląd powinien pokazywać różnice w wersjach.
- Start, Footer i Custom emails powinny mieć swój oddzielny dział. Zamiast po nazwie - te typy Ogłoszeń powinny mieć specjalne znaczniki (inny dla każdego typu)
- Dodać komentarze pod artykułami (albo czat room)
- Powiadomienia email przy zmianie treści artykułu (tylko przy okazji innych wiadomości)
- Edytowanie ogłoszeń tylko przez autora
- Zmiana autora jeśli ktoś zostanie wyrzucony z grupy
- Ocenianie artykułów. Najniżej oceniane trafiają do ukrytego archiwum.
- Przewijanie artykułów na blogu

# OBYWATELE

- Do profilu użytkownika możliwość wyboru ról/zadań (it, marketing, księgowość, administracja)
- Walidacja czyści formularz jeśli pierwsze pole jest nieprawidłowe (przy zapraszaniu nowej osoby)
- Dodaj opcję kasowania własnego konta i wszystkich danych użytkownika. Powinna być możliwość samodzielnego usunięcia z grupy ale też powinien być okres karencji po którym potwierdza się chęć odejścia. W okresie karencji będziemy mieli szansę zapytać co jest nie tak.
- Temat grace period (okres karencji) pojawił się też przy normalnym usuwaniu użytkowników oraz przy czasowej banicji (jako konsekwencji złamania przepisu). Może da się upiec 3 pieczenie przy jednym ogniu.
- Podczas zakładania konta powinny się wyświetlić aktualne zasady i trzeba je zaakceptować
- Okres próbny: wszystkie głosowania są zablokowane, finanse i emaile do ludzi nie są widoczne

- Banowanie użytkowników na określony czas. Stany usera: zbanowany czasowo, zbanowany na stałe, członek honorowy bez prawa głosu (obserwator)
- Ochrona czasowa. Banowanie poprzedzić możliwością rozmowy z osobą
- Ograniczenie praw osobom, które mają być wyrzucone
- Tłumaczenie nie działa: `templates/allauth/account/messages/email_confirmation_sent.txt`
- Próg akceptacji (chwilowy i przegłosowany)
- Dodawanie prywatnych notatek do osoby
- Potwierdzenie konta za pomocą SMSa
- Dodać losowanie osoby sprawującej daną funkcję
- Zmianę emaila, nazwiska i użytkownika przenieść do jednego formularza
- Możliwość dodawania własnych pól w Zasobach
- Link "obywatele" zmienić na "ludzie"
- Akceptacja/odrzucenie bez wchodzenia w profil osoby: https://www.reddit.com/r/django/comments/b3ow2b/_/

# HOME

- Imię, nazwisko, username from email, miasto
- Zgoda na warunki przed przystąpieniem do grupy (grupa jawna/tajna do custom_settings)
- GROUP_IS_PUBLIC oprogramować
- Formularz zapisywania się nie zapisuje danych
- Fixtures: Start i Footer do startowych fixtures
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

- Ludzie piszą do grupy. Grupy piszą do siebie.
- Wyślij wiadomość do całej grupy
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

# JORDAN (TO DO)
**NOWE FUNKCJE** 
- w profilu użytkownika można sprawdzić:
  - {napisać wiadomość bezpośrednio}
- wszystkie strony mają korzystać z tych samych styli *(Design system / style guide)*
- system update, tak żeby można było zrobić update strony jednym przyciskiem (ściąga repo z githuba i instaluje)
- **ogłoszenia**
  - dodanie opcji "wyświetl na pulpicie użytkowników" wtedy pojawia się na pulpicie. 
  - data ważności (po tej dacie ogłoszenie się archiwizuje) 
**BUGS**
**Przydatne komendy**
docker compose up --build -d - r
docker compose restart

Get-ChildItem -Path . -Recurse -Filter __pycache__ -Directory | Remove-Item -Recurse -Force 


------------------------------------------------------------

# NIE BĘDZIE ZROBIONE

- Flutter - aplikacja na Androida i iOS
- Riot/Matrix integration - trzeba by tworzyć oddzielne konta na Riot dla użytkowników
- Pogrubić login w emailu - to jest w module venv
- Nasz człowiek w parlamencie
- Ankiety do błahych decyzji - zamiast tego up_vote/down_vote do chatu

------------------------------------------------------------

# ZROBIONE

- Dobrowolny formularz dla nowej osoby, która sama się zapisuje. Pola: dlaczego chcesz należeć do grupy, imię, nazwisko, telefon, miasto, zawód, hobby, biznes, umiejętności, wiedza.
- Zadania - małe guziczki za/przeciw w widoku listy.
- Jeśli ktoś próbuje zapisać się po raz drugi (ten sam email) to dostaje informację, że kandydatura jest w kolejce.
- Do Start dodano Zadania w realizacji i nowe wiadomości na czacie
- Chat: Treść u góry, wszystkie inne elementy wiadomości u dołu.
- Chat: room dla Task i Vote znika za szybko - częściowo zrobione ale nie są zachowywane na wieki
- Chat: Archiwum czatów powinno być pod guzikiem, nie pod rozwijaną listą. Bardziej ukryte żeby nie zaśmiecać interfejsu.
- Chat: Po utworzeniu propozycji - utworzyć dla niej pokój
- Chat: Linki do poszczególnych pokoi i wiadomości
- Chat: Po kliknięciu "Kliknij tutaj aby włączyć powiadomienia" — informacja, że trzeba zrestartować stronę.
- Chat: Pole tekstowe rośnie dynamicznie
- Chat: Przenieść wszystko z home do chat
- Głosowania: 2 dni przerwy pomiędzy końcem zbierania podpisów a możliwością wycofania podpisu
- Głosowania: Imienne dodawanie argumentów za i przeciw
- Głosowania: Pozytywy, negatywy referendum - każdy może komentować oba?
- Bookkeeping: Raporty używają "lazy loading" i przez to nie odświeżają się
- Bookkeeping: Kasowanie/edycja wpisów tylko przez autora
- Start: zapamiętuj stan guzika 'Show unread only' w localStorage przeglądarki
- Chat: guzik powrotu do listy pokoi chowa się gdy klawiatura ekranowa podnosi się na mobile.
- Start: godzina wydarzenia pokazuje się nieprawidłowo w Start.
- Chat: filtr tylko nieprzeczytane
- Możliwość wyłączenia wszystkich powiadomień!
- Głosowania: W emailu o głosowaniu - dodać tytuł propozycji

