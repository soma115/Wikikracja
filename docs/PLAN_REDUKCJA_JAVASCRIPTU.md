# Plan redukcji JavaScriptu

## Cel

Zmniejszyć liczbę plików, stanów i interakcji obsługiwanych przez JavaScript, zachowując większość obecnej funkcjonalności aplikacji.

Preferowany model:

- Django odpowiada za dane, uprawnienia, walidację, filtrowanie, sortowanie i zapisy;
- HTML odpowiada za linki, formularze i podstawową nawigację, a dla prostych akcji jest pierwszym wyborem;
- HTMX może obsługiwać komunikację HTTP i wymianę renderowanych przez Django fragmentów, jeśli pilotaż uzasadni tę zależność;
- Alpine.js może obsługiwać mały, lokalny stan komponentów UI, jeśli natywne `<details>`, `<dialog>` lub mały dedykowany JS nie są prostsze;
- CSS odpowiada za layout, responsywność i proste stany wizualne;
- Django Channels oraz dedykowany klient czatu obsługują transport i komunikację czasu rzeczywistego; HTMX i Alpine.js mogą obsługiwać wybrane, nietransportowe części interfejsu czatu;
- własny JavaScript pozostaje tam, gdzie daje istotną ergonomię, atrakcyjność wizualną albo jest technicznie niezbędny.

## Zmieniona filozofia JavaScriptu

Celem nie jest mechaniczne usunięcie JavaScriptu ani rezygnacja z wygodnego i atrakcyjnego interfejsu. Celem jest usunięcie obowiązku utrzymywania własnej infrastruktury JavaScriptowej tam, gdzie gotowy model server-driven jest wystarczający.

Docelowo:

- HTML/formularz jest pierwszym wyborem dla prostych akcji HTTP, a HTMX jest kandydatem dla aktualizacji fragmentów strony bez pełnego przeładowania;
- natywne elementy HTML są pierwszym wyborem dla prostego lokalnego stanu, a Alpine.js jest kandydatem dla komponentów, których nie da się prościej obsłużyć przez HTML/CSS lub mały dedykowany JS;
- własny globalny framework UI nie jest rozwijany w `app.js`;
- czat pozostaje osobną wyspą opartą na Django Channels, ale może mieć hybrydowy interfejs: dedykowany JS dla realtime oraz HTMX/Alpine.js dla wybranych fragmentów server-driven i lokalnego stanu;
- push, Service Worker, edytory, uploady, drag-and-drop i inne funkcje przeglądarkowe pozostają świadomymi wyjątkami;
- każda migracja musi zachować ergonomię, dostępność, responsywność i jakość wizualną, a nie tylko zmniejszyć liczbę linii JS.

Najważniejsza zasada upraszczania:

> JavaScript ma być progresywnym ulepszeniem interfejsu, a nie drugim backendem ani własnym frameworkiem aplikacji. Używamy go chętnie tam, gdzie poprawia doświadczenie użytkownika, ale wspólną obsługę prostych akcji oddajemy HTML-owi, Django oraz — po uzasadnieniu — HTMX/Alpine.js; Django Channels pozostaje warstwą realtime.

Dokument jest wynikiem przeglądu projektu z 2026-09-16. Na etapie audytu nie zmieniono kodu, konfiguracji, zależności ani danych.

Ważny stan wyjściowy: HTMX i Alpine.js nie są obecnie używane w repozytorium ani wymienione w `package.json`. Są kierunkiem docelowym, a nie istniejącą warstwą, którą można od razu wykorzystać. Przed dodaniem obu zależności trzeba przeprowadzić mały pilotaż i porównać je z natywnym HTML-em, istniejącym JavaScriptem oraz już używanymi komponentami `tw-*`; plan nie zakłada automatycznego dodania dwóch bibliotek.

## Zakres audytu

W repozytorium jest 80 śledzonych plików `.js`; po wyłączeniu testów, skryptów E2E, konfiguracji, bibliotek vendorowych i plików minifikowanych pozostaje 39 produkcyjnych plików źródłowych JavaScript. Najważniejsze obszary to:

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

Czat korzysta z WebSocketów, reconnectu, dołączania do pokojów, obsługi wiadomości, reakcji, odpowiedzi, edycji i synchronizacji odczytu. Transport, reconnect, rejoin, obecność i obsługa zdarzeń realtime powinny pozostać w dedykowanym kliencie JavaScript, ale nie oznacza to, że cały interfejs czatu musi pozostać imperatywny.

HTMX może obsługiwać wybrane operacje HTTP i renderowane przez Django fragmenty, np. listę pokojów, początkową historię, tworzenie pokoju, ustawienia, formularze i stany błędów. Alpine.js może obsługiwać lokalny stan paneli, modali, dropdownów, widoku mobile, formularza odpowiedzi/edycji oraz stany ładowania. Nie powinny one przejmować źródła prawdy dla wiadomości ani logiki reconnectu.

Możliwe jest również dalsze ograniczenie zakresu czatowego JavaScriptu przez usunięcie funkcji drugorzędnych, np. lokalnych szkiców, automatycznego sortowania, rozbudowanych filtrów, preview pokoju na mobile i części dynamicznych modalów. Każda taka migracja musi zachować kontrakt WebSocket i nie może dublować stanu między Alpine.js a klientem czatu.

#### Push notifications

`chat/static/chat/js/push-notifications.js` używa Service Workera, Firebase Messaging i Notification API. Python może wysyłać powiadomienia do Firebase, ale nie zastąpi kodu wykonywanego w przeglądarce.

#### Rich text

`contenteditable`, clipboard, skróty klawiaturowe i synchronizacja z ukrytym polem formularza wymagają JavaScriptu. Możliwe jest natomiast uproszczenie samego edytora albo zastąpienie go zwykłym `textarea`.

#### Uploady

Podgląd obrazów, drag-and-drop, wybór wielu plików i usuwanie wybranych plików przed wysłaniem wymagają JavaScriptu. Obecny uploader nie kompresuje plików po stronie klienta. Sam upload może działać jako zwykły formularz Django, kosztem preview i dynamicznego zarządzania wyborem plików.

## Najlepsi kandydaci do usunięcia

### 1. Carousel dokumentów na dashboardzie

Inline JS w `home/templates/home/home.html` obsługuje automatyczne przełączanie, przyciski poprzedni/następny, timer i zatrzymywanie po najechaniu.

Możliwe uproszczenie:

- zwykła lista dokumentów;
- poziome przewijanie CSS;
- wyświetlanie jednego dokumentu i link „Pokaż wszystkie”.

To funkcja wyłącznie prezentacyjna i może zostać usunięta bez wpływu na logikę domenową.

### Dashboardowy mini-kalendarz

Inline JS w `home/templates/home/home.html` pobiera przez `fetch()` kolejny miesiąc kalendarza i aktualizuje hash historii przeglądarki. Można zastąpić go statycznym bieżącym miesiącem wyrenderowanym przez Django oraz linkiem do pełnego kalendarza albo zwykłymi linkami z parametrem `month`. To osobny przypadek od JS pełnego widoku `events` i należy go zinwentaryzować przed migracją.

### 2. Countdowny ankiet i etapów głosowań

`home/static/home/js/app.js` aktualizuje co sekundę elementy `[data-countdown]`. Dotyczy to nie tylko ankiet, ale również terminów etapów głosowań renderowanych przez `glosowania`. Można wyrenderować przez Django czas pozostały w chwili ładowania i aktualizować go dopiero po przeładowaniu strony. Termin zakończenia i tak musi być egzekwowany po stronie backendu, ale migracja wymaga zachowania rozróżnienia „rozpoczyna się” / „kończy się” oraz aktualizacji istniejących testów i tekstów dostępności.

### 3. Scroll restore i automatyczne ukrywanie toastów

`home/static/home/js/scroll-restore.js` przywraca pozycję scrolla oraz automatycznie usuwa komunikaty po kilku sekundach.

Można pozostawić komunikaty widoczne do ręcznego zamknięcia i zrezygnować z przywracania scrolla. Jest to niewielka utrata wygody przy znacznie prostszym zachowaniu.

### 4. Ostatnie wyszukiwanie i lokalne preferencje

`search-keys.js` i część `app.js` zapisują w `localStorage` ostatnie wyszukiwania, a `PagePrefs` zapisuje również widoki, zakładki, filtry i ostatnie adresy wielu modułów. Dodatkowo aktywność synchronizuje część stanu z sesją Django, a skrypt w `<head>` przywraca filtry przed pierwszym renderem. Nie jest to więc wyłącznie mechanizm „ostatniego wyszukiwania”.

Rekomendowane uproszczenie:

- stan filtrów i nawigacji przechowywać jawnie w parametrach URL;
- wynik strony renderować z tych parametrów w Django;
- usunąć ukryte przywracanie filtrów z `localStorage` dopiero po zinwentaryzowaniu `PagePrefs`, skryptu w `<head>`, patchowania linków w sidebarze i synchronizacji sesji;
- ewentualnie zachować tylko jeden prosty parametr widoku, jeśli jest uzasadniony UX-em.

Migracja nie może polegać na samym usunięciu `localStorage`: trzeba zachować linki zakładek, przycisk Wstecz, przejście z pulpitu do list oraz poprawne domyślne filtry.

Zysk:

- URL jest źródłem prawdy;
- linki można kopiować i udostępniać;
- przycisk Wstecz działa naturalnie;
- brak niespodziewanych filtrów z poprzedniej wizyty.

### 5. Quick links i preferencje pulpitu — korekta audytu

Aktualny kod repozytorium nie zawiera obsługi zaznaczania `.tw-quick-link-circle`, zapisu ukończenia quick links w `localStorage` ani wyliczania postępu. Pulpit renderuje zwykłą listę, a etykieta postępu pozostaje `0/{{ total }}`. Ten fragment wcześniejszego audytu był nieaktualny i nie powinien być osobnym zadaniem migracyjnym.

Rzeczywiście istniejące preferencje wymagające osobnej oceny to:

- kolejność kafelków pulpitu zapisywana przez `sortable-list.js` w `dashboardLayout-<user id>`;
- administracyjne przeciąganie quick links w `home/templates/home/site_admin.html`, które zapisuje kolejność na serwerze przez POST.

Ich usunięcie lub zastąpienie formularzami wymaga osobnej decyzji UX. Nie należy mylić tych dwóch mechanizmów z nieistniejącym lokalnym postępem quick links.

### 6. Responsywne pomiary DOM

Globalna część `app.js` używa `ResizeObserver`, `getBoundingClientRect()` i pomiarów szerokości do etapowego zwijania toolbarów i sidebaru.

Można zastąpić ją prostszym CSS:

- `flex-wrap`;
- media queries;
- krótsze etykiety na mobile;
- stałe ukrywanie drugorzędnych elementów.

Może to wymagać niewielkiego kompromisu wizualnego, ale usunie kod zależny od pomiarów DOM. Obecny kod obsługuje nie tylko zawijanie toolbara, lecz także etapowe ukrywanie kontrolek i automatyczne zwijanie sidebaru przez `tw-auto-collapsed`; migracja CSS musi zachować te stany albo świadomie je uprościć.

## Kandydaci do zastąpienia formularzami Django

W poniższych propozycjach zwykły redirect pozostaje podstawowym i działającym wariantem. Po pozytywnym pilotażu można użyć formularzy HTMX zwracających te same partiale Django, aby zachować natychmiastową aktualizację i ergonomię bez ręcznego `fetch()`.

### 1. Aktywność: przeczytane, nieprzeczytane i bookmarki

Strona aktywności używa `window.apiFetch()` (wspólnej warstwy opartej na `fetch()`) do:

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

Usunięcie Sortable.js i modalowego CRUD-u zmniejszyłoby powierzchnię frontendu, ale nie wystarczy samo usunięcie managera kategorii: `Sortable.min.js` i `sortable-list.js` obsługują również zmianę kolejności kafelków pulpitu. Bibliotekę można usunąć dopiero po podjęciu decyzji dla obu konsumentów i sprawdzeniu wszystkich użyć.

### 4. Sekcje profilu obywatela

`app.js` dociąga sekcje profilu przez AJAX i wstawia partiale do DOM.

Można użyć zwykłych linków:

```text
/obywatele/<id>/zadania/
/obywatele/<id>/czaty/
/obywatele/<id>/aktywnosc/
/obywatele/<id>/zalozono/
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

Nie należy bezwarunkowo ustawiać stałego `step="0.01"`: aktualny kod dobiera krok do precyzji wybranego aktywa, więc stały krok może odrzucić poprawne kwoty o większej liczbie miejsc po przecinku. Możliwe warianty to:

- wyrenderowanie precyzji już po stronie serwera, jeśli aktywo jest znane przed pierwszym renderem;
- przeładowanie formularza po zmianie aktywa;
- pozostawienie małej funkcji JS i traktowanie walidacji Django jako źródła prawdy.

To kandydat niskiego priorytetu, dopóki nie zostanie potwierdzony kontrakt precyzji aktywów.

### 9. Formularz wydarzenia — element nieaktualny

Aktualny `events/templates/events/event_form.html` nie zawiera inline JavaScriptu przełączającego pola częstotliwości. Pola dla wydarzeń miesięcznych są obecnie renderowane przez formularz Django. Ten punkt był nieaktualnym opisem wcześniejszego zachowania i należy go usunąć z kolejki migracji.

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

- transportu WebSocketowego czatu;
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

- [ ] **2.1** Dla pierwszego pilotażu porównać HTMX z istniejącym `window.apiFetch()` i natywnym HTML-em; dopiero po uzasadnieniu dodać HTMX jako zależność oraz ustalić sposób jego ładowania i wersjonowania. Obecnie HTMX nie jest zainstalowany.
- [ ] **2.2** Dla lokalnego stanu porównać Alpine.js z natywnym `<details>`, `<dialog>` i małym dedykowanym JS; dodać Alpine.js tylko wtedy, gdy zmniejszy złożoność pilotażu. Obecnie Alpine.js nie jest zainstalowany.
- [ ] **2.3** Jeśli pilotaż wybierze HTMX, przygotować standard odpowiedzi: partial, pełna strona, błędy walidacji, redirect i komunikaty.
- [ ] **2.4** Jeśli pilotaż wybierze HTMX/Alpine.js, przygotować standard atrybutów `hx-*`, eventów Alpine.js, identyfikatorów targetów i fallbacku bez JS.
- [ ] **2.5** Ustalić, że Django pozostaje źródłem prawdy dla danych, uprawnień, walidacji i renderowania.
- [ ] **2.6** Nie przenosić logiki domenowej do wyrażeń HTMX, Alpine.js ani kodu klienta.

### Faza 3 — migracja zwykłych funkcji aplikacji

- [ ] **3.1** Zacząć od jednego małego, rzeczywiście istniejącego pilotażu, np. oznaczania elementu aktywności jako przeczytanego albo prostego filtra GET; quick links nie są poprawnym kandydatem, bo opisany lokalny stan obecnie nie istnieje.
- [ ] **3.2** Przenieść akcje HTTP z ręcznego `fetch()` do zwykłych formularzy i odpowiedzi renderowanych przez Django; HTMX stosować dopiero po pozytywnym pilotażu, gdy daje realny zysk UX.
- [ ] **3.3** Przenieść modale, dropdowny, tabs i collapse do Alpine.js albo natywnego HTML, bez tworzenia kolejnego globalnego menedżera UI.
- [ ] **3.4** Przenieść filtrowanie, sortowanie i nawigację do parametrów URL oraz backendu; HTMX stosować tam, gdzie poprawia ergonomię.
- [ ] **3.5** Migrować etapami aktywność, profil obywatela, kalendarz, zadania, kategorie i księgowość.
- [ ] **3.6** Zachować animacje, stany ładowania, focus, responsywność i natychmiastową informację zwrotną tam, gdzie są ważne dla UX.
- [ ] **3.7** Po każdej migracji usunąć odpowiadający kod z `app.js` lub modułu domenowego, jeżeli nie ma już innych konsumentów.

### Faza 4 — stabilna wyspa czatu realtime

- [ ] **4.1** Zachować Django Channels jako backend komunikacji i Redis jako warstwę kanałów zgodnie z istniejącym kontraktem WebSocket.
- [ ] **4.2** Utrzymać dedykowanego klienta czatu dla transportu, reconnectu, rejoinu i obecności; nie wyklucza to użycia HTMX/Alpine.js w warstwie interfejsu.
- [ ] **4.3** Oddzielić kod transportu, stanu realtime, renderowania wiadomości oraz server-driven/local UI; nie dopuścić do dwóch źródeł prawdy dla tego samego stanu.
- [ ] **4.4** Zdefiniować publiczny kontrakt zdarzeń czatu, aby przyszłe funkcje nie powiększały globalnego `app.js`.
- [ ] **4.5** Rozwijać funkcje czatu — reakcje, odpowiedzi, edycję, załączniki, obecność i powiadomienia — w ramach tej izolowanej wyspy.
- [ ] **4.6** Nie traktować fallbacku HTTP jako istniejącej funkcji; jego zaprojektowanie i ewentualną implementację dla historii, wysyłania wiadomości oraz podstawowych operacji zaplanować w Fazie 7. Nie może to naruszyć kontraktu WebSocket ani stać się warunkiem migracji całego UI.
- [ ] **4.7** Pokryć reconnect, wielokrotne karty, opóźnienia i ponowne dołączanie testami regresji; wykorzystać istniejące testy Jest i nie rozszerzać zakresu na E2E bez potrzeby.

### Faza 5 — ergonomia, atrakcyjność i dostępność

- [ ] **5.1** Nie traktować redukcji JS jako celu ważniejszego niż czytelność, szybkość reakcji i wygoda użytkownika.
- [ ] **5.2** Dodać wspólne stany wybranego rozwiązania (HTML/HTMX/Alpine.js): ładowanie, sukces, błąd, disabled, focus i aktualizację optymistyczną tylko tam, gdzie jest bezpieczna.
- [ ] **5.3** Utrzymać spójne animacje, przejścia, modale, dropdowny i responsywność w ramach istniejących standardów `tw-*`.
- [ ] **5.4** Sprawdzać klawiaturę, czytniki ekranu, focus, mobile i działanie bez JS dla każdej migrowanej funkcji.
- [ ] **5.5** Dokumentować świadome wyjątki, w których własny JS pozostaje, ponieważ daje istotną wartość UX.

### Faza 6 — usunięcie starej infrastruktury i utrzymanie kierunku

- [ ] **6.1** Ograniczyć globalne skrypty ładowane w `home/templates/home/base.html` do rzeczywiście wspólnych funkcji.
- [ ] **6.2** Usunąć duplikaty modali, dropdownów, collapse, AJAX helpers i obsługi formularzy.
- [ ] **6.3** Zmniejszyć `home/static/home/js/app.js` bez przenoszenia jego odpowiedzialności do innego monolitycznego pliku.
- [ ] **6.4** Usunąć nieużywane zależności i moduły dopiero po sprawdzeniu wszystkich konsumentów.
- [ ] **6.5** Dodać do code review pytanie: czy nowa funkcja może być Django + HTMX, Alpine.js lub HTML/CSS, zanim powstanie własny JS?
- [ ] **6.6** Utrzymywać czat jako osobną wyspę odpowiedzialności i nie rozbudowywać wspólnej warstwy UI kosztem jego potrzeb; jednocześnie dopuszczać HTMX/Alpine.js tam, gdzie upraszczają nietransportowe fragmenty czatu.

### Faza 7 — hybrydowy interfejs czatu: Channels + dedykowany JS + HTMX/Alpine.js

HTMX i Alpine.js mogą być użyte również w czacie. Ich rolą nie jest zastąpienie WebSocketu, lecz ograniczenie własnego kodu interfejsu tam, gdzie czat korzysta ze zwykłego HTTP albo lokalnego stanu komponentu.

- [ ] **7.1** Zachować `websocket-manager.js`, `wsapi.js`, reconnect, rejoin, routing zdarzeń realtime, obecność i synchronizację odczytu w dedykowanym kliencie czatu.
- [ ] **7.2** Zinwentaryzować fragmenty czatu możliwe do renderowania przez Django: lista pokojów, początkowa historia, tworzenie/edycja ustawień pokoju, formularze, stany błędów i uprawnień oraz ewentualny fallback po utracie WebSocketu.
- [ ] **7.3** Użyć HTMX dla wybranych operacji HTTP i wymiany partiali tylko wtedy, gdy endpoint ma jasny kontrakt HTML, CSRF, uprawnienia, pełnostronicowy fallback i bezpieczne zachowanie po wielokrotnym żądaniu.
- [ ] **7.4** Użyć Alpine.js dla lokalnego stanu UI, np. widoku lista/pokój na mobile, otwierania paneli, modali, dropdownów, formularza odpowiedzi/edycji i stanów ładowania; Alpine nie może stać się drugim magazynem wiadomości ani stanów WebSocketu.
- [ ] **7.5** Zdefiniować most między HTMX/Alpine.js a klientem WebSocket: nazwy zdarzeń, cykl życia po podmianie fragmentu, idempotentną inicjalizację i jednego właściciela każdego fragmentu stanu. Nie dodawać tej integracji do globalnego `app.js`.
- [ ] **7.6** Zacząć od jednego niekrytycznego pilotażu, np. tworzenia pokoju, listy pokojów albo widoku pustego/stanu błędu; nie zaczynać od transportu wiadomości ani reconnectu.
- [ ] **7.7** Zachować zwykły fallback HTML dla pilotażu oraz sprawdzić CSRF, uprawnienia, anonimowość, wielokrotne karty, reconnect i zachowanie po częściowej awarii WebSocketu.
- [ ] **7.8** Mierzyć efekt osobno dla kodu czatu: usunięte handlery i odpowiedzialności, rozmiar klienta realtime, liczbę źródeł stanu oraz regresje UX. Nie uznawać samego przeniesienia kodu do templatek za redukcję.
- [ ] **7.9** Nie migrować mechanicznie uploadów, rich text, push notifications ani obsługi reconnectu; pozostawić je w dedykowanych modułach, chyba że powstanie osobna decyzja i test charakterystyki.

## Kryteria akceptacji dla kolejnych zmian

Każdy etap redukcji powinien mieć:

- listę usuwanych funkcji i ich obecnych konsumentów;
- test charakterystyki zachowania przed zmianą, jeśli funkcja jest istotna;
- działający wariant HTML/formularzowy dla funkcji HTTP/UI albo świadomą decyzję o usunięciu; dla czatu realtime — sprawdzony kontrakt WebSocket i osobną decyzję, czy fallback HTTP jest wymagany;
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
- `docs/PLAN_REFAKTOR_ARCHITEKTURY.md` — granice aplikacji i odpowiedzialności backendu;
- `docs/UI_DEVELOPMENT_GUIDE.md` — zasady wspólnych komponentów UI;
- `docs/UI_STANDARDS.html` — referencja wizualna;
- `home/templates/home/base.html` — globalne ładowanie JavaScriptu;
- `home/static/home/js/app.js` — główne skupisko wspólnego JavaScriptu;
- `chat/static/chat/js/chat.js` — routing i stan czatu;
- `chat/static/chat/js/push-notifications.js` — FCM i Service Worker.

## Rekomendacja końcowa

Rekomendowany kierunek architektoniczny to **Django jako źródło prawdy + server-driven UI + ewentualnie HTMX/Alpine.js + Django Channels**. HTMX i Alpine.js są kandydatami do pilotażu, nie aktualnymi zależnościami ani obowiązkowymi dodatkami. Dla prostych przypadków natywny HTML (`<form>`, `<details>`, `<dialog>`, linki GET) powinien mieć pierwszeństwo przed dokładaniem biblioteki.

Nie należy usuwać JavaScriptu mechanicznie ani przenosić do Pythona interakcji, które są z natury klienckie. Największy i najbezpieczniejszy efekt da:

1. przeniesienie zwykłych akcji HTTP do formularzy HTML lub — po pozytywnym pilotażu — HTMX i renderowanych przez Django partiali;
2. przeniesienie lokalnego stanu UI do natywnego HTML-u, małego dedykowanego JS albo Alpine.js tylko wtedy, gdy zmniejsza to złożoność;
3. usunięcie własnej globalnej infrastruktury UI z `app.js` bez tworzenia drugiego monolitycznego pliku;
4. pozostawienie dedykowanego JavaScriptu dla transportu czatu, push, rich text, uploadów i innych świadomych wyjątków, przy jednoczesnym użyciu HTMX/Alpine.js w wybranych fragmentach interfejsu czatu;
5. zachowanie animacji, responsywności, dostępności i natychmiastowej informacji zwrotnej tam, gdzie poprawiają ergonomię;
6. rozwijanie czatu jako hybrydowej wyspy opartej na Channels: dedykowany JS dla realtime oraz HTMX/Alpine.js dla wybranych operacji HTTP i lokalnego stanu UI.

Docelowo aplikacja ma być server-driven, ale nie pozbawiona atrakcyjności. JavaScript nie znika — przestaje być obowiązkiem każdej części aplikacji i pozostaje skoncentrowany tam, gdzie daje użytkownikowi realną wartość.
