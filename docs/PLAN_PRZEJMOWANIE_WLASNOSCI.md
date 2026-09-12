# Plan: przejmowanie własności porzuconej treści

> **Status: odłożony i poza bieżącym audytem widoków edycji.**
>
> W bieżącym zakresie projektu nie wprowadzamy uogólnionej własności treści ani mechanizmu przejmowania. Domyślna reguła pozostaje taka jak obecnie: poza istniejącymi, jawnie potwierdzonymi wyjątkami zalogowany użytkownik może edytować dokumenty. Nie dodajemy nowych pól właściciela, migracji, blokad edycji ani przycisku „Przejmij” jako części tego audytu.
>
> Poniższy dokument zachowuje wcześniejszą koncepcję wyłącznie jako materiał do ewentualnej osobnej decyzji. Nie należy traktować jego proponowanego modelu, terminów ani przepływów jako aktualnych wymagań.

## 1. Cel — koncepcja odłożona

Ewentualne umożliwienie obywatelowi zgłoszenia chęci przejęcia porzuconej treści wymaga osobnej decyzji produktowej i nie jest implementowane w ramach obecnego audytu.

> Termin przejęcia wynosi 2 dni bez odpowiedzi właściciela; przed implementacją można uczynić go parametrem konfiguracji.

## 2. Stan obecny i ograniczenia architektoniczne

- Dokumenty są obsługiwane przez `board.Post`; pole `author` jest informacją o autorze dokumentu, a nie ogólną blokadą edycji.
- Nie należy traktować pól `author` w poszczególnych modelach jako wspólnego mechanizmu własności. Istniejące wyjątki edycji pozostają regułami domenowymi konkretnych modułów i wymagają osobnego potwierdzenia w audycie.
- Bieżące widoki edycji nie powinny kopiować logiki „właściciel albo treść bez właściciela” ani blokować edycji na podstawie samego `author`, chyba że wynika to z istniejącego, potwierdzonego wyjątku.
- Prywatne wiadomości korzystają z `chat.Room` (`public=False`, dwóch użytkowników) i `chat.services.send_message`; ich użycie do przejmowania treści jest odłożone.
- Czat działa przez istniejący WebSocket i szablony EJS w `chat/static/chat/js/templates.js`; wiadomości nie mają obecnie strukturalnego typu akcji ani wbudowanych przycisków decyzji.
- Harmonogram zadań jest już realizowany przez APScheduler w `zzz/scheduler.py`; nie należy wprowadzać drugiego mechanizmu schedulerowego.
- Style produkcyjne pochodzą wyłącznie z `home/static/home/css/tailwind.css` i są generowane przez `npm run build:css`. Nowe elementy UI muszą używać istniejących komponentów `tw-*`.

## 3. Założenia biznesowe do potwierdzenia — tylko przy wznowieniu planu

Jeżeli temat zostanie kiedyś wznowiony, przed implementacją trzeba ponownie zatwierdzić poniższe punkty, ponieważ wpływają na model danych i uprawnienia. Żaden z nich nie jest obecnie obowiązującą regułą aplikacji:

1. **Definicja porzucenia:** czy porzucona jest wyłącznie treść z `author IS NULL`, czy także treść z istniejącym autorem, który nie wykonał określonej czynności przez ustalony czas? Obecny kod traktuje `author IS NULL` jako treść możliwą do przejęcia przy edycji.
2. **Zakres pierwszej wersji:** rekomendowany jest najpierw `board.Post`, a następnie rozszerzenie na `Event`, zasoby księgowe i inne typy przez wspólny adapter/rejestr. Dzięki temu nie zmieniamy od razu wszystkich kontraktów modułów.
3. **Znaczenie zgody:** rekomendowane jest natychmiastowe przejęcie po kliknięciu **Zgódź się**; **Nie zgódź się** kończy wniosek odmową i blokuje ten konkretny wniosek.
4. **Ponowna próba:** czy po odmowie można od razu złożyć nowy wniosek, czy obowiązuje blokada do czasu ręcznego wznowienia przez właściciela? Rekomendacja: nie tworzyć kolejnego aktywnego wniosku, a ponowną próbę dopuścić dopiero po jawnej regule biznesowej.
5. **Brak właściciela:** jeśli `author IS NULL`, nie ma komu wysłać sprzeciwu. Rekomendacja: pokazać wniosek jako oczekujący, ale pominąć wiadomość do właściciela i przejąć treść po terminie; alternatywnie przejmować ją od razu. Ten przypadek musi być jednoznaczny.
6. **Odwołanie wniosku:** czy zgłaszający może anulować oczekujący wniosek? Rekomendacja: tak, do czasu decyzji lub automatycznego przejęcia.
7. **Treść systemowa/usunięta:** wpisy z `system_key`, treści usunięte i obiekty objęte innymi ograniczeniami nie mogą być przejmowane.
8. **Strefa czasu:** termin dwóch dni należy liczyć jako 48 godzin od utworzenia wniosku, zapisywać w UTC i prezentować w lokalnej strefie aplikacji.

## 4. Proponowany model domenowy

### 4.1. Wspólny model w `core`

Dodać do istniejącej aplikacji `core` model, np. `OwnershipTakeoverRequest`, zamiast dodawać osobny model dla każdego modułu. Model powinien przechowywać:

- typ i identyfikator obiektu przez istniejący mechanizm generycznej relacji albo uzgodniony adapter domenowy;
- `claimant` — użytkownika składającego wniosek;
- `owner_at_request` — migawkę właściciela z chwili złożenia wniosku, nullable dla treści bez właściciela;
- `status`: `pending`, `approved`, `rejected`, `expired`, `cancelled`;
- `requested_at`, `deadline_at`, `decided_at`;
- opcjonalnie identyfikator prywatnej rozmowy i wiadomości akcji, jeśli będzie to potrzebne do idempotentnego odświeżania przycisków.

Dodać ograniczenia i indeksy zapewniające najwyżej jeden aktywny wniosek dla danego obiektu oraz szybkie wyszukiwanie wniosków oczekujących po `deadline_at`. Nie zmieniać bezpośrednio istniejących migracji — przygotować nową migrację po zatwierdzeniu modelu.

### 4.2. Adapter własności

W `core` wydzielić mały kontrakt dla treści przejmowalnej, np. funkcje `get_owner`, `set_owner`, `get_url`, `is_eligible`. Rejestr adapterów powinien mapować `app_label` na model i nie importować konkretnych modułów w każdym widoku czatu.

Dla `board.Post` adapter powinien:

- uznawać za kwalifikujące tylko istniejące, nieusunięte, niesystemowe dokumenty;
- przy zapisie sprawdzać ponownie aktualnego autora w transakcji;
- zachować istniejące powiązanie z pokojem dokumentu i nie zmieniać tytułu pokoju;
- nie pozwalać na przejęcie obiektu, który w międzyczasie otrzymał właściciela lub został usunięty.

## 5. Przepływ zgłoszenia

1. Na stronie szczegółów kwalifikującej się treści pojawia się wspólny przycisk **Przejmij** tylko dla zalogowanego użytkownika, który nie jest właścicielem i nie ma już aktywnego wniosku.
2. Kliknięcie używa standardowego formularza POST lub istniejącego wzorca endpointu JSON; wymagane są CSRF, logowanie i walidacja po stronie serwera. Preferowany jest zwykły POST z bezpiecznym przekierowaniem, chyba że aktualny widok wymaga aktualizacji bez przeładowania.
3. Serwis domenowy w transakcji:
   - blokuje rekord treści (`select_for_update`);
   - ponownie sprawdza kwalifikację, właściciela i brak aktywnego wniosku;
   - tworzy wniosek z terminem `requested_at + 48 godzin`;
   - pobiera lub tworzy istniejącą prywatną rozmowę z właścicielem;
   - wysyła jedną wiadomość systemową z nazwą dokumentu, osobą zgłaszającą, terminem oraz linkiem do dokumentu.
4. Powtórne kliknięcie nie tworzy drugiego wniosku ani drugiej wiadomości. Serwis zwraca stan istniejącego wniosku.
5. Po sukcesie widok pokazuje `tw-alert`/badge statusu i termin, zamiast ponownie oferować przycisk.

## 6. Wiadomość prywatna i decyzja właściciela

### 6.1. Wiadomość

Użyć istniejącej funkcji `Room.get_or_create_for_users` oraz `chat.services.send_message`, aby nie tworzyć równoległego systemu powiadomień. Wiadomość powinna być systemowa (`sender=None`) i zawierać bezpieczny link do dokumentu oraz identyfikator wniosku przekazany jako dane akcji, a nie parsowany z tekstu.

Nie opierać autoryzacji na treści wiadomości, nazwie pokoju ani ukrytych danych w HTML. Właściciel musi być sprawdzany po stronie serwera przy każdym kliknięciu.

### 6.2. Przyciski

Rozszerzyć istniejący kontrakt payloadu wiadomości o opcjonalne dane strukturalne, np. `ownership_request` z identyfikatorem wniosku, dozwolonymi akcjami i stanem. Wspólny renderer czatu w `templates.js` powinien:

- renderować przyciski tylko dla odbiorcy będącego aktualnym właścicielem;
- używać `tw-btn tw-btn-primary` dla zgody i `tw-btn tw-btn-danger` albo `tw-btn tw-btn-secondary` dla odmowy zgodnie z semantyką z `UI_STANDARDS.html`;
- mieć ikony ze słownika standardów, etykiety tekstowe, `title` i stan niedostępności po decyzji;
- nie używać inline style ani nowych arkuszy CSS;
- po decyzji zastąpić przyciski informacją o wyniku i odświeżyć stan dokumentu.

Dodać obsługę kliknięcia w istniejącym delegowanym systemie handlerów czatu. Akcja powinna korzystać z osobnego, zabezpieczonego endpointu lub jawnego polecenia WebSocket, z idempotentną odpowiedzią dla ponowionego żądania.

Jeśli decyzja ma być dostępna również przy odświeżeniu lub na innej karcie, wiadomość musi być renderowana z aktualnego payloadu historii, a nie tylko z jednorazowego zdarzenia WebSocket.

## 7. Decyzja i automatyczne przejęcie

Wydzielić w `core` serwis z operacjami `approve`, `reject` i `expire_pending_requests`. Każda operacja powinna:

- działać w `transaction.atomic()` i blokować wniosek oraz treść;
- sprawdzać status, uprawnionego użytkownika, aktualnego autora i termin;
- być bezpieczna przy dwóch równoczesnych kliknięciach lub jednoczesnym zadaniu schedulera;
- ustawiać właściciela tylko po pozytywnej, ponownej walidacji;
- zapisywać wynik i czas decyzji;
- wysyłać komunikat systemowy do właściwej rozmowy oraz aktualizować stan obu stron.

Automatyzację zrealizować jako istniejące zadanie Django uruchamiane przez obecny APScheduler, najlepiej w osobnym commandzie odpowiedzialnym wyłącznie za wygaszanie wniosków. Job powinien wyszukiwać `pending` z `deadline_at <= now`, przetwarzać je małymi partiami i być idempotentny. Nie wykonywać przejęcia w samym GET widoku dokumentu.

## 8. UI zgodne ze standardami

- Przycisk na stronie treści powinien korzystać ze wspólnego toolbaru/komponentu `tw-btn`, a nie z modułowej klasy CSS.
- Potwierdzenie zgłoszenia może użyć istniejącego `tw-modal`, jeśli potrzebne jest wyjaśnienie konsekwencji; bez nowego komponentu modalowego.
- Status oczekujący, zaakceptowany i odrzucony powinien korzystać z istniejących `tw-badge-status` lub `tw-alert-*` oraz wspólnych tokenów kolorów.
- Przyciski akcji w czacie powinny być czytelne na mobile, umieszczone w dolnej/prawej części grupy akcji, z pełnymi etykietami tekstowymi i bez polegania wyłącznie na kolorze.
- Jeżeli okaże się konieczny nowy wzorzec „wiadomość z akcjami”, przed implementacją udokumentować go w `docs/UI_STANDARDS.html`, `docs/UI_DEVELOPMENT_GUIDE.md` i odpowiednim przewodniku Tailwind; klasy dodać wyłącznie do `home/static/home/css/tailwind.css` i safelisty, gdy są generowane dynamicznie.
- Wszystkie nowe teksty oznaczyć `{% trans %}`/`gettext`, a po implementacji uzupełnić lokalizacje.

## 9. Testy

### Backend

- kwalifikacja: właściwy typ treści, brak właściciela/porzucenie, treść systemowa i usunięta;
- jeden aktywny wniosek mimo wielokrotnego POST i wyścigu równoległych żądań;
- utworzenie wiadomości w istniejącym DM oraz brak wiadomości dla treści bez właściciela;
- zgoda właściciela przejmuje treść natychmiast;
- sprzeciw kończy wniosek i nie zmienia właściciela;
- brak reakcji do `deadline_at` (po 48 godzinach) przejmuje treść przez zadanie;
- próba decyzji przez zgłaszającego, osobę trzecią, nieaktualnego właściciela lub po zakończeniu wniosku jest odrzucana;
- równoczesna decyzja i wygaszenie nie powodują podwójnego przejęcia;
- anulowanie, jeśli zostanie zaakceptowane, nie zmienia właściciela;
- URL dokumentu i stan statusu są poprawne dla zalogowanego i niezalogowanego użytkownika.

### Czat i frontend

- payload historii i zdarzenie WebSocket zawierają ten sam strukturalny stan akcji;
- przyciski są widoczne wyłącznie właściwemu właścicielowi;
- kliknięcie blokuje przyciski, obsługuje błąd i odświeża wynik bez duplikowania wiadomości;
- ponowne otwarcie pokoju pokazuje wynik decyzji;
- testy JS dla renderowania, delegowania kliknięć i stanów `pending/approved/rejected/expired`;
- test dostępności: etykiety, focus, `aria-disabled`/`disabled`, brak komunikatu opartego wyłącznie na kolorze.

## 10. Kolejność implementacji

1. Potwierdzić definicję porzucenia, zakres pierwszej wersji, okres 48 godzin i zasady braku właściciela.
2. Zaprojektować kontrakt adaptera własności i model wniosku w `core`; uzgodnić migrację przed jej wykonaniem.
3. Zaimplementować serwis domenowy oraz adapter `board.Post`, endpoint zgłoszenia i status w widoku dokumentu.
4. Dodać integrację z istniejącym DM i systemowym payloadem wiadomości.
5. Dodać decyzje właściciela w endpointach/WebSocket oraz renderer i handlery w czacie.
6. Dodać command wygaszający i pojedynczy wpis w istniejącym `zzz/scheduler.py`.
7. Uzupełnić tłumaczenia, testy backendu/JS i standard UI, jeśli powstanie nowy wzorzec.
8. Wykonać weryfikację zgodną z `AGENTS.md`: dotknięte testy przez `.venv\Scripts\python.exe`, a przy zmianach UI także `npm run build:css`, `scripts/regression_scan.py` i `scripts/ui_guard.py`.

## 11. Kryteria akceptacji

- Zalogowany użytkownik może zgłosić przejęcie kwalifikującej się porzuconej treści tylko raz naraz.
- Właściciel dostaje prywatną wiadomość z linkiem i działającymi przyciskami zgody/sprzeciwu.
- Zgoda przejmuje treść, sprzeciw ją pozostawia, a brak reakcji przez 48 godzin przejmuje ją automatycznie.
- Wszystkie trzy rozstrzygnięcia są idempotentne, audytowalne i odporne na wyścigi.
- Po rozstrzygnięciu żaden użytkownik nie widzi nieaktualnych przycisków ani nie może przejąć treści przez stary request.
- Rozwiązanie korzysta z istniejącego czatu, schedulerowego mechanizmu, wspólnego pipeline’u Tailwind i istniejących komponentów UI, bez dublowania systemów.
