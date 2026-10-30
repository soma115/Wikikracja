# Przepływ zadań

## 1. Propozycja

- Status: `active`, faza: `proposal`.
- Przy utworzeniu autor zostaje koordynatorem i otrzymuje głos „Pomogę”.
- Nowe zadanie wymaga tekstowego szacunku kosztu, liczby osób, odpowiedzi tak/nie o zgodzie spoza grupy oraz miary sukcesu. Liczba osób domyślnie wynosi `1`; termin jest opcjonalny.
- Koordynator może edytować specyfikację w propozycji bez resetowania głosów.
- Głosowanie pozostaje otwarte. Gdy głosów przeciw jest co najmniej o jeden więcej niż głosów „Pomogę”, status zmienia się automatycznie na `rejected`.

## 2. Rozpoczęcie realizacji

System automatycznie rozpoczyna realizację, gdy:

- zadanie ma status `active` i fazę `proposal`;
- ma przypisanego koordynatora;
- bilans głosów wynosi co najmniej `2`;
- zespół osiągnął wymaganą liczbę osób; koordynator wlicza się do zespołu, a zatwierdzeni pomocnicy uzupełniają skład.

Starsze zadania bez liczby osób traktują koordynatora jako minimum jednego członka zespołu i nie są automatycznie uzupełniane. Przy edycji zadania w fazie propozycji trzeba podać brakującą liczbę osób. Pozostałe brakujące dane starszych zadań nie blokują rozpoczęcia.

## 3. Realizacja

- Status: `active`, faza: `realization`.
- Głosowanie nadal jest otwarte; przewaga głosów przeciw o co najmniej jeden może ustawić status `rejected`.
- Pól zasadniczej specyfikacji (tytułu, opisu, kosztu, liczby osób, zgody zewnętrznej i miary sukcesu) nie można edytować bezpośrednio. Jeśli bilans głosów spadnie poniżej `2`, zniknie koordynator albo zatwierdzony zespół będzie mniejszy od wymaganego, faza automatycznie wraca do `proposal`; głosy, koordynator i pozostali zatwierdzeni pomocnicy są zachowywani.
- Termin i kategorię koordynator może aktualizować również podczas realizacji; zmiany te nie resetują głosów.
- Koordynator musi być przypisany, zanim zasadnicza specyfikacja będzie dostępna do edycji. Edycja w fazie propozycji nie zeruje głosów.
- Koordynator i zatwierdzeni pomocnicy mogą dodawać, edytować, porządkować, odhaczać i usuwać zadania. Zadania mają jeden poziom zagnieżdżenia; ręczne przeciąganie między listą główną i zagnieżdżoną zmienia relację nadrzędne–podrzędne. Przeniesienie zadania nadrzędnego przesuwa cały blok zadań zagnieżdżonych.
- Zaznaczenie zadania nadrzędnego zaznacza zadania zagnieżdżone; odznaczenie zagnieżdżonego odznacza zadanie nadrzędne, a zaznaczenie wszystkich zagnieżdżonych zaznacza zadanie nadrzędne. Zadania nadrzędnego z zagnieżdżonymi nie można usunąć, dopóki nie zostaną przeniesione lub usunięte.
- Listę zadań można zmieniać do zamknięcia działania; jej zmiany nie wpływają na głosy.

## 4. Zamknięcie

- Koordynator zamyka zadanie ze statusem `completed` albo `cancelled`.
- Zespół zostaje przypisany do zadania; checklistę blokujemy.
- Po zamknięciu każdy użytkownik może oceniać wynik jako sukces lub porażkę. Oceny pozostają zmienialne.
- Ranking obejmuje wszystkie `completed`, `cancelled` i `rejected` z całego okresu, a zadanie przypisuje koordynatorowi obecnemu przy zamknięciu lub odrzuceniu. Oceny sukcesu, porażki, mieszane i brak ocen są liczone osobno dla każdego statusu. Sortowanie: liczba sukcesów ze wszystkich trzech statusów, potem liczba wszystkich zadań końcowych, potem nazwa koordynatora.

## 5. Ponowne otwarcie

- Obecne uprawnienie do ponownego otwarcia pozostaje przy twórcy lub koordynatorze.
- Zadanie `completed`, `cancelled` albo `rejected` wraca do statusu `active` i fazy `proposal`.
- Głosy Pomogę/Blokuj są zerowane, a koordynator i zatwierdzeni pomocnicy pozostają przypisani.
