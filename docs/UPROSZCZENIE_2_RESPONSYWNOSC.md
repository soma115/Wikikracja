# Uproszczenie 2 — stabilniejszy toolbar na małych ekranach

Dokument opisuje ograniczony eksperyment z responsywnością. Checkbox oznacza zadanie do wykonania albo decyzję do potwierdzenia; nie oznacza wykonania zmiany.

## 1. Cel i zakres

Celem jest zmniejszenie migotania i nieprzewidywalnego układu toolbaru bez przepisywania całego globalnego JavaScriptu.

1. [ ] Zastąpić najbardziej problematyczne dopasowanie toolbaru prostymi regułami CSS.
2. [ ] Pozostawić JavaScriptowi stan interakcji i `PagePrefs`.
3. [ ] Zachować obecne warianty widoku oraz zapisane preferencje do czasu potwierdzenia, że któryś jest zbędny.
4. [ ] Nie zmieniać zachowania sidebara, jeśli nie jest to konieczne dla tego eksperymentu.

### Poza zakresem

Nie robimy teraz:

- generalnego usuwania `ResizeObserver`, `MutationObserver` ani wszystkich klas `tw-responsive-*`;
- automatycznej migracji lub usuwania widoku `compact`;
- przebudowy wszystkich toolbarów, stepperów i widoków w jednym kroku;
- optymalizacji globalnego ładowania skryptów — to osobny, niezależny temat;
- zmian w sanitizacji, powiadomieniach push, czacie lub innych funkcjach domenowych.

## 2. Problem

`home/static/home/js/app.js` automatycznie mierzy szerokość elementów i zmienia klasy toolbarów. Daje to dopasowanie do dowolnej szerokości, ale zwiększa złożoność i może powodować skoki układu.

Nie ma jeszcze wystarczającej podstawy, aby usuwać cały mechanizm. Najpierw trzeba ustalić, który konkretny toolbar faktycznie zyskuje na prostszym CSS.

Główne miejsca:

- `home/static/home/js/app.js` — responsywne dopasowanie oraz niezależny `PagePrefs`;
- `home/static/home/css/tailwind.css` — style toolbarów i breakpointów;
- odpowiedni partial toolbaru — do wybranego pilotażu.

## 3. Minimalne rozwiązanie

1. [ ] Wybrać jeden wspólny toolbar z widocznym problemem na mobile.
2. [ ] Opisać jego dwa lub trzy stany szerokości: pełny, zwinięty i zawinięty.
3. [ ] Zaimplementować te stany przez istniejące klasy `tw-*`, `@media` i `flex-wrap`.
4. [ ] Pozostawić dotychczasowy JavaScript jako zabezpieczenie do czasu porównania zachowania.
5. [ ] Nie zmieniać `PagePrefs`, kluczy localStorage ani kontraktu `data-view`.
6. [ ] Dopiero po udanym pilotażu zdecydować, czy ten sam wzorzec opłaca się zastosować do steppera lub kolejnego toolbaru.

Widok `compact` pozostaje bez zmian. Można go usunąć dopiero w osobnym kroku, po sprawdzeniu użycia, migracji zapisów localStorage i aktualizacji testów.

## 4. Kolejność realizacji

1. [ ] Zmierzyć obecne zachowanie wybranego toolbaru na desktopie, tablecie i mobile.
2. [ ] Zanotować klasy oraz funkcje JavaScript odpowiedzialne wyłącznie za ten przypadek.
3. [ ] Dodać CSS-owy wariant bez usuwania starego mechanizmu.
4. [ ] Porównać wyszukiwanie, sortowanie, filtry i przełącznik listy/siatki.
5. [ ] Usunąć tylko kod, który po pilotażu okaże się nieużywany i nie obsługuje innych elementów.
6. [ ] Dopiero wtedy rozważyć zastosowanie wzorca w kolejnym miejscu.

## 5. Kryteria akceptacji

1. [ ] Wybrany toolbar układa się poprawnie bez pomiarów JavaScriptu w typowych szerokościach.
2. [ ] Zmiana szerokości nie powoduje migotania ani losowego zwijania sidebara.
3. [ ] Wszystkie istniejące akcje toolbaru pozostają dostępne.
4. [ ] `PagePrefs` nadal przywraca widok, filtry i zakładkę.
5. [ ] Widok `compact` i stare zapisy pozostają działające.
6. [ ] Nie ma regresji w dynamicznie renderowanym toolbarze czatu, jeśli korzysta z tego samego kodu.

## 6. Ryzyko i weryfikacja

1. [ ] Nie usuwać obserwatorów globalnie na podstawie jednego pilotażu.
2. [ ] Sprawdzić długie etykiety i tłumaczenia na mobile.
3. [ ] Uruchomić focused testy Jest dotyczące zmienionego toolbaru i `PagePrefs`.
4. [ ] Przy zmianie CSS uruchomić `npm run build:css`, `.venv\Scripts\python.exe scripts\regression_scan.py` oraz `.venv\Scripts\python.exe scripts\ui_guard.py`, jeśli istnieje.
5. [ ] Osobno ocenić sens ograniczenia globalnych skryptów po pomiarze, bez łączenia tego z refaktoryzacją responsywności.
