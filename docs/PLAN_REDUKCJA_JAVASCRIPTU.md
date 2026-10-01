# Plan redukcji JavaScriptu

## Cel

Ograniczyć globalne zależności i odpowiedzialności skupione w `app.js`, nie zmniejszając użyteczności interfejsu dla samej liczby linii. Zmiany mają usuwać niepotrzebne ładowanie kodu i poprawiać granice modułów, a nie przenosić logikę bez korzyści ani odtwarzać jej w innym miejscu.

Django pozostaje źródłem prawdy dla danych, uprawnień, walidacji i zapisów. HTML/formularze są właściwym wyborem dla prostych nawigacji i akcji, ale dynamiczne zachowanie zostaje tam, gdzie wspiera ergonomię.

## Stan projektu istotny dla planu

- `home/static/home/js/app.js` łączy funkcje wspólne z zachowaniami konkretnych widoków. Są tam m.in. `PagePrefs`, aktywność, filtry kategorii używane przez zadania i board oraz stan quick links na dashboardzie.
- `home/templates/home/base.html` ładuje globalnie m.in. `app.js`, `scroll-restore.js`, `Sortable.min.js`, `sortable-list.js` i `category-manager.js`. Manager kategorii jest inicjowany przez współdzielony partial kategorii; Sortable obsługuje zarówno kolejność kafelków dashboardu, jak i sortowanie kategorii.
- Wspólne żądania HTTP mają już `window.apiFetch()` w `home/static/common/js/dom-utils.js`; testy Jest obejmują helper i wybrane funkcje `app.js`. Nie dodawać drugiego ogólnego klienta żądań.
- Czat ma osobne moduły ES, testy i transport Django Channels. Jego WebSocket, reconnect, obecność, push i synchronizacja wiadomości nie są kandydatami do mechanicznej migracji.
- Istniejące preferencje mają znaczenie dla UX: `PagePrefs` przywraca widoki, filtry i nawigację, quick links zapisują przeczytany stan i wyliczają postęp, a kolejność kafelków dashboardu jest zapamiętywana. Nie usuwać tych zachowań przy porządkowaniu skryptów.
- HTMX i Alpine.js nie są zależnościami projektu. Ich dodanie nie jest celem tego planu; najpierw należy wykorzystać HTML/Django i istniejące mechanizmy, a bibliotekę rozważać wyłącznie przy wykazanej, konkretnej korzyści.

## Priorytety

### 1. Ograniczyć niepotrzebne globalne ładowanie skryptów

- [x] Zinwentaryzować skrypty i zależności ładowane w `home/templates/home/base.html` oraz ustalić ich rzeczywistych konsumentów.
- [x] Ładować `category-manager.js` przy partialu/widokach, które udostępniają zarządzanie kategoriami, zamiast na każdej stronie.
- [x] Ładować `Sortable.min.js` i `sortable-list.js` tylko w widokach używających sortowania; zachować sortowanie kategorii i kolejność kafelków dashboardu.
- [x] Po zmianie sprawdzić dashboard, zarządzanie kategoriami i pozostałe miejsca, które korzystają z przeniesionych skryptów; usunąć globalny include dopiero po potwierdzeniu wszystkich konsumentów.

### 2. Zmniejszyć odpowiedzialność `app.js` bez tworzenia nowego monolitu

- [x] Oprzeć się na istniejących testach Jest dla `PagePrefs` i filtrów kategorii; dopisać testy charakterystyki tylko dla niepokrytych zachowań przed ich przeniesieniem.
- [x] Ocenić jako pierwszy kandydat filtr kategorii używany w zadaniach i boardzie: wydzielić go do miejsca, które ma tych konsumentów, i ładować tylko na odpowiednich widokach, jeśli uprości to zależności i inicjalizację.
- [x] Zachować query params, Wstecz/Dalej, aktualizację listy zadań, fallback do pełnego przeładowania, ponowne inicjowanie kart oraz współpracę z `PagePrefs`.
- [x] Usunąć starą implementację i jej globalną inicjalizację dopiero po przeniesieniu wszystkich konsumentów oraz przejściu testów.
- [x] Nie rozdzielać pozostałych funkcji `app.js` wyłącznie według liczby linii; wydzielać je tylko wtedy, gdy mają jasno określonych konsumentów i da się ograniczyć ich ładowanie lub uprościć testowanie.

### 3. Ujednolicić obsługę żądań tylko tam, gdzie jest duplikacja

- [x] Przy okazji zmian sprawdzić ręczne `fetch()` i lokalne wrappery obok `window.apiFetch()`; użyć istniejącego helpera dla zgodnych żądań JSON, bez zmiany kontraktu odpowiedzi.
- [x] Pozostawić bezpośrednie `fetch()`, gdy odpowiedź zawiera HTML partialu albo wymaga innej semantyki; nie dodawać abstrakcji tylko po to, by wszystkie wywołania wyglądały identycznie.

## Zachować — poza zakresem mechanicznej redukcji

Nie usuwać ani nie upraszczać bez osobnej decyzji i sprawdzenia wpływu na UX:

- `PagePrefs`, odtwarzania filtrów/nawigacji oraz zapamiętywania widoków;
- stanu przeczytania quick links i zapamiętywanej kolejności kafelków dashboardu;
- natychmiastowej aktualizacji odczytu i bookmarków w aktywności, motywu i responsywnych zachowań wspólnego UI;
- interakcji głosowania i koordynacji zadań;
- nawigacji kalendarza, countdownów oraz elementów prezentacyjnych dashboardu;
- WebSocketów czatu, reconnectu, powiadomień push, rich text i podglądu/uploadu plików.

Są to działające funkcje albo świadome interakcje przeglądarkowe. Zmniejszenie ilości JavaScriptu nie uzasadnia ich regresji.

## Kryteria każdej zmiany

- Zmiana ma wskazanego właściciela kodu i konsumentów; nie powiela implementacji ani nie przenosi jej do kolejnego globalnego pliku.
- Zachowanie, URL-e, uprawnienia, CSRF, błędy i dostępność pozostają bez zmian, chyba że osobna decyzja jawnie określa inaczej.
- Testy obejmują zmieniany zakres; dla zmian UI sprawdzone są także klawiatura, focus i widok mobilny.
- Usunięte są stare include'y i nieużywane zależności dopiero po sprawdzeniu wszystkich ich konsumentów.

## Poza zakresem

Nie planować teraz migracji wszystkich formularzy, filtrów, kalendarza ani czatu do server-driven UI; nie dodawać HTMX/Alpine.js bez pilotażu wykazującego przewagę nad HTML/Django i istniejącym JavaScriptem. Nie usuwać kosmetycznych lub wygodnych interakcji tylko po to, by zmniejszyć licznik linii.
