# Plan naprawy nazw i cyklu życia pokoi czatu

## Status

Kod, testy i narzędzia audytu/naprawy są zaimplementowane. Pozostaje audyt i ewentualna naprawa danych na starszej instancji oraz weryfikacja po wdrożeniu; nie uruchamiałem tych operacji na bazie wdrożonej.

## Cel i przyczyna

`Room.public` określa dostęp, nie rodzaj pokoju. Pokój dokumentu grupowego ma `public=False` i `source_app='board'`, więc reguły przeznaczone dla DM błędnie podmieniają jego tytuł w aktywności, a w innych miejscach mogą wybrać, zarchiwizować lub usunąć taki pokój. Autor wiadomości i tytuł pokoju są odrębnymi danymi. Stara wiadomość powitalna nie jest przyczyną błędu: dawnych wiadomości nie usuwamy, a do nowych pokoi nie przywracamy powitań — odnośnik do treści źródłowej pozostaje w UI.

## Uzgodnione zasady

- `public` nadal oznacza zasady dostępu; nie przestawiamy go na `True` dla dokumentów grupowych.
- Rodzaj pokoju ustalamy z istniejącego `source_app`: pokój powiązany z treścią ma oznaczone źródło, a DM nie ma źródła i jest niepubliczny. Przy wyszukiwaniu pary DM trzeba dodatkowo sprawdzić, czy pokój należy dokładnie do dwóch osób. Nie dodajemy teraz pola `kind` ani migracji schematu.
- W aktywności, digescie, liście czatów i powiadomieniach pokój dokumentu grupowego pokazuje tytuł dokumentu; autor wiadomości jest prezentowany niezależnie. Anonimowość wiadomości i dotychczasowa personalizacja DM pozostają zachowane.
- Nowo przyjęty obywatel dostaje członkostwo także w istniejących pokojach dokumentów grupowych i archiwalnych. Nie dostaje przez to dostępu do DM.
- Pokój powiązany z treścią może być automatycznie archiwizowany po bezczynności i ponownie aktywowany zgodnie z istniejącymi regułami; nie może być automatycznie usuwany z powodu wieku wiadomości ani stanu jednego z członków. Zmiany stanu obiektu źródłowego nadal mogą aktualizować stan pokoju.
- Po usunięciu konta usuwamy prawdziwe pokoje DM tej osoby, tak jak dotychczas; pokój dokumentu i jego wiadomości muszą pozostać.
- Nazwę pokoju ankiety wyświetlamy bez prefiksu `Survey #ID:`, bez zmiany tytułu zapisanego w bazie.
- Dane starszych instancji najpierw audytujemy tylko do odczytu. Jeżeli znajdziemy błędne powiązania, naprawa jest osobnym, idempotentnym krokiem po kopii zapasowej i przeglądzie wyników; bez automatycznego kasowania pokojów lub wiadomości.

## 1. Testy ujawniające błąd

- [x] W `home/test_activity.py` oraz `home/test_feed.py` odtworzyć dokument grupowy, autora A, inną osobę B i wiadomość przypominającą historyczne powitanie. Potwierdzić, że aktywność pokazuje tytuł dokumentu oraz autora A, a nie nazwę B; sprawdzić dostęp uczestnika i brak dostępu osoby nieuprawnionej.
- [x] W `home/test_email_digest.py` sprawdzić tytuł ograniczonego pokoju dokumentu oraz zachowanie personalizacji i izolacji wspólnego cache'u dla DM.
- [x] Dodać testy regresyjne w `chat/tests/` dla doboru pokoju DM, obecności i usunięcia użytkownika, w tym pokoju dokumentu z dokładnie dwoma członkami i kolizji tytułów.
- [x] Dodać testy powiadomień: tytuł dokumentu grupowego, inicjały w DM i brak ujawnienia autora wiadomości anonimowej.

## 2. Jedna reguła klasyfikacji i nazwy

- [x] W istniejącym kodzie `chat` wprowadzić współdzieloną regułę rozpoznawania DM, bez nowego modułu i bez używania samego `public=False` jako synonimu DM. Spójnie stosować ją do odczytu obiektu i zapytań wybierających pokoje.
- [x] Zachować `Room.displayed_name()` jako regułę tytułu widocznego dla konkretnego użytkownika; dla pokoi źródłowych używać `clean_title()`, dla DM nazwy rozmówcy. Nie wykonywać zapytania do bazy na każdą pozycję feedu: wykorzystać istniejące zbiorcze dane członków.
- [x] Uzupełnić `Room.clean_title()` o prefiks ankiet, zachowując istniejące identyfikatory, prefiksy i przechowywane tytuły zadań, głosowań i dokumentów.
- [x] Potwierdzić testami obecne nazwy pokoi publicznych, systemowych, federacyjnych oraz źródłowych (`board`, `tasks`, `glosowania`, `ankiety`).

## 3. Aktywność, digest i powiadomienia

- [x] W `chat/feed.py` budować czytelny tytuł również dla pokoju źródłowego z `public=False`; personalizować nazwę tylko dla DM. Zachować filtrowanie dostępu przez `allowed`, `author=None` przy anonimowości, identyfikator wiadomości i kontrakt hooków feedu.
- [x] Utrzymać w `core.services.feed` współdzielony surowy cache bez danych spersonalizowanych: nie mutować wpisu źródłowego podczas przygotowywania aktywności i digestu; przetestować kolejność wywołań dla różnych użytkowników i nie zwiększać liczby zapytań per wiadomość.
- [x] W `chat/notifications.py` pokazywać oczyszczony tytuł pokoju dokumentu grupowego, ale zachować obecną konwencję inicjałów i ochronę anonimowości w DM. Zweryfikować payload zwykłego powiadomienia oraz wzmianki.
- [x] Nie dodawać nowych wiadomości powitalnych i nie usuwać historycznych; sprawdzić, że przycisk prowadzący do źródłowej treści nadal działa.

## 4. Bezpieczeństwo wyboru i cykl życia pokoju

- [x] Ograniczyć `Room.find_all_with_users()`, `find_with_users()` i `find_private_rooms_for_user_pairs()` do prawdziwych DM; tam, gdzie szukamy pary, nie akceptować pokoju z innymi członkami. Zweryfikować `open_dm`, profil i sygnały obecności.
- [x] Przy kolizji tytułu tworzonego DM nie pobierać ani nie modyfikować przypadkowego pokoju o tej nazwie; zachować powiązanie po uczestnikach, a konflikt obsłużyć bez przejmowania pokoju źródłowego.
- [x] W `chat/signals.py` ograniczyć usuwanie pokojów przy odejściu użytkownika do DM; w pokojach źródłowych usunąć tylko jego członkostwa/preferencje. Sprawdzić zachowanie wiadomości i powiązań obiektów źródłowych.
- [x] W `chat/management/commands/chat_rooms.py` oddzielić pokoje źródłowe od DM. Dla źródłowych stosować uzgodnioną autoarchiwizację po bezczynności i reaktywację, ale wykluczyć automatyczne usunięcie oraz regułę „nieaktywny członek => archiwizuj/usuń”. Zachować dotychczasową politykę zwykłych pokojów publicznych i DM.
- [x] Testami upewnić się, że archiwizacja źródłowego pokoju nie gubi `source_app/source_object_id`, nie usuwa wiadomości i nie zmienia niespodziewanie widoczności dokumentu; uwzględnić pokój dokumentu w stanie archiwalnym i jego ponowną aktywację.

## 5. Członkostwo nowych obywateli i starsze dane

- [x] Poszerzyć obsługę `citizen_accepted` o istniejące pokoje dokumentów grupowych i archiwalnych (również już automatycznie zarchiwizowane), korzystając z metadanych źródła i istniejącej logiki preferencji powiadomień; nie dodawać użytkownika do DM. Przetestować widoczność w czacie, aktywności i możliwość wejścia do pokoju.
- [x] Dodać `repair_discussion_rooms --audit` jako raport wyłącznie do odczytu: wykrywa brakujące i niespójne powiązania, duplikaty, brakujące/nadmiarowe członkostwa oraz niejednoznaczne prywatne pokoje. Raport należy uruchomić i przejrzeć osobno na starszej instancji przed naprawą.
- [x] Dodać idempotentny `repair_discussion_rooms --repair-source-data`, który wymaga `--confirm-reviewed-backup`, naprawia tylko jednoznaczne braki i dodaje brakujących aktywnych członków; nie usuwa wiadomości ani nie zmienia niejednoznacznych rekordów. Trybu naprawczego nie uruchamiano na żadnej wdrożonej bazie.
- [x] Potwierdzić, że istniejące `source_app/source_object_id` wystarcza dla obsługiwanych pokoi źródłowych; nie dodawać pola `kind` ani migracji. Jeśli raport produkcyjny ujawni wyjątek nieklasyfikowalny z tych danych, wrócić z odrębną propozycją przed zmianą schematu.

## 6. Weryfikacja i wdrożenie

- [x] Uruchomić testy dotyczące wyłącznie zmienionych obszarów (`chat`, `home` feed/digest/aktywność, `board`, onboarding), najpierw jako regresje, potem po poprawkach. Komendy Pythonowe uruchamiać przez repozytoryjne `.venv`; przed nimi sprawdzić wersję interpretera, stosować izolowane ustawienia testowe zgodnie z `AGENTS.md`.
- [x] Sprawdzić Django check, lint oraz testy zapytań, anonimowości, uprawnień i wspólnego cache'u. Jeśli dotknięty zostanie UI/JS, użyć odpowiednich kontroli UI i testów E2E wyłącznie na dedykowanym koncie.
- [ ] Na starszej instancji najpierw uruchomić `repair_discussion_rooms --audit` i przejrzeć raport. Po kopii zapasowej można uruchomić `--repair-source-data --confirm-reviewed-backup` tylko dla jednoznacznych przypadków; następnie sprawdzić stary wpis aktywności, nową wiadomość, DM, digest, powiadomienia i archiwizację. Nie wykonywać napraw na wdrożonej bazie bez tego przeglądu.
- [x] Opisać wykonane zmiany i decyzje w `docs/LOG_AI.md`; aktualizować checkboxy etapami. Nie wykonywać commitów ani push bez polecenia użytkownika.
