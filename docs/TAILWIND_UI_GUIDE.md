# Migracja Tailwind i utrzymanie standardu UI

Ten dokument opisuje zakończoną migrację interfejsu z Bootstrapa i rozproszonego CSS do jednego pipeline'u Tailwind oraz zasady utrzymywania tego standardu.

## Aktualny status

Migracja bazowa jest zakończona. Nowe zmiany UI nie powinny tworzyć kolejnej fazy migracji ani przywracać zależności od Bootstrapa.

- źródło stylów: `home/static/home/css/tailwind.css`;
- tokeny kolorów i motywu: `home/static/home/css/tokens.css`;
- konfiguracja i safelist: `tailwind.config.js`;
- plik generowany: `home/static/home/css/tailwind.build.css` — nie edytować ręcznie;
- wspólne partiale: `home/templates/home/includes/`;
- szablony formularzy: `home/templates/tw/`;
- wspólne interakcje: `home/static/common/js/tw-*.js`;
- standardy wizualne i ikony: `docs/UI_STANDARDS.html`;
- przewodnik tworzenia i utrzymania UI: `docs/UI_DEVELOPMENT_GUIDE.md`.

## Zasady utrzymania

1. **Jedno źródło stylów.** Nowe style trafiają do `tailwind.css`; nie dodajemy arkuszy CSS per moduł ani kolejnych tagów `<link rel="stylesheet">`.
2. **Prefiks `tw-`.** Nowe klasy komponentów i utility muszą mieć prefiks `tw-`. Wyjątki są dozwolone tylko dla istniejących, udokumentowanych haków JS lub kontraktów z bibliotekami zewnętrznymi.
3. **Wspólne komponenty przed lokalnymi wyjątkami.** Najpierw używamy istniejących wzorców: `tw-btn`, `tw-card`, `tw-toolbar`, `tw-form-*`, `tw-modal`, `tw-dropdown`, `tw-alert`, `tw-proposals-list` i wspólnych partiali. Wspólny toolbar używa dla grupy wyszukiwania `flex: 1 1 0` oraz `min-width: 1rem`, dzięki czemu pole może kurczyć się między kontrolkami; poniżej `591.98px` umieszcza wyszukiwarkę w pełnym wierszu nad filtrami i przełącznikiem List / Grid. Nie twórz lokalnych wariantów tej kolejności.
4. **Tokeny zamiast wartości lokalnych.** Kolory i parametry motywu pochodzą z `tokens.css`; nie duplikujemy ich w modułach.
5. **Inline style tylko dla danych dynamicznych.** Dopuszczalne są dynamiczne zmienne CSS, np. `--featured-img` lub `--vote-progress`. Widoczność, odstępy, kolory i wymiary realizujemy klasami.
6. **Ikony ze słownika.** Nową semantykę ikony najpierw dodajemy do `UI_STANDARDS.html`.
7. **Generowane pliki są nietykalne.** Po zmianie źródła uruchamiamy `npm run build:css`; `tailwind.build.css` nie modyfikujemy ręcznie.
8. **Dokumentujemy tylko decyzje trwałe.** Ten plik aktualizujemy przy zmianie architektury pipeline'u, wspólnego kontraktu lub zasad utrzymania, a nie przy każdej migracji pojedynczego szablonu.

## Zakończone prace migracyjne

### Fundament i layout

- skonfigurowano Tailwind z prefiksem `tw-`, tokenami projektu i breakpointami zgodnymi z dotychczasowym UI;
- utworzono pipeline `tailwind.css` → `tailwind.build.css`;
- zmigrowano globalny layout, topbar, sidebar, toasty i obsługę mobile;
- pozostawiono `tokens.css` jako jedyne źródło kolorów i parametrów motywu.

### Wspólne komponenty

Ustandaryzowano między innymi:

- przyciski, karty, badge i alerty;
- formularze oraz własny template pack `tw` dla Crispy Forms;
- toolbar i przełączniki widoku listy/siatki;
- modale, dropdowny, collapse, tooltipy, popovery i zakładki;
- pusty stan, nagłówki modali, przyciski potwierdzeń i filtry chip;
- wspólne helpery DOM, toastów, liczników i nawigacji klikalnych kart/wierszy;
- nagłówek widoku szczegółów oraz warianty metadanych `tw-detail-meta` i `tw-detail-fields`.

### Moduły aplikacji

Migracją objęto dashboard oraz szablony modułów:

- `board`;
- `obywatele`;
- `glosowania`;
- `ankiety`;
- `events`;
- `tasks`;
- `bookkeeping`;
- `chat`;
- globalne strony `home` i szablony allauth.

### Usunięte zależności i stare ścieżki

- usunięto zależności `django-bootstrap5` i `crispy-bootstrap5`;
- usunięto Bootstrap CSS/JS oraz `darkly.css`;
- usunięto nieużywane, modułowe arkusze CSS i ich linki;
- zastąpiono `data-bs-*` kontraktami `data-tw-*`;
- zachowano tylko udokumentowane wyjątki wymagane przez JS, szablony lub biblioteki zewnętrzne.

## Guardrails i weryfikacja

Regresję sprawdzają trzy mechanizmy:

- `scripts/regression_scan.py` — blokuje powrót Bootstrapa, usuniętych arkuszy, niedozwolonych linków CSS i niedozwolonych inline styles;
- `scripts/ui_guard.py` — kontroluje prefiksy klas, ikony, listy/siatki, inline styles i nowe arkusze;
- CI oraz pre-commit — uruchamiają odpowiednie kontrole dla zmienionych plików.

Po zmianie UI dobieramy weryfikację do zakresu:

```text
npm run build:css                         # gdy zmieniono źródło/config Tailwinda
python scripts/regression_scan.py         # zmiana template/CSS/JS
python scripts/ui_guard.py                # zmiana template/CSS/JS
python scripts/ui_guard.py --all --strict # nowy lub szeroko zmieniony wzorzec
```

Dla nowego wspólnego wzorca należy dodatkowo zaktualizować:

1. `home/static/home/css/tailwind.css` oraz ewentualnie safelistę w `tailwind.config.js`;
2. `docs/UI_STANDARDS.html`;
3. `docs/UI_DEVELOPMENT_GUIDE.md`, jeśli zmieniają się zasady tworzenia lub utrzymania UI;
4. ten dokument tylko wtedy, gdy wzorzec zmienia trwałe zasady architektury lub pipeline'u.

## Granice odpowiedzialności dokumentów

- `docs/UI_STANDARDS.html` — wizualne wzorce, komponenty i słownik ikon;
- `docs/UI_DEVELOPMENT_GUIDE.md` — przewodnik pracy nad nowym UI;
- ten dokument — historia migracji, aktualny pipeline i zasady jego utrzymania;
- `docs/TODO.md` — osobista lista użytkownika, której nie aktualizujemy automatycznie.

## Historyczne decyzje

- prefiks `tw-` został przyjęty jako trwała przestrzeń nazw, aby uniknąć konfliktów i powrotu do klas Bootstrapa;
- `tokens.css` pozostał osobnym źródłem tokenów, a komponenty Tailwinda korzystają z jego zmiennych;
- własne lekkie komponenty JavaScript zastąpiły użycie Bootstrap JS tam, gdzie projekt potrzebował tylko modali, dropdownów, collapse, tooltipów, popoverów i zakładek;
- współdzielone partiale i helpery wybrano zamiast kopiowania markupów między aplikacjami;
- klasy semantyczne pozostawiono wyłącznie wtedy, gdy są aktywnymi kontraktami JS, danych lub zewnętrznych bibliotek.
