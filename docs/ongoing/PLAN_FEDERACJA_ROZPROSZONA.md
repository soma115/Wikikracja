# Plan rozproszonej federacji instancji

## Status

Plan szerszej federacji — **częściowo zaimplementowany**. Bezpośrednie wiadomości do skonfigurowanego peera używają uwierzytelniania HMAC i ochrony przed replay; discovery, katalog peerów, parowanie/rotacja i decyzje grupowe pozostają niezaimplementowane. Wdrażanie uwierzytelniania wymaga skonfigurowania tego samego sekretu po obu stronach.

## Cel

Umożliwić niezależnym instancjom Wikikracji bezpieczną wymianę wiadomości federacyjnych oraz automatyczne odkrywanie innych instancji. Każda grupa przechowuje wykryte instancje i samodzielnie wybiera, które z nich włącza. Nie ma centralnego serwera katalogowego.

Automatyczne odkrywanie nie może automatycznie oznaczać zaufania ani aktywować wszystkich znalezionych instancji.

## Decyzje i ograniczenia architektoniczne

### Brak centralnego katalogu wymaga bootstrapu

Całkowicie nowa, odizolowana instancja nie może sama poznać adresów innych instancji. Aplikacja Wikikracji powinna mieć zahardkodowany adres `odswojego.wikikracja.pl` jako początkowy punkt wejścia do odkrywania pozostałych instancji. W przyszłości punktów startowych może być więcej albo mogą się zmieniać, ale adresy bootstrapowe zawsze muszą być zahardkodowane w aplikacji. Nie jest to centralna usługa katalogowa — adres służy wyłącznie do pierwszego kontaktu, po którym katalog może być rozgłaszany między peerami.

Wymaganie „użytkownicy nie wpisują każdej instancji ręcznie” można spełnić przez pobieranie i wymianę katalogu po skonfigurowaniu pierwszego peera. Nie należy obiecywać odkrywania z pustego stanu bez bootstrapu poza wskazanymi w aplikacji punktami startowymi.

### Wspólny sekret a tożsamość instancji

Sekret powinien uwierzytelniać bezpośrednie połączenie dwóch instancji, a nie być globalnym hasłem współdzielonym przez wszystkie grupy. Dla każdej pary peerów aplikacja generuje niezależny, losowy sekret; przechowuje go w bazie wyłącznie w postaci szyfrogramu chronionego `SECRET_KEY` i pokazuje w uwierzytelnionych ustawieniach grupy do bezpiecznego przekazania peerowi. Jawnego sekretu nie wolno zwracać przez endpointy federacyjne ani zapisywać w logach czy katalogu.

Wiadomości powinny być podpisywane HMAC-SHA-256 z kanonicznej reprezentacji metody, ścieżki, identyfikatora nadawcy, timestampu, nonce i surowego body. Odbiorca weryfikuje podpis w stałym czasie, dopuszcza ograniczone odchylenie zegara i odrzuca ponowne użycie nonce (replay). Klucz nie może być wysyłany w samym żądaniu.

Wymiana informacji o peerach wymaga osobnej weryfikowalnej tożsamości nadawcy. Sam HMAC pary peerów uwierzytelnia bezpośredniego nadawcę, ale nie dowodzi prawdziwości twierdzeń o instancjach trzecich. Planowane rekordy katalogowe powinny być podpisane kluczem instancji (np. Ed25519), a podpis i pochodzenie rekordu zachowane przy propagacji. Jeśli projekt zdecyduje się nie wprowadzać kluczy instancji, rekordy przekazane pośrednio muszą być wyraźnie niezweryfikowanymi kandydatami i nie mogą służyć do automatycznego zaufania.

### Discovery nie aktywuje federacji

- Katalog lokalny przechowuje wszystkie odkryte rekordy wraz ze źródłem, czasem ostatniej weryfikacji i stanem weryfikacji.
- Rekordy odkryte pośrednio mają status „kandydat/niezweryfikowany”; nie mogą być użyte do dostarczania wiadomości ani do kolejnego bezwarunkowego rozgłaszania.
- Każda grupa ma niezależny wybór: wyłączona / włączona. Zatwierdzenie wejścia grupy/instancji do sojuszu wymaga głosowania, podobnie jak przy tworzeniu referendum dotyczącego zmiany parametrów systemu (`/glosowania/parameters/propose/`). Przed głosowaniem należy przedstawić do oceny zgodność domeny, tożsamość instancji i zasady kontaktu; sama obecność w katalogu ani bezpośrednia weryfikacja nie zastępują decyzji grupy.
- Wyłączenie grupy zatrzymuje dostarczanie do tej instancji bez usuwania rekordu z katalogu.
- Odwołanie, rotacja klucza, konflikt tożsamości i nieosiągalność peerów muszą być widoczne i audytowalne.

## Proponowany przepływ

1. Operator/grupa inicjuje parowanie przez zaproszenie, bootstrap URL lub lokalną konfigurację pierwszego peera.
2. Obie instancje uzgadniają tożsamość i ustanawiają niezależny sekret dla tego połączenia. Sekret jest generowany kryptograficznie, pokazywany tylko w kontrolowanym przepływie parowania i zapisywany bezpiecznie po obu stronach.
3. Peer wymienia podpisane informacje o sobie i wersji protokołu. Odbiorca sprawdza URL i tożsamość; nie pobiera zasobów z adresów innych niż jawnie dozwolone endpointy protokołu.
4. Instancje wymieniają paginowany katalog kandydatów z limitem rozmiaru, limitem liczby rekordów, TTL i pochodzeniem każdego wpisu.
5. Odbiorca zapisuje rekordy jako nieaktywne. Weryfikacja bezpośredniego połączenia lub ważnego podpisu potwierdza tożsamość, ale nie włącza peera dla grupy.
6. Użytkownicy grupy przeglądają wykryte instancje, a wejście do sojuszu zatwierdzają w głosowaniu. Dopiero pozytywny wynik głosowania pozwala włączyć instancję do federacji dla tej grupy.
7. Wiadomości są wysyłane wyłącznie do aktywnych peerów i podpisywane sekretem konkretnej relacji. Idempotencja opiera się na stabilnym identyfikatorze wiadomości i identyfikatorze nadawcy.
8. Okresowy, ograniczony refresh pobiera aktualizacje katalogu. Brak odpowiedzi nie usuwa automatycznie peerów aktywnych; oznacza je jako nieosiągalne po określonym czasie.

## Model danych do zaprojektowania

Przed implementacją należy ustalić, czy wystarczą istniejące modele `FederatedInstance` i pokoje, czy potrzebne są osobne rekordy katalogu oraz relacji:

- **Instancja:** kanoniczny URL, stabilny identyfikator, nazwa, klucz publiczny/tożsamość, status weryfikacji, wersja protokołu, źródła odkrycia, `first_seen`, `last_seen`, data wygaśnięcia.
- **Relacja bezpośrednia:** para lokalna–zdalna, status parowania, zaszyfrowany sekret peera ustawiany w UI, data rotacji i ostatniego poprawnego uwierzytelnienia. Jawnego sekretu nie przechowywać w bazie.
- **Wybór grupy:** instancja oraz stan włączenia, osoba/grupa podejmująca decyzję (zgodnie z modelem kolektywnym), czas i opcjonalny powód.
- **Pochodzenie rekordu:** peer, który przekazał wpis, podpis/odcisk klucza i status walidacji. Zachować wiele źródeł bez duplikowania tej samej instancji.

Każda migracja musi uwzględnić obecne rekordy `FederatedInstance`, unikalność URL bez różnic końcowego ukośnika/wielkości hosta i bezpieczne zachowanie istniejących relacji.

## Bezpieczeństwo i odporność

- SSRF: walidować schemat HTTPS (HTTP wyłącznie dla jawnego środowiska testowego), host, port, adresy IP po rozwiązaniu DNS oraz ponownie każdy redirect. Odrzucać loopback, link-local, prywatne i zarezerwowane adresy. Chronić przed DNS rebinding i nie pobierać dowolnych URL z rekordów katalogu.
- Podpisy: wiązać podpis z pełnym body, metodą, ścieżką, źródłem, czasem i nonce; porównywać HMAC w stałym czasie; ograniczyć replay i rotować sekrety z okresem nakładania kluczy.
- Anti-poisoning: limity liczby peerów i rozmiaru katalogu, paginacja, TTL, deduplikacja, walidacja domeny/identyfikatora oraz blokowanie pętli propagacji.
- Uprawnienia: stan discovery jest globalnym katalogiem instancji, ale wybór włączenia należy do grupy. Sam fakt znalezienia instancji nie dodaje jej do pokoju ani nie wysyła danych.
- Prywatność: ujawniać wyłącznie minimalne metadane instancji; nie propagować członków, adresów e-mail, prywatnych pokoi ani danych wiadomości.
- Obserwowalność: logować identyfikator peer/reason/status i identyfikator żądania, nigdy sekret, pełny podpis, treść wiadomości ani dane uwierzytelniające.
- Awarie: kolejka/ponawianie z backoffem i idempotencją; awaria discovery nie może blokować lokalnego czatu ani głosowań.

## Etapy realizacji po osobnej zgodzie

1. Spisać aktualny kontrakt endpointów federacyjnych i istniejący model `FederatedInstance`; zdecydować o globalnym katalogu i wyborze per grupa.
2. Uzgodnić bootstrap i tożsamość: pairwise HMAC secret dla bezpośredniego transportu oraz podpisy kluczem instancji dla propagowanych rekordów; określić bezpieczny sposób parowania/rotacji.
3. Zaprojektować migracje oraz statusy: odkryta, niezweryfikowana, zweryfikowana, aktywna dla grupy, wyłączona, odwołana, nieosiągalna.
4. Zdefiniować wersjonowany protokół `well-known`/discovery i podpisany katalog; dodać walidację SSRF, limity, TTL, nonce oraz idempotencję.
5. Wdrożyć najpierw opt-in dla bezpośredniego peera, z kompatybilnością wsteczną i bez wysyłania do nieaktywowanych wpisów.
6. Dodać wymianę/propagację katalogu kandydatów jako osobny etap, z testami fałszywych wpisów, pętli, replay, DNS rebinding, rotacji sekretu i niedostępnych peerów.
7. Dodać interfejs przeglądania katalogu i jawnego włączania/wyłączania przez grupę; sprawdzić czytelność, tłumaczenia i audytowalność.
8. Uzgodnić plan wdrożenia, migracji obecnych peerów, rotacji sekretów i wycofania niezabezpieczonego endpointu.

## Kryteria akceptacji przyszłej implementacji

- Nie istnieje centralna usługa wymagana do bieżącej pracy; zahardkodowane w aplikacji punkty startowe umożliwiają bootstrap, a po nim peerzy wymieniają katalog między sobą.
- Instancja z katalogu nie jest automatycznie zaufana ani włączona dla grupy; wejście do sojuszu wymaga pozytywnego wyniku głosowania grupy.
- Żądanie wiadomości bez poprawnego podpisu, z odtworzonym nonce lub z niezgodnym źródłem jest odrzucane przed zapisaniem wiadomości.
- Propagowany wpis zachowuje weryfikowalne pochodzenie; błędny/niepodpisany wpis nie może aktywować peerów.
- Testy potwierdzają ochronę SSRF także po DNS resolution i po redirectach.
- Jawne sekrety nie trafiają do API, logów, e-maili ani repozytorium; w bazie przechowywane są wyłącznie szyfrogramy.
- Wyłączenie peerów przez grupę natychmiast zatrzymuje wysyłkę, nie kasując lokalnych danych.
- Istniejące instancje mogą przejść na nowy protokół bez cichego przejścia na niezabezpieczone żądania.

## Postęp zabezpieczeń transportu

- Wiadomości federacyjne są podpisywane HMAC-SHA-256 kluczem przypisanym do konkretnego peera. Podpis obejmuje metodę, ścieżkę, kanoniczny URL źródła, timestamp, nonce i surowe body; timestamp ma ograniczone okno ważności, a nonce jest atomowo rejestrowany w cache Redis, aby odrzucać replay.
- Żądania bez sekretu peera, z niepoprawnym podpisem, nieaktualnym timestampem lub powtórzonym nonce są odrzucane przed zapisaniem wiadomości. Nie ma fallbacku do niezabezpieczonego transportu.
- Nowy peer otrzymuje automatycznie wygenerowany sekret o długości 32 bajtów entropy, pokazywany w ustawieniach grupy do przekazania drugiej instancji. Peer wpisuje ten sam klucz w polu sekretu otrzymanego; jeśli obie strony wygenerowały własne klucze, należy wybrać jeden i ustawić go po obu stronach. Regeneracja unieważnia poprzedni klucz. W bazie jest wyłącznie szyfrogram Fernet chroniony kluczem wyprowadzonym z Django `SECRET_KEY`; po rotacji klucza aplikacji poprzednie klucze należy czasowo podać przez `SECRET_KEY_FALLBACKS`.
- Zabezpieczenie dotyczy obecnego endpointu wiadomości; przyszłe endpointy reakcji/odczytu muszą korzystać z tej samej weryfikacji. Pozostałe etapy planu nadal wymagają osobnej realizacji.


