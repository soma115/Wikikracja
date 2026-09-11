# LOG_AI

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
