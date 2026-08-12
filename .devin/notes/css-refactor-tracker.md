# CSS refactor tracker — Wikikracja

Cel: uproszczenie, standaryzacja i deduplikacja CSS oraz usunięcie inline styles.
Dokument służy do śledzenia postępu i przechowywania wiedzy o ryzyku, ponieważ kontekst może być wyczyszczony.

---

## Ogólne zasady

- Nie dodawać nowych `!important` bez uzasadnienia.
- Preferować jedną odpowiedzialność na klasę (rozmiar, kolor, stan).
- Inline `style` dozwolone tylko gdy wartość jest dynamiczna i nie da się jej wyrazić klasą.
- Po każdej fazie uruchamiać `npx jest` i ręcznie weryfikować kluczowe widoki.
- Commitować po każdej fazie (lub mniejszej podsieci), nie czekać do końca.

---

## Fazy

### Faza P0 — szybkie i bezpieczne

1. Naprawić `<style>` w `home/templates/home/search.html` (niezdefiniowana `--bg-card-hover`).
2. Przenieść 4 inline `<style>` do `app.css`:
   - `home/templates/home/search.html`
   - `home/templates/home/home.html`
   - `obywatele/templates/obywatele/my_profile.html`
   - `glosowania/templates/glosowania/historia.html`
3. Usunąć `onmouseover/onmouseout` z `home/templates/home/base.html` i dodać `:hover` do CSS.
4. Zamienić `style.width` na CSS variables w:
   - `home/static/home/js/app.js` (quick links, result bars)
   - `chat/static/chat/js/domapi.js` (chat vote bars)
5. Unifikować awatary w najważniejszych miejscach:
   - `home/templates/home/base.html`
   - `home/templates/home/activity.html`
   - `glosowania/templates/glosednia/_proposal_card.html`
   - `tasks/templates/tasks/_task_card.html`
   - `board/templates/board/_post_card.html`
   - `chat/static/chat/js/templates.js` (dodać citizen-color do fallbacków)

### Faza P1 — systematyzacja

6. Standaryzacja klas tekstowych (`text-muted-78/85/75/50/9`, `text-accent-80/85/70/14`, `font-75` → jednolity system).
7. Unifikacja badge (`text-bg-*`, `badge-status badge-*`, `badge bg-*` → custom `.badge-status--*` + filter).
8. Unifikacja button (`action-btn`, `task-vote-btn`, `toolbar-add-btn`, `btn-cta` → spójna skala).
9. Redukcja `!important` w `.card`/`.card-header`/`.card-footer` i alertach.

### Faza P2 — architektura

10. Podział `app.css` na mniejsze pliki (tokens, base, components, modules, utilities, light-mode).
11. Redukcja `color-mix()` poprzez tokeny CSS.
12. Unifikacja `<progress>` w ankiety z resztą systemu.

---

## Ryzyka związane z JS

Poniżej lista miejsc, gdzie zmiana klas/CSS może zepsuć logikę JS.

### `home/static/home/js/app.js`

- Linie 42-54: `maxHeight` dla expandable — dotyczy animacji, nie CSS, nie ruszać w P0.
- Linie 180-202: quick links — JS modyfikuje `style.color/opacity/width` oraz className ikon.
  - **Ryzyko**: zmiana nazw klas `quick-link-circle` lub `task-dash-link` zepsuje update UI.
  - **Ochrona**: zachować nazwy klas i dodać nowe klasy stanu (`is-read`), a JS ma przełączać klasy zamiast styli.
- Linie 639-643: `style.setProperty('--progress', ...)` oraz `style.setProperty('--w', ...)`.
  - **Ryzyko**: `.progress-fill` używa `--progress`, `.result-bar-fill` używa `--w`. Unifikacja na `--progress` wymaga aktualizacji CSS.
  - **Ochrona**: najpierw dodać do `.result-bar-fill` `width: var(--progress)`, potem zmienić JS.

### `chat/static/chat/js/domapi.js`

- Linie 115-126: `barFill.style.width`, `barWrap.style.display`, `barLabel.style.display`.
  - **Ryzyko**: wypełnienie paska głosowania w czacie może przestać się animować.
  - **Ochrona**: użyć `style.setProperty('--vote-progress', ...)` i dodać `.vote-bar-fill { width: var(--vote-progress); }` w `chat.css`.

### `chat/static/chat/js/templates.js`

- Linia 196: `style="width:<%- _pct %>%"` w template EJS.
  - **Ryzyko**: szablon czatu nie renderuje paska jeśli klasa/zmienna się nie zgadza.
  - **Ochrona**: zamienić na `style="--vote-progress:<%- _pct %>%"` i zsynchronizować z `domapi.js`.
- Linie 141-143, 220-224: fallback awatara w czacie.
  - **Ryzyko**: JS wybiera między `<img>` a `<span>`, dodanie `citizen-color-*` musi być warunkowe.
  - **Ochrona**: przekazać `citizen_color_class` w payloadzie, generować tylko gdy brak `avatar_url`.

### `tasks/static/tasks/js/tasks.js`

- Linie 54, 78-79: selektory `.task-vote-btn`.
  - **Ryzyko**: unifikacja nazw klas w P1 zepsuje głosowanie na zadaniach.
  - **Ochrona**: w P1 zaktualizować selektory w JS równolegle z HTML.

### `obywatele/static/obywatele/js/profile.js`

- Manipuluje awatarem w `my_profile.html`.
  - **Ryzyko**: zmiana struktury awatara w `my_profile.html` zepsuje podgląd uploadu.
  - **Ochrona**: zachować `id="avatar-img"` oraz `id="avatar-wrap"`, nie zmieniać ID.

### `home/static/home/js/category-manager.js` i `obywatele/js/assets-column-toggle.js`

- Używają `style.display` do pokazywania/chowania elementów.
  - **Ryzyko**: niska, ale w P1/P2 warto rozważyć zastąpienie przez klasy `d-none`/`.is-visible`.

---

## Checklist weryfikacji po każdej fazie

- [ ] `npx jest` przechodzi (83 testy).
- [ ] `python scripts/start_dev.py --full` startuje bez błędów.
- [ ] Home — quick links, activity feed, footer, sidebar user, avatary, paski postępu.
- [ ] Głosowania — lista propozycji, karta propozycji, szczegóły, pasek wyników.
- [ ] Zadania — lista, szczegóły, karta zadania, głosy, awatary.
- [ ] Czat — lista pokoi, wiadomości, głosowanie na wiadomości, awatary.
- [ ] Board — lista postów, karta postu, szczegóły postu.
- [ ] Obywatele — lista/siatka, szczegóły, profil, formularze (pasek completion).
- [ ] Wydarzenia — lista, agenda, karta wydarzenia.
- [ ] Ankiety — lista, szczegóły (progress bary).
- [ ] Wyszukiwarka — wyniki, hover wierszy.
- [ ] Tryb jasny (`my_profile`) — wszystkie powyższe bez wizualnych regresji.
- [ ] Mobile — sidebar, chat, karty, tabele.
- [ ] Brak inline `style=` w HTML (poza dynamicznymi `style="--..."`).
- [ ] Brak nowych błędów w konsoli przeglądarki.

---

## Postęp

### Faza P0

- [ ] P0.1 search.html
- [ ] P0.2 inline <style>
- [ ] P0.3 base.html hover
- [ ] P0.4 progress bars JS
- [ ] P0.5 avatars
- [ ] Weryfikacja P0

### Faza P1

- [ ] P1.1 text utilities
- [ ] P1.2 badges
- [ ] P1.3 buttons
- [ ] P1.4 !important reduction
- [ ] Weryfikacja P1

### Faza P2

- [ ] P2.1 split app.css
- [ ] P2.2 color-mix tokens
- [ ] P2.3 <progress> unify
- [ ] Weryfikacja P2
