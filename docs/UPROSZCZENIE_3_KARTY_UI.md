# Uproszczenie 3 — wspólny system kart i list

Dokument opisuje propozycję ujednolicenia wizualnej i CSS-owej struktury kart. Checkbox oznacza zadanie do wykonania albo decyzję do potwierdzenia; nie oznacza wykonania zmiany.

## 1. Cel

1. [ ] Zdefiniować wspólną strukturę karty dla propozycji, zadań i wydarzeń.
2. [ ] Ujednolicić nagłówek, tytuł, metadane, treść i sekcje karty.
3. [ ] Zostawić klasy domenowe tylko dla rzeczywiście unikalnych elementów.
4. [ ] Ograniczyć liczbę specjalnych reguł CSS dla listy, siatki i trybu kompaktowego.
5. [ ] Zachować obecne dane, akcje i logikę domenową.

## 2. Znaleziony problem

Propozycje, zadania i wydarzenia korzystają z bardzo podobnego modelu markup'u, ale mają osobne hierarchie klas:

1. [ ] `tw-proposal-card` / `tw-proposal-card-header` / `tw-proposal-card-meta` / `tw-proposal-card-body`.
2. [ ] `tw-task-card` / `tw-task-card-header` / `tw-task-card-meta` / `tw-task-card-body`.
3. [ ] `tw-event-card` / `tw-event-card-header` / `tw-event-card-meta` / `tw-event-card-body`.

Reprezentatywne szablony:

- `glosowania/templates/glosowania/_proposal_card.html`;
- `tasks/templates/tasks/_task_card.html`;
- `events/templates/events/_event_card.html`.

CSS częściowo scala podstawowe deklaracje, ale następnie rozdziela je na wiele wariantów domenowych i widokowych. Szczególnie rozbudowane są reguły dla `tw-proposals-list`, `tw-view-grid`, `tw-view-compact` oraz osobnych kart propozycji i zadań.

Główne miejsce:

- `home/static/home/css/tailwind.css:387-752`.

## 3. Docelowy kontrakt wizualny

Wspólna warstwa strukturalna powinna używać kilku klas:

```text
tw-content-card
tw-content-card-header
tw-content-card-title-row
tw-content-card-title
tw-content-card-meta
tw-content-card-body
tw-content-card-section
tw-content-card-section-label
tw-content-card-section-text
```

1. [ ] Zastąpić wspólne selektory trzech kart klasami `tw-content-card-*`.
2. [ ] Zostawić klasy domenowe wyłącznie dla unikalnych fragmentów, np.:
   - `tw-task-vote-row`;
   - `tw-event-date-pill`;
   - `tw-proposal-status`;
   - `tw-proposal-section--consequences`.
3. [ ] Nie przenosić całej zawartości kart do jednego ogromnego partiala.
4. [ ] Współdzielić strukturę i style, ale pozwolić modułom zachować własne pola danych.
5. [ ] Ustalić jeden sposób oznaczania tytułu, metadanych, badge'y i akcji.
6. [ ] Ustalić, które sekcje są widoczne w widoku listy, a które w siatce.

## 4. Uproszczenie wyglądu

1. [ ] Ujednolicić padding i wysokość nagłówków kart.
2. [ ] Ujednolicić rozmiar tytułu i tekstu metadanych.
3. [ ] Ujednolicić położenie badge'y i akcji po prawej stronie.
4. [ ] Ujednolicić zachowanie hover/focus dla całej karty.
5. [ ] Ujednolicić sposób skracania długich tytułów.
6. [ ] Ograniczyć liczbę wyjątków, które ukrywają całe ciało karty zależnie od kombinacji klas.
7. [ ] Zachować osobny wygląd tylko wtedy, gdy wynika z semantyki danych, a nie z historii modułu.

## 5. Kolejność realizacji

1. [ ] Zainwentaryzować klasy strukturalne używane w trzech wskazanych partialach.
2. [ ] Wyodrębnić deklaracje wspólne z `tw-proposal-card`, `tw-task-card` i `tw-event-card`.
3. [ ] Dodać wspólny kontrakt `tw-content-card-*` w `home/static/home/css/tailwind.css`.
4. [ ] Przepisać najpierw kartę propozycji i kartę zadania.
5. [ ] Przepisać kartę wydarzenia po potwierdzeniu, że jej pill daty pozostaje klasą domenową.
6. [ ] Ograniczyć selektory `tw-proposals-list` do układu listy/siatki, nie do szczegółów każdej domeny.
7. [ ] Zmniejszyć safelistę w `tailwind.config.js` dopiero po usunięciu wszystkich użytkowników starych klas.
8. [ ] Zaktualizować `docs/UI_STANDARDS.html` jako wspólny wzorzec karty.
9. [ ] Nie edytować ręcznie `home/static/home/css/tailwind.build.css`.

## 6. Kryteria akceptacji

1. [ ] Propozycja, zadanie i wydarzenie mają wspólną strukturę nagłówka, metadanych i ciała.
2. [ ] Zmiana wspólnego paddingu lub typografii wymaga edycji jednego zestawu reguł.
3. [ ] Unikalne akcje głosowania, koordynacji i kalendarza nadal działają bez zmiany endpointów.
4. [ ] Listy i siatki zachowują swoją odrębną gęstość informacji.
5. [ ] Karty pozostają dostępne klawiaturą i zachowują `data-detail-url`, role oraz istniejące linki dzieci.
6. [ ] Nie dodano nowych arkuszy CSS ani klas bez prefiksu `tw-`.
7. [ ] Zaktualizowano dokumentację wzorca i sprawdzono regresję szablonów.

## 7. Ryzyko i granice

1. [ ] Nie łączyć na siłę kart księgowości, obywateli i czatu, jeśli mają odmienną semantykę.
2. [ ] Nie zmieniać logiki głosowania, liczenia podpisów, koordynacji ani widoczności danych.
3. [ ] Zweryfikować klikane nagłówki kart oraz linki i przyciski z `data-tw-stop-propagation`.
4. [ ] Sprawdzić desktop, tablet, mobile, listę, siatkę i ewentualny tryb kompaktowy.
5. [ ] Uruchomić po zmianie UI `npm run build:css`, `python scripts/regression_scan.py` i `python scripts/ui_guard.py`.
