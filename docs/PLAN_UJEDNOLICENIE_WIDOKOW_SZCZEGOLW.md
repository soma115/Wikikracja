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
- [x] **UŻYTKOWNIK ZAAKCEPTOWAŁ:** akcje globalne (edycja, usuwanie, powrót, nawigacja) są oddzielone od akcji domenowych (głosowanie, podpis, przejęcie zadania, ocena, dodanie argumentu).
- [x] **UŻYTKOWNIK ZAAKCEPTOWAŁ:** dokument używa `data-tw-back`, aby zachować powrót do poprzedniego kontekstu listy, a nie zawsze do jednej stałej listy.

### Kryterium zakończenia

Docelowy podział akcji i zachowanie linku powrotu są zaakceptowane. Nie ma potrzeby tworzenia osobnego layoutu dla każdego modułu.

---

## Etap 1 — nawigacja i akcje globalne

**Ryzyko: niskie**  
**Wpływ na użytkowników: widoczna zmiana położenia przycisków**

- [x] Usunąć drugi, dolny link „Back” z `board/templates/board/post_detail.html`; pozostaje górny `data-tw-back` z powrotem kontekstowym.
- [x] Pozostawić ikony edycji/usuwania wydarzenia w nagłówku przez `events/templates/events/_event_detail_actions.html`.
- [x] Ustalić warianty przycisków globalnych: `tw-btn-*` dla akcji tekstowych i uzasadniony `tw-detail-nav-btn` dla ikonowych akcji w nagłówku.
- [x] Wykorzystać istniejące `tw-flex`, `tw-gap-*` i `tw-flex-wrap` do spójnego odstępu oraz zawijania akcji na małych ekranach.
- [x] Zapewnić `title`, `aria-label` i `fa-fw` dla ikonowych akcji wydarzenia.

### Kryterium zakończenia

Każdy widok ma najwyżej jeden podstawowy mechanizm powrotu, a akcje globalne są wizualnie rozpoznawalne i mają spójne ikony.

---

## Etap 2 — wspólne warianty metadanych

**Ryzyko: niskie do średniego**  
**Wpływ na użytkowników: zmiana prezentacji informacji pomocniczych**

Wprowadzić i udokumentować dwa warianty, bez tworzenia modułowych kopii:

- [x] `tw-detail-meta` — krótki pasek autora, daty, statusu i liczników.
- [x] `tw-detail-fields` — układ etykieta–wartość dla danych szczegółowych.
- [x] Zastosować wariant `tw-detail-meta` w zadaniach, głosowaniach i ankietach tam, gdzie dane są krótkie.
- [x] Zastosować wariant `tw-detail-fields` w księgowości i profilu obywatela tam, gdzie występuje wiele pól.
- [x] Zachować statusy jako `tw-badge-status` lub `tw-badge-*`, bez zastępowania ich zwykłym tekstem.
- [x] Ustalić wspólne zachowanie długich nazw, dat i wartości na mobile: warianty używają zawijania i `min-width: 0`, bez wymuszania poziomego scrolla.

### Kryterium zakończenia

Metadane o podobnym znaczeniu wyglądają tak samo niezależnie od modułu, a różnice wynikają wyłącznie z liczby i rodzaju danych.

---

### Status etapu

Etap 2 wykonany. Wspólne warianty są zdefiniowane w źródłowym CSS, użyte w widokach szczegółów, opisane w dokumentacji i objęte safelistą Tailwinda.

---

## Etap 3 — sekcje treści i hierarchia typografii

**Ryzyko: niskie**  
**Wpływ na użytkowników: spójniejsza czytelność treści**

- [x] Używać `tw-detail-section-label` dla etykiety sekcji z ikoną.
- [x] Używać `tw-detail-section-text` dla głównej wartości lub treści.
- [x] Używać `tw-detail-subsection` do oddzielania kolejnych sekcji w jednej karcie.
- [x] Ograniczyć różnorodność nagłówków `h2`, `h5`, `h6` i zastąpić ją ustaloną hierarchią:
  - `h1` — tytuł widoku w `detail_header`;
  - `h2` — główne sekcje strony;
  - `h3` — podsekcje;
  - klasy `tw-section-heading` tylko dla elementów niebędących nagłówkami.
- [x] Zastąpić `tw-event-section-*` wspólnymi `tw-detail-section-*`; klasy `tw-task-section-*` nie występują w migrowanych widokach szczegółów.
- [x] Sprawdzić ikony sekcji względem słownika w `docs/UI_STANDARDS.html`.

### Status etapu

Etap 3 wykonany. Widoki szczegółów używają wspólnego wzorca oznaczonych sekcji i ustalonej hierarchii nagłówków, przy zachowaniu domenowych kart argumentów, załączników i profilu.

### Kryterium zakończenia

Sekcje szczegółów mają przewidywalną hierarchię, wspólne odstępy i wspólną semantykę ikon.

---

## Etap 4 — karty i układ strony

**Ryzyko: średnie**  
**Wpływ na użytkowników: widoczna zmiana kompozycji stron**

- [x] Utrzymać wspólny shell:
  ```text
  tw-container tw-my-4
  ├── detail_header
  ├── tw-card — podstawowe informacje
  ├── tw-card — akcje lub formularz domenowy
  └── tw-card — sekcje dodatkowe
  ```
- [x] Ujednolicić `detail_header` jako samodzielny element, a treść domenową umieszczać w jednej lub kilku kartach `tw-card`.
- [x] Usunąć zbędne zagnieżdżenia kart; nagłówki księgowości zostały wyjęte z kart, a akcje dokumentu przeniesione do wspólnego nagłówka.
- [x] Zachować specjalny układ argumentów głosowania, list pomocników zadania, tabeli profilu i karty dokumentu, ponieważ poprawia zrozumienie funkcji.
- [x] Ujednolicić odstęp między kartami i sekcjami przez istniejące utility `tw-gap-*`, `tw-mb-*` i `tw-mt-*`.

### Status etapu

Etap 4 wykonany. Widoki szczegółów mają wspólny kontener i samodzielny nagłówek; domenowe karty i specjalne układy pozostały zachowane zgodnie z decyzją użytkownika.

### Kryterium zakończenia

Widoki mają wspólną geometrię strony, ale zachowują potrzebne domenowe komponenty.

---

## Etap 5 — responsywność i dostępność

**Ryzyko: średnie**  
**Wpływ na użytkowników: lepsza obsługa urządzeń mobilnych**

- [x] Dodać `min-width: 0`, zawijanie długich tytułów i zawijanie grup ikonowych akcji w `detail_header`.
- [x] Dodać ograniczenia szerokości i `overflow-wrap` dla metadanych oraz pól szczegółów, aby nie wymuszały poziomego scrolla.
- [x] Dodać widoczny stan `:focus-visible` dla ikonowych przycisków nawigacji.
- [x] Uzupełnić `aria-label`, `title`, `aria-disabled` i `aria-hidden` dla zmigrowanych kontrolek ikonowych.
- [x] Zachować `data-tw-stop-propagation` w miejscach, gdzie linki są zagnieżdżone w interaktywnych kartach; widoki szczegółów nie dodają nowej nawigacji rodzica.
- [x] **UŻYTKOWNIK POTWIERDZIŁ:** ręczna weryfikacja widoków na desktopie i mobile zakończona dla ankiety, zadania, wydarzenia, dokumentu, głosowania i profilu obywatela.

Podczas weryfikacji sprawdzono długie tytuły, zawijanie akcji, brak poziomego scrolla, widoczny focus i kontrast przycisków oraz badge’y.

### Status implementacji

Etap 5 wykonany.

### Kryterium zakończenia

Najważniejsze informacje i akcje są dostępne na mobile, bez ucinania treści i bez poziomego scrolla.

---

## Etap 6 — automatyczne guardraile

**Ryzyko: niskie**  
**Wpływ na użytkowników: brak**

- [x] Dodać focused guard w `scripts/ui_guard.py` sprawdzający, że widoki szczegółów używają `detail_header.html`.
- [x] Sprawdzać obecność kontenera `tw-container` w stronach szczegółów; wyjątki są jawnie deklarowane w `DETAIL_CONTAINER_EXEMPTIONS`.
- [x] Wykrywać powielone linki „Back” w jednym widoku, z wyjątkiem pojedynczej nawigacji kontekstowej `data-tw-back`.
- [x] Wykrywać nowe inline styles inne niż dynamiczne custom properties.
- [x] Nie dopuszczać nowych klas bez prefiksu `tw-` w widokach szczegółów.
- [x] Objąć strukturę wspólnego nagłówka regresją guardu uruchamianego w trybie zmienionych plików i `--all --strict`.

### Status etapu

Etap 6 wykonany. Guard został rozszerzony o kontrakt strukturalny widoków szczegółów i nie zgłasza problemów dla całego repozytorium.

### Dodatkowa unifikacja po Etapie 6

- [x] Ujednolicić etykietę powrotu do krótkiego „Wróć” przez tłumaczenie `Back`.
- [x] Umieścić metadane autora, koordynatora, dat i statusu bezpośrednio pod tytułem w `detail_header`.
- [x] Umieścić akcje edycji i usuwania inline po prawej stronie tytułu; renderować je wyłącznie jako ikony z etykietami dostępnymi.
- [x] Nie renderować dodatkowego guzika czatu, gdy szczegół zawiera osadzony czat.
- [x] Ujednolicić kafelek tytułu wydarzenia z pozostałymi szczegółami przez wspólny `detail_header` i `tw-detail-meta`.
- [x] Ujednolicić główną kartę treści wydarzenia do `tw-card` i `tw-card-body`, bez event-specific opakowania.
- [x] Ujednolicić odstęp między kafelkiem tytułu a pierwszą kartą treści do `1rem`; usunąć dodatkowy rodzicielski `gap` ze szczegółów wydarzenia.

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
