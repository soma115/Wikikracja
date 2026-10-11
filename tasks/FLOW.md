# Task workflow

Poniżej opis przepływu w czystym Markdown prezentujący decyzje i możliwe stany.

1. **Start: nowe zadanie**
   - Status: `active`
   - `assigned_to`: `None`
   - Warunek przejścia:
     - Jeśli nikt nie przejmuje zadania → pozostaje w tym stanie.
     - Jeśli zalogowany użytkownik wybiera akcję **„Weź zadanie”** → przejście do kroku 2.

2. **Zadanie aktywne z właścicielem**
   - Status: `active`
   - `assigned_to`: użytkownik, który przejął zadanie (`take_task`)
   - Właściciel ma trzy opcje:
     1. **Edycja** – można edytować treść zadania; po zapisie pozostaje w tym samym stanie.
     2. **Rezygnacja** – akcja **„Resign”** przekazuje koordynację pierwszej innej osobie z aktualnym głosem „za”, według kolejności `TaskVote.updated_at` i ID. Osoba rezygnująca jest pomijana tylko przy tym przekazaniu; jej głos pozostaje w kolejce. Jeśli nie ma innych chętnych, `assigned_to=None` i działanie wraca do puli oczekujących, pozostając w stanie `active`.
     3. **Zamknięcie** – uruchamia formularz `TaskStatusForm`, który zezwala tylko na status `completed` lub `cancelled`. Przejście do kroku 3.

3. **Zamknięcie zadania**
   - Formularz wymusza wybór jednego z dwóch stanów:
     - `completed` → zadanie uznane za ukończone, przypisanie zostaje zachowane.
     - `cancelled` → zadanie anulowane, przypisanie również pozostaje.
   - Zadanie przechodzi do sekcji zadań zamkniętych; pojawia się możliwość oceny oraz **reopen**.

4. **Ponowne otwarcie (dowolny użytkownik)**
   - Dla zadania ze statusem `completed` lub `cancelled` każdy zalogowany użytkownik może wybrać akcję **„Reopen task”**.
   - Efekty:
     - Status wraca do `active`.
     - Wszystkie głosy (`TaskVote`) są usuwane, więc ranking startuje od zera.
     - `assigned_to` pozostaje bez zmian (czyli może wskazywać poprzedniego właściciela lub `None`).
   - Po reopen zadanie wraca do kroku 2 (aktywny stan z właścicielem albo oczekujące na przypisanie).
