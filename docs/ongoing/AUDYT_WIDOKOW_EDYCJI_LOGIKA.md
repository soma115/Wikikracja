# Audyt widoków edycji — logika i kontrakty

Ten dokument obejmuje wszystko poza warstwą UI: autoryzację, zakres dostępu, kontrakty endpointów, integralność i atomowość zapisu, semantykę danych oraz testy regresji. Zasady warstwy prezentacji i aktualny baseline widoków edycji są opisane w [`UI_DEVELOPMENT_GUIDE.md`](UI_DEVELOPMENT_GUIDE.md), a wzorce wizualne w [`UI_STANDARDS.html`](UI_STANDARDS.html).

Checkbox oznacza zadanie do wykonania lub decyzję do potwierdzenia; nie oznacza, że poprawka została już wdrożona.

## 1. Zakres

Sprawdzamy minimalny kontrakt widoku potrzebny do bezpiecznego użycia formularza:

- czy niezalogowany użytkownik nie może wejść do formularza;
- czy endpoint egzekwuje potwierdzony zakres uprawnień;
- czy nie ma niebezpiecznych przekierowań ani zbyt szerokiego zakresu pól;
- czy zapis wieloetapowy jest odporny na częściowe wykonanie;
- czy krytyczna logika ma test regresji.

Poza zakresem pozostają migracje, schedulery, anonimowość głosowań i ogólne przebudowy domenowe, chyba że konkretny problem jest konieczny do poprawnego działania audytowanego formularza.

Potwierdzone wyjątki: Transaction — autor; argument głosowania — właściciel; zadanie — koordynator albo członek zespołu. Ankiety, Board, Event, Asset, Category i Partner mogą być edytowane przez każdego zalogowanego użytkownika.

## 2. Inwentaryzacja endpointów

1. Board: `PostUpdateView`, `delete_attachment`, `PostCategoryEditAPI`.
2. Bookkeeping: `AssetUpdateView`, `CategoryUpdateView`, `PartnerUpdateView`, `TransactionUpdateView`.
3. Event: `EventUpdateView`.
4. Tasks: `TaskEditView`, `TaskCategoryEditAPI`.
5. Ankiety: `survey_edit`.
6. Głosowania: `edit`, `parameters_propose` w trybie edycji, `edit_argument`.
7. Obywatele: `candidate_edit`, `my_assets`, `change_email`, `change_username`, `upload_avatar`, `toggle_notification`, `set_user_language` oraz zewnętrzny `account_change_password`.
8. Ustawienia grupy: `group_settings` i operacje quick linków.

## 3. Autoryzacja i zakres dostępu

1. [x] Board pozostaje otwarty dla każdego zalogowanego użytkownika; usuwanie załączników również pozostaje otwarte.
2. [x] Event pozostaje wspólnym zasobem grupy.
3. [x] Asset, Category i Partner pozostają wspólnymi zasobami grupy.
4. [x] Transaction pozostaje ograniczony do autora.
5. [x] Argument głosowania pozostaje ograniczony do autora i jest blokowany po zakończeniu głosowania.
6. [x] Zadanie pozostaje ograniczone do koordynatora albo członka zespołu zgodnie z istniejącą logiką.
7. [x] `candidate_edit` pozostaje dostępne każdemu zalogowanemu użytkownikowi jako część wspólnego onboardingu.
8. [x] `PostCategoryEditAPI` i `TaskCategoryEditAPI` (wspólna baza `CategoryEditAPI`) pozostają dostępne każdemu zalogowanemu użytkownikowi; nie dodajemy ograniczenia właściciela ani roli.
9. [x] Warunek wyświetlania akcji edycji propozycji głosowania jest zgodny z warunkiem w widoku.
10. [ ] Dodać pełne testy dostępu dla każdego endpointu: anonimowy użytkownik, poprawny użytkownik i użytkownik bez uprawnień, jeśli przypadek ma zastosowanie.

## 4. Integralność i semantyka zapisu

1. [ ] **Edycja propozycji:** rozważyć objęcie utworzenia `DecyzjaWersja` i zmiany `Decyzja` jedną transakcją. To dotyka audytowanej logiki głosowań i wymaga osobnej decyzji przed implementacją.
2. [x] **Edycja parametrów:** snapshot i aktualizacja decyzji zapisują się w jednej transakcji. Snapshot obejmuje poprzednie `proposed_parameters` i kopię logo; brak nowego pliku zachowuje logo, jawna akcja usuwa je z referendum, a poprzedni plik jest usuwany dopiero po sukcesie. Pliki utworzone podczas nieudanej edycji są sprzątane. Wersje sprzed tej migracji mają te dwa nowe pola puste, bo dawnych wartości nie da się odtworzyć.
3. [x] **Ankiety:** efekt usunięcia opcji i powiązanych głosów jest komunikowany w formularzu; zapis opcji odbywa się w transakcji. Pozostaje utrzymanie testów tego zachowania.
4. [x] **Quick linki:** usunięto nieużywane pole `edit_link_id`, a backend rozpoznaje jeden kontrakt pola akcji. URL-e są ograniczone do ścieżek względnych i `http(s)`.
5. [x] Parametr `next` w istniejących przepływach edycji pozostaje chroniony przez `url_has_allowed_host_and_scheme`; nie należy wprowadzać prostego `redirect(request.GET['next'])`.
6. [ ] W `CategoryCreate/UpdateView` i `PartnerCreate/UpdateView` zastąpić `fields = '__all__'` jawnymi listami pól.

## 5. Obsługa błędów i dane formularzy

1. [x] `change_email`, `change_username` i `my_assets` po błędzie ponownie renderują formularz z danymi i błędami; potwierdzają to testy formularzy.
2. [x] `upload_avatar` stosuje serwerowo wspólny limit `UPLOAD_IMAGE_MAX_SIZE_MB`; testy potwierdzają komunikat błędu i brak zapisu pliku przekraczającego limit.
3. [x] Zachowanie `FILES` i błędów zweryfikowano: Board zapisuje załączniki i odrzuca za duże pliki, profil kandydata nie obsługuje uploadu avatara i ponownie renderuje błędny formularz, a propozycja parametrów zapisuje poprawne logo i pokazuje błędy niepoprawnego uploadu.
4. [ ] Ujednolicić komunikaty sukcesu i błędu bez zmieniania istniejących kontraktów tłumaczeń bez planu migracji.

## 6. Testy regresji

1. [x] Board ma test bezpośredniego wejścia na URL przez użytkownika niebędącego autorem.
2. [x] Testy dostępu obejmują anonimowy GET i POST dla Event, Asset, Category, Partner i `candidate_edit`; istnieją również testy zalogowanego dostępu zgodnego z ustaloną regułą.
3. [x] Testy dostępu `PostCategoryEditAPI` i `TaskCategoryEditAPI` (wspólna baza `CategoryEditAPI`) obejmują anonimowy POST, poprawny i błędny POST oraz CSRF. Każdy zalogowany użytkownik jest dozwolony — nie ma osobnej roli do sprawdzania.
4. [x] Testy formularzy profilu sprawdzają zachowanie danych i błędów po nieudanym zapisie.
5. [x] Testy avatara obejmują niepoprawny format i odrzucenie pliku przekraczającego wspólny limit.
6. [x] Quick linki mają focused testy dodawania poprawnych URL-i i odrzucania niebezpiecznego schematu.
7. [ ] Dodać testy quick linków dla edycji, nieistniejącego ID i kolejności.
8. [ ] Dodać test atomowości historii propozycji, jeżeli decyzja z sekcji 4.1 potwierdzi potrzebę tej zmiany.
9. [x] Ankiety mają test destrukcyjnego efektu usunięcia opcji i zachowania kolejności.
10. [ ] Dla każdego endpointu edycji sprawdzić GET, poprawny POST, POST z błędami, anonimowego użytkownika i użytkownika bez uprawnień, jeśli przypadek ma zastosowanie.

### Następny krok

Uzgodnione i wdrożone zachowanie edycji parametrów opisuje punkt 4.2. Następnie osobno rozstrzygnąć, czy zwykła edycja propozycji ma atomowo obejmować `DecyzjaWersja` i `Decyzja` (punkt 4.1); to odrębny fragment logiki głosowań i wymaga własnej decyzji przed zmianą.

## 7. Kryterium zamknięcia audytu logicznego

1. [ ] Każdy endpoint z inwentaryzacji ma potwierdzony zakres dostępu.
2. [ ] Każda decyzja dotycząca integralności zapisu jest zaakceptowana, wdrożona albo jawnie odłożona.
3. [ ] Nie ma niebezpiecznych przekierowań ani niezamierzonego wystawiania nowych pól modeli.
4. [ ] Krytyczne zachowania mają testy regresji.
5. [ ] Nie rozszerzono audytu o nieuzgodnione migracje, schedulery, anonimowość ani nowe reguły własności.

## 8. Potwierdzone decyzje domenowe

- Nie wprowadzamy w tym audycie uogólnionej własności dokumentów.
- Mechanizm przejmowania własności z [`PLAN_PRZEJMOWANIE_WŁASNOŚCI_TREŚCI.md`](PLAN_PRZEJMOWANIE_WŁASNOŚCI_TREŚCI.md) jest odłożony.
- Transaction edytuje i usuwa wyłącznie autor.
- Argument edytuje wyłącznie właściciel.
- Zadanie edytuje koordynator albo członek zespołu.
- Ankiety, Board, Event, Asset, Category i Partner pozostają dostępne do edycji każdemu zalogowanemu użytkownikowi.
- `PostCategoryEditAPI` i `TaskCategoryEditAPI` pozostają dostępne każdemu zalogowanemu użytkownikowi.
- `candidate_edit` pozostaje dostępne każdemu zalogowanemu użytkownikowi.
- Przy edycji propozycji parametrów brak nowego logo zachowuje obecne; jawne usunięcie wycofuje logo z referendum, ale nie zmienia bieżącego logo witryny. Historia przechowuje kopię poprzedniego pliku, a jego oryginał jest usuwany po zatwierdzeniu zapisu.
