# Uproszczenie 2 — prostsza responsywność i mniej globalnego JavaScriptu

Dokument opisuje propozycję ograniczenia JavaScriptu odpowiedzialnego za układ interfejsu. Checkbox oznacza zadanie do wykonania albo decyzję do potwierdzenia; nie oznacza wykonania zmiany.

## 1. Cel

1. [ ] Przenieść decyzje o układzie toolbarów i steppera z JavaScriptu do CSS.
2. [ ] Zachować w JavaScript tylko stan interakcji i zapamiętywanie preferencji użytkownika.
3. [ ] Ograniczyć liczbę trybów widoku do tych, które są faktycznie potrzebne.
4. [ ] Uczynić zachowanie mobilne przewidywalnym na podstawie kilku jawnych breakpointów.

## 2. Znaleziony problem

`home/static/home/js/app.js` zawiera rozbudowany mechanizm responsywności:

1. [ ] Pomiary `getBoundingClientRect()` i `scrollWidth`.
2. [ ] `ResizeObserver` dla toolbarów, steppera i kontrolek.
3. [ ] `MutationObserver` dla dynamicznie dodawanych elementów.
4. [ ] Trzy etapy kompaktowania: ukrywanie nieaktywnych etykiet, ukrywanie wszystkich etykiet i zawijanie.
5. [ ] Automatyczne zwijanie sidebara, gdy inne elementy nie mieszczą się na ekranie.
6. [ ] Osobne klasy stanu `tw-responsive-*` i `tw-auto-collapsed`.

Główne miejsca:

- `home/static/home/js/app.js:107-263` — pomiar i kompaktowanie responsywne;
- `home/static/home/js/app.js:492-707` — `PagePrefs`, widoki, filtry i zakładki;
- `home/static/home/css/tailwind.css:392-543` — kombinacje `list`, `grid` i `compact`;
- `home/templates/home/base.html:56-103` — globalnie ładowane skrypty.

## 3. Docelowe uproszczenie

1. [ ] Ustalić dwa podstawowe widoki: `list` i `grid`.
2. [ ] Potwierdzić, czy widok `compact` jest potrzebny użytkownikom, czy pozostaje wyłącznie historycznym kontraktem testów i CSS.
3. [ ] Jeśli `compact` nie jest potrzebny, usunąć go z nowych kontraktów, UI i `PagePrefs`, zachowując świadomą migrację starych zapisów localStorage.
4. [ ] Zostawić `PagePrefs` odpowiedzialny za zapis widoku, filtrów i zakładek, ale nie za pomiary layoutu.
5. [ ] Zastąpić `ResizeObserver` prostymi regułami `@media` i `flex-wrap`.
6. [ ] Pozostawić ręczne zwijanie sidebara, ale usunąć jego automatyczne sterowanie przez overflow toolbaru.
7. [ ] Zredukować liczbę klas `tw-responsive-*` do minimum albo usunąć je po migracji CSS.

## 4. Globalne skrypty

Globalny layout ładuje wiele skryptów na każdej stronie, w tym funkcje związane z czatem, Sortable, kategoriami, powiadomieniami push i DOMPurify.

1. [ ] Zmapować, które skrypty są wymagane na każdej stronie.
2. [ ] Przenieść skrypty specyficzne dla modułu do istniejącego bloku `extra_js`, jeśli nie są potrzebne globalnie.
3. [ ] Nie ładować Firebase, Sortable ani logiki czatu na stronach, które ich nie używają.
4. [ ] Zachować kolejność i kontrakty skryptów używanych przez wspólny layout.
5. [ ] Nie wprowadzać nowego bundlera tylko po to, aby ukryć nieużywane skrypty; najpierw ograniczyć miejsca ładowania.

## 5. Kolejność realizacji

1. [ ] Zmierzyć i zapisać aktualne zachowanie toolbaru na desktopie, tablecie i mobile.
2. [ ] Zaimplementować CSS-owy wariant toolbaru bez usuwania starego JavaScriptu.
3. [ ] Porównać zachowanie dla wyszukiwarki, sortowania, filtrów i przełącznika listy/siatki.
4. [ ] Przełączyć stepper na ten sam prosty model breakpointów.
5. [ ] Usunąć automatyczne zwijanie sidebara, jeśli nie jest konieczne dla czytelności.
6. [ ] Dopiero po stabilizacji usunąć nieużywane funkcje i klasy JavaScript/CSS.
7. [ ] Ograniczyć globalne ładowanie skryptów niezależnie od refaktoryzacji responsywności albo wykonać je jako osobny mały krok.

## 6. Kryteria akceptacji

1. [ ] Toolbar nie wymaga `ResizeObserver` do poprawnego ułożenia.
2. [ ] Zmiana szerokości okna nie powoduje migotania, skoków ani losowego zwijania sidebara.
3. [ ] Etykiety i ikony mają przewidywalne zachowanie na określonych breakpointach.
4. [ ] `PagePrefs` nadal przywraca wybrany widok, filtr i zakładkę.
5. [ ] Stare wartości `compact` są obsłużone świadomie: zmigrowane albo jawnie zastąpione przez `list`.
6. [ ] Chat z dynamicznie renderowanym toolbar'em nadal działa.
7. [ ] Po zmianie przechodzą focused testy Jest dotyczące `PagePrefs`, toolbaru i przełączania widoku.

## 7. Ryzyko i decyzje do potwierdzenia

1. [ ] Potwierdzić zgodę na odejście od dopasowania do każdej szerokości kontenera na rzecz breakpointów.
2. [ ] Potwierdzić, czy użytkownicy potrzebują trzeciego widoku `compact`.
3. [ ] Sprawdzić długie etykiety i tłumaczenia, zwłaszcza na mobile.
4. [ ] Nie usuwać automatycznie mechanizmów dotyczących bezpieczeństwa, sanitizacji rich text ani powiadomień push.
