# Plan rozwoju modułu zadań

## Etap 1 — Fazy i dane zadania

- [x] Dodać jawną fazę zadania: `proposal` (propozycja) albo `realization` (realizacja), niezależną od statusu ukończenia, anulowania lub odrzucenia.
- [x] Dodać pola specyfikacji:
  - [x] Kwota — wymagana dla nowych zadań, nieujemna, maksymalnie dwa miejsca po przecinku.
  - [x] Waluta — dowolny krótki wpis; wymagana, gdy kwota jest większa od zera, opcjonalna przy kwocie `0`.
  - [x] Wymagana liczba osób — wymagana dla nowych zadań, co najmniej `1`.
  - [x] Wymóg zgody osób spoza grupy — wymagany wybór „tak” albo „nie”.
  - [x] Miara sukcesu — wymagana.
  - [x] Termin — opcjonalny.
- [x] Dodać model podzadania z treścią, stanem checkboxa i pozycją na liście.
- [x] Przygotować migrację istniejących danych:
  - [x] Aktywne zadania z koordynatorem i bilansem głosów `>= 2` oznaczyć jako realizację; pozostałe aktywne zadania jako propozycję.
  - [x] Starszym zadaniom bez określonej wymaganej liczby osób pozwolić rozpocząć realizację przy minimum jednej osobie — koordynatorze.
  - [x] Pozwolić starszym zadaniom rozpocząć realizację bez pozostałych nowych danych; wymagane informacje muszą zostać uzupełnione przy ich edycji.
- [x] Zachować obecne zachowanie tworzenia: autor zostaje koordynatorem i otrzymuje głos „Pomogę”.

## Etap 2 — Przejścia faz i głosowanie

- [x] Umożliwić koordynatorowi jawną akcję rozpoczęcia realizacji.
- [x] Nie pozwalać na rozpoczęcie realizacji, dopóki:
  - [x] bilans głosów nie osiągnie co najmniej `2`;
  - [x] zespół nie osiągnie wymaganej liczebności — koordynator wlicza się do zespołu, zatwierdzeni pomocnicy zwiększają jego liczebność;
  - [x] wymagane dane nowego zadania nie są uzupełnione.
- [x] Pozostawić głosowanie Pomogę/Nie róbmy otwarte podczas realizacji; bilans `<= -2` nadal automatycznie ustawia status `rejected`.
- [x] Dodać osobną akcję „Cofnij do propozycji”:
  - [x] Wyświetlić potwierdzenie informujące o wyzerowaniu głosów i wyczyszczeniu zespołu.
  - [x] Po potwierdzeniu wyzerować głosy i usunąć koordynatora oraz zatwierdzonych pomocników.
  - [x] Wymagać ponownego przejęcia koordynacji przed edycją specyfikacji.
  - [x] Nie resetować głosów przy edycji specyfikacji w fazie propozycji.
- [x] Pozwolić koordynatorowi zmieniać termin i kategorię także w realizacji bez resetowania głosów.
- [x] Przy ponownym otwarciu zadania ukończonego, anulowanego lub odrzuconego:
  - [x] Przywrócić fazę propozycji.
  - [x] Wyzerować głosy.
  - [x] Zachować koordynatora i zatwierdzonych pomocników.

## Etap 3 — Podzadania i uprawnienia

- [x] Umożliwić koordynatorowi i zatwierdzonym pomocnikom dodawanie, edytowanie, porządkowanie, odhaczanie i usuwanie podzadań.
- [x] Pozwolić zmieniać checklistę w propozycji i realizacji; zablokować zmiany po zamknięciu zadania.
- [x] Dodać drag-and-drop do zmiany kolejności oraz dostępną klawiaturową alternatywę.
- [x] Wykorzystać istniejący SortableJS i wspólny helper projektu, bez dodawania nowej biblioteki.
- [x] Walidować uprawnienia i kolejność po stronie serwera.
- [x] Nie resetować głosów po zmianie checklisty.

## Etap 4 — Ranking koordynatorów

- [x] Uwzględniać zadania `completed`, `cancelled` i `rejected` z całego okresu.
- [x] Przypisywać zadanie koordynatorowi obecnemu przy zamknięciu albo odrzuceniu.
- [x] Pokazywać bieżące wyniki ocen — sukces, porażkę, wynik mieszany i brak ocen — oddzielnie dla każdego statusu końcowego.
- [x] Uwzględniać bieżące oceny zadań ukończonych, anulowanych i odrzuconych; oceny mogą zmieniać prezentowane wyniki po zamknięciu.
- [x] Sortować po łącznej liczbie sukcesów ze wszystkich statusów końcowych, następnie po liczbie wszystkich takich zadań, a potem alfabetycznie po nazwie koordynatora.

## Etap 5 — UI i weryfikacja

- [x] Wyraźnie oddzielić specyfikację zadania od pozostałej treści, korzystając ze wspólnych wzorców UI.
- [x] Pokazywać, dlaczego nie można rozpocząć realizacji, jeśli brakuje głosów lub wymaganej liczby osób w zespole.
- [x] Przed cofnięciem do propozycji wyjaśniać skutki: reset głosów, wyczyszczenie zespołu i konieczność ponownego przejęcia koordynacji.
- [x] Dodać testy wymaganych pól, faz i progów rozpoczęcia, wyjątków dla starszych zadań, resetu głosów, ponownego otwarcia, uprawnień checklisty, sortowania oraz rankingu.
- [x] Po zmianach UI uruchomić budowanie CSS i skany regresji zgodnie z zasadami projektu.
- [ ] Uruchomić Playwright po skonfigurowaniu `E2E_BASE_URL` i uruchomieniu dedykowanego lokalnego serwera E2E.
