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
- Specyfikacja obejmuje tytuł, opis zasadniczy, szacowany koszt i walutę, wymaganą liczbę osób, wymóg zgody spoza grupy, miarę sukcesu i opcjonalny termin.
- Przy tworzeniu wymagane są wszystkie dane poza terminem. Kwota może wynosić `0`; waluta jest wtedy opcjonalna. Starsze zadania mogą zachować brakujące dane do czasu edycji; bez liczby osób ich minimalny skład to koordynator.
- Autor nowego zadania zostaje koordynatorem i dostaje głos „Pomogę”.
- Rozpoczęcie realizacji wymaga jawnej akcji koordynatora, bilansu głosów co najmniej `2` oraz zespołu o wymaganej liczebności. Koordynator wlicza się do zespołu, a zatwierdzeni pomocnicy uzupełniają skład.
- Zasadnicza specyfikacja (tytuł, opis, koszt, liczba osób, zgoda zewnętrzna i miara sukcesu) jest edytowalna przez koordynatora w fazie propozycji; edycja w tej fazie nie resetuje głosów. Termin i kategorię można zmieniać również podczas realizacji, bez resetu głosów.
- Powrót z realizacji do propozycji wymaga potwierdzenia; zeruje głosy, usuwa koordynatora i zatwierdzonych pomocników. Ponowne przejęcie koordynacji jest konieczne przed edycją zasadniczej specyfikacji.
- Zamknięcie przez koordynatora ustawia `completed` albo `cancelled`. Ponowne otwarcie przez twórcę lub koordynatora ustawia fazę `proposal`, zeruje głosy i zachowuje zespół.

#### Głosowanie i priorytety

- Każdy zalogowany użytkownik ma jeden głos „Pomogę” (`+1`) albo „Nie róbmy” (`-1`) na zadanie; ponowne głosowanie nadpisuje poprzedni wybór, a ponowne kliknięcie wycofuje głos.
- Głosowanie pozostaje otwarte również podczas realizacji. Bilans `<= -2` automatycznie ustawia status `rejected`.
- Głosy „Pomogę” wyznaczają priorytet listy; sprzeciwy są osobnym sygnałem odrzucenia.

#### Zespół i podzadania

- Koordynator zatwierdza chętnych do zespołu; koordynator i zatwierdzeni pomocnicy mogą pisać w czacie trybu zespołowego.
- Koordynator i zatwierdzeni pomocnicy mogą dodawać, edytować, porządkować, odhaczać oraz usuwać podzadania w obu aktywnych fazach.
- Zmiany checklisty nie resetują głosów. Po zamknięciu zadania checklista jest tylko do odczytu.
- Kolejność podzadań można zmieniać przez przeciąganie lub dostępne kontrolki klawiaturowe.

#### Statystyki

- Statystyki pokazują ukończone zadania, oceny i wskaźnik sukcesu.
- Ranking koordynatorów obejmuje zadania ukończone, anulowane i odrzucone z całego okresu; przypisuje je koordynatorowi obecnemu przy zamknięciu albo odrzuceniu.
- Sukcesy, porażki, wyniki mieszane i brak ocen są pokazywane osobno dla każdego statusu, według bieżących ocen. Ranking sortuje po sukcesach ze wszystkich statusów, potem po liczbie wszystkich zadań końcowych i nazwie koordynatora.
