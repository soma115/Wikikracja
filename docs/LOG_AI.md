# LOG_AI

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
