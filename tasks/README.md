### Tablica zadań — stan modułu

#### Do zrobienia

- Ukrywanie i/lub usuwanie bardzo starych zadań

---

Moduł `tasks` obsługuje propozycje działań, ich realizację, checklisty zespołów oraz ocenę wyników.

#### Fazy i widoki

1. **Awaiting** — aktywne zadania w fazie `proposal`.
2. **In progress** — aktywne zadania w fazie `realization`.
3. **Finished** — ukończone (`completed`), anulowane (`cancelled`) oraz automatycznie odrzucone (`rejected`).
4. **Mine** — aktywne zadania utworzone, przypisane lub poparte przez bieżącego użytkownika.

#### Specyfikacja i cykl życia

- Zadanie ma status (`active`, `completed`, `cancelled`, `rejected`) oraz osobną fazę (`proposal`, `realization`).
- Specyfikacja obejmuje tytuł, opis zasadniczy, tekstowy szacunek kosztu (w tym walutę), wymaganą liczbę osób, wymóg zgody spoza grupy, miarę sukcesu i opcjonalny termin.
- Przy tworzeniu wymagane są wszystkie dane poza terminem; liczba osób domyślnie wynosi `1`. Starsze zadania bez tej liczby pozostają niezmienione, ale jej podanie jest wymagane podczas edycji; do czasu edycji minimalny skład takiego zadania to koordynator.
- Autor nowego zadania zostaje koordynatorem i dostaje głos „Pomogę”.
- Realizacja rozpoczyna się automatycznie, gdy bilans głosów osiągnie co najmniej `2`, koordynator jest przypisany, a zatwierdzony zespół osiągnie wymaganą liczebność. Koordynator wlicza się do zespołu.
- Zasadnicza specyfikacja (tytuł, opis, koszt, liczba osób, zgoda zewnętrzna i miara sukcesu) jest edytowalna przez koordynatora w fazie propozycji; edycja w tej fazie nie resetuje głosów. Termin i kategorię można zmieniać również podczas realizacji, bez resetu głosów.
- Jeśli wymagania realizacji przestaną być spełnione, faza automatycznie wraca do propozycji bez zerowania głosów ani usuwania koordynatora lub zatwierdzonych pomocników.
- Zamknięcie przez koordynatora ustawia `completed` albo `cancelled`. Ponowne otwarcie przez twórcę lub koordynatora ustawia fazę `proposal`, zeruje głosy i zachowuje zespół.

#### Głosowanie i priorytety

- Każdy zalogowany użytkownik ma jeden głos „Pomogę” (`+1`) albo „Blokuj” (`-1`) na zadanie; ponowne głosowanie nadpisuje poprzedni wybór, a ponowne kliknięcie wycofuje głos.
- Głosowanie pozostaje otwarte również podczas realizacji. Gdy głosów przeciw jest co najmniej o jeden więcej niż głosów „Pomogę”, działanie otrzymuje status `rejected`.
- Głosy „Pomogę” wyznaczają priorytet listy; sprzeciwy są osobnym sygnałem odrzucenia.

#### Zespół i zadania

- Realizację prowadzą koordynator i zatwierdzone osoby, które zgłosiły chęć pomocy; nie cała grupa. Koordynator zatwierdza chętnych do zespołu; koordynator i zatwierdzeni pomocnicy mogą pisać w czacie trybu zespołowego.
- Koordynator i zatwierdzeni pomocnicy mogą dodawać, edytować, porządkować, odhaczać oraz usuwać zadania w obu aktywnych fazach.
- Zadania mogą być zagnieżdżone o jeden poziom; ręczne przeciąganie między listą główną i zagnieżdżoną zmienia relację nadrzędne–podrzędne. Przeniesienie zadania nadrzędnego przesuwa cały blok zadań zagnieżdżonych.
- Zaznaczenie zadania nadrzędnego zaznacza jego zadania zagnieżdżone; nadrzędne staje się ukończone, gdy wszystkie zagnieżdżone zadania są ukończone. Usunięcie zadania nadrzędnego z zagnieżdżonymi jest blokowane.
- Zmiany listy zadań nie resetują głosów. Po zamknięciu działania lista jest tylko do odczytu.
- Kolejność zadań można zmieniać przez ręczne przeciąganie.

#### Statystyki

- Statystyki pokazują ukończone zadania, oceny i wskaźnik sukcesu.
- Ranking koordynatorów obejmuje zadania ukończone, anulowane i odrzucone z całego okresu; przypisuje je koordynatorowi obecnemu przy zamknięciu albo odrzuceniu.
- Sukcesy, porażki, wyniki mieszane i brak ocen są pokazywane osobno dla każdego statusu, według bieżących ocen. Ranking sortuje po sukcesach ze wszystkich statusów, potem po liczbie wszystkich zadań końcowych i nazwie koordynatora.
