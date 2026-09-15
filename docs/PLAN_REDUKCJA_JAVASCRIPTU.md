# Plan redukcji JavaScriptu

## Cel

Zmniejszyć liczbę plików, stanów i interakcji obsługiwanych przez JavaScript, zachowując większość obecnej funkcjonalności aplikacji.

Preferowany model:

- Django odpowiada za dane, uprawnienia, walidację, filtrowanie, sortowanie i zapisy;
- HTML odpowiada za linki, formularze i podstawową nawigację;
- HTMX obsługuje komunikację HTTP i wymianę renderowanych przez Django fragmentów;
- Alpine.js obsługuje mały, lokalny stan komponentów UI;
- CSS odpowiada za layout, responsywność i proste stany wizualne;
- Django Channels oraz dedykowany klient czatu obsługują komunikację czasu rzeczywistego;
- własny JavaScript pozostaje tam, gdzie daje istotną ergonomię, atrakcyjność wizualną albo jest technicznie niezbędny.

## Zmieniona filozofia JavaScriptu

Celem nie jest mechaniczne usunięcie JavaScriptu ani rezygnacja z wygodnego i atrakcyjnego interfejsu. Celem jest usunięcie obowiązku utrzymywania własnej infrastruktury JavaScriptowej tam, gdzie gotowy model server-driven jest wystarczający.

Docelowo:

- HTMX jest pierwszym wyborem dla akcji HTTP, formularzy i aktualizacji fragmentów strony;
- Alpine.js jest pierwszym wyborem dla lokalnego stanu modali, dropdownów, zakładek i podobnych komponentów;
- własny globalny framework UI nie jest rozwijany w `app.js`;
- czat pozostaje osobną wyspą JavaScriptu opartą na Django Channels i może rozwijać się niezależnie;
- push, Service Worker, edytory, uploady, drag-and-drop i inne funkcje przeglądarkowe pozostają świadomymi wyjątkami;
- każda migracja musi zachować ergonomię, dostępność, responsywność i jakość wizualną, a nie tylko zmniejszyć liczbę linii JS.

Najważniejsza zasada upraszczania:

> JavaScript ma być progresywnym ulepszeniem interfejsu, a nie drugim backendem ani własnym frameworkiem aplikacji. Używamy go chętnie tam, gdzie poprawia doświadczenie użytkownika, ale jego wspólną infrastrukturę oddajemy HTMX, Alpine.js i Django Channels.

Dokument jest wynikiem przeglądu projektu z 2026-09-15. Na etapie audytu nie zmieniono kodu, konfiguracji, zależności ani danych.

## Zakres audytu

Projekt ma około 36 produkcyjnych plików JavaScript, oprócz testów Jest oraz bibliotek vendorowych. Najważniejsze obszary to:

- `home/static/home/js/app.js` — około 1783 linii, wiele niezależnych funkcji wspólnych;
- `home/static/common/js/` — wspólne komponenty UI i utility;
- `chat/static/chat/js/` — czat, WebSocket, obecność i push;
- `tasks/static/tasks/js/tasks.js` — głosowanie i dynamiczne elementy zadań;
- `board/static/js/uploader.js` — TinyMCE i uploady;
- `obywatele/static/obywatele/js/` — lista obywateli, profil i tabela majątku;
- inline JavaScript w szablonach `home`, `events`, `tasks`, `bookkeeping`, `chat` i `obywatele`.

Globalne skrypty są ładowane w `home/templates/home/base.html`. Obejmują między innymi modale, dropdowny, collapse, tooltipy, popovery, utility DOM, `app.js`, autosave, Sortable, manager kategorii, obecność, powiadomienia i push.

## Granice uproszczenia

### JavaScript, który powinien pozostać

#### Czat

Czat korzysta z WebSocketów, reconnectu, dołączania do pokojów, obsługi wiadomości, reakcji, odpowiedzi, edycji i synchronizacji odczytu. Tego nie można sensownie przenieść do renderowania Django bez utraty funkcji czasu rzeczywistego.

Możliwe jest jednak dalsze ograniczenie zakresu czatowego JavaScriptu przez usunięcie funkcji drugorzędnych, np. lokalnych szkiców, automatycznego sortowania, rozbudowanych filtrów, preview pokoju na mobile i części dynamicznych modalów.

#### Push notifications

`chat/static/chat/js/push-notifications.js` używa Service Workera, Firebase Messaging i Notification API. Python może wysyłać powiadomienia do Firebase, ale nie zastąpi kodu wykonywanego w przeglądarce.

#### Rich text

`contenteditable`, clipboard, skróty klawiaturowe i synchronizacja z ukrytym polem formularza wymagają JavaScriptu. Możliwe jest natomiast uproszczenie samego edytora albo zastąpienie go zwykłym `textarea`.

#### Uploady

Podgląd obrazów, drag-and-drop, wybór wielu plików i kompresja po stronie klienta wymagają JavaScriptu. Sam upload może działać jako zwykły formularz Django, kosztem preview i dynamicznego usuwania plików.

## Najlepsi kandydaci do usunięcia

### 1. Carousel dokumentów na dashboardzie

Inline JS w `home/templates/home/home.html` obsługuje automatyczne przełączanie, przyciski poprzedni/następny, timer i zatrzymywanie po najechaniu.

Możliwe uproszczenie:

- zwykła lista dokumentów;
- poziome przewijanie CSS;
- wyświetlanie jednego dokumentu i link „Pokaż wszystkie”.

To funkcja wyłącznie prezentacyjna i może zostać usunięta bez wpływu na logikę domenową.

### 2. Countdown ankiet

Licznik czasu w `home/static/home/js/app.js` aktualizuje się co sekundę. Można wyrenderować pozostały czas przez Django i aktualizować go dopiero po przeładowaniu strony. Termin zakończenia i tak musi być egzekwowany po stronie backendu.

### 3. Scroll restore i automatyczne ukrywanie toastów

`home/static/home/js/scroll-restore.js` przywraca pozycję scrolla oraz automatycznie usuwa komunikaty po kilku sekundach.

Można pozostawić komunikaty widoczne do ręcznego zamknięcia i zrezygnować z przywracania scrolla. Jest to niewielka utrata wygody przy znacznie prostszym zachowaniu.

### 4. Ostatnie wyszukiwanie i lokalne preferencje

`search-keys.js` oraz część `app.js` zapisują w `localStorage` ostatnie wyszukiwania, filtry i widoki.

Rekomendowane uproszczenie:

- stan filtrów przechowywać jawnie w parametrach URL;
- wynik strony renderować z tych parametrów w Django;
- usunąć ukryte przywracanie filtrów z `localStorage`;
- ewentualnie zachować tylko jeden prosty parametr widoku.

Zysk:

- URL jest źródłem prawdy;
- linki można kopiować i udostępniać;
- przycisk Wstecz działa naturalnie;
- brak niespodziewanych filtrów z poprzedniej wizyty.

### 5. Lokalny stan quick links

Dashboard zapisuje zaznaczenie quick links w `localStorage` i sam wylicza pasek postępu.

Możliwe warianty:

- usunąć stan przeczytania i pozostawić zwykłą listę;
- zapisywać stan na serwerze, jeśli funkcja jest ważna domenowo;
- zastąpić ją zwykłymi linkami bez postępu.

Nie warto utrzymywać lokalnego pseudo-postępu, jeśli nie jest częścią danych użytkownika.

### 6. Responsywne pomiary DOM

Globalna część `app.js` używa `ResizeObserver`, `getBoundingClientRect()` i pomiarów szerokości do etapowego zwijania toolbarów i sidebaru.

Można zastąpić ją prostszym CSS:

- `flex-wrap`;
- media queries;
- krótsze etykiety na mobile;
- stałe ukrywanie drugorzędnych elementów.

Może to wymagać niewielkiego kompromisu wizualnego, ale usunie kod zależny od pomiarów DOM.

## Kandydaci do zastąpienia formularzami Django

W poniższych propozycjach zwykły redirect pozostaje poprawnym fallbackiem. Docelowo preferujemy formularze HTMX zwracające te same partiale Django, aby zachować natychmiastową aktualizację i ergonomię bez ręcznego `fetch()`.

### 1. Aktywność: przeczytane, nieprzeczytane i bookmarki

Strona aktywności używa `fetch()` do:

- oznaczania elementu jako przeczytany;
- oznaczania jako nieprzeczytany;
- dodawania i usuwania bookmarka;
- oznaczania wszystkich elementów jako przeczytane.

Backend już posiada odpowiednie widoki. Można użyć zwykłych formularzy POST z CSRF i redirectem do listy.

Zachowana zostaje funkcjonalność i kontrola uprawnień. Użytkownik traci tylko natychmiastową aktualizację bez przeładowania strony.

### 2. Głosowanie nad zadaniami

`tasks/static/tasks/js/tasks.js` obsługuje AJAX-owe głosowanie, aktualizację liczników, list pomocników, koordynatora i zatwierdzania pomocników.

Można użyć zwykłych formularzy POST oraz redirectu do szczegółu zadania. Listy osób można wyrenderować na stronie albo pokazać przez zwykły link do osobnej sekcji.

Popovery z listami osób można zastąpić:

- `<details>`;
- widoczną sekcją na stronie szczegółu;
- osobnym widokiem Django.

### 3. Zarządzanie kategoriami

`home/static/home/js/category-manager.js` realizuje przez AJAX:

- listowanie kategorii;
- dodawanie;
- edycję;
- usuwanie;
- potwierdzanie usunięcia;
- pobieranie elementów kategorii;
- sortowanie drag-and-drop.

Najprostszy wariant Django:

- osobna strona zarządzania kategoriami;
- `CreateView`, `UpdateView`, `DeleteView`;
- zwykłe formularze POST;
- redirect po zapisie;
- przyciski „w górę” i „w dół” zamiast drag-and-drop.

Usunięcie Sortable.js i modalowego CRUD-u znacząco zmniejszy powierzchnię frontendu.

### 4. Sekcje profilu obywatela

`app.js` dociąga sekcje profilu przez AJAX i wstawia partiale do DOM.

Można użyć zwykłych linków:

```text
/profil/<id>/zadania/
/profil/<id>/aktywnosc/
/profil/<id>/utworzono/
```

Każdy widok renderuje pełną stronę. Backend już rozróżnia partiale dla żądań AJAX i pełne szablony, więc ta zmiana wymagałaby uporządkowania widoków, ale nie tworzenia nowej logiki domenowej.

### 5. Filtrowanie obywateli

`obywatele/static/obywatele/js/citizens_list.js` wykonuje lokalne filtrowanie, okresowe odświeżanie i częściową podmianę listy.

Można przenieść wyszukiwanie do Django:

```text
/obywatele/?q=anna&aktywnosc=online
```

Okresowe odświeżanie obecności można usunąć albo zastąpić zwykłym odświeżeniem strony.

### 6. Kalendarz wydarzeń

Inline JS w `events/templates/events/event_list.html` obsługuje:

- zmianę miesiąca przez AJAX;
- dociąganie agendy;
- filtrowanie od wybranego dnia;
- zmiany hashy i historii przeglądarki;
- aktualizację widoku listy i gridu.

Można zastąpić go zwykłymi linkami:

```text
/events/?month=2026-09
/events/?month=2026-09#day-2026-09-15
```

Django już posiada widoki kalendarza i partiale. Zostaje pełna funkcjonalność, ale każde przejście przeładowuje stronę.

### 7. Kolumny tabeli majątku

`obywatele/static/obywatele/js/assets-column-toggle.js` tworzy checkboxy, zapisuje wybór w `localStorage` i ukrywa komórki tabeli.

Możliwe warianty:

- usunięcie personalizacji kolumn;
- parametr GET `?columns=uid,city,responsibilities` obsługiwany przez Django;
- zwykły formularz GET, który przeładowuje stronę.

Nie powinno się utrzymywać równolegle lokalnego stanu JS i serwerowego stanu tabeli.

### 8. Transakcje księgowe

Inline JS w `bookkeeping/templates/bookkeeping/transaction_form.html` zmienia atrybut `step` kwoty w zależności od aktywa.

Można:

- ustawić stałe `step="0.01"`;
- walidować dokładność wyłącznie w formularzu Django;
- przeładowywać formularz po zmianie aktywa.

Najprostszy wariant to stały krok i walidacja backendowa.

### 9. Formularz wydarzenia

Przełączanie pól dla częstotliwości miesięcznej można zastąpić:

- pokazywaniem wszystkich pól;
- osobnym formularzem wydarzenia cyklicznego;
- pozostawieniem niewielkiej funkcji JS jako świadomego wyjątku.

Nie jest to priorytet, ponieważ obecna funkcja jest mała i poprawia ergonomię.

## Funkcje możliwe do zastąpienia HTML/CSS

### Modale

Proste modale można zastąpić osobnymi stronami albo natywnym `<dialog>`. Największy zysk da usunięcie modalowego CRUD-u kategorii, niekoniecznie migracja każdego modala.

### Dropdowny

Proste menu informacyjne i nawigacyjne można zastąpić `<details>` albo zwykłymi linkami. Dropdowny wymagające pozycjonowania względem viewportu mogą pozostać do czasu ich naturalnej przebudowy.

### Collapse

Sekcje informacyjne i listy mogą korzystać z `<details><summary>`. Dotyczy to zwłaszcza prostych sekcji, a nie złożonych stanów czatu.

### Tooltipy i popovery

Tooltipy można zastąpić atrybutem `title`, a popovery — widocznym tekstem, `<details>` albo linkiem do strony szczegółowej. Nie warto utrzymywać popovera tylko po to, aby pokazać dane dostępne już na stronie.

### Motyw jasny/ciemny

Obecnie motyw jest przywracany przed załadowaniem CSS przez `localStorage`. Możliwa jest obsługa przez cookie, sesję lub pole profilu:

```text
POST /profile/theme/ → redirect → Django renderuje data-theme
```

Traci się natychmiastową zmianę bez przeładowania, ale znika anti-FOUC JavaScript i lokalny stan przeglądarki.

## Funkcje, których nie warto przenosić do Pythona

Nie należy próbować zastępować backendem:

- WebSocketowego czatu;
- reconnectu połączenia;
- powiadomień systemowych i FCM;
- Service Workera;
- obsługi clipboardu i `contenteditable`;
- podglądu obrazów przed uploadem;
- drag-and-drop plików, jeśli ta funkcja zostanie zachowana.

Backend powinien pozostać źródłem prawdy dla danych, uprawnień i zapisów. JavaScript może obsługiwać prezentację i synchronizację stanu klienta tylko tam, gdzie jest to konieczne.

## Proponowana kolejność prac

### Faza 1 — inwentaryzacja i granice odpowiedzialności

- [ ] **1.1** Spisać wszystkie produkcyjne skrypty, ich konsumentów, zależności i wpływ na UX.
- [ ] **1.2** Oznaczyć każdą funkcję jako: HTMX, Alpine.js, HTML/CSS, dedykowany JS albo usunięcie.
- [ ] **1.3** Wyodrębnić `chat/static/chat/js/` jako osobną wyspę realtime, której nie migruje się mechanicznie razem z resztą aplikacji.
- [ ] **1.4** Ustalić charakterystykę zachowania dla krytycznych interakcji przed migracją.
- [ ] **1.5** Ustalić metryki sukcesu: mniej kodu globalnego, brak regresji, zachowana ergonomia i brak pogorszenia dostępności.

### Faza 2 — wspólna warstwa server-driven UI

- [ ] **2.1** Dodać HTMX jako wspólną zależność i ustalić sposób jego ładowania oraz wersjonowania.
- [ ] **2.2** Dodać Alpine.js jako wspólną zależność wyłącznie do lokalnego stanu komponentów.
- [ ] **2.3** Przygotować standard odpowiedzi HTMX: partial, pełna strona, błędy walidacji, redirect i komunikaty.
- [ ] **2.4** Przygotować standard atrybutów `hx-*`, eventów Alpine.js, identyfikatorów targetów i fallbacku bez JS.
- [ ] **2.5** Ustalić, że Django pozostaje źródłem prawdy dla danych, uprawnień, walidacji i renderowania.
- [ ] **2.6** Nie przenosić logiki domenowej do wyrażeń HTMX, Alpine.js ani kodu klienta.

### Faza 3 — migracja zwykłych funkcji aplikacji

- [ ] **3.1** Zacząć od jednego małego pilotażu, np. quick links albo prostej akcji listy.
- [ ] **3.2** Przenieść akcje HTTP z ręcznego `fetch()` do formularzy HTMX i odpowiedzi renderowanych przez Django.
- [ ] **3.3** Przenieść modale, dropdowny, tabs i collapse do Alpine.js albo natywnego HTML, bez tworzenia kolejnego globalnego menedżera UI.
- [ ] **3.4** Przenieść filtrowanie, sortowanie i nawigację do parametrów URL oraz backendu; HTMX stosować tam, gdzie poprawia ergonomię.
- [ ] **3.5** Migrować etapami aktywność, profil obywatela, kalendarz, zadania, kategorie i księgowość.
- [ ] **3.6** Zachować animacje, stany ładowania, focus, responsywność i natychmiastową informację zwrotną tam, gdzie są ważne dla UX.
- [ ] **3.7** Po każdej migracji usunąć odpowiadający kod z `app.js` lub modułu domenowego, jeżeli nie ma już innych konsumentów.

### Faza 4 — stabilna wyspa czatu realtime

- [ ] **4.1** Zachować Django Channels jako backend komunikacji i Redis jako warstwę kanałów zgodnie z istniejącym kontraktem WebSocket.
- [ ] **4.2** Utrzymać dedykowanego klienta czatu zamiast zmuszać HTMX lub Alpine.js do obsługi reconnectu, rejoinu i obecności.
- [ ] **4.3** Oddzielić kod transportu, stanu czatu i renderowania wiadomości.
- [ ] **4.4** Zdefiniować publiczny kontrakt zdarzeń czatu, aby przyszłe funkcje nie powiększały globalnego `app.js`.
- [ ] **4.5** Rozwijać funkcje czatu — reakcje, odpowiedzi, edycję, załączniki, obecność i powiadomienia — w ramach tej izolowanej wyspy.
- [ ] **4.6** Zapewnić fallback HTTP dla historii, wysyłania wiadomości i podstawowych operacji, gdy WebSocket jest niedostępny.
- [ ] **4.7** Pokryć reconnect, wielokrotne karty, opóźnienia i ponowne dołączanie testami regresji.

### Faza 5 — ergonomia, atrakcyjność i dostępność

- [ ] **5.1** Nie traktować redukcji JS jako celu ważniejszego niż czytelność, szybkość reakcji i wygoda użytkownika.
- [ ] **5.2** Dodać wspólne stany HTMX/Alpine.js: ładowanie, sukces, błąd, disabled, focus i aktualizację optymistyczną tylko tam, gdzie jest bezpieczna.
- [ ] **5.3** Utrzymać spójne animacje, przejścia, modale, dropdowny i responsywność w ramach istniejących standardów `tw-*`.
- [ ] **5.4** Sprawdzać klawiaturę, czytniki ekranu, focus, mobile i działanie bez JS dla każdej migrowanej funkcji.
- [ ] **5.5** Dokumentować świadome wyjątki, w których własny JS pozostaje, ponieważ daje istotną wartość UX.

### Faza 6 — usunięcie starej infrastruktury i utrzymanie kierunku

- [ ] **6.1** Ograniczyć globalne skrypty ładowane w `home/templates/home/base.html` do rzeczywiście wspólnych funkcji.
- [ ] **6.2** Usunąć duplikaty modali, dropdownów, collapse, AJAX helpers i obsługi formularzy.
- [ ] **6.3** Zmniejszyć `home/static/home/js/app.js` bez przenoszenia jego odpowiedzialności do innego monolitycznego pliku.
- [ ] **6.4** Usunąć nieużywane zależności i moduły dopiero po sprawdzeniu wszystkich konsumentów.
- [ ] **6.5** Dodać do code review pytanie: czy nowa funkcja może być Django + HTMX, Alpine.js lub HTML/CSS, zanim powstanie własny JS?
- [ ] **6.6** Utrzymywać czat jako osobny wyjątek i nie rozbudowywać wspólnej warstwy UI kosztem jego potrzeb.

## Kryteria akceptacji dla kolejnych zmian

Każdy etap redukcji powinien mieć:

- listę usuwanych funkcji i ich obecnych konsumentów;
- test charakterystyki zachowania przed zmianą, jeśli funkcja jest istotna;
- działający wariant HTML/formularzowy albo świadomą decyzję o usunięciu funkcji;
- brak zmiany uprawnień, anonimowości, głosowania i danych audytowalnych;
- sprawdzenie linków, formularzy, CSRF i redirectów;
- testy tylko dla zmienionego zakresu;
- aktualizację dokumentacji, jeśli zmienia się wspólny wzorzec UI.

Dla każdej funkcji należy odnotować jedną z kategorii:

- **HTMX** — akcja HTTP, formularz lub wymiana fragmentu renderowanego przez Django;
- **Alpine.js** — mały, lokalny stan komponentu UI;
- **zachować w dedykowanym JS** — funkcja przeglądarkowa lub czasu rzeczywistego, zwłaszcza czat;
- **przenieść do Django** — dane, walidacja, filtrowanie, zapis lub renderowanie;
- **zastąpić HTML/CSS** — prosty stan prezentacyjny;
- **usunąć** — funkcja kosmetyczna lub nieistotna;
- **pozostawić jako wyjątek** — funkcja, której usunięcie pogorszyłoby ergonomię bardziej niż uprościło kod.

## Powiązane dokumenty

- `docs/PLAN_STABILIZACJA_I_UPROSZCZENIE.md` — nadrzędny plan stabilizacji, szczególnie Faza 5 i Faza 6;
- `docs/PLAN_refaktoryzacja_architektury.md` — granice aplikacji i odpowiedzialności backendu;
- `docs/UI_DEVELOPMENT_GUIDE.md` — zasady wspólnych komponentów UI;
- `docs/UI_STANDARDS.html` — referencja wizualna;
- `home/templates/home/base.html` — globalne ładowanie JavaScriptu;
- `home/static/home/js/app.js` — główne skupisko wspólnego JavaScriptu;
- `chat/static/chat/js/chat.js` — routing i stan czatu;
- `chat/static/chat/js/push-notifications.js` — FCM i Service Worker.

## Rekomendacja końcowa

Wybrany kierunek to **Django + HTMX + Alpine.js + Django Channels**.

Nie należy usuwać JavaScriptu mechanicznie ani przenosić do Pythona interakcji, które są z natury klienckie. Największy i najbezpieczniejszy efekt da:

1. przeniesienie zwykłych akcji HTTP do HTMX i renderowanych przez Django partiali;
2. przeniesienie lokalnego stanu UI do Alpine.js;
3. usunięcie własnej globalnej infrastruktury UI z `app.js`;
4. pozostawienie dedykowanego JavaScriptu w czacie, push, rich text, uploadach i innych świadomych wyjątkach;
5. zachowanie animacji, responsywności, dostępności i natychmiastowej informacji zwrotnej tam, gdzie poprawiają ergonomię;
6. rozwijanie czatu jako niezależnej wyspy opartej na Channels, bez uzależniania go od ograniczeń prostego CRUD-u.

Docelowo aplikacja ma być server-driven, ale nie pozbawiona atrakcyjności. JavaScript nie znika — przestaje być obowiązkiem każdej części aplikacji i pozostaje skoncentrowany tam, gdzie daje użytkownikowi realną wartość.
