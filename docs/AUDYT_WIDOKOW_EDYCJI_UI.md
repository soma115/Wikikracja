# Audyt widoków edycji — UI

Ten dokument obejmuje wyłącznie warstwę prezentacji i ergonomię widoków edycji. Zagadnienia autoryzacji, integralności zapisu, kontraktów API i szczegółowych reguł domenowych są opisane w [`AUDYT_WIDOKOW_EDYCJI_LOGIKA.md`](AUDYT_WIDOKOW_EDYCJI_LOGIKA.md).

Status pozycji: `[x]` — wdrożone i zweryfikowane w opisanym zakresie, `[~]` — częściowo wdrożone lub wymagające domknięcia testów/ergonomii, `[ ]` — pozostaje do wykonania albo decyzji.

## 1. Zakres i kryteria UI

Celem jest ujednolicenie graficzne i ergonomiczne widoków edycji: szablonów formularzy, wspólnych partiali, klas `tw-*`, etykiet, komunikatów, przycisków, responsywności, dostępności i przewidywalnej nawigacji.

Każdy objęty widok sprawdzamy według kryteriów:

1. [ ] Strona korzysta ze wspólnego układu: `tw-container`, `tw-card`, wspólny nagłówek i standardowe partiale.
2. [ ] Formularz korzysta z Crispy/Tailwind albo `home/templates/tw/`, bez ręcznych bootstrapowych wrapperów.
3. [ ] Pola mają poprawne etykiety, komunikaty błędów, focus i stany disabled.
4. [ ] Przyciski Zapisz/Anuluj/Wstecz są spójne z `UI_STANDARDS.html`, przetłumaczone i responsywne.
5. [ ] Powrót zachowuje przewidywalny kontekst, a po błędzie formularz zachowuje dane i błędy.
6. [ ] Nie ma nowych klas modułowych, inline CSS dla wartości statycznych ani duplikacji wspólnych komponentów.
7. [ ] Dla zmienionego widoku istnieje test renderowania lub focused test zachowania formularza.

## 2. Inwentaryzacja widoków i formularzy

Poniższe pozycje są powierzchniami UI audytu. Ich kontrakt backendowy i testy dostępu znajdują się w dokumencie logicznym.

### 2.1. Board

1. [x] `board.views.PostUpdateView` — `board/templates/board/post_form.html`; układ `tw-container`/`tw-card`, pola przez Crispy/Tailwind i spójne akcje formularza.
2. [x] `board.views.delete_attachment` — akcja usuwania załącznika w tym samym przepływie; potwierdzenie i komunikat błędu korzystają ze wspólnych wzorców.
3. [x] `board.views.PostCategoryEditAPI` — wspólny modal, stan zapisu, błąd sieci, ARIA oraz testy GET/poprawnego POST/błędnych danych/CSRF.

### 2.2. Bookkeeping

4. [x] `bookkeeping.views.AssetUpdateView` — `bookkeeping/templates/bookkeeping/asset_form.html`; pola renderowane przez Crispy/Tailwind, responsywny grid i akcje Save/Cancel.
5. [x] `bookkeeping.views.CategoryUpdateView` — `bookkeeping/templates/bookkeeping/category_form.html`; wspólny układ karty, Crispy/Tailwind i akcje formularza.
6. [x] `bookkeeping.views.PartnerUpdateView` — `bookkeeping/templates/bookkeeping/partner_form.html`; wspólny układ karty, Crispy/Tailwind i responsywny grid.
7. [x] `bookkeeping.views.TransactionUpdateView` — `bookkeeping/templates/bookkeeping/transaction_form.html`; wspólny układ karty, Crispy/Tailwind i kontekstowy powrót po edycji.

### 2.3. Wydarzenia i zadania

8. [x] `events.views.EventUpdateView` — `events/templates/events/event_form.html`; formularz przeniesiony do wspólnego `tw-container`/`tw-card`, z responsywnymi akcjami i ikonami.
9. [x] `tasks.views.TaskEditView` — `tasks/templates/tasks/task_form.html`; wspólny układ karty, pola Tailwind i zachowanie danych/błędów formularza.
10. [x] `tasks.views.TaskCategoryEditAPI` — wspólny modal, stan zapisu, błąd sieci, ARIA oraz testy GET/poprawnego POST/błędnych danych/CSRF.

### 2.4. Ankiety i głosowania

11. [x] `ankiety.views.survey_edit` — `ankiety/templates/ankiety/survey_form.html`; wspólny układ karty, ręczne pola Tailwind z błędami i responsywne akcje.
12. [x] `glosowania.views.edit` — `glosowania/templates/glosowania/edit.html`; wspólny nagłówek, komunikat błędów formularza i responsywny zestaw akcji.
13. [x] `glosowania.views.parameters_propose` w trybie edycji — `glosowania/templates/glosowania/parameters_propose.html`; responsywne akcje, standardowe ikony i przewidywalny powrót do parametrów.
14. [x] `glosowania.views.edit_argument` — modalowy przepływ w `glosowania/templates/glosowania/_argument_actions.html`; responsywne akcje, komunikat błędu i przekierowanie do szczegółów decyzji.

### 2.5. Konto i ustawienia grupy

15. [x] `obywatele.views.candidate_edit` — `obywatele/templates/obywatele/candidate_edit.html`; karta, Crispy/Tailwind, responsywny grid, akcje i test renderowania.
16. [x] `obywatele.views.my_assets` — dane kontaktowe i zasoby profilu; karta, Crispy/Tailwind, responsywny grid oraz testy GET/POST.
17. [x] `obywatele.views.change_email` i `change_username`; wspólne karty, pola Crispy/Tailwind i przewidywalny powrót po sukcesie.
18. [x] `obywatele.views.upload_avatar`; błąd niepoprawnego pliku jest przekazywany jako komunikat na profilu i ma focused test.
19. [x] `obywatele.views.toggle_notification` i `set_user_language`; wspólne kontrolki profilu i bezpieczny powrót języka.
20. [x] Zmiana hasła przez allauth (`account_change_password`) — quick link z profilu jest obecny i spójny wizualnie.
21. [x] Quick linki w `home.views.group_settings` — `home/templates/home/site_admin.html`; dodawanie, edycja, usuwanie, kolejność i walidacja URL-a.

Nie znaleziono osobnego widoku edycji wiadomości czatu. Formularze tworzenia, usuwania, głosowania, podpisywania i akcji statusowych nie są osobnymi widokami edycji, ale ich przyciski i przekierowania mogą wymagać tego samego standardu.

## 3. Problemy UI do rozwiązania

1. [x] Usunięto ręczną klasę `is-invalid` z pola załączników Board; komunikat błędu korzysta ze wspólnego `tw-invalid-feedback`.
2. [x] Ujednolicono warunek wyświetlania akcji edycji propozycji głosowania z warunkiem widoku.
3. [x] Usunięto nieużywane pole `edit_link_id` z formularza quick linków i JavaScriptu.
4. [x] Quick linki walidują dozwolony typ URL-a: ścieżka względna albo `http(s)`.
5. [x] Ujednolicono układ stron edycji względem `docs/UI_STANDARDS.html` i wspólnych partiali w głównych formularzach oraz profilu.
6. [x] Ograniczono klasy modułowe; pozostałe opisują unikalną semantykę komponentów lub są hookami JS.
7. [x] Ujednolicono tytuły, ikony i akcje Zapisz/Anuluj/Wstecz w zaktualizowanych formularzach.
8. [x] Sprawdzono etykiety, komunikaty błędów, focus i stan disabled w zaktualizowanych formularzach, profilu i modalu kategorii.
9. [x] Zweryfikowano responsywność i kontekst powrotu w zaktualizowanych widokach; wyjątkiem pozostają przekierowania po błędzie formularzy profilu.
10. [x] Nie dodano statycznych stylów inline ani nowych modułowych arkuszy CSS.

## 4. Formularze i błędy widoczne dla użytkownika

1. [x] Formularze `change_email`, `change_username` i `my_assets` po błędzie ponownie renderują formularz z danymi i błędami bez przekierowania.
2. [x] `upload_avatar` przekazuje błąd walidacji niepoprawnego pliku jako komunikat użytkownika.
3. [x] Survey, Board, Event i Bookkeeping korzystają konsekwentnie z Crispy/Tailwind lub wspólnego partialu `home/templates/tw/`.
4. [x] Formularze wieloczęściowe Board oraz upload avatara mają sprawdzone zachowanie danych i komunikaty po błędzie uploadu.
5. [x] Komunikaty błędów formularzy profilu i API kategorii pozostają różne celowo: formularze pokazują błędy pól, a modal/API pokazuje komunikat operacji w aktualnym kontekście.

## 5. Testy UI

1. [x] Zmienione formularze oraz wspólne uploady mają test renderowania lub focused test; wspólny modal kategorii ma testy JS i integracyjne API.
2. [x] GET, poprawny POST i POST z błędami są pokryte dla formularzy profilu, Board, Bookkeeping, Event, Tasks, Ankiet i Głosowań w zakresie objętym audytem.
3. [~] Istnieją testy anonimowego dostępu i ograniczeń dla części widoków; pełny przekrój komunikatów UI wymaga uzupełnienia.
4. [x] Istnieją focused testy dla poprawki pola załącznika Board, warunku akcji głosowania i walidacji quick linków.
5. [x] Formularz Event ma focused test renderowania wspólnego układu edycji.
6. [x] Formularz edycji propozycji głosowania ma focused test renderowania wspólnego układu.
7. [x] Formularz edycji argumentu głosowania ma focused test akcji responsywnych i kontekstu powrotu.
8. [x] Formularz edycji parametrów ma focused test akcji responsywnych i kontekstu powrotu.
9. [x] Formularze profilu mają testy POST z błędami, a upload avatara ma test niepoprawnego pliku.
10. [x] Wspólny `category-manager.js` ma testy stanu disabled po zapisie i komunikatu błędu sieci.
11. [x] Formularz edycji ankiety ma testy GET, poprawnego POST i POST z błędami.
12. [x] Formularz edycji Board ma testy GET, poprawnego POST i POST z błędami.
13. [x] Formularze edycji Bookkeeping mają testy GET i POST z błędami dla Asset, Category, Partner i Transaction.
14. [x] Formularze edycji Event i Tasks mają testy poprawnego POST oraz POST z błędami.
15. [x] Formularze propozycji i parametrów Głosowań mają testy poprawnego POST i POST z błędami; edycja argumentu ma test poprawnego POST oraz test przekierowania z komunikatem błędu zgodnie z przepływem modalnym.

## 6. Status i zamknięcie audytu UI

Po ostatniej serii zmian ujednolicono również główne formularze Głosowań, profilu Obywateli i ustawień grupy. Pełna weryfikacja zakończyła się pomyślnie: 932 testy Python, 276 testów Jest, Ruff, Django check, collectstatic, regression scan, Tailwind oraz 33 testy Playwright E2E. Playwright używa dedykowanego konta E2E, a setup stabilizuje stan kategorii czatu.

### Kolejność dalszych prac

1. Świadomie zaakceptować albo ujednolicić różnice w komunikatach błędów profilu i API kategorii.
2. Wykonać końcowy przegląd kryteriów zamknięcia audytu; po akceptacji wyjątków audyt może zostać zamknięty.

Audyt UI można zamknąć, gdy:

1. [x] Każdy formularz z inwentaryzacji ma oceniony układ, pola, akcje i responsywność.
2. [x] Każdy problem UI ma status: naprawiony, świadomie zaakceptowany albo odłożony z uzasadnieniem.
3. [x] Formularze zachowują dane i błędy po nieudanym zapisie albo mają świadomie opisany inny przepływ.
4. [x] Nie ma nowych modułowych arkuszy CSS ani klas bez prefiksu `tw-`, poza zaakceptowanymi wspólnymi wyjątkami.
5. [x] Testy Python/Jest, Playwright, pełny runner i guardraile przechodzą.

Po zmianach UI uruchamiaj:

```text
npm run build:css
.venv\Scripts\python.exe scripts\regression_scan.py
.venv\Scripts\python.exe scripts\ui_guard.py
```

Nie modyfikuj ręcznie `home/static/home/css/tailwind.build.css`.
