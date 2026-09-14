# Uproszczenie 3 — wspólne podstawy kart UI

Dokument opisuje ostrożne ujednolicenie powtarzalnej struktury kart. Checkbox oznacza zadanie do wykonania albo decyzję do potwierdzenia; nie oznacza wykonania zmiany.

## 1. Cel i zakres

Najbardziej opłacalna jest redukcja powtarzających się reguł strukturalnych, nie pełne ujednolicenie kart wszystkich modułów.

1. [ ] Zidentyfikować wspólne elementy kart propozycji, zadań i wydarzeń.
2. [ ] Ujednolicić tylko podstawy: nagłówek, tytuł, metadane i opcjonalne ciało.
3. [ ] Zachować dane, akcje, gęstość list/siatek i unikalne elementy domenowe.
4. [ ] Nie wprowadzać nowego arkusza ani zmiany logiki domenowej.

### Poza zakresem

Nie robimy teraz:

- jednego ogromnego partiala dla trzech modułów;
- pełnego przepisywania wszystkich kart i wszystkich wariantów `list`, `grid`, `compact`;
- łączenia na siłę kart księgowości, obywateli i czatu;
- usuwania starych klas w tym samym kroku co wprowadzenie nowych;
- zmiany endpointów, dostępności, obsługi kliknięć ani logiki głosowania.

## 2. Problem

Szablony:

- `glosowania/templates/glosowania/_proposal_card.html`;
- `tasks/templates/tasks/_task_card.html`;
- `events/templates/events/_event_card.html`

mają podobny układ, ale osobne klasy strukturalne. Wspólne reguły są przez to powtarzane w `home/static/home/css/tailwind.css`, szczególnie przy kartach propozycji i zadań.

Nie wszystkie trzy karty muszą jednak mieć ten sam wygląd. Najpierw trzeba znaleźć realne przecięcie, a nie narzucać wspólny model na podstawie nazw klas.

## 3. Minimalne rozwiązanie

Zacząć od dwóch najbardziej podobnych kart: propozycji i zadania. Wprowadzić kilka wspólnych klas strukturalnych tylko tam, gdzie markup i zachowanie są faktycznie równoważne, np.:

```text
tw-content-card
tw-content-card-header
tw-content-card-title
tw-content-card-meta
tw-content-card-body
```

1. [ ] Zestawić markup, style i warianty obu kart.
2. [ ] Wybrać najmniejszy wspólny zestaw klas.
3. [ ] Dodać wspólne reguły do istniejącego `home/static/home/css/tailwind.css`.
4. [ ] Migrować kartę propozycji i zadania stopniowo, zachowując stare klasy jako aliasy przejściowe, jeśli są potrzebne.
5. [ ] Ocenić kartę wydarzenia dopiero po porównaniu jej semantyki; pill daty pozostawić klasą domenową.
6. [ ] Nie przenosić zawartości kart do wspólnego partiala.
7. [ ] Usunąć stare klasy i zmniejszyć safelistę dopiero po znalezieniu wszystkich użytkowników.

Unikalne elementy, takie jak głosowanie, status propozycji, termin wydarzenia i akcje zadania, pozostają w modułach domenowych.

## 4. Kolejność realizacji

1. [ ] Zainwentaryzować markup i selektory dwóch kart pilotażowych.
2. [ ] Potwierdzić, że wspólne klasy zmniejszą liczbę reguł zamiast dodać kolejną warstwę aliasów.
3. [ ] Dodać wspólny kontrakt w źródłowym `tailwind.css`.
4. [ ] Przepisać najpierw jeden fragment, np. nagłówek i metadane, oraz porównać wygląd.
5. [ ] Dokończyć migrację propozycji i zadania tylko po udanym porównaniu.
6. [ ] Osobno zdecydować, czy wydarzenia rzeczywiście korzystają ze wspólnego kontraktu.
7. [ ] Zaktualizować `docs/UI_STANDARDS.html` tylko jeśli powstanie trwały, wspólny wzorzec.
8. [ ] Nie edytować ręcznie `home/static/home/css/tailwind.build.css`.

## 5. Kryteria akceptacji

1. [ ] Karty propozycji i zadań współdzielą tylko potwierdzoną strukturę podstawową.
2. [ ] Zmiana wspólnego paddingu lub typografii wymaga zmiany jednego zestawu reguł.
3. [ ] Unikalne akcje i dane nadal działają bez zmiany endpointów.
4. [ ] Lista, siatka i ewentualny compact zachowują dotychczasową gęstość informacji.
5. [ ] Zachowane są `data-detail-url`, role, linki dzieci oraz `data-tw-stop-propagation`.
6. [ ] Wszystkie nowe klasy mają prefiks `tw-` i pochodzą z głównego pipeline'u CSS.
7. [ ] Nie powstaje nowy wzorzec UI bez aktualizacji dokumentacji wymaganej przez standardy projektu.

## 6. Ryzyko i weryfikacja

1. [ ] Nie łączyć kart o odmiennej semantyce tylko dla redukcji nazw klas.
2. [ ] Sprawdzić klikane nagłówki, przyciski i linki z zatrzymaniem propagacji.
3. [ ] Porównać desktop, tablet, mobile, listę i siatkę dla obu kart pilotażowych.
4. [ ] Po zmianie UI uruchomić `npm run build:css`, `.venv\Scripts\python.exe scripts\regression_scan.py` i `.venv\Scripts\python.exe scripts\ui_guard.py`, jeśli istnieje.
5. [ ] Uruchomić focused testy szablonów/regresji, jeśli są dostępne.
