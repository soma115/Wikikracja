# Audyt widoków edycji

Dokument jest checklistą audytu i planem porządkowania widoków edycji. Checkbox oznacza **zadanie do wykonania lub decyzję do potwierdzenia**; nie oznacza, że poprawka została już wdrożona.

## 1. Zakres audytu — UI przede wszystkim

Celem jest ujednolicenie graficzne i ergonomiczne widoków edycji. Audyt obejmuje szablony formularzy, ich wspólne partiale, klasy `tw-*`, etykiety, komunikaty, przyciski, responsywność, dostępność i przewidywalną nawigację. Nie wykonujemy pełnego audytu backendu, modeli, migracji, atomowości ani wszystkich endpointów.

Sprawdzamy tylko minimalny kontrakt widoku potrzebny do bezpiecznego użycia formularza: czy niezalogowany użytkownik nie może wejść do formularza, czy formularz poprawnie obsługuje błędy oraz czy UI nie obiecuje akcji, której endpoint odrzuca. Szczegółowe reguły domenowe pozostają poza zakresem, poza potwierdzonymi wyjątkami.

Kryteria UI:

1. [ ] Strona korzysta ze wspólnego układu: `tw-container`, `tw-card`, wspólny nagłówek i standardowe partiale.
2. [ ] Formularz korzysta z Crispy/Tailwind albo `home/templates/tw/`, bez ręcznych bootstrapowych wrapperów.
3. [ ] Pola mają poprawne etykiety, komunikaty błędów, focus i stany disabled.
4. [ ] Przyciski Zapisz/Anuluj/Wstecz są spójne z `UI_STANDARDS.html`, przetłumaczone i responsywne.
5. [ ] Powrót zachowuje przewidywalny kontekst, a po błędzie formularz zachowuje dane i błędy.
6. [ ] Nie ma nowych klas modułowych, inline CSS dla wartości statycznych ani duplikacji wspólnych komponentów.
7. [ ] Dla zmienionego widoku istnieje test renderowania lub focused test zachowania formularza.

Poza zakresem pozostają audyty API, migracji, historii głosowań, schedulerów, anonimowości i ogólnych uprawnień. Wyjątki edycji pozostają jawne: Transaction — autor; argument głosowania — właściciel; zadanie — koordynator lub członek zespołu. Ankiety i wydarzenia mogą edytować wszyscy zalogowani użytkownicy.

## 2. Inwentaryzacja widoków edycji

### 2.1. Dokumenty Board

1. [ ] `board.views.PostUpdateView` — `board/urls.py:10`, `board/views.py:268-271`, `board/templates/board/post_form.html:10-80`.
   - Edytuje tytuł, podtytuł, slug, kategorię, obraz, załączniki, widoczność, ważność i treść.
   - Współdzieli logikę z tworzeniem przez `PostFormViewMixin`.
2. [ ] `board.views.delete_attachment` — `board/urls.py:15`, `board/views.py:327-334`.
   - Nie jest formularzem edycji całego dokumentu, ale modyfikuje jego załączniki i należy do tego samego przepływu.
3. [ ] `board.views.PostCategoryEditAPI` — `board/urls.py:17`, `categories/views.py:60-78`.
   - Edytuje nazwę i opis kategorii z poziomu interfejsu Board.

### 2.2. Bookkeeping

4. [ ] `bookkeeping.views.AssetUpdateView` — `bookkeeping/urls.py:40`, `bookkeeping/views.py:117-121`, `bookkeeping/templates/bookkeeping/asset_form.html`.
5. [ ] `bookkeeping.views.CategoryUpdateView` — `bookkeeping/urls.py:52`, `bookkeeping/views.py:161-164`, `bookkeeping/templates/bookkeeping/category_form.html`.
6. [ ] `bookkeeping.views.PartnerUpdateView` — `bookkeeping/urls.py:46`, `bookkeeping/views.py:266-269`, `bookkeeping/templates/bookkeeping/partner_form.html`.
7. [ ] `bookkeeping.views.TransactionUpdateView` — `bookkeeping/urls.py:34`, `bookkeeping/views.py:366-385`, `bookkeeping/templates/bookkeeping/transaction_form.html`.
   - Ma odrębne sprawdzenie autora i bezpieczną obsługę parametru `next`.

### 2.3. Wydarzenia

8. [ ] `events.views.EventUpdateView` — `events/urls.py:13`, `events/views.py:170-174`, `events/templates/events/event_form.html`.
   - Współdzieli formularz z tworzeniem wydarzenia.

### 2.4. Zadania

9. [ ] `tasks.views.TaskEditView` — `tasks/urls.py:13`, `tasks/views.py:503-515`, `tasks/templates/tasks/task_form.html`.
   - Edytuje tytuł, opis i kategorię.
   - Widok ogranicza edycję do koordynatora aktywnego zadania.
10. [ ] `tasks.views.TaskCategoryEditAPI` — `tasks/urls.py:28`, wspólna implementacja w `categories/views.py:60-78`.
    - Edycja kategorii odbywa się asynchronicznie.

### 2.5. Ankiety

11. [ ] `ankiety.views.survey_edit` — `ankiety/urls.py:11`, `ankiety/views.py:192-210`, `ankiety/templates/ankiety/survey_form.html`.
    - Każdy zalogowany użytkownik może edytować aktywną ankietę; zamknięta ankieta pozostaje nieedytowalna.
    - Zapisuje również listę opcji, w tym usuwanie opcji i powiązanych głosów; UI tego skutku wymaga osobnego sprawdzenia.

### 2.6. Głosowania

12. [ ] `glosowania.views.edit` — `glosowania/urls.py:11`, `glosowania/views.py:103-162`, `glosowania/templates/glosowania/edit.html`.
    - Edycja propozycji przepisu przed rozpoczęciem kolejnego etapu.
    - Tworzy snapshot `DecyzjaWersja`.
13. [ ] `glosowania.views.parameters_propose` w trybie edycji — `glosowania/urls.py:20`, `glosowania/views.py:589-670`, `glosowania/templates/glosowania/parameters_propose.html`.
    - Edycja propozycji zmiany parametrów systemu, opcjonalnie z nowym logo.
14. [ ] `glosowania.views.edit_argument` — `glosowania/urls.py:23`, `glosowania/views.py:449-473`, `glosowania/templates/glosowania/edit_argument.html`.
    - Ogranicza edycję do autora argumentu i blokuje ją po zakończeniu głosowania.

### 2.7. Obywatele i konto użytkownika

15. [ ] `obywatele.views.candidate_edit` — `obywatele/urls.py:14`, `obywatele/views.py:751-770`, `obywatele/templates/obywatele/candidate_edit.html`.
    - Edycja profilu nieaktywnego kandydata.
16. [ ] `obywatele.views.my_assets` — `obywatele/urls.py:20`, `obywatele/views.py:569-590`.
    - Edycja danych kontaktowych i zasobów własnego profilu.
17. [ ] `obywatele.views.change_email` i `change_username` — `obywatele/urls.py:26-27`, `obywatele/views.py:151-184`.
18. [ ] `obywatele.views.upload_avatar` — `obywatele/urls.py:21`, `obywatele/views.py:508-514`.
19. [ ] `obywatele.views.toggle_notification` i `set_user_language` — `obywatele/views.py:519-563`, `807-824`.
    - Są to małe endpointy ustawień, ale również zapisują zmiany użytkownika.
20. [ ] Zmiana hasła przez allauth (`account_change_password`) — link w `obywatele/templates/obywatele/my_profile.html:83-92`; implementacja jest zewnętrzna względem aplikacji.

### 2.8. Ustawienia grupy

21. [ ] Edycja szybkich linków w `home.views.group_settings` — `home/views.py:369-429`, `home/templates/home/site_admin.html:26-100`.
    - Ten sam formularz obsługuje dodawanie i edycję po przełączeniu nazwy ukrytego pola przez JavaScript.
22. [ ] `board` i `tasks` — wspólne endpointy kategorii (`CategoryEditAPI`) należy traktować jako część audytu uprawnień API, nie tylko interfejsu.

### 2.9. Obszary sprawdzone bez osobnego widoku edycji

23. [ ] Nie znaleziono osobnego widoku edycji wiadomości czatu w przeglądanych trasach.
24. [ ] Formularze tworzenia, usuwania, głosowania, podpisywania i akcji statusowych nie są osobnymi widokami edycji, ale ich przyciski i przekierowania mogą wymagać wspólnego standardu.

## 3. Ustalenia i problemy do rozwiązania

> Sekcje 3.1–3.3 są zachowanym rejestrem wcześniejszych obserwacji backendowych. Nie są aktywnym zakresem tego audytu, chyba że konkretny punkt jest konieczny do poprawnego działania UI. Aktywna praca koncentruje się na sekcji 3.4 oraz na formularzach ankiet i wydarzeń.

### 3.1. Autoryzacja i zakres dostępu

1. [x] **Board: pozostawić otwartą edycję i usuwanie.** Ukrywanie lub blokowanie akcji według autora nie jest regułą bieżącego audytu; wyjątkiem pozostają ograniczenia systemowe wynikające z modelu dokumentu.
2. [x] **Wydarzenia: potwierdzić jako wspólny zasób grupy.** Edycja i usuwanie pozostają dostępne każdemu zalogowanemu użytkownikowi.
3. [x] **Bookkeeping: potwierdzić model zasobów wspólnych.** Asset, Category i Partner pozostają edytowalne przez każdego zalogowanego użytkownika. Transaction pozostaje ograniczony do autora.
4. [ ] **Kandydat: potwierdzić, kto może edytować profil nieaktywnego użytkownika.** `candidate_edit` wymaga logowania, ale nie sprawdza autora kandydata ani szczególnej roli (`obywatele/views.py:751-770`). Jeżeli jest to celowy etap wspólnego onboardingu, trzeba udokumentować tę regułę; jeżeli nie, należy dodać ograniczenie.
5. [ ] **Głosowania: ujednolicić warunek w UI i widoku.** Partial akcji dopuszcza `id.author == None`, natomiast `glosowania.views.edit` przekierowuje użytkownika, gdy autor nie jest bieżącym użytkownikiem (`glosowania/templates/glosowania/_detail_actions.html:2-7`, `glosowania/views.py:110-112`).
6. [ ] **Kategorie API: dodać testy autoryzacji i CSRF zgodne z przeznaczeniem endpointów.** Wspólne `CategoryEditAPI` wymaga logowania, ale nie ma ograniczenia właściciela ani roli; zakres tej operacji powinien być jawny dla Board i Tasks.

### 3.2. Integralność i logika zapisu

7. [ ] **Edycja propozycji: objąć snapshot i zmianę obiektu jedną transakcją.** `glosowania.views.edit` tworzy `DecyzjaWersja`, następnie modyfikuje `Decyzja`, ale nie używa `transaction.atomic()` (`glosowania/views.py:120-132`). Należy zabezpieczyć historię przed częściowym zapisem; zmiana dotyka audytowanej logiki głosowań i wymaga osobnej decyzji przed implementacją.
8. [ ] **Edycja parametrów: sprawdzić atomowość i semantykę logo.** `parameters_propose` zapisuje snapshot, parametry i plik w jednym przebiegu (`glosowania/views.py:604-639`), ale należy potwierdzić zachowanie przy błędzie zapisu oraz możliwość zastąpienia/usunięcia wcześniej proponowanego logo.
9. [ ] **Ankiety: potwierdzić destrukcyjny efekt zmiany opcji.** `SurveyForm.create_options()` usuwa opcje nieobecne w przesłanym tekście, a kaskada usuwa ich głosy (`ankiety/forms.py:73-100`). Interfejs powinien jasno ostrzegać o tym skutku, a testy powinny pokrywać zmianę nazwy, usunięcie i zachowanie kolejności.
10. [ ] **Quick links: ujednolicić kontrakt pól formularza.** Szablon posiada `edit_link_id`, ale backend rozpoznaje `edit_quick_link`, a JavaScript zmienia nazwę ukrytego pola (`home/templates/home/site_admin.html:28-30`, `72-100`, `home/views.py:396-408`). Usunąć nieużywane pole albo uprościć przepływ do jednego nazwanego pola.
11. [ ] **Quick links: doprecyzować walidację URL.** `_quick_link_data()` sprawdza obecność i długość tekstu, ale nie sprawdza formatu ani dozwolonego schematu URL (`home/views.py:369-381`). Ustalić, czy linki mogą być względne, czy tylko `http(s)`, i walidować zgodnie z tą regułą.
12. [ ] **Parametr `next`: utrzymać ochronę przed open redirect.** Transaction ma sprawdzenie `url_has_allowed_host_and_scheme`, a zadania mają analogiczne helpery. Przy kolejnych widokach edycji nie kopiować prostego `redirect(request.GET['next'])`.

### 3.3. Formularze i obsługa błędów

13. [ ] **Ujednolicić zwracanie błędów formularzy.** `change_email`, `change_username` i `my_assets` po błędzie przekierowują do profilu zamiast ponownie wyrenderować formularz z błędami (`obywatele/views.py:161-184`, `569-590`). Użytkownik traci kontekst i wartości formularza.
14. [ ] **Upload avatara: obsłużyć błąd walidacji.** `upload_avatar` ignoruje błędy `AvatarForm` i zawsze przekierowuje do profilu (`obywatele/views.py:508-514`). Dodać komunikat lub render/redirect z czytelnym błędem, bez ujawniania danych technicznych.
15. [ ] **Wspólny rendering pól.** Survey i część profilu ręcznie składają pola oraz błędy, podczas gdy Board, Event i Bookkeeping korzystają z crispy. Wybrać jeden preferowany wariant (`crispy` lub wspólny partial `home/templates/tw/`) i stopniowo ograniczyć duplikację.
16. [ ] **Zawęzić pola modeli w prostych CBV.** `CategoryCreateView` i `CategoryUpdateView` oraz `PartnerCreateView` i `PartnerUpdateView` używają `fields = '__all__'` (`bookkeeping/views.py:155-164`, `260-269`). Zastąpić jawną listą pól, aby nowe pole modelu nie stało się automatycznie edytowalne.
17. [ ] **Zachować dane `FILES` i błędy w przepływach wieloczęściowych.** Zweryfikować ponowne renderowanie formularzy Board, profilu kandydata i propozycji parametrów, szczególnie po błędzie walidacji uploadu.
18. [ ] **Ujednolicić komunikaty po zapisie.** Część widoków używa `messages`, część tylko przekierowania; dla użytkownika powinien istnieć jeden wzorzec sukcesu i błędu dla widoków edycji.

### 3.4. UI i dostępność

19. [ ] **Ujednolicić układ stron edycji.** Formy korzystają z różnych struktur: `tw-card`, `tw-detail-layout`, `tw-event-card`, sam nagłówek, a także `bookkeeping/menu.html`. Przejrzeć każdy szablon względem `docs/UI_STANDARDS.html` i wspólnych partiali.
20. [ ] **Ograniczyć klasy modułowe.** Zweryfikować `tw-event-card`, `tw-event-back-link`, `tw-quick-link-*` i pozostałe klasy specyficzne dla widoku; pozostawić je wyłącznie tam, gdzie opisują rzeczywiście unikalną semantykę.
21. [ ] **Usunąć niedozwolone lub niespójne klasy formularzy.** W `board/post_form.html:31` występuje `is-invalid`, podczas gdy standard projektu wymaga prefiksu `tw-` dla nowych klas i wspólnego wariantu błędu.
22. [ ] **Ujednolicić tytuły i akcje.** Formularze używają naprzemiennie „Edit”, „Update”, „Save”, „Back” i „Cancel”, różnych ikon oraz różnych rozmiarów przycisków. Ustalić słownik dla formularzy edycji, bez zmiany istniejących kontraktów tłumaczeń bez planu migracji.
23. [ ] **Dodać właściwe nagłówki i kontenery.** `glosowania/templates/glosowania/edit_argument.html` nie używa karty dla formularza, a formularze zmiany nazwy/e-maila nie korzystają ze wspólnego kontenera strony. Sprawdzić hierarchię nagłówków i szerokości na mobile.
24. [ ] **Sprawdzić etykiety, komunikaty błędów i stan disabled.** Szczególnie checkboxy Board, pola dynamiczne Event, pola opcji Survey i uploady powinny mieć powiązane etykiety, błędy z rolą `alert` oraz czytelny stan niedostępności.
25. [ ] **Nie przenosić stylów statycznych do inline CSS.** Przy porządkowaniu nie dodawać nowych stylów inline; trzymać się pipeline'u `tailwind.css` → `tailwind.build.css`.

### 3.5. Testy regresji

26. [ ] Dodać test bezpośredniego wejścia na URL Board przez użytkownika niebędącego autorem.
27. [ ] Dodać testy ustalonej reguły autorstwa/roli dla Event, Asset, Category, Partner i kandydata.
28. [ ] Dodać testy wspólnego `CategoryEditAPI`: anonimowy użytkownik, zalogowany użytkownik, niepoprawne dane, CSRF i zakres dozwolonej roli.
29. [ ] Dodać testy formularzy profilu zachowujące dane i błędy po nieudanym zapisie.
30. [ ] Dodać test obsługi niepoprawnego avatara oraz przekroczenia limitu pliku.
31. [ ] Dodać testy quick linków dla dodawania, edycji, nieistniejącego ID, kolejności i walidacji URL.
32. [ ] Dodać test atomowości historii propozycji: brak osieroconego snapshotu po nieudanym zapisie bieżącej wersji.
33. [ ] Rozszerzyć istniejące testy ankiet o destrukcyjny efekt usunięcia opcji i komunikat ostrzegawczy w formularzu.
34. [ ] Dla każdego widoku edycji sprawdzić GET, poprawny POST, POST z błędami, użytkownika anonimowego i użytkownika bez uprawnień.

## 4. Zalecana kolejność prac — UI

1. [ ] Ustalić wspólny układ formularza edycji: kontener, karta, nagłówek i akcje.
2. [ ] Przejrzeć formularze Board, Event, Ankiety i Bookkeeping względem `UI_STANDARDS.html`.
3. [ ] Ujednolicić rendering pól, błędów, etykiet i stanów mobilnych bez tworzenia nowych wyjątków CSS.
4. [ ] Ujednolicić akcje zapisu/anulowania/powrotu i zachowanie parametrów kontekstu.
5. [ ] Naprawić ankiety i wydarzenia tak, aby UI odzwierciedlało dostęp każdego zalogowanego użytkownika do edycji.
6. [ ] Dodać wyłącznie focused testy renderowania i zachowania zmienionych formularzy.
7. [ ] Po zmianach UI uruchomić `npm run build:css`, `python scripts/regression_scan.py` i `python scripts/ui_guard.py`.

## 5. Status wykonania audytu UI

W ramach bieżącego etapu ujednolicono lub objęto wspólnym standardem formularze:

- Board: `post_form.html`;
- Ankiety: `survey_form.html` i akcje na szczegółach;
- Event: `event_form.html`;
- Tasks: `task_form.html`;
- Bookkeeping: formularze Asset, Category, Partner i Transaction;
- Głosowania: edycja propozycji, argumentu i parametrów;
- Obywatele: edycja kandydata, zasobów, e-maila i nazwy użytkownika;
- Ustawienia grupy: quick links.

Wspólny zakres poprawionych elementów obejmuje kontenery i karty, nagłówki, akcje formularzy, klasy layoutu oraz komunikaty błędów. Nie zmieniano logiki API kategorii ani pozostałych obszarów backendowych poza uzgodnionym udostępnieniem edycji aktywnych ankiet wszystkim zalogowanym użytkownikom.

## 6. Kryterium zamknięcia audytu

1. [ ] Każdy objęty audytem formularz ma oceniony układ, pola, akcje i responsywność.
2. [ ] Każdy znaleziony problem UI ma status: naprawiony, świadomie zaakceptowany albo odłożony z uzasadnieniem.
3. [ ] Formularze zachowują dane i błędy po nieudanym zapisie albo mają świadomie opisany inny przepływ.
4. [ ] UI nie pokazuje akcji sprzecznych z potwierdzonymi wyjątkami domenowymi.
5. [ ] Nie rozszerzono audytu o nieuzgodnione zmiany backendowe, migracje ani nowe reguły własności.
6. [ ] Nie dodano nowych modułowych arkuszy CSS ani klas bez prefiksu `tw-`.
7. [ ] Nie zmodyfikowano `docs/TODO.md`.
8. [ ] Dla zmienionych obszarów uruchomiono właściwe testy i guardraile.

## 7. Etap 1 audytu — potwierdzone obserwacje

Ten etap jest audytem read-only: nie zmienia reguł dostępu ani logiki biznesowej. Problemy wymagające decyzji domenowej pozostają nierozstrzygnięte.

### 6.1. Board

- `PostUpdateView` dziedziczy `LoginRequiredMixin`, ale `get_queryset()` ogranicza obiekty wyłącznie do `is_deleted=False`; nie filtruje po `author=request.user`. Ukrycie przycisku w `_post_detail_actions.html` nie jest kontrolą serwerową.
- `PostFormViewMixin.form_valid()` ustawia `updated_by`, lecz nie sprawdza, kto może edytować istniejący dokument. To nie zastępuje autoryzacji.
- `delete_attachment` pobiera załącznik po `post` i nie ogranicza dokumentu do autora. Jest to osobny punkt zapisu w tym samym przepływie edycji.
- Formularz korzysta z Crispy/Tailwind dla większości pól, ale ręczny input załączników dodaje klasę `is-invalid`, niespełniającą standardu prefiksu `tw-`. Wymaga to późniejszego uporządkowania UI, niezależnie od decyzji o uprawnieniach.
- W istniejących testach Board nie ma testu bezpośredniego wejścia na URL edycji ani usuwania załącznika przez użytkownika niebędącego autorem.

### 6.2. Wydarzenia

- `EventUpdateView` i `EventDeleteView` wymagają logowania, ale nie mają dodatkowego ograniczenia w `get_queryset()` ani `UserPassesTestMixin`.
- Model `Event` nie ma pola autora/właściciela. Nie można więc bez dodatkowej reguły założyć, że właściwym ograniczeniem jest autorstwo; trzeba potwierdzić, czy wydarzenia są zasobami wspólnymi grupy.
- Szablon akcji pokazuje Edytuj/Usuń każdemu zalogowanemu użytkownikowi, co jest spójne z implementacją widoku, ale sama spójność nie potwierdza poprawności reguły domenowej.
- Istniejące testy widoków obejmują listę, szczegóły i widoczność, lecz nie obejmują GET/POST edycji ani usuwania przez użytkownika zalogowanego i anonimowego.

### 6.3. Bookkeeping i wspólne API kategorii

- `AssetUpdateView`, `CategoryUpdateView` i `PartnerUpdateView` mają tylko `LoginRequiredMixin`; dodatkowo `CategoryUpdateView` i `PartnerUpdateView` używają `fields = '__all__'`. Zakres dostępu i zakres pól wymagają jawnego potwierdzenia.
- `TransactionUpdateView` sprawdza autorstwo przez `UserPassesTestMixin` i waliduje parametr `next` przez `url_has_allowed_host_and_scheme`; ten wzorzec jest bezpieczniejszy i powinien pozostać referencją dla pozostałych przekierowań.
- `CategoryEditAPI` wymaga logowania przez wspólny mixin, ale nie sprawdza właściciela ani roli. Ten sam endpoint jest używany przez Board i Tasks, więc ewentualna zmiana uprawnień wymaga decyzji o wspólnym kontrakcie.

### 6.4. Zakres dalszej pracy

1. Uzyskać decyzję domenową dla Board, Event, zasobów Bookkeeping, API kategorii oraz profili kandydatów — bez implementowania zmian w tych obszarach przed potwierdzeniem.
2. Następnie przejrzeć szczegółowo przepływy formularzy i błędów: `obywatele`, `ankiety`, `glosowania` oraz quick links w `home`.
3. Dopiero po ustaleniu reguł przygotować testy regresji, a poprawki UI wykonywać według `UI_DEVELOPMENT_GUIDE.md` i wspólnych partiali.

## 8. Potwierdzone decyzje domenowe

- **Domyślna reguła:** nie wprowadzamy w tym audycie uogólnionej własności dokumentów. Poza poniższymi wyjątkami każdy zalogowany użytkownik może edytować dokumenty.
- **Przejmowanie własności:** mechanizm w `docs/PLAN_PRZEJMOWANIE_WLASNOSCI.md` jest odłożony i nie stanowi zakresu tego audytu.
- **Transaction:** edytować i usuwać może tylko autor transakcji.
- **Argumenty głosowania:** edytować może tylko właściciel argumentu.
- **Zadania:** edytować może koordynator albo członek zespołu zgodnie z istniejącą logiką zadania.
- **Ankiety, Board, Event, Asset, Category i Partner:** edycja pozostaje dostępna każdemu zalogowanemu użytkownikowi; usuwanie Board i załączników również pozostaje otwarte.
- **CategoryEditAPI:** pozostaje dostępne każdemu zalogowanemu użytkownikowi; nie dodajemy ograniczenia właściciela ani roli.
- **candidate_edit:** pozostaje dostępne każdemu zalogowanemu użytkownikowi.

### Korekta wcześniejszego etapu audytu

Wcześniejszy etap zawierał propozycję ograniczenia Board, Event oraz Asset/Category/Partner do właściciela. Po decyzji produktowej propozycja została odrzucona; nie należy jej realizować ani traktować jako otwartego błędu bezpieczeństwa. Zmiany implementacyjne wprowadzone wyłącznie na podstawie tej propozycji zostały wycofane.
