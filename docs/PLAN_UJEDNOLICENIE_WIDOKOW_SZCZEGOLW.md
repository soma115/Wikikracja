# Plan: ujednolicenie wyglądu widoków szczegółów

## Cel

Ujednolicić wspólny szkielet, nawigację, metadane, akcje, sekcje treści i zachowanie mobilne widoków szczegółów, bez spłaszczania różnic wynikających z funkcji domenowej.

Plan dotyczy wyłącznie prezentacji i komponentów UI. Nie obejmuje zmian modeli, migracji, uprawnień, procesów głosowania ani logiki biznesowej.

## Stan początkowy

- Wspólny nagłówek istnieje w `home/templates/home/includes/detail_header.html`.
- Część widoków została już przełączona na wspólny kontener `tw-container tw-my-4`.
- Link powrotu jest częściowo przekazywany przez `back_url` do wspólnego nagłówka.
- Standard widoku szczegółów został opisany w `docs/UI_STANDARDS.html` i `docs/UI_DEVELOPMENT_GUIDE.md`.
- Nadal występują różne warianty metadanych, akcji, kart i nagłówków sekcji.
- Zmiany wykonane przed utworzeniem tego planu pozostają niezacommitowane i wymagają przeglądu użytkownika przed dalszą migracją.

## Zasady realizacji

1. Wspólny jest szkielet strony i komponenty UI; treść domenowa pozostaje w module.
2. Nie tworzyć osobnego partiala dla każdego modułu.
3. Nie przenosić logiki biznesowej do partiali prezentacyjnych.
4. Preferować istniejące `tw-*`, `tw-card`, `tw-btn`, `tw-badge-*` i `tw-detail-*`.
5. Nie tworzyć nowych arkuszy CSS ani ręcznie edytować `tailwind.build.css`.
6. Każda nowa klasa wizualna musi mieć prefiks `tw-` i być dodana do źródłowego pipeline’u Tailwind.
7. Zachować specjalizację głosowań, profilu obywatela, argumentów, zadań i czatu, jeśli wynika ona z funkcji strony.
8. Nie zmieniać tekstów użytkownika bez aktualizacji tłumaczeń.
9. Nie modyfikować `docs/TODO.md`.

## Oznaczenia

- `[ ]` — zadanie do wykonania.
- `[x]` — zadanie wykonane.
- **DO ZROBIENIA PRZEZ CIEBIE** — wymaga decyzji, akceptacji albo ręcznego sprawdzenia przez użytkownika.
- **BLOKER** — bez wykonania tego punktu nie należy przechodzić dalej.

---

## Etap 0 — decyzja o docelowym standardzie

**Ryzyko: niskie**  
**Wpływ na użytkowników: brak**

- [x] Użyć `detail_header.html` jako wspólnego nagłówka wszystkich widoków szczegółów.
- [x] Używać `back_url` dla stałej nawigacji do listy zamiast powielać link powrotu w treści.
- [x] Przyjąć strukturę: kontener → nagłówek szczegółów → treść domenowa → sekcje dodatkowe.
- [x] Pozostawić akcje domenowe w treści, jeśli wymagają kontekstu lub formularza.
- [ ] **DO ZROBIENIA PRZEZ CIEBIE — BLOKER:** potwierdzić, że powyższy podział akcji jest właściwy:
  - akcje globalne: edycja, usuwanie, powrót, nawigacja;
  - akcje domenowe: głosowanie, podpis, przejęcie zadania, ocena, dodanie argumentu.
- [ ] **DO ZROBIENIA PRZEZ CIEBIE:** zaakceptować zachowanie dokumentu, w którym `data-tw-back` zachowuje powrót do poprzedniego kontekstu listy, a nie zawsze do jednej stałej listy.

### Kryterium zakończenia

Docelowy podział akcji i zachowanie linku powrotu są zaakceptowane. Nie ma potrzeby tworzenia osobnego layoutu dla każdego modułu.

---

## Etap 1 — nawigacja i akcje globalne

**Ryzyko: niskie**  
**Wpływ na użytkowników: widoczna zmiana położenia przycisków**

- [ ] Usunąć drugi, dolny link „Back” z `board/templates/board/post_detail.html`, jeśli górny `data-tw-back` pozostaje wystarczający.
- [ ] Przejrzeć `events/templates/events/_event_detail_actions.html` i ustalić, czy ikony edycji/usuwania pozostają w nagłówku.
- [ ] Ujednolicić nazewnictwo i warianty przycisków globalnych (`tw-btn-*` albo uzasadniony `tw-detail-nav-btn`).
- [ ] Ujednolicić odstępy między akcjami oraz ich zawijanie na małych ekranach.
- [ ] Zapewnić `title` lub `aria-label` dla przycisków ikonowych.

### Kryterium zakończenia

Każdy widok ma najwyżej jeden podstawowy mechanizm powrotu, a akcje globalne są wizualnie rozpoznawalne i mają spójne ikony.

---

## Etap 2 — wspólne warianty metadanych

**Ryzyko: niskie do średniego**  
**Wpływ na użytkowników: zmiana prezentacji informacji pomocniczych**

Wprowadzić i udokumentować dwa warianty, bez tworzenia modułowych kopii:

- [ ] `tw-detail-meta` — krótki pasek autora, daty, statusu i liczników.
- [ ] `tw-detail-fields` — układ etykieta–wartość dla danych szczegółowych.
- [ ] Zastosować wariant `tw-detail-meta` w zadaniach, głosowaniach i ankietach tam, gdzie dane są krótkie.
- [ ] Zastosować wariant `tw-detail-fields` w księgowości i profilu obywatela tam, gdzie występuje wiele pól.
- [ ] Zachować statusy jako `tw-badge-status` lub `tw-badge-*`, bez zastępowania ich zwykłym tekstem.
- [ ] Ustalić wspólne zachowanie długich nazw, dat i wartości na mobile: zawijanie albo ellipsis, bez poziomego scrolla.

### Kryterium zakończenia

Metadane o podobnym znaczeniu wyglądają tak samo niezależnie od modułu, a różnice wynikają wyłącznie z liczby i rodzaju danych.

---

## Etap 3 — sekcje treści i hierarchia typografii

**Ryzyko: niskie**  
**Wpływ na użytkowników: spójniejsza czytelność treści**

- [ ] Używać `tw-detail-section-label` dla etykiety sekcji z ikoną.
- [ ] Używać `tw-detail-section-text` dla głównej wartości lub treści.
- [ ] Używać `tw-detail-subsection` do oddzielania kolejnych sekcji w jednej karcie.
- [ ] Ograniczyć różnorodność nagłówków `h2`, `h5`, `h6` i zastąpić ją ustaloną hierarchią:
  - `h1` — tytuł widoku w `detail_header`;
  - `h2` — główne sekcje strony;
  - `h3` — podsekcje;
  - klasy `tw-section-heading` tylko dla elementów niebędących nagłówkami.
- [ ] Przejrzeć `tw-event-section-*` i `tw-task-section-*`; zachować je wyłącznie tam, gdzie mają odrębne znaczenie domenowe.
- [ ] Sprawdzić ikony sekcji względem słownika w `docs/UI_STANDARDS.html`.

### Kryterium zakończenia

Sekcje szczegółów mają przewidywalną hierarchię, wspólne odstępy i wspólną semantykę ikon.

---

## Etap 4 — karty i układ strony

**Ryzyko: średnie**  
**Wpływ na użytkowników: widoczna zmiana kompozycji stron**

- [ ] Utrzymać wspólny shell:
  ```text
  tw-container tw-my-4
  ├── detail_header
  ├── tw-card — podstawowe informacje
  ├── tw-card — akcje lub formularz domenowy
  └── tw-card — sekcje dodatkowe
  ```
- [ ] Ujednolicić, czy `detail_header` występuje samodzielnie, czy wewnątrz `tw-card`; preferowany wariant: samodzielny nagłówek, gdy strona ma wiele kart.
- [ ] Usunąć zbędne zagnieżdżenia kart, ale nie scalać kart, które reprezentują odrębne funkcje.
- [ ] Zachować specjalny układ argumentów głosowania, list pomocników zadania i tabeli profilu, jeśli poprawia zrozumienie funkcji.
- [ ] Ujednolicić odstęp między kartami i sekcjami przez istniejące utility `tw-gap-*`, `tw-mb-*` i `tw-mt-*`.

### Kryterium zakończenia

Widoki mają wspólną geometrię strony, ale zachowują potrzebne domenowe komponenty.

---

## Etap 5 — responsywność i dostępność

**Ryzyko: średnie**  
**Wpływ na użytkowników: lepsza obsługa urządzeń mobilnych**

- [ ] Sprawdzić długie tytuły i akcje w `detail_header` na szerokościach mobilnych.
- [ ] Sprawdzić zawijanie grup przycisków w ankietach, zadaniach i profilu obywatela.
- [ ] Sprawdzić, czy metadane nie powodują poziomego scrolla.
- [ ] Sprawdzić widoczny focus i kontrast przycisków oraz badge’y.
- [ ] Uzupełnić `aria-label`, `title`, `aria-pressed` i `aria-expanded` tam, gdzie stan kontrolki nie wynika z tekstu.
- [ ] Zweryfikować, że linki i przyciski wewnątrz kart nie aktywują nawigacji rodzica; używać `data-tw-stop-propagation`.
- [ ] **DO ZROBIENIA PRZEZ CIEBIE:** ręcznie sprawdzić kilka widoków szczegółów na desktopie i mobile po wdrożeniu każdego etapu:
  - ankieta;
  - zadanie;
  - wydarzenie;
  - dokument;
  - głosowanie;
  - profil obywatela.

### Kryterium zakończenia

Najważniejsze informacje i akcje są dostępne na mobile, bez ucinania treści i bez poziomego scrolla.

---

## Etap 6 — automatyczne guardraile

**Ryzyko: niskie**  
**Wpływ na użytkowników: brak**

- [ ] Dodać focused guard lub test szablonów sprawdzający, że widoki szczegółów używają `detail_header.html`.
- [ ] Sprawdzać obecność kontenera `tw-container` w stronach szczegółów, z wyjątkami dla stron dziedziczących kontener nadrzędny.
- [ ] Wykrywać powielone linki „Back” w jednym widoku, z wyjątkiem nawigacji kontekstowej `data-tw-back`.
- [ ] Wykrywać nowe inline styles inne niż dynamiczne custom properties.
- [ ] Nie dopuszczać nowych klas bez prefiksu `tw-` w widokach szczegółów.
- [ ] Dodać regresję dla struktury wspólnego nagłówka po zmianach w `detail_header.html`.

### Kryterium zakończenia

Przyszłe widoki szczegółów nie mogą wrócić do własnych nagłówków, duplikatów nawigacji ani lokalnych wariantów CSS bez jawnego wyjątku.

---

## Weryfikacja każdego etapu

Po zmianach UI:

```powershell
npm run build:css
.venv\Scripts\python.exe scripts\regression_scan.py
.venv\Scripts\python.exe scripts\ui_guard.py
.venv\Scripts\python.exe scripts\ui_guard.py --all --strict
```

Dodatkowo:

```powershell
git diff --check
```

Dla zmian wpływających na renderowanie szablonów można uruchomić odpowiednie testy Django. Nie uruchamiać pełnego runnera bez potrzeby i nie używać browser preview zgodnie z zasadami projektu.

## Bramka akceptacyjna

- [ ] **DO ZROBIENIA PRZEZ CIEBIE:** zaakceptować układ po ręcznym przejrzeniu widoków.
- [ ] Nie ma powielonych linków powrotu ani tytułów.
- [ ] Akcje globalne i domenowe są rozdzielone.
- [ ] Metadane korzystają z jednego z dwóch wspólnych wariantów.
- [ ] Sekcje korzystają ze wspólnych klas `tw-detail-*` tam, gdzie nie ma uzasadnienia domenowego.
- [ ] Przechodzą wszystkie guardraile UI.
- [ ] `docs/UI_STANDARDS.html` i `docs/UI_DEVELOPMENT_GUIDE.md` opisują stan faktyczny.
- [ ] Nie zmodyfikowano `docs/TODO.md`.
