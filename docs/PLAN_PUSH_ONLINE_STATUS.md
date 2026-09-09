# Plan: status online na podstawie odebranych powiadomień push

## Cel

- [x] Pokazywać na liście użytkowników wskaźnik informujący o czasie najnowszego wiarygodnego sygnału (`push` lub aktywność aplikacji).
- [x] Nie utożsamiać aktywnego tokena ani wysłania powiadomienia z jego odebraniem; logowanie i aktywność aplikacji są osobnymi sygnałami.
- [x] Zapewnić działanie wskaźnika także wtedy, gdy użytkownik nie ma włączonych powiadomień push.
- [x] Rozdzielić dwa sygnały obecności: potwierdzony odbiór push oraz aktywność aplikacji.
- [x] Ustalić, że status użytkownika bez push oznacza ostatnią potwierdzoną aktywność aplikacji, a nie odbiór push.

## Potwierdzone założenia

- [x] Status wynika z najnowszego wiarygodnego sygnału z dowolnego urządzenia lub karty użytkownika.
- [x] Uwzględniane są: logowanie, otwarcie aplikacji, okresowy heartbeat, widoczność karty, kliknięcia, wpisywanie, zapisy, dodawanie treści, push i WebSocket.
- [x] Kliknięcia i wpisywanie aktualizują aktywność z ograniczeniem częstotliwości zapisu do maksymalnie raz na 5 minut.
- [x] Otwarta karta może utrzymywać aktywność przez okresowy heartbeat, także bez ręcznej interakcji.
- [x] Samo zalogowanie jest pełnym sygnałem aktywności.
- [x] Odebrany push jest sygnałem aktywności również wtedy, gdy aplikacja nie jest otwarta.
- [x] Status jest widoczny wszystkim użytkownikom uprawnionym do oglądania listy obywateli.
- [x] Wylogowanie lub wygaśnięcie sesji natychmiast wygasza sygnały aktywności aplikacji; push po wylogowaniu nie jest zaliczany.
- [x] Domyślne progi to: zielony do 15 minut, żółty do 7 dni, czerwony później lub bez sygnału; wartości pozostają konfigurowalne.
- [x] Aktywna karta wysyła heartbeat co 15 minut; backend powinien zabezpieczyć się przed nadmiarowymi aktualizacjami.
- [x] Tooltip ma pokazywać szczegółowe źródło sygnału i czas, np. „aktywność aplikacji”, „ostatnia interakcja” albo „odebrano push”.

## Ustalenia do potwierdzenia przed implementacją

- [x] Progi kolorów są konfigurowalne; wartości domyślne to: zielony do 15 minut, żółty do 7 dni, czerwony później lub bez sygnału.
- [x] Status opisuje odbiór/aktywność na dowolnym urządzeniu użytkownika; agregacja wybiera najnowszy sygnał.
- [x] Bez push używany będzie heartbeat aktywnej sesji oraz pozostałe sygnały aktywności aplikacji; heartbeat działa co 15 minut.
- [x] Kolory są wspólne dla sygnałów, ale tooltip rozróżnia „online przez push” i „online przez aktywność aplikacji”.
- [x] Żółty status obejmuje cały okres od zielonego progu do czerwonego progu.
- [x] Tooltip zawiera status, źródło najnowszego sygnału i jego czas; tłumaczenia etykiet pozostają częścią implementacji UI.

## Model danych i backend

- [x] Dodać trwały, indeksowany znacznik czasu najnowszego sygnału obecności oraz źródła sygnału dla użytkownika; przyjęto agregację na poziomie użytkownika.
- [x] Nie zapisywać tokena FCM ani danych wrażliwych; przechowywać wyłącznie czas i źródło najnowszego sygnału.
- [x] Za sygnał push uznawać wyłącznie status `shown` po faktycznym pokazaniu powiadomienia; nie zaliczać `skipped` i `error`.
- [x] Rozszerzyć istniejący `PushNotificationAckView`, który obecnie loguje ACK, tak aby status `shown` aktualizował monotonicznie sygnał `push` właściwego zalogowanego użytkownika.
- [x] Zachować odporność na powtórne ACK-i, opóźnione ACK-i, brak `notification_id` i wielokrotne urządzenia; aktualizacja nie cofa czasu ostatniego sygnału.
- [x] Ograniczyć źródła zapisu obecności do kontrolowanych wartości `app` i `push`; status ACK nadal zachowuje istniejący kontrakt logowania.
- [x] Wydzielić funkcję wyliczającą status (`green`/`yellow`/`red`) oraz monotoniczny zapis sygnału w `core.presence`.
- [x] Dodać migrację; istniejący użytkownicy zaczynają bez sygnału i mają status czerwony do czasu aktywności.
- [x] Przygotować listę użytkowników z `select_related('uzytkownik')`; status jest wyliczany bez N+1 zapytań.
- [x] Nie zmieniać istniejącego `activity_status` opartego o `last_login`; nowy wskaźnik ma osobną semantykę hybrydowej obecności.
- [x] Dodać wspólny znacznik ostatniej aktywności aplikacji dla użytkownika bez aktywnego push; fallback nie opiera się wyłącznie na `last_login`.
- [x] Zdefiniować priorytet sygnałów: najnowszy wiarygodny sygnał aktywności wyznacza status, a źródło (`push`/`app`) pozostaje dostępne do opisu.

## Frontend push i niezawodność sygnału

- [x] Przejrzeć wszystkie ścieżki odbioru powiadomień: foreground FCM, background/service worker, kliknięcie powiadomienia oraz ścieżkę WebSocket.
- [x] Wysyłać ACK po rzeczywistym pokazaniu powiadomienia, a nie tylko po otrzymaniu wiadomości przez aplikację.
- [x] Nie uznawać samego kliknięcia za wymagane do statusu online — użytkownik może odebrać powiadomienie bez kliknięcia.
- [x] ACK zawiera aktualnie uwierzytelnionego użytkownika i nie pozwala klientowi oznaczyć innego użytkownika jako online.
- [x] Brak sieci przy ACK nie blokuje interfejsu; istniejące wysyłanie fire-and-forget pozostaje ograniczone do bieżącego zdarzenia.
- [x] Po wylogowaniu push nie jest zaliczany; brak aktywności aplikacji wygasa naturalnie po braku heartbeat.
- [x] Statusy są rozsyłane przez istniejący WebSocket do wszystkich zalogowanych, podłączonych kart aplikacji; heartbeat korzysta z tego samego połączenia.
- [x] Globalny skrypt aplikacji rejestruje kliknięcia, wpisywanie, połączenie WebSocket i wiadomości WebSocket z throttlingiem 5 minut.

## Lista użytkowników i UI

- [x] Dodać kropkę w prawym górnym rogu każdej ikony użytkownika renderowanej przez wspólny partial, w tym w tabeli/siatce obywateli, profilach, aktywności, dokumentach, głosowaniach, zadaniach i dashboardzie.
- [x] Użyć i rozszerzyć istniejący komponent avatara `home/_user_avatar.html`; prywatny avatar w linku pokoju czatu również otrzymuje wskaźnik.
- [x] Wprowadzić wspólne klasy z prefiksem `tw-` dla kropki, położenia, rozmiaru i kolorów; nie używać nowych klas Bootstrap ani stylów inline.
- [x] Zaprojektować kropkę jako element dekoracyjny z dostępnym tekstem/tooltipem opisującym znaczenie i czas ostatniego sygnału.
- [x] Nie polegać wyłącznie na kolorze: dodać `title`, `aria-label` i tekstowy status w danych elementu.
- [x] Na urządzeniach dotykowych dotknięcie kropki otwiera popover ze statusem; drugie dotknięcie lub dotknięcie poza nim zamyka popover. Długie przytrzymanie nie jest wymagane.
- [x] Sprawdzić wygląd na jasnym i ciemnym motywie oraz na małych ekranach przez wspólne tokeny i responsywny układ avatara.
- [x] Sprawdzić `docs/UI_STANDARDS.html`, istniejące tokeny i wspólne komponenty; nowy wzorzec kropki został udokumentowany.

## Testy

- [x] Dodać testy funkcji wyliczającej status dla granic: brak daty, dokładny próg, tuż przed i tuż po każdym progu.
- [x] Dodać test ACK-a `shown`: aktualizuje czas użytkownika.
- [x] Dodać test ACK-ów `skipped` i `error`: nie aktualizują czasu.
- [x] Dodać test opóźnionego ACK-a: starsze zdarzenie nie nadpisuje nowszego czasu.
- [x] Dodać test bezpieczeństwa: ACK użytkownika nie może zmienić statusu innego użytkownika.
- [ ] Dodać test listy użytkowników zapewniający poprawne statusy bez zapytań N+1.
- [x] Dodać testy szablonu dla zielonej, żółtej i czerwonej kropki w widoku tabeli i siatki.
- [x] Dodać test regresji dla użytkownika bez urządzenia push i dla wielu aktywnych sygnałów.
- [x] Dodać test regresji użytkownika bez push: status może być aktualizowany sygnałem aplikacji.

## Weryfikacja i wdrożenie

- [x] Uruchomić testy backendu i frontendu dotknięte zmianą oraz kontrole Django/lintingu.
- [x] Jeśli zmiana dotyczy UI, uruchomić `npm run build:css`, `python scripts/regression_scan.py` i `python scripts/ui_guard.py`.
- [x] Zweryfikować, że `tailwind.build.css` został wygenerowany przez pipeline, a nie edytowany ręcznie.
- [x] Zweryfikować migrację i zachowanie istniejących użytkowników bez sygnału; rejestracja tokena nie zmienia statusu sama w sobie.
- [x] Opisać w dokumentacji technicznej, że kolor oznacza czas ostatniego wiarygodnego sygnału (`push` albo aktywność aplikacji), a nie gwarantowaną obecność człowieka przy urządzeniu.

## Kryteria akceptacji

- [x] Użytkownik z najnowszym wiarygodnym sygnałem w progu zielonym ma zieloną kropkę.
- [x] Użytkownik z najnowszym wiarygodnym sygnałem w starszym, ale jeszcze ważnym progu ma żółtą kropkę.
- [x] Użytkownik bez potwierdzonego odbioru push, ale z aktualną aktywnością aplikacji, otrzymuje status wynikający z tej aktywności.
- [x] Użytkownik bez żadnego wiarygodnego sygnału lub poza najstarszym progiem ma czerwoną kropkę.
- [x] Status zmienia się po ACK-u, sygnale aktywności aplikacji albo upływie progu, bez ręcznego odświeżania strony.
- [x] Status jest widoczny zarówno w widoku listy, jak i siatki, przy ikonie użytkownika w prawym górnym rogu.
- [x] Interfejs nie polega wyłącznie na kolorze i ma opis statusu.
- [ ] Żaden scenariusz nie oznacza użytkownika online wyłącznie na podstawie `last_login`, aktywnego tokena, wysłania push, `skipped` ani `error`.

## Ryzyka i decyzje poza zakresem

- [x] Traktować status jako heurystykę aktywności, nie dowód, że użytkownik patrzy na ekran.
- [x] Nie wprowadzać automatycznego monitorowania obecności, geolokalizacji ani heartbeat częstszego niż ustalone 15 minut.
- [ ] Nie zmieniać zasad autoryzacji, onboardingu, głosowań ani innych kontraktów biznesowych.

## Podsumowanie: kiedy widzimy aktywność

- **Zielona kropka:** najnowszy sygnał (`app` albo `push`) pochodzi z ostatnich 15 minut. Sygnał `app` może pochodzić z logowania, otwartej karty z heartbeat, kliknięcia, wpisywania, zapisu, dodania treści lub WebSocketu.
- **Żółta kropka:** najnowszy sygnał jest starszy niż 15 minut, ale nie starszy niż 7 dni.
- **Czerwona kropka:** brak sygnału albo najnowszy sygnał jest starszy niż 7 dni.
- Po zamknięciu karty status nie gaśnie natychmiast — wygasa naturalnie, gdy przestaną przychodzić heartbeat. Push po wylogowaniu nie aktualizuje statusu.
- Kropka oznacza ostatnią potwierdzoną aktywność techniczną, a nie pewność, że człowiek patrzy w ekran. Tooltip pokazuje źródło i czas sygnału.

## Krótki opis dla użytkowników

> Kropka przy zdjęciu pokazuje, kiedy ostatnio aplikacja miała wiarygodny sygnał aktywności tej osoby. Zielona oznacza aktywność w ciągu ostatnich 15 minut, żółta — wcześniejszą aktywność, a czerwona — brak świeżej aktywności. Sygnałem może być korzystanie z aplikacji albo odebranie powiadomienia push. To orientacyjna informacja — nie oznacza, że osoba w tej chwili patrzy na ekran.

## Co jeszcze zostało do zrobienia

- [x] Dopracować lokalizację tooltipu statusu przez wspólne filtry tłumaczeń źródła i stanu.
- [x] Dodać test bezpieczeństwa potwierdzający, że ACK jednego użytkownika nie zmienia statusu innego użytkownika.
- [x] Dodać test widoku listy z kontrolą braku wzrostu liczby zapytań N+1.
- [x] Dodać testy szablonu dla trzech kolorów w widoku listy i siatki.
- [x] Dodać test regresji użytkownika bez push i wielu aktywnych sygnałów.
- [x] Uzupełnić widoki autorów i koordynatorów w ankietach, dokumentach, transakcjach i szczegółach zadań o wspólny avatar ze znacznikiem.
- [x] Dodać powyższy opis do właściwego miejsca interfejsu — tooltipu kafelka aktywności.

## Propozycja kafelka aktywności na pulpicie

### Rekomendowany wariant: „puls aktywności”

- [x] Zastąpić samą liczbę procentową kafelkiem z dużym wynikiem „aktywni w ciągu 30 dni”.
- [x] Pokazać pod wynikiem poziomy, kolorowy pasek z podziałem użytkowników według świeżości sygnału:
  - zielony — aktywność do 15 minut;
  - żółty — aktywność od 15 minut do 7 dni;
  - szary/czerwony — brak aktywności w ostatnich 7–30 dniach;
  - brak aktywności od ponad 30 dni nie wchodzi do wyniku 30-dniowego.
- [x] Dodać krótkie podpisy z liczbami dla każdej części paska, aby wykres był zrozumiały bez rozpoznawania kolorów.
- [x] Dodać mały pierścień pokazujący procent aktywnych w ciągu 30 dni; środek pierścienia zawiera liczbę procentową.
- [x] Zachować kliknięcie kafelka prowadzące do listy obywateli z odpowiednim filtrem aktywności.
- [x] Oprzeć pierwszy wariant na istniejącym `last_presence_at`, bez zapisywania historii każdego zdarzenia.

### Wariant rozszerzony: kalendarz 30 dni

- [ ] Jeśli potrzebna jest historia „jak aktywność zmieniała się każdego dnia”, dodać dzienne agregaty aktywności.
- [ ] Pokazać wtedy miniaturowy kalendarz/heatmapę 30 dni: jeden kafelek na dzień, intensywność zależna od liczby aktywnych użytkowników.
- [ ] Nie udawać takiej historii na podstawie samego `last_presence_at`, ponieważ obecny model przechowuje tylko najnowszy sygnał każdej osoby.
