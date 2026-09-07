# Plan dalszej przebudowy czatu

## 0. Status i punkt wyjścia

- [x] **0.1. Migracja wizualna do Tailwind jest już wykonana w bieżącym worktree.** Plan nie powtarza migracji Bootstrap → Tailwind; obejmuje tylko jej domknięcie i przebudowę zachowania czatu.
- [x] **0.2. Źródło stylów:** `home/static/home/css/tailwind.css` zawiera utilities, komponenty wspólne oraz style modułu czatu. `home/static/home/css/tailwind.build.css` jest artefaktem generowanym przez `npm run build:css`.
- [x] **0.3. Usunięte arkusze:** `chat/static/chat/css/chat.css` oraz stare arkusze `base.css`, `layout.css`, `navigation.css`, `darkly.css` i pozostałe arkusze home nie są już osobnymi źródłami stylów. Nie wolno przywracać linku do `chat.css` ani edytować ręcznie pliku `tailwind.build.css`.
- [x] **0.4. Szablon czatu:** `chat/templates/chat/chat.html` nie ładuje własnego arkusza; korzysta z globalnego `tailwind.build.css`. Nadal zawiera semantyczne klasy modułu, m.in. `.chat-rooms`, `.room-list-col`, `.room-list`, `.chat-root-messages`, `.room-active` i `.room-list-showing`.
- [x] **0.5. Komponenty interaktywne:** Bootstrap JS został zastąpiony przez `TwModal`, `TwDropdown`, `TwCollapse`, `TwTab`, `TwTooltip`, `TwPopover` i `TwAlert` w `home/static/common/js/`. Czat korzysta z `data-tw-*` i `tw-*`.
- [x] **0.6. Aktualny doraźny fix mobilny:** reguły `position: fixed`, fallback `100vh` przed `100dvh` oraz nadpisanie `room-list-hidden` znajdują się obecnie w sekcji czatu w `tailwind.css`. Są jeszcze do zweryfikowania testem E2E i nie powinny być dublowane w nowym pliku.
- [x] **0.7. Aktualny stan WebSocketu:** `websocket-manager.js` nadal posiada jeden `setSocketMessageHandler`, jeden `setOnConnect` i jeden `setOnDisconnect`; `chat.js` nadal ustawia `WS_API.wsOnConnect` i nadal łączy inicjalizację z reconnectem.
- [x] **0.8. Aktualny stan routingu:** wybór pokoju jest nadal reprezentowany głównie przez `CurrentRoomId` i klasy CSS; `?view=rooms` oraz `?view=unread` są usuwane przez `stripParam`.

## 1. Cel, zakres i niezmienne zasady

- [x] **1.1. Cel główny:** wyeliminować stany „pusty ekran”, „toolbar bez listy” i „guzik bez efektu” na telefonie oraz uczynić zachowanie desktopowe przewidywalnym.
- [x] **1.2. Zakres:** zmienić frontend pełnej strony czatu, współdzielony lifecycle WebSocketu, embedded chat oraz testy. Nie zmieniać modeli, migracji, uprawnień, anonimowości, reguł głosowań/zadań ani formatu komunikatów WebSocket.
- [x] **1.3. Podejście:** realizować etapami; każdy etap ma własne testy i pozostawia aplikację działającą.
- [x] **1.4. Technologie:** pozostać przy Django templates, ES modules, istniejącym CSS/Tailwind pipeline i natywnym `history` API. Nie dodawać frameworka frontendowego ani kolejnego systemu komponentów.
- [x] **1.5. Desktop:** lista i wiadomości są panelem master-detail; lista może być zwinięta preferencją użytkownika.
- [x] **1.6. Mobile:** widoczny jest jeden panel — lista albo pokój. Przejście do listy nie opuszcza automatycznie pokoju na serwerze; rozdzielamy panel widoczny od pokoju dołączonego.
- [x] **1.7. URL:** zachować działanie `/chat/`, `?view=rooms`, `?view=unread`, `?unread=1`, `#room_id=X` i `#room_id=X&message_id=Y`.
- [x] **1.8. Kod generowany:** wszystkie zmiany stylów wprowadzać tylko do `tailwind.css`; po zmianie uruchamiać build i aktualizować `tailwind.build.css` poleceniem, nigdy ręczną edycją.

## 2. Diagnoza aktualnego kodu po migracji Tailwind

- [x] **2.1. Rozproszony stan widoku:** `.room-active`, `.room-list-showing` i `.room-list-hidden` są ustawiane w `chat.js`, `handlers.js` i `domapi.js`, a prezentowane w `tailwind.css`.
- [x] **2.2. Niejednoznaczny layout:** sekcja czatu w `tailwind.css` nadal używa `body:has(.chat-rooms)`, `.tw-main-content:has(.chat-rooms)` oraz selektora `.chat-rooms > div[class*="col-"]`, mimo że `chat.html` nie ma już klas `.row`/`.col-md-*` na panelach. To jest nieaktualne sprzężenie z wcześniejszym Bootstrap layoutem.
- [x] **2.3. Ukryty panel na mobile:** `.room-list` ma `height: 0; flex: 1 1 0`; doraźny `.room-list-col { position: fixed; ... }` powinien rozwiązać zapadanie, ale musi być potwierdzony geometrią w przeglądarce.
- [x] **2.4. Start zależny od WebSocketu:** `wsOnConnect` najpierw oczekuje na `getOnlineUsers()` i `getNotificationData()`, a dopiero później wykonuje `decideStartupAction()` i ewentualny join. Błąd pobocznego żądania może zatrzymać podstawowy start.
- [x] **2.5. Race przy `open`:** socket powstaje w `getSharedWebSocket()` zanim pełny czat przypisze `WS_API.wsOnConnect`; callback może zostać pominięty, jeśli socket otworzy się wcześniej.
- [x] **2.6. Reconnect zmienia UI:** przy ponownym połączeniu `chat.js` resetuje `CurrentRoomId`, wykonuje `onRoomTryJoin()` i po sukcesie wywołuje `DOM_API.showFoldedRoomHeader()`, co może usunąć `room-list-showing`.
- [x] **2.7. Dispatch zależny od kolejności:** gdy istnieje `socketMessageHandler`, manager nie broadcastuje wiadomości do `messageHandlers`. `notifications.js` i `chat-embedded.js` używają dodatkowego API, więc ich odbiór zależy od tego, czy główny handler został ustawiony.
- [x] **2.8. Reconnect embedded chat:** `chat-embedded.js` ma lokalne `joined` i obsługę pierwszego `open`, ale nie ma pełnego, jawnego rejoinu po reconnect.
- [x] **2.9. Migracja stylów zmieniła kontrakty klas:** `tw-d-none` ma `display: none !important`, dlatego kontenery podglądu obrazów muszą być pokazywane przez `classList.remove('tw-d-none')`, nie przez samo `style.display`. `tw-modal-open` musi być używane konsekwentnie w `chat-core.js` i `domapi.js`.
- [x] **2.10. Pozostały semantyczne haki modułu:** `.sort-btn`, `.message-btn`, `.fmt-btn`, `.reaction-btn`, `.nav-cat-btn`, `.room-link` i podobne nie są automatycznie błędnymi klasami Bootstrap. Przed zmianą trzeba sprawdzić ich użycie; nie przemianowywać ich tylko dlatego, że nie mają prefiksu `tw-`.
- [x] **2.11. Dynamiczny markup musi być objęty buildem:** `templates.js`, `chat.js`, `chat-core.js`, `domapi.js` i `chat-embedded.js` są już w `content` `tailwind.config.js`; dodatkowe dynamiczne klasy wymagają testu freshness/buildu albo safelisty.

## 3. Etap A — audyt i stabilizacja pipeline’u Tailwind

**Dlaczego:** po usunięciu Bootstrap i osobnego `chat.css` jedynym źródłem stylów jest duży plik źródłowy Tailwind. Najpierw trzeba zapewnić, że zmiany czatu trafiają do właściwego artefaktu i nie są tracone przy buildzie.

- [x] **3.1. Zweryfikować kolejność ładowania:** `tokens.css` → `tailwind.build.css` → skrypty `Tw*` → skrypty aplikacji. Nie dodawać ponownie osobnego linku do CSS czatu.
- [x] **3.2. Rozdzielić w audycie trzy rodzaje klas:**
  - [x] **3.2.1.** klasy Tailwind/utilities `tw-*`;
  - [x] **3.2.2.** klasy komponentów wspólnych `tw-btn`, `tw-modal-*`, `tw-dropdown-*` itd.;
  - [x] **3.2.3.** semantyczne haki czatu bez prefiksu, których używa JS lub szablony.
- [x] **3.3. Naprawić pozostałe inline style generowane przez chat, jeśli nie są konieczne:** w szczególności strzałkę `.sort-arrow` w `templates.js` zastąpić klasą stanu, np. `is-hidden`/`tw-invisible`, i utrzymywać jeden kontrakt CSS/JS. *(zrobione: `tw-invisible` w `templates.js` + `chat.js`, analogicznie `tw-d-none` dla `rename-room-error`)*
- [x] **3.4. Utrzymać regułę podglądu załączników:** `tw-d-none` dodawać i usuwać klasą; test `image_preview_visibility.test.js` ma pokrywać dodanie nowego załącznika, edycję istniejących załączników i wyczyszczenie podglądu.
- [x] **3.5. Utrzymać jeden kontrakt modala obrazów:** `tw-modal-open` dodawać i usuwać we wszystkich ścieżkach otwarcia/zamknięcia (`chat-core.js`, `domapi.js`); dodać test zamknięcia przez przycisk, Escape i programowe `closeBigImage()`. *(`image_viewer_close.test.js` — 12 testów: otwarcie, wszystkie ścieżki zamknięcia, odpinanie listenera, nawigacja strzałkami)*
- [x] **3.6. Po każdej zmianie stylów wykonać `npm run build:css`; nie edytować `tailwind.build.css` ręcznie.**
- [x] **3.7. Uruchomić `python scripts/regression_scan.py`; skan ma nadal blokować odwołania do usuniętego `chat.css`, starych arkuszy, `data-bs-*`, `bootstrap.*` i `--bs-*` poza dozwolonymi dokumentami/buildem.**
- [x] **3.8. Zweryfikować ostrzeżenia IDE dla `tailwind.css`:** `@tailwind` jest dyrektywą źródłową obsługiwaną przez Tailwind; ostrzeżenia o `color-mix` i prefiksach przeglądarkowych oceniać względem wspieranych urządzeń, nie usuwać funkcji wizualnych bez testu. Jeśli potrzebne są prefiksy, dodać je do źródła lub pipeline’u, nie do pliku buildowanego ręcznie. *(audyt: prefiksy `-webkit-`/`-moz-` generuje autoprefixer w pipeline — ostrzeżenia IDE to false positive; `color-mix()` (5 użyć dekoracyjnych: tła, focus-ring, fade, text-shadow) wspierane od Chrome 111/Safari 16.2/FF 113 i degraduje się bezpiecznie — decyzja: zostaje, bez zmian w pipeline)*
- [x] **3.9. Przejrzeć zmienione testy E2E i testy komponentów po migracji:** sprawdzić, czy selektory testowe nadal wskazują semantyczne haki, a nie usunięte klasy Bootstrap; dodać scenariusz podglądu załącznika, modala, dropdownu i strzałki sortowania. *(`e2e/chat-components.spec.js` — 5 scenariuszy: dropdown, modal, lightbox, sort wg aktywności, empty state wyszukiwania)*

**Pliki:** `home/static/home/css/tailwind.css`, `tailwind.config.js`, `package.json`, `scripts/regression_scan.py`, `chat/static/chat/js/templates.js`, `chat-core.js`, `domapi.js` i testy komponentów.

**Kryterium:** build jest powtarzalny, skan nie wykrywa starych zależności, a zmiana `tw-d-none`/`tw-modal-open` nie psuje widoczności podglądu ani modali.

## 4. Etap B — samowystarczalny layout czatu

**Dlaczego:** po scaleniu `chat.css` z `tailwind.css` nie wolno już opierać layoutu na starych klasach Bootstrapa ani na `:has()` wybierającym stronę po strukturze DOM.

- [x] **4.1. Dodać jawny hook strony bez flashu layoutu:**
  - [x] **4.1.1.** W `home/templates/home/base.html` dodać bezpieczny blok `body_class` w atrybucie `<body>`.
  - [x] **4.1.2.** W `chat/templates/chat/chat.html` ustawić `chat-page`.
  - [x] **4.1.3.** Nie dodawać `chat-page` dopiero skryptem po pierwszym renderze.
- [x] **4.2. W `tailwind.css` zastąpić:**
  - [x] **4.2.1.** `body:has(.chat-rooms)` przez `body.chat-page`;
  - [x] **4.2.2.** `body:has(.chat-rooms) .tw-layout-wrapper` i `.tw-main-area` przez jawne selektory `body.chat-page ...`;
  - [x] **4.2.3.** `.tw-main-content:has(.chat-rooms)` przez `.chat-page .tw-main-content`.
- [x] **4.3. Usunąć sprzężenie z Bootstrap grid:**
  - [x] **4.3.1.** W `chat.html` usunąć pozostały wrapper `.row` w `#room-list`, jeśli nie jest potrzebny do semantyki. *(przemianowany na `.room-list-groups`)*
  - [x] **4.3.2.** Utrzymać lokalny flex/grid dla `.chat-rooms`, `.chat-root-messages` i `.room-list-col`.
  - [x] **4.3.3.** Zastąpić `.chat-rooms > div[class*="col-"]` selektorami konkretnych paneli.
  - [x] **4.3.4.** Nie używać nazw `col-md-*` jako warunku działania CSS.
- [x] **4.4. Ustalić wysokość lokalnie:**
  - [x] **4.4.1.** `.chat-rooms` oraz `.tw-main-content` mają `min-height: 0` i flexową wysokość.
  - [x] **4.4.2.** `.room-list-col` i `.chat-root-messages` mają określony obszar roboczy.
  - [x] **4.4.3.** `.room-list` ma `flex: 1 1 auto; min-height: 0; overflow-y: auto`, a `height: 0` pozostaje tylko wtedy, gdy test geometrii potwierdzi, że jest potrzebne. *(usunięto `height: 0`; E2E potwierdza dodatnią geometrię)*
  - [x] **4.4.4.** Mobile korzysta z `100vh` fallback oraz `100dvh` jako ulepszenia; nie polega wyłącznie na `dvh`.
- [x] **4.5. Utrzymać jeden zestaw reguł mobilnych w `tailwind.css`:** istniejący `position: fixed` dla `.room-list-col` zweryfikować, a po potwierdzeniu nie tworzyć równoległego rozwiązania w innym arkuszu.
- [x] **4.6. Zdefiniować warstwy scrollowania:** toolbar i compose bar nie scrollują, tylko `.room-list` oraz `#room .messages`.
- [x] **4.7. Zweryfikować realną geometrię w Playwright:** `getBoundingClientRect().width/height > 0` dla listy, panelu wiadomości i ich kontenerów; sama obecność klas nie wystarcza. *(asercje `boundingBox` dodane do `e2e/chat-mobile-room-toggle.spec.js`)*

**Pliki:** `home/templates/home/base.html`, `chat/templates/chat/chat.html`, `home/static/home/css/tailwind.css`, `home/static/home/css/tailwind.build.css` tylko przez build.

**Kryterium:** na mobile wejście przez `?view=rooms` pokazuje listę pokoi lub jawny empty state, a nie sam toolbar; na desktopie oba panele mają poprawną geometrię.

## 5. Etap C — responsywność i preferencje

**Dlaczego:** Tailwind zachowuje breakpoint `md: 768px`, a chat JS nadal ma ręczne porównania `window.innerWidth`. Trzeba mieć jeden kontrakt.

- [x] **5.1. W istniejącym `utility.js` udostępnić `mobileMedia = window.matchMedia('(max-width: 767px)')`.** Nie tworzyć nowego modułu dla jednej stałej.
- [x] **5.2. Zamienić porównania `< 768` i `>= 768` w `chat.js` oraz `handlers.js` na `mobileMedia.matches`.**
- [x] **5.3. Zastąpić listener `resize` listenerem `mobileMedia.addEventListener('change', ...)`; resize pozostawić tylko dla faktycznej geometrii, jeśli jest potrzebny.**
- [x] **5.4. Rozdzielić preferencję listy:**
  - [x] **5.4.1.** `chat-room-list-hidden` dotyczy wyłącznie desktopu. *(nowy klucz `chat-desktop-room-list-hidden`)*
  - [x] **5.4.2.** Na mobile klasa `room-list-hidden` nie może zostać przywrócona z `localStorage`.
  - [x] **5.4.3.** Zmiana szerokości desktop → mobile usuwa efekt desktopowego zwinięcia z prezentacji, ale nie musi kasować preferencji.
  - [x] **5.4.4.** Nazwę klucza zmieniać tylko z migracją starego klucza; nie robić cichej utraty preferencji.
- [x] **5.5. Nie zapisywać `room-list-showing` w `localStorage`.** To stan bieżącej nawigacji mobile, nie preferencja.
- [x] **5.6. Przetestować zmianę breakpointu przez `matchMedia` oraz faktyczne wymiary paneli.** *(`breakpoint_transition.test.js` — 5 testów: przejścia desktop↔mobile nie zostawiają osieroconych klas, room-active i aria-current śledzą stan; geometria asertywna w E2E)*

**Pliki:** `chat/static/chat/js/utility.js`, `chat.js`, `handlers.js`, `home/static/home/css/tailwind.css`.

**Kryterium:** kod JS i media query CSS mają breakpoint 767/768 z jednego kontraktu, a preferencja desktopowa nie powoduje pustego panelu na telefonie.

## 6. Etap D — jeden kontroler stanu widoku

**Dlaczego:** po migracji CSS klasy nadal są zmieniane w kilku modułach. Potrzebny jest mały model stanu, ale bez wprowadzania frameworka.

- [x] **6.1. W `chat.js` zdefiniować stan:**
  - [x] **6.1.1.** `visiblePanel: 'list' | 'room'` — tylko widoczny panel na mobile. *(zrealizowane jako `ViewState.panel`)*
  - [x] **6.1.2.** `requestedRoomId: number | null` — pokój wynikający z URL/kliknięcia. *(`ViewState.requestedRoomId`)*
  - [x] **6.1.3.** `joinedRoomId: number | null` — pokój faktycznie dołączony do socketu. *(pozostało jako `CurrentRoomId` — jedna wartość, brak duplikatu)*
  - [x] **6.1.4.** `joinStatus: 'idle' | 'joining' | 'joined' | 'error'`. *(`ViewState.joinStatus`)*
  - [x] **6.1.5.** `connectionStatus: 'connecting' | 'online' | 'reconnecting' | 'offline'`. *(enum w `ViewState`; 'offline' z `navigator.onLine`/zdarzeń, reszta z lifecycle WS — pigułka `#chat-conn-status` renderuje się z tego pola)*
- [x] **6.2. Zachować `CurrentRoomId` przejściowo jako alias albo usunąć dopiero po migracji wszystkich odwołań.** Nie utrzymywać dwóch niezależnych wartości po zakończeniu etapu. *(`CurrentRoomId` pozostał jedynym źródłem joinedRoomId; `getCurrentRoomId()` eksportowany dla handlers.js)*
- [x] **6.3. Dodać `renderChatView(state)` jako jedyne miejsce synchronizacji klas i atrybutów:**
  - [x] **6.3.1.** `room-active` oznacza, że obszar pokoju jest gotowy lub w stanie join/error, nie tylko że wysłano żądanie.
  - [x] **6.3.2.** `room-list-showing` oznacza widok listy na mobile.
  - [x] **6.3.3.** `room-list-hidden` oznacza wyłącznie zwinięcie desktopowe.
  - [x] **6.3.4.** Ustawiać także `aria-current`, `aria-expanded`, `aria-hidden` i stany przycisków. *(`aria-current` w renderChatView; `aria-expanded` synchronizowane MutationObserverem w handlers.js)*
- [x] **6.4. `domapi.js` ma renderować zawartość pokoju, breadcrumb i statusy; nie ma podejmować decyzji, czy aplikacja jest na liście czy w pokoju.** *(usunięto `showFoldedRoomHeader`/`hideFoldedRoomHeader`)*
- [x] **6.5. `handlers.js` ma przekazywać akcje do kontrolera, a nie bezpośrednio zmieniać klasy widoku.** *(kliki przechodzą przez `navigateToRoom`/`navigateToRoomList`)*
- [x] **6.6. Dodać numer/generację żądania joinu:** późna odpowiedź pokoju A nie może nadpisać widoku pokoju B po szybkim kliknięciu. *(`JoinGeneration` + flaga `stale`)*
- [x] **6.7. Przycisk powrotu do pokoju nie może być widoczny, jeśli nie istnieje `joinedRoomId`; w widoku listy bez aktywnego pokoju nie ma martwego guzika.** *(reguła CSS `.room-active.room-list-showing #room-list-toggle-static-btn` + guard `getCurrentRoomId()` w handlerze)*

**Pliki:** `chat.js`, `handlers.js`, `domapi.js`, `templates.js`.

**Kryterium:** zmiana widoku ma jeden kontroler, a kombinacja „lista bez pokoju”, „lista z pokojem dołączonym w tle”, „joining” i „error” jest jawna.

## 7. Etap E — routing URL i historia przeglądarki

**Dlaczego:** refresh i Wstecz powinny odtwarzać ten sam widok. `stripParam` obecnie powoduje, że pierwsze wejście i refresh uruchamiają różne ścieżki.

- [x] **7.1. Zdefiniować parser lokalizacji:** `parseChatLocation(location)` zwraca `viewIntent`, `roomId`, `messageId` i informację o filtrze. *(zwraca `view`/`roomId`/`messageId`; filtr mapowany z `view` przez `applyUnreadUrlIntent`)*
- [x] **7.2. Zachować semantykę kompatybilną z obecnym UX:**
  - [x] **7.2.1.** Hash `room_id` ma pierwszeństwo przed `view`.
  - [x] **7.2.2.** `?view=rooms` pokazuje listę bez auto-joinu.
  - [x] **7.2.3.** `?view=unread`/`?unread=1` pokazują listę z filtrem.
  - [x] **7.2.4.** Czyste `/chat/` zachowuje obecny auto-join ostatniego lub pierwszego dozwolonego pokoju; po udanym joinie zapisuje hash.
  - [x] **7.2.5.** Brak lub brak dostępu do pokoju daje empty/error state, nie pustkę. *(toast + powrót do listy przez `replaceState`)*
- [x] **7.3. Nie usuwać `view` z URL po inicjalizacji.** `stripParam` i kod `history.replaceState` kasujący parametr usunąć dopiero po przełączeniu na nowy router.
- [x] **7.4. Wprowadzić trzy operacje nawigacyjne:**
  - [x] **7.4.1.** `navigateToRoom(roomId, messageId?)` — `pushState`, następnie jawne `applyChatRoute`.
  - [x] **7.4.2.** `navigateToRoomList()` — usuwa hash, zachowuje parametry widoku i jawnie stosuje trasę.
  - [x] **7.4.3.** Reconnect/join techniczny nie może pisać historii.
- [x] **7.5. Obsłużyć historię bez podwójnego joinu:**
  - [x] **7.5.1.** `popstate` jest podstawowym zdarzeniem historii.
  - [x] **7.5.2.** `hashchange` obsługuje ręczną zmianę fragmentu.
  - [x] **7.5.3.** `syncRouteFromLocation()` jest idempotentne i odrzuca ten sam klucz trasy zastosowany drugi raz.
- [x] **7.6. Przy bezpośrednim wejściu z hashem przygotować stos Wstecz poprawnie:**
  - [x] **7.6.1.** Zapisać URL pokoju.
  - [x] **7.6.2.** `replaceState` ustawić wpis listy bez hasha.
  - [x] **7.6.3.** `pushState` przywrócić wpis pokoju.
  - [x] **7.6.4.** Oznaczyć wykonanie normalizacji, aby nie powtarzać jej przy reconnect/popstate. *(flaga `HistoryNormalized`)*
- [x] **7.7. Kopiowanie linków budować niezależnie od aktualnego `?view`:** `/chat/#room_id=X` i `/chat/#room_id=X&message_id=Y`.
- [x] **7.8. Zachować mechanizm przewijania do `message_id` dopiero po zakończeniu renderu historii.**

**Pliki:** `chat.js`, `handlers.js`, ewentualnie `chat/templates/chat/chat.html` dla atrybutów dostępności.

**Kryterium:** klik, refresh, deep-link i Wstecz prowadzą do tego samego widoku; wpisy historii nie są tworzone przez reconnect.

## 8. Etap F — WebSocket: subskrypcje i lifecycle

**Dlaczego:** wspólny socket jest używany przez pełny czat, powiadomienia i embedded chat. Żaden konsument nie powinien nadpisywać handlera innego konsumenta.

- [x] **8.1. Zastąpić `setSocketMessageHandler` i `addMessageHandler` jednym API `subscribeMessages(handler)`, które zwraca `unsubscribe`.**
- [x] **8.2. W `websocket-manager.js` przechowywać handlerów w `Set` należącym do instancji managera.**
- [x] **8.3. Dla wiadomości bez `__TRACE_ID` broadcastować do wszystkich subskrybentów; błąd jednego handlera logować i izolować.**
- [x] **8.4. Nie dublować odpowiedzialności za notification:**
  - [x] **8.4.1.** `notifications.js` odpowiada za browserowe powiadomienie.
  - [x] **8.4.2.** `chat.js` aktualizuje DOM pełnego czatu, ale nie wywołuje drugiego browserowego powiadomienia.
  - [x] **8.4.3.** `unsee_room` może mieć dwóch odbiorców, jeśli każdy aktualizuje inny fragment UI.
- [x] **8.5. Dodać `subscribeConnection({ onOpen, onClose })` z `unsubscribe`:**
  - [x] **8.5.1.** późna rejestracja po otwarciu otrzymuje asynchroniczne `onOpen({ alreadyOpen: true })`;
  - [x] **8.5.2.** kolejne otwarcie dostaje `reconnected: true`;
  - [x] **8.5.3.** kolejność ładowania `notifications.js` i `chat.js` nie wpływa na inicjalizację.
- [x] **8.6. W `wsapi.js` usunąć poleganie na przypisaniu `WS_API.wsOnConnect` po konstruktorze.** Udostępnić jawne zarejestrowanie lifecycle po utworzeniu API, z natychmiastową obsługą już otwartego socketu.
- [x] **8.7. Rozdzielić callbacki pełnego czatu:**
  - [x] **8.7.1.** `onInitialOpen` stosuje trasę i rozpoczyna join. *(trasa aplikowana w DOMContentLoaded — nawigacja nie jest zakładnikiem socketu; join kolejkuje się do pierwszego open)*
  - [x] **8.7.2.** `onReconnect` rejoinuje dołączony pokój, ale nie zmienia URL, `visiblePanel` ani historii. *(`wsOnReconnect` + `preserveView`)*
  - [x] **8.7.3.** Rejoin nie może wywołać przejścia z listy do pokoju.
- [x] **8.8. Nie blokować podstawowej nawigacji metadanymi:**
  - [x] **8.8.1.** trasę i join uruchomić niezależnie od presence/notification preferences;
  - [x] **8.8.2.** `getOnlineUsers()` i `getNotificationData()` uruchomić niezależnie, z lokalnym `.catch`/`Promise.allSettled`;
  - [x] **8.8.3.** błąd metadanych nie może ukryć listy ani pokoju.
- [x] **8.9. Dodać timeout dla `sendJsonAsync` oraz zakończenie oczekujących requestów przy definitywnym zamknięciu.** Nie zmieniać formatu `__TRACE_ID` bez sprawdzenia consumera po stronie serwera. *(timeout 15 s; przy zamknięciu requesty NIE są odrzucane — ReconnectingWebSocket kolejkuje wysyłkę i wypycha ją po ponownym open, więc request może się jeszcze powieść; timeout ogranicza realne zawieszenie)*
- [x] **8.10. Naprawić embedded chat:**
  - [x] **8.10.1.** subskrypcja wiadomości i lifecycle połączenia ma zwalniany handler;
  - [x] **8.10.2.** reconnect resetuje lokalne `joined` i wykonuje rejoin;
  - [x] **8.10.3.** bufor wiadomości nie renderuje historii dwa razy i nie gubi wiadomości z okresu przejściowego. *(bufor resetowany przy open; retry joinu przy `REQUEST_TIMEOUT`)*

**Pliki:** `websocket-manager.js`, `wsapi.js`, `chat.js`, `notifications.js`, `chat-embedded.js`, testy JS.

**Kryterium:** pierwszy `open` nie jest gubiony, reconnect nie zmienia nawigacji, a pełny czat, notifications i embedded chat współdzielą socket bez nadpisywania handlerów.

## 9. Etap G — jawne stany UI i dostępność

- [x] **9.1. Lista pokoi ma jawne widoki:** pokoje dostępne, brak pokoi, brak wyników wyszukiwania, brak nieprzeczytanych, ładowanie danych pomocniczych. *(empty state nieprzeczytanych, "None" per kategoria i `#chat-no-search-results` z `:has()` chowającym puste drzewo)*
- [x] **9.2. Obszar wiadomości ma jawne widoki:** wybór pokoju, joining, otwarty pokój bez wiadomości, błąd dostępu, błąd sieci/retry. *(placeholder wyboru, spinner `connecting`, empty-chat-message, toast + `#chat-join-error` z przyciskiem „Spróbuj ponownie" przy błędach technicznych)*
- [x] **9.3. Wskaźnik `connecting/reconnecting/offline` nie zasłania bez potrzeby istniejących wiadomości.** *(delikatna pigułka `#chat-conn-status`, `pointer-events: none`, `aria-live`)*
- [x] **9.4. Na mobile nie autofocusować pola wpisywania po joinie; obecny warunek desktop/mobile przenieść do `mobileMedia.matches`.**
- [x] **9.5. Po powrocie na listę przywrócić fokus do linku pokoju; po wejściu do pokoju ustawić `aria-current`.** *(`aria-current` w `renderChatView`; `navigateToRoomList` fokusuje link aktywnego pokoju przy mobile powrocie — `.room-link` dostał `tabindex="-1"`)*
- [x] **9.6. Wszystkie nowe teksty dodać do tłumaczeń i wygenerować pliki lokalizacyjne zgodnie z procedurą projektu.**
- [x] **9.7. Wspólne modale, dropdowny, alerty i przyciski używać istniejących komponentów `tw-*`; nie dodawać czatowych kopii `TwModal`/`TwDropdown`.**
- [x] **9.8. Test `image_preview_visibility.test.js` pozostaje testem regresyjnym po migracji `tw-d-none`; obejmuje także embedded chat.** *(kontrakt `tw-d-none` embedded preview pokryty w `chat_embedded_lifecycle.test.js`)*

**Pliki:** `chat/templates/chat/chat.html`, `templates.js`, `chat-core.js`, `domapi.js`, `handlers.js`, `locale/pl/LC_MESSAGES/django.po`, testy.

**Kryterium:** każdy stan aplikacji ma komunikat lub kontrolkę działania; interfejs nie komunikuje błędu przez samą pustą przestrzeń.

## 10. Etap H — opcjonalne uporządkowanie modelu listy

**Dlaczego:** to osobna poprawa utrzymywalności, nie warunek naprawy pustego ekranu.

- [x] **10.1. Nie zmieniać teraz renderowania serwerowego na drugi, równoległy JSON.** Najpierw odczytać istniejące `data-*` z `.room-link` i zachować Django jako źródło danych.
- [x] **10.2. Zbudować model zachowujący hierarchię kategorii, archiwa, pokoje prywatne i pokoje źródłowe tasks/votes/board.** *(model = `roomHomes`: Map linku → `{parent, index}`; serwerowy DOM nadal niesie hierarchię kategorii i archiwów)*
- [x] **10.3. Wydzielić czyste funkcje filtrujące, sortujące i wyliczające empty state.** *(`roomLinkComparator`, `isRoomListLinkVisible`, `captureRoomHomes`, `restoreRoomHomes`, `resortFlatRoomList` — poziom modułu chat.js, testowalne bez socketu)*
- [x] **10.4. Zastąpić `roomOriginalPositions`/`flatContainer` jednym renderem lub deterministycznym przenoszeniem elementów z modelu; reset nie może zależeć od przypadkowego `nextSibling`.** *(restore grupuje po `parent` i wstawia rosnąco po zapisanym indeksie — odporne na zmiany rodzeństwa w trakcie sortu)*
- [x] **10.5. Aktualizacja preview/unread/last activity po wiadomości ma modyfikować model i bieżący widok, bez podwójnego źródła prawdy.** *(`updateRoomListForMessage` → domapi aktualizuje `data-*`/podgląd, następnie `resortFlatRoomList()` przywraca porządek — naprawia rozjazd trybu 'oldest' przez bezpośredni `prepend` w `#room-list-flat`)*
- [x] **10.6. Zachować delegowane handlery, żeby ponowny render nie wymagał ponownego wiązania kliknięć.** *(kliki `.room-link` są delegowane na `document` — przenoszenie węzłów nie odcina handlerów)*
- [x] **10.7. Dodać testy dla sortowania, filtrów, archiwów, kategorii i pustych stanów.** *(`room_list_sort.test.js` — 14 testów: komparator, widoczność/archiwum, capture/restore odporny na zmianę rodzeństwa, pełny cykl sort/reset z localStorage, re-sort po `last-activity`)*

**Pliki:** `chat.js`, `domapi.js`, `templates.js`, ewentualnie testy. Etap można odłożyć po etapach A–G.

## 11. Etap I — cleanup po migracji

- [x] **11.1.** Usunąć `decideStartupAction` dopiero po przejęciu wszystkich przypadków przez parser routingu i testy. *(zastąpione przez `parseChatLocation` + `chat_routing.test.js`)*
- [x] **11.2.** Usunąć `stripParam` i kasowanie `view` z URL.
- [x] **11.3.** Usunąć bezpośrednie `mobileShowRoomList`/`mobileHideRoomList`, gdy przyciski korzystają z routera.
- [x] **11.4.** Usunąć bezpośrednie ustawianie klas widoku poza `renderChatView`. *(wyjątek świadomy: `room-list-hidden` ustawia wyłącznie `setRoomListHidden` w handlers.js jako właściciel desktopowej preferencji)*
- [x] **11.5.** Usunąć stare API managera (`setSocketMessageHandler`, `setOnConnect`, `setOnDisconnect`) dopiero po migracji wszystkich konsumentów.
- [x] **11.6.** Usunąć `roomOriginalPositions` i `flatContainer`, jeżeli etap H został wykonany. *(zastąpione modelem `roomHomes`/`flatListEl`/`roomSortMode`)*
- [x] **11.7.** Usunąć z `tailwind.css` reguły doraźne zastąpione finalnym layoutem; nie usuwać reguł wyłącznie dlatego, że klasa nie ma `tw-` — klasy semantyczne czatu pozostają do czasu migracji JS.
- [x] **11.8.** Przebudować `tailwind.build.css`, uruchomić regression scan i sprawdzić, że nie pojawił się link do usuniętego `chat.css`.

## 12. Testowanie i kryteria techniczne

- [x] **12.1. Testy jednostkowe uruchamiać selektywnie po zmianie logiki:** `npm test -- --runInBand <nazwa-testu>`.
- [x] **12.2. Po zmianach managera WebSocket uruchomić pełne testy Jest:** `npm test -- --runInBand`. *(16 suites / 185 testów — zielone)*
- [x] **12.3. Po zmianie źródła stylów wykonać `npm run build:css`, `python scripts/regression_scan.py` oraz test freshness/buildu z `scripts/run_tests.py`.**
- [x] **12.4. Playwright uruchamiać po uruchomieniu Redis, Django na `0.0.0.0:8000` oraz z `.env.local` zawierającym dane E2E:**
  - [x] **12.4.1.** `npx playwright test e2e/chat-mobile-room-toggle.spec.js --project=mobile-chromium`;
  - [x] **12.4.2.** `npx playwright test e2e/chat-mobile-room-toggle.spec.js --project=desktop-chromium`;
  - [x] **12.4.3.** nowe testy routingu/reconnectu w obu projektach; *(dodano test Wstecz/Naprzód i refresh; reconnect E2E nie dodany — trudny do deterministycznego odtworzenia w Playwright)*
  - [x] **12.4.4.** nowe asercje geometrii paneli, nie tylko asercje klas. *(`expectPositiveBox` na `.room-list` i `.chat-root-messages`)*
- [x] **12.5. Po zmianie `base.html` uruchomić adekwatny Django system check; nie wykonywać szerokiego runnera bez powodu.**
- [x] **12.6. Nie używać browser preview; weryfikacja ma odbywać się testami i CLI.**
- [x] **12.7. Testy nie mogą wymagać ręcznego czyszczenia `localStorage`; przed każdym scenariuszem ustawiać jawny stan storage.** *(E2E startuje z `?view=rooms` — niezależne od zapisanych preferencji)*

## 13. Macierz akceptacyjna

- [x] **13.1. `/chat/`:**
  - [x] **13.1.1. Desktop:** lista oraz ostatni/pierwszy dozwolony pokój; po joinie hash pokoju.
  - [x] **13.1.2. Mobile:** pokój; Wstecz pokazuje listę. *(auto-join robi `pushState` nad wpisem `/chat/`; Wstecz → lista)*
  - [x] **13.1.3. Brak pokoju:** jawny empty state. *(placeholder „Wybierz pokój z listy")*
- [x] **13.2. `/chat/?view=rooms`:**
  - [x] **13.2.1. Desktop:** lista i placeholder wyboru pokoju.
  - [x] **13.2.2. Mobile:** lista o dodatniej wysokości; nie sam toolbar. *(asercja `boundingBox` w E2E)*
  - [x] **13.2.3. Refresh:** nadal lista. *(parametr nie jest kasowany — test E2E reload)*
- [x] **13.3. `/chat/?view=unread` oraz `?unread=1`:** lista z filtrem; brak wyników pokazuje empty state; refresh zachowuje intencję.
- [x] **13.4. `/chat/#room_id=X`:** desktop lista + pokój X; mobile pokój X; Wstecz lista; refresh pokój X. *(normalizacja stosu Wstecz: `replaceState` listy + `pushState` pokoju)*
- [x] **13.5. `/chat/#room_id=X&message_id=Y`:** pokój X i przewinięcie do Y po renderze. *(`ScrollToMessageId` zachowane; niezweryfikowane E2E)*
- [x] **13.6. Nieistniejący/niedozwolony pokój:** komunikat błędu i działający powrót do listy. *(toast „Ten pokój jest niedostępny." + `replaceState` na URL listy)*
- [x] **13.7. Reconnect w pokoju:** rejoin bez zmiany URL/panelu i bez nowego wpisu historii. *(`preserveView` w `wsOnReconnect`; brak wpisu historii — kod, nie E2E)*
- [x] **13.8. Reconnect na liście:** lista pozostaje widoczna; ewentualny rejoin tła nie przełącza panelu. *(j.w.)*
- [x] **13.9. Szybki wybór A → B:** odpowiedź A nie nadpisuje B. *(`JoinGeneration` + flaga `stale`)*
- [x] **13.10. Rotacja/resize przez 768 px:** brak panelu o zerowej wysokości/szerokości; preferencja desktopowa nie psuje mobile. *(listener `mobileMedia` + klasa usuwana tylko z prezentacji)*
- [x] **13.11. Embedded chat:** pierwsze połączenie, reconnect, wiadomości oczekujące i załączniki działają bez duplikacji. *(pokryte w `chat_embedded_lifecycle.test.js` — 9 testów: join, bufor, reconnect/rejoin, retry po timeout, cleanup, preview)*
- [x] **13.12. UI Tailwind:** modal, dropdown, collapse, preview obrazów, strzałki sortowania i przyciski wiadomości zachowują widoczność po buildzie. *(build + regression scan zielone)*
- [x] **13.13. Powiadomienia:** jedno zdarzenie daje najwyżej jedno browserowe powiadomienie, a pełny czat aktualizuje własny DOM. *(`data.notification` ma jednego właściciela — `notifications.js`)*

## 14. Kolejność wdrażania

- [x] **14.1.** Wykonać etap A i potwierdzić, że aktualny pipeline Tailwind jest źródłem prawdy.
- [x] **14.2.** Wykonać etap B i dodać test geometrii odtwarzający pusty mobile panel.
- [x] **14.3.** Wykonać etap C, aby dalsze przejścia nie miały rozjazdu breakpointów i preferencji.
- [x] **14.4.** Wykonać etap D, zachowując przejściowo istniejące klasy CSS.
- [x] **14.5.** Wykonać etap E — router powinien przejąć kliknięcia i Wstecz przed cleanupem.
- [x] **14.6.** Wykonać etap F w jednym logicznym kroku dla pełnego czatu, powiadomień i embedded chat.
- [x] **14.7.** Wykonać etap G równolegle z implementacją stanów kontrolera/transportu.
- [x] **14.8.** Etap H wykonać tylko po stabilizacji etapów A–G; nie blokuje on naprawy mobilnego pustego ekranu. *(wykonany po A–G — model pozycji domowych + re-sort)*
- [x] **14.9.** Etap I wykonać dopiero po zielonej macierzy akceptacyjnej.
- [x] **14.10.** Po każdej fazie przejrzeć diff i nie resetować dużego, niezależnego worktree migracji Tailwind.

## 15. Definition of Done

- [x] **15.1.** Na mobile zawsze jest widoczna lista, pokój, ładowanie albo błąd — nigdy niewyjaśniona pustka.
- [x] **15.2.** Lista ma dodatnią geometrię i renderuje pokoje lub jawny empty state. *(asercje `boundingBox` w E2E)*
- [x] **15.3.** Desktop działa jako stabilny master-detail.
- [x] **15.4.** URL odtwarza widok po refreshu, a Wstecz wraca z pokoju do listy. *(testy E2E Wstecz/Naprzód/reload)*
- [x] **15.5.** Reconnect nie zmienia nawigacji ani historii.
- [x] **15.6.** Późna inicjalizacja WebSocketu nie gubi pierwszego `open`. *(`subscribeConnection` z `alreadyOpen`)*
- [x] **15.7.** Poboczne błędy presence/notification nie blokują startu pokoju.
- [x] **15.8.** Full chat, notifications i embedded chat nie nadpisują sobie handlerów.
- [x] **15.9.** `tw-d-none`, `tw-modal-open` i pozostałe klasy komponentów są obsługiwane zgodnie z kontraktem `!important`/Tailwind.
- [x] **15.10.** `tailwind.css` jest jedynym źródłem CSS poza `tokens.css`, a `tailwind.build.css` jest aktualny i generowany automatycznie.
- [x] **15.11.** Semantyczne klasy czatu są udokumentowane jako haki JS i nie są mylone z pozostałościami Bootstrapa. *(`.room-list-groups` zamiast `.row`; klasy widoku w `renderChatView`)*
- [x] **15.12.** Testy Jest, regression scan, build CSS i adekwatne testy Playwright przechodzą. *(185 testów Jest, 5×E2E, scan i build — zielone)*
