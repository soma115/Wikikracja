# Plan: należności i opłaty cykliczne

## Cel i nazewnictwo

Wprowadzić w Wikikracji ewidencję oczekiwanych płatności, która obsłuży:

- składki i inne kwoty należne od członków na rzecz wspólnoty;
- faktury i opłaty za usługi kupowane przez wspólnotę, w tym przyszłe terminy płatności;
- jednorazowe oraz cykliczne opłaty, np. roczne.

W interfejsie używać nazwy **Należności**. Funkcja nie wystawia faktur w znaczeniu formalnych dokumentów księgowych — rejestruje oczekiwane płatności i ich stan. Kierunek płatności rozróżnia, czy kwota ma wpłynąć do wspólnoty, czy zostać przez nią zapłacona.

## Rozpoznany kontekst i proponowane granice

- `bookkeeping.Transaction` zapisuje faktyczne operacje finansowe, natomiast `resources.Entity` opisuje zasoby rzeczowe i aktywa finansowe. Obecna lista `/bookkeeping/resource/` dotyczy ofert i potrzeb członków, nie płatności.
- Należności powinny być częścią finansów (`bookkeeping`) i korzystać z istniejącego aktywa finansowego/waluty, partnerów i nawigacji finansowej. Nie należy dopisywać faktur do encji zasobu ani udawać, że są transakcjami.
- Oznaczenie opłaty jako zapłaconej wymaga utworzenia powiązanej `Transaction`. Transakcja oraz zmiana stanu terminu muszą zostać zapisane atomowo; wpływają więc na istniejące raporty finansowe.
- Powiadomienia należy integrować z `core.notifications`, konfiguracją `PUSH_EVENTS` i istniejącymi preferencjami Finansów. E-mail i push kierować tylko do odbiorców danej opłaty, bez rozsyłania do wszystkich aktywnych użytkowników.
- Dla faktur zewnętrznych użytkownik wybrał ręczne wskazywanie odbiorców przypomnienia.

## Ustalenia

- Funkcja należy do **Finansów** i w interfejsie nazywa się **Należności**.
- Każdy aktywny członek może tworzyć plany i oznaczać terminy jako opłacone.
- Plan definiuje domyślną kategorię i aktywo finansowe; formularz potwierdzenia transakcji pozwala skorygować wszystkie jej pola.
- Dla składki tworzonej dla konkretnego członka Partner jest wybierany ręcznie podczas potwierdzania płatności; nie łączymy automatycznie profilu z rekordem Partner.
- Przy generowaniu okresu składkowego tworzy się termin dla każdego członka aktywnego w tym momencie. System utrzymuje tylko jeden kolejny okres naprzód.
- Przypomnienie o nieopłaconym terminie wysyłane jest w dniu płatności. Odbiorcami rachunku zewnętrznego są osoby wskazane ręcznie.
- Usunięcie transakcji powiązanej z terminem przywraca termin do stanu oczekującego.
- Powiadomienia e-mail respektują istniejące ustawienia wypisania i preferencje.
- Push respektuje preferencję Finansów oraz ustawienia urządzeń, zgodnie z istniejącym kontraktem powiadomień.
- Zmiana kwoty planu aktualizuje najbliższy wygenerowany, przyszły i nieopłacony termin; starsze terminy pozostają bez zmian.
- Jeśli cykliczny dzień nie występuje w miesiącu/roku, termin przypada na ostatni dostępny dzień tego okresu.
- W pierwszej wersji cykle są jednorazowe, miesięczne lub roczne. Zakończenie planu zatrzymuje kolejne generowanie, ale nie usuwa ani nie anuluje już utworzonych terminów.

## Model funkcjonalny

Proponowany podział:

1. **Plan opłaty** — definicja jednorazowej lub cyklicznej opłaty: nazwa, kierunek (wpłata do wspólnoty / płatność wspólnoty), kwota, aktywo finansowe, partner opcjonalny, częstotliwość, następny termin i aktywność planu.
2. **Termin płatności** — konkretna należność za dany okres, z terminem, kwotą, kategorią, aktywem finansowym i płatnikiem/odbiorcami. Dla składek członkowskich powstaje osobny termin dla każdego aktywnego członka w chwili generowania okresu; dla opłaty zewnętrznej — jeden termin z ręcznie wybranymi osobami odpowiedzialnymi za jej opłacenie.
3. **Transakcja** — powiązany z terminem zapis w `bookkeeping.Transaction`. Dla składki jest to wpływ; dla rachunku wspólnoty — wydatek. W formularzu potwierdzenia wartości z planu/terminu są domyślne, a użytkownik może zmienić wszystkie pola transakcji, w tym Partnera, kategorię, aktywo, kwotę, datę i notatkę.
4. Stan terminu: **oczekuje**, **opłacono** albo **anulowano**. Przy oznaczeniu jako opłacony zapisuje się transakcję, datę oraz użytkownika potwierdzającego. Termin i transakcja muszą być powiązane tak, aby usunięcie transakcji przywracało termin do oczekujących.

Przyszłe terminy powinny być widoczne przed datą płatności. Plan cykliczny zapewnia jeden kolejny okres i po jego nadejściu generuje następny. Lista członków jest ustalana w chwili generowania okresu i nie zmienia się samoczynnie po późniejszej zmianie członkostwa. Każdy termin zachowuje migawkę danych; zmiana kwoty planu aktualizuje tylko najbliższy wygenerowany termin, jeśli nadal oczekuje na płatność.

W pierwszym zakresie częstotliwość obejmuje opłatę jednorazową oraz powtarzanie miesięczne i roczne. Jeśli wskazany dzień nie występuje w danym miesiącu lub roku, termin przypada na ostatni dostępny dzień tego okresu.

## Fazy

### Faza 1 — doprecyzowanie zasad

- [x] Umieścić funkcję w Finansach i używać nazwy „Należności”.
- [x] Ustalić, że każdy aktywny członek może zarządzać planami i potwierdzać płatności.
- [x] Ustalić naliczanie składek dla członków aktywnych w chwili generowania okresu oraz utrzymywanie jednego kolejnego okresu.
- [x] Ustalić wysyłkę przypomnienia w dniu terminu oraz ręczny wybór odbiorców dla rachunku zewnętrznego.
- [x] Ustalić, że potwierdzenie płatności tworzy transakcję z formularza wstępnie wypełnionego danymi planu, z możliwością edycji wszystkich pól.
- [x] Ustalić ręczny wybór Partnera przy potwierdzaniu składki oraz przywrócenie terminu do oczekujących po usunięciu powiązanej transakcji.
- [x] Ustalić respektowanie istniejących ustawień wypisania e-maili.
- [x] Ustalić respektowanie preferencji push Finansów i ustawień urządzeń.
- [x] Ustalić, że zmiana kwoty aktualizuje najbliższy wygenerowany, nieopłacony termin.
- [x] Ustalić przesuwanie daty na ostatni dostępny dzień okresu, jeśli wskazany dzień nie występuje.
- [x] Ograniczyć pierwszą wersję do opłaty jednorazowej oraz cyklu miesięcznego i rocznego.
- [x] Ustalić, że zakończenie planu zatrzymuje generowanie, ale zachowuje już utworzone terminy.

### Faza 2 — dane i reguły domenowe

- [ ] Dodać modele planu opłaty oraz konkretnych terminów płatności w istniejącej aplikacji finansowej, z walutą/aktywem finansowym i opcjonalnym partnerem.
- [ ] Obsłużyć kierunek płatności, kategorię, aktywo finansowe, płatnika albo listę osób odpowiedzialnych, termin, kwotę, stan, datę potwierdzenia i osobę potwierdzającą.
- [ ] Powiązać termin z transakcją księgową; przy potwierdzeniu zapisywać transakcję i zmianę stanu w jednej operacji atomowej.
- [ ] Zaprojektować generowanie jednego kolejnego okresu tak, aby kolejne uruchomienia były idempotentne, nie tworzyły duplikatów i obejmowały członków aktywnych w chwili generowania.
- [ ] Określić techniczną regułę archiwizacji planu: zachować historię i terminy, nie usuwać powiązanych transakcji.
- [ ] Przy usunięciu powiązanej transakcji przywracać termin do oczekujących i umożliwiać ponowne potwierdzenie.
- [ ] Przygotować migrację danych dopiero po zatwierdzeniu modelu; nie przekształcać istniejących transakcji w należności automatycznie.

### Faza 3 — widoki i obsługa skarbnika

- [ ] Dodać widok listy z podziałem na oczekujące, przyszłe, opłacone i anulowane oraz widoczną kwotą, walutą, terminem i kierunkiem płatności.
- [ ] Dodać tworzenie i edycję planu oraz podgląd konkretnych terminów; jasno odróżniać wpłaty członków od rachunków wspólnoty.
- [ ] Dodać formularz potwierdzenia transakcji z wartościami domyślnymi z terminu/planu; pozwolić edytować wszystkie pola, w tym Partnera wybieranego dla danej składki.
- [ ] Udostępnić zarządzanie planami aktywnym członkom; zabezpieczyć akcję POST przed podwójnym utworzeniem transakcji.
- [ ] Pokazać, kto i kiedy oznaczył termin jako opłacony oraz link do powiązanej transakcji.
- [ ] Zastosować istniejące wzorce UI i komponenty finansów, bez nowych arkuszy CSS ani własnych wzorców bez uzasadnienia.

### Faza 4 — przypomnienia i harmonogram

- [ ] Dodać przypomnienia wysyłane w dniu płatności do wskazanych płatników lub ręcznie wybranych odbiorców opłat zewnętrznych.
- [ ] Wysłać e-mail i push z linkiem do właściwego terminu; push dodać do katalogu istniejących zdarzeń Finansów i przekazywać do dispatcher’a dokładne ID odbiorców.
- [ ] Uzgodnić i wdrożyć śledzenie wysłanych przypomnień per termin, odbiorca i kanał, aby ponowne uruchomienie zadania nie powodowało duplikatów oraz aby błąd jednego kanału nie blokował drugiego.
- [ ] Dodać cykliczne zadanie do istniejącego schedulera dopiero po osobnym potwierdzeniu zmiany procesu cyklicznego; zadanie ma utrzymywać jeden kolejny termin, generować nowe okresy i wysyłać należne przypomnienia bez wielokrotnego przetwarzania.
- [ ] Obsłużyć brak konfiguracji Firebase bez awarii e-maili; respektować preferencje powiadomień oraz globalne wypisanie zgodnie z istniejącymi kontraktami.

### Faza 5 — testy i wdrożenie

- [ ] Dodać testy logiki terminów: miesięczne/roczne cykle, przesuwanie dat granicznych, edycję planu, tworzenie przyszłych terminów i brak duplikatów.
- [ ] Dodać testy statusów, uprawnień, przypisania odbiorców, atomowego utworzenia transakcji przy oznaczaniu płatności oraz zachowania po anulowaniu i usunięciu transakcji.
- [ ] Dodać testy powiadomień: wyłącznie wskazani odbiorcy, deduplikacja, niezależność e-maila i push, preferencje oraz wypisanie.
- [ ] Uruchomić testy dotkniętych modułów i wymagane kontrole zgodnie z `AGENTS.md`; przy zmianach UI wykonać również wymagane kontrole frontendowe.
- [ ] Zaktualizować dokumentację kontraktu powiadomień po ustaleniu i wdrożeniu nowego zdarzenia.

## Status

Ustalenia powyżej pochodzą z odpowiedzi użytkownika. Plan wdrożenia pozostaje niezrealizowany. Nie wprowadzono modeli, migracji, zmian w schedulerze, powiadomieniach ani interfejsie.
