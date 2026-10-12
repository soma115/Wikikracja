# Przepływ zadań

## 1. Propozycja

- Status: `active`, faza: `proposal`.
- Przy utworzeniu autor zostaje koordynatorem i otrzymuje głos „Pomogę”.
- Nowe zadanie wymaga kwoty, liczby osób, odpowiedzi tak/nie o zgodzie spoza grupy oraz miary sukcesu. Termin jest opcjonalny; przy kwocie `0` waluta może pozostać pusta.
- Koordynator może edytować specyfikację w propozycji bez resetowania głosów.
- Głosowanie pozostaje otwarte. Bilans `<= -2` automatycznie ustawia status `rejected`.

## 2. Rozpoczęcie realizacji

Koordynator uruchamia osobną akcję. System rozpoczyna realizację tylko wtedy, gdy:

- zadanie ma status `active` i fazę `proposal`;
- bilans głosów wynosi co najmniej `2`;
- zespół osiągnął wymaganą liczbę osób; koordynator wlicza się do zespołu, a zatwierdzeni pomocnicy uzupełniają skład.

Starsze zadania bez liczby osób traktują koordynatora jako minimum jednego członka zespołu. Pozostałe brakujące dane starszych zadań nie blokują rozpoczęcia; trzeba je uzupełnić przy edycji.

## 3. Realizacja

- Status: `active`, faza: `realization`.
- Głosowanie nadal jest otwarte; bilans `<= -2` może ustawić status `rejected`.
- Pól zasadniczej specyfikacji (tytułu, opisu, kosztu, liczby osób, zgody zewnętrznej i miary sukcesu) nie można edytować bezpośrednio. Koordynator może użyć akcji „Cofnij do propozycji”. Potwierdzenie tej akcji od razu zeruje głosy, usuwa koordynatora i zatwierdzonych pomocników oraz przywraca fazę `proposal`.
- Termin i kategorię koordynator może aktualizować również podczas realizacji; zmiany te nie resetują głosów.
- Po cofnięciu ktoś musi ponownie przejąć koordynację, zanim edycja zasadniczej specyfikacji będzie dostępna. Edycja w propozycji nie zeruje głosów.
- Koordynator i zatwierdzeni pomocnicy mogą dodawać, edytować, porządkować, odhaczać i usuwać podzadania. Checklistę można zmieniać do zamknięcia zadania; jej zmiany nie wpływają na głosy.

## 4. Zamknięcie

- Koordynator zamyka zadanie ze statusem `completed` albo `cancelled`.
- Zespół zostaje przypisany do zadania; checklistę blokujemy.
- Po zamknięciu każdy użytkownik może oceniać wynik jako sukces lub porażkę. Oceny pozostają zmienialne.
- Ranking obejmuje wszystkie `completed`, `cancelled` i `rejected` z całego okresu, a zadanie przypisuje koordynatorowi obecnemu przy zamknięciu lub odrzuceniu. Oceny sukcesu, porażki, mieszane i brak ocen są liczone osobno dla każdego statusu. Sortowanie: liczba sukcesów ze wszystkich trzech statusów, potem liczba wszystkich zadań końcowych, potem nazwa koordynatora.

## 5. Ponowne otwarcie

- Obecne uprawnienie do ponownego otwarcia pozostaje przy twórcy lub koordynatorze.
- Zadanie `completed`, `cancelled` albo `rejected` wraca do statusu `active` i fazy `proposal`.
- Głosy Pomogę/Nie róbmy są zerowane, a koordynator i zatwierdzeni pomocnicy pozostają przypisani.
