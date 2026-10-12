# Zmienna aktywność obywateli

## Cel i zakres

Aktywność grupy zmienia się w czasie: od okresów ciszy po okresy intensywnych rozmów, zmian i decyzji. Mechanizmy aplikacji powinny uwzględniać oba skraje, ale nie sprowadzać wszystkich zjawisk do jednego wskaźnika.

Należy odróżnić:

1. **Liczebność grupy** — ilu jest aktywnych członków.
2. **Udział obywateli** — jaka część członków uczestniczy w rozmowach, pracy i decyzjach.
3. **Natężenie zdarzeń** — ile wiadomości, zmian i powiadomień pojawia się w jednostce czasu.

Obecność online nie jest równoznaczna z uczestnictwem obywatelskim. Częste logowania nie dowodzą udziału w głosowaniach, a dużo wiadomości nie musi oznaczać szerokiego zaangażowania.

Dokument ma dwie odrębne części: **stan obecny**, wynikający z przeglądu projektu, oraz **propozycje**, które wymagają dalszych decyzji. Nie jest zgodą na automatyczną zmianę reguł głosowania, członkostwa ani innej krytycznej logiki biznesowej.

# 1. Stan obecny

## 1.1. Głosowania i podejmowanie decyzji

- Parametry zmieniane przez referenda obejmują liczbę wymaganych podpisów oraz czasy zbierania podpisów, dyskusji i referendum. Wartości domyślne to odpowiednio 2 podpisy, 365 dni, 3 dni i 3 dni (`site_settings/models.py`, pola modelu `SiteParameters`).
- Centralny rejestr określa dozwolone zakresy. Liczba wymaganych podpisów ma zakres 2–20, a czasy są konfigurowalne w szerokich granicach (`site_settings/params.py`, `PARAM_SPECS`).
- Po osiągnięciu progu podpisów wniosek przechodzi do dyskusji; obowiązuje też dwudniowy okres oczekiwania od ostatniej modyfikacji (`glosowania/management/commands/vote.py`, obsługa `PROPOSITION`).
- Wynik referendum opiera się na większości oddanych głosów: `za > przeciw` zatwierdza propozycję. Kod nie wymaga określonego udziału obywateli (quorum) (`glosowania/management/commands/vote.py`, obsługa zamknięcia referendum).
- Głosy są anonimowe i ujawniane oraz zliczane po zamknięciu referendum.
- Liczba podpisów oraz wyniki `za` i `przeciw` są polami `SmallIntegerField` (`glosowania/models.py`). To potencjalne ograniczenie przy dużej skali i niektórych silnikach baz danych; nie należy zakładać, że jest bieżącym problemem w używanym SQLite.

**Znaczenie skrajnych sytuacji:** przy niskiej aktywności krótkie okresy dyskusji i głosowania mogą utrudniać udział, a brak quorum pozwala, by wynik zależał od małej liczby głosujących. Przy wysokiej aktywności lub dużej liczebności stały próg podpisów może nie odpowiadać skali grupy; obecny limit 20 ogranicza jego podnoszenie.

## 1.2. Czat

- Maksymalna długość wiadomości wynosi domyślnie 1500 znaków i jest konfigurowana ustawieniem `MESSAGE_MAX_LENGTH` (`zzz/settings.py`).
- Historia jest pobierana porcjami po 100 wiadomości (`chat/command_handlers.py`, `join` i `fetch_messages`).
- W zwykłym przepływie czatu nie znaleziono trybu powolnego ani limitu tempa wysyłania wiadomości. Wysyłanie sprawdza dostęp do pokoju i waliduje załączniki, ale nie ogranicza liczby wiadomości na użytkownika w czasie (`chat/command_handlers.py`).
- PUSH czatu ma osobny cooldown dla pary użytkownik–pokój: pierwsze powiadomienie jest natychmiastowe, a kolejne w ciągu godziny są koaleskowane do najnowszego (`chat/notification_queue.py`, `CHAT_PUSH_COOLDOWN_SECONDS` i `dispatch_or_defer_chat_notification`). Otwarcie pokoju czyści oczekujące powiadomienie i cooldown.
- Pokoje publiczne są archiwizowane po okresie bez aktywności i usuwane później; parametry domyślne wynoszą 9 i 360 dni. Pokoje powiązane z obiektami oraz chronione są wyłączone z części operacji usuwania (`site_settings/params.py`, `site_settings/models.py`, `chat/management/commands/chat_rooms.py`).

**Znaczenie skrajnych sytuacji:** obecne ograniczanie dotyczy powiadomień PUSH, a nie tempa rozmowy. Przy intensywnym ruchu odbiorca może dostać tylko najnowszy alert z pokoju, mimo wielu nowych wiadomości. Przy małym ruchu pojedyncza wiadomość może pozostać niezauważona.

## 1.3. Powiadomienia PUSH, WebSocket i e-mail

- Obywatel ustawia częstotliwość digestu e-mail: codziennie, tygodniowo, miesięcznie albo nigdy (`obywatele/models.py`, `EmailFrequency`).
- Preferencje PUSH są podzielone na moduły, m.in. czat, głosowania, wydarzenia, zadania i dokumenty. Osobno można wyłączyć urządzenia mobilne lub komputerowe (`obywatele/models.py`).
- `PUSH_EVENTS` w `zzz/settings.py` włącza niezależnie kanały FCM i WebSocket dla typów zdarzeń. Niektóre zdarzenia utworzenia są rozsyłane, a część edycji lub argumentów ma kanały wyłączone.
- Wspólna dokumentacja powiadomień wskazuje, że odbiorcą jest aktywny użytkownik z włączoną preferencją modułu i że wysyłka nie jest ogólnie ograniczona do osób powiązanych z danym obiektem (`docs/POWIADOMIENIA_EMAIL_PUSH_AKTYWNOSC.md`, sekcja „PUSH i WebSocket”). Istnieją wyjątki adresowane do konkretnych osób, np. koordynatora zadania (`core/notifications.py`, odbiorcy `task_helper_joined` i `task_status_changed`).
- Digest agreguje zmiany dotyczące tego samego obywatela, pokoju lub obiektu (`core/services/feed.py`, `_digest_group_key` i `build_user_digest`).
- Aktualizacje ważnego dokumentu mają osobny throttle; nie jest to ogólny limit zdarzeń (`core/notifications.py`, `_claim_post_update_notification`).

**Znaczenie skrajnych sytuacji:** pojedyncze powiadomienie może być szczególnie cenne w okresie ciszy. Przy dużej liczbie zmian szeroka dystrybucja może powodować zmęczenie alertami. Istniejący digest i cooldown PUSH ograniczają część hałasu, ale agregacja nie jest jednolita dla wszystkich modułów.

## 1.4. Feed, pulpit i historia aktywności

- Surowy feed obejmuje 90 dni aktywności i jest cache’owany przez godzinę (`core/services/feed.py`, `FEED_DAYS` i `FEED_CACHE_TTL`).
- Pulpit pokazuje sześć ostatnich pozycji poza wydarzeniami (`home/services/dashboard.py`, `last_feed_items`).
- Widok `/aktywnosc/` generuje i filtruje listę; w analizowanym widoku nie znaleziono stronicowania (`home/views.py`, `activity_page`).
- Digest e-mail liczy się od poprzedniego wysłania, a jego częstotliwość jest osobną preferencją (`home/management/commands/send_email_digest.py`). Jego zakresu nie należy utożsamiać z 90-dniowym feedem.

**Znaczenie skrajnych sytuacji:** przy niskiej aktywności starsze wpisy po 90 dniach przestają pojawiać się w zwykłym feedzie, choć mogą być dostępne w modułach źródłowych lub w zakładkach. Przy wysokiej aktywności długa lista utrudnia odnalezienie ważnych wpisów i może zwiększać ilość danych renderowanych naraz.

## 1.5. Obecność, członkostwo i reputacja

- Profil zapisuje czas i źródło ostatniej obecności (`obywatele/models.py`, `last_presence_at`, `last_presence_source`).
- Statusy obecności rozróżniają użytkownika obecnego, niedawnego i nieaktywnego; katalog obywateli umożliwia filtrowanie po obecności w ostatnich 7 dniach (`core/presence.py`, `obywatele/views.py`, `zzz/settings.py`).
- Dashboard obywateli liczy osoby aktywne w ostatnich 30 dniach i procent populacji (`obywatele/dashboard.py`).
- Próg reputacji przyjmowania członków zależy od liczebności małej grupy. Przy małej populacji próg jest tymczasowo obniżany, a nowy obywatel może automatycznie przyznawać istniejącym członkom reputację (`obywatele/views.py`, `required_reputation`; `obywatele/management/commands/count_citizens.py`, `grant_automatic_reputation`). To adaptacja do liczebności, nie bieżącego tempa aktywności.
- Usuwanie nieaktywnych kont jest odrębnym procesem opartym na statusie konta i `last_login`, z okresem ustawianym parametrem (domyślnie 30 dni). Nie mierzy udziału aktywnych obywateli w grupie (`obywatele/management/commands/count_citizens.py`, `delete_inactive_users`).

**Znaczenie:** projekt ma sygnały obecności technicznej, ale nie ma wspólnego obrazu udziału obywatelskiego obejmującego głosowania, zadania i rozmowy. Sama obecność online nie wystarcza do uznania obywatela za zaangażowanego lub niezaangażowanego.

## 1.6. Tworzenie treści i skalowanie

- Część treści ma jawne limity, np. propozycje i argumenty w głosowaniach (`glosowania/models.py`, `glosowania/forms.py`), opis ankiety do 3000 znaków oraz opcja ankiety do 200 znaków (`ankiety/models.py`, `ankiety/forms.py`). Ankieta wymaga co najmniej dwóch opcji, ale formularz nie ma widocznego limitu ich całkowitej liczby (`ankiety/forms.py`, `clean_options_text`).
- Opis zadania (`tasks/models.py`, `Task.description`), treść dokumentu (`board/models.py`, `Post.text`) i opis wydarzenia (`events/models.py`, `Event.description`) nie mają widocznego wspólnego limitu długości.
- Codzienny proces głosowań wywołuje tworzenie pokoi prywatnych dla par aktywnych użytkowników (`glosowania/management/commands/vote.py`, koniec `run`). `Room.create_all_one2one_rooms()` iteruje po parach użytkowników (`chat/models.py`), więc potencjalna liczba par rośnie kwadratowo wraz z liczebnością grupy.
- Rozsyłanie powiadomień do użytkowników z daną preferencją skaluje się z wielkością grupy; wysokie tempo zdarzeń może dodatkowo zwiększać ten koszt.

**Znaczenie:** limity długości, liczby elementów i tempa dodawania to odrębne zagadnienia. Obecnie nie ma wspólnej warstwy limitów liczby wpisów ani tempa ich tworzenia w modułach. Ograniczenia wydajnościowe zależą zarówno od liczebności, jak i natężenia ruchu.

## 1.7. Podsumowanie stanu obecnego

1. Projekt już reguluje część zachowań: parametry głosowań, preferencje powiadomień, digest, cooldown PUSH czatu, archiwizację pokoi i próg reputacji zależny od liczebności małej grupy.
2. Te mechanizmy są konfigurowane osobno; aplikacja nie wykrywa wspólnego trybu niskiej lub wysokiej aktywności i nie dostosowuje do niego zachowania.
3. Największe różnice między skrajnymi scenariuszami dotyczą udziału w głosowaniach, tempa czatu, hałasu powiadomień i przeglądalności feedu.
4. Wskaźniki obecności nie są równoważne udziałowi obywatelskiemu.

# 2. Propozycje

## 2.1. Podstawa: osobne, wygładzone wskaźniki

Nie wprowadzać jednego wskaźnika „aktywności grupy”. Wyliczać niezależne miary, a następnie dostosowywać tylko tę funkcję, której dana miara dotyczy:

- **udział obywatelski:** udział członków w głosowaniach i działaniach wymagających decyzji;
- **aktywność uczestników:** liczba unikalnych osób uczestniczących w rozmowie lub pracy;
- **ruch komunikacyjny:** tempo wiadomości osobno dla pokoju;
- **ruch treści:** nowe i aktualizowane obiekty na moduł;
- **liczebność:** liczba aktywnych członków, raportowana osobno.

Do decyzji automatycznych używać zagregowanych trendów w krótszym i dłuższym oknie (np. tygodniowym i miesięcznym), nie pojedynczych zdarzeń. Przed wdrożeniem trzeba określić, które sygnały są wiarygodne, jak wykluczać działania systemowe i jak traktować sezonowość. Obecność, liczba wiadomości i frekwencja w głosowaniu nie powinny być łączone bez uzasadnienia w jeden „wynik aktywności”.

## 2.2. Adaptacja według obszaru

| Obszar | Niska aktywność | Wysoka aktywność |
|---|---|---|
| **Powiadomienia** | Przypomnienia o ważnych sprawach i terminach, z rozsądnymi odstępami | Grupowanie seryjnych aktualizacji i ograniczanie niepilnych alertów |
| **Czat** | Nie nakładać ograniczeń tempa; rozważyć dłuższą ekspozycję nieaktywnych, ważnych pokoi | Opcjonalny slow mode per pokój albo grupowanie serii wiadomości |
| **Feed** | Dłużej eksponować ważne sprawy i ułatwiać odnajdywanie starszych wpisów | Stronicować lub ładować porcjami, wyróżniać ważne elementy, ograniczać powtarzalność |
| **Zadania** | Dawać zespołowi więcej czasu na zebranie wymaganej liczby osób | Informować koordynatora o zainteresowaniu i ułatwiać zarządzanie większym zespołem |
| **Ankiety i konsultacje** | Przypominać o terminie, gdy udział jest mały | Ułatwiać przegląd dużej liczby opcji i odpowiedzi |
| **Retencja** | Rozważyć dłuższą ekspozycję lub retencję treści, do których grupa wraca rzadko | Priorytetem jest sprawne przeglądanie i archiwizacja, nie samo skracanie historii |

To kierunki, nie gotowe wartości progów. W pierwszej kolejności warto rozwijać powiadomienia, przypomnienia i widoczność treści: są mniej ingerujące niż zmiana reguł decyzyjnych.

## 2.3. Konkretne mechanizmy do rozważenia

### Powiadomienia

- Grupować powtarzające się zmiany dla tego samego obiektu lub pokoju.
- Rozróżniać zdarzenia pilne od informacyjnych; niepilne aktualizacje mogą trafiać do podsumowania, a ważne zachować jako natychmiastowe.
- Tam, gdzie to właściwe, zawężać odbiorców do osób powiązanych z obiektem, z zachowaniem preferencji użytkownika i istniejących wyjątków.
- Przypomnienia ustalać względem terminu i udziału, z limitem częstotliwości, aby niska aktywność nie powodowała spamu.
- Nie zabierać użytkownikom obecnego wyboru częstotliwości digestu ani preferencji modułowych bez osobnej decyzji.

### Czat

- Rozważyć opcjonalny slow mode per pokój, niezależny od obecnego godzinnego cooldownu PUSH.
- Włączać go wyłącznie po utrzymującym się wysokim ruchu w danym pokoju, a nie z powodu jednego krótkiego skoku.
- Określić widoczny czas oczekiwania, warunki aktywacji i automatycznego wyłączenia oraz czy i jak uczestnicy mogą go nadpisać.
- Rozważyć wyjątki dla wiadomości o charakterze systemowym lub pilnych; nie ograniczać odczytu historii.
- Przy niskiej aktywności unikać ograniczania publikowania i rozważyć wydłużenie okresu, zanim ważny pokój zostanie zarchiwizowany.

### Głosowania i konsultacje

- Analizować frekwencję oraz czas do osiągnięcia progów, zanim zaproponuje się automatyczne dostosowanie.
- Można rozważyć wydłużanie przyszłych okresów dyskusji lub głosowania na podstawie uprzednio uzgodnionej polityki.
- Nie zmieniać warunków referendum już po jego rozpoczęciu.
- Quorum, próg przyjęcia, progi podpisów i inne zasady demokracji zmieniać wyłącznie w drodze decyzji społeczności. To nie powinno być automatyczną reakcją na krótkotrwały spadek aktywności.

### Zadania i praca zespołowa

- Jeśli wymagane jest zebranie zespołu, przy niskim zainteresowaniu lepiej rozważyć dodatkowy czas, informację dla koordynatora lub ponowne zaproszenie do udziału niż automatycznie obniżać wymagania.
- Wymagana liczebność zespołu powinna wynikać ze specyfikacji danego zadania. Nie zmieniać jej po cichu na podstawie bieżącej aktywności, zwłaszcza po rozpoczęciu realizacji.
- Przy większym zainteresowaniu pokazywać czytelnie wielkość zespołu i stan zgłoszeń; ewentualny limit miejsc powinien być jawny dla konkretnego zadania.
- W rankingach koordynatorów surowe sumy ukończonych zadań mogą faworyzować osoby aktywne dłużej lub w okresie większego ruchu. Rozważyć prezentację okresu, liczby zamkniętych zadań i ocen obok siebie, zamiast pojedynczej liczby oderwanej od kontekstu.

### Feed i limity treści

- Przy dużym wolumenie wprowadzić stronicowanie lub ładowanie porcjami, zachowując filtry, status przeczytania i zakładki.
- Przy małym wolumenie ułatwić dostęp do istotnej historii wykraczającej poza bieżące okno feedu.
- Traktować osobno limit długości pojedynczego pola, liczbę elementów (np. opcji ankiety) i tempo ich tworzenia.
- Nie wprowadzać ogólnych limitów treści wyłącznie dlatego, że grupa jest aktywna. Limity mają uzasadnienie przy problemie z ergonomią, nadużyciami lub zmierzonym kosztem technicznym.

## 2.4. Zasady automatycznego przełączania

Każdy automatyczny mechanizm powinien być:

- **lokalny:** wpływa na dany pokój, moduł lub proces, a nie całą instancję bez potrzeby;
- **przewidywalny:** obywatele widzą, co się zmieniło, dlaczego i kiedy nastąpi powrót;
- **odwracalny:** ma warunki wyłączenia i nie pozostawia trwałych skutków ubocznych;
- **wygładzony:** opiera się na trendzie, z osobnym progiem aktywacji i dezaktywacji oraz minimalnym okresem utrzymania ustawienia;
- **bezpieczny dla trwających procesów:** nie zmienia po rozpoczęciu głosowania jego terminów ani warunków;
- **zgodny z decyzjami społeczności:** automatyzacja wykonuje wcześniej przyjętą politykę, a nie zastępuje głosowanie w sprawie polityki.

Przykład: utrzymujący się wysoki ruch może czasowo włączyć slow mode w jednym pokoju; nie zmienia przez to preferencji powiadomień użytkowników ani parametrów referendum w całej grupie.

## 2.5. Czego nie dostosowywać automatycznie

Bez osobnej decyzji społeczności nie należy automatycznie zmieniać:

- quorum ani zasad liczenia wyniku referendum;
- progów członkostwa i reputacji;
- anonimowości, weryfikowalności ani okresu ujawnienia głosów;
- wymaganej liczby osób do realizacji już rozpoczętego zadania;
- terminów lub warunków procesów, które już trwają;
- retencji lub usuwania danych w sposób, który może odebrać obywatelom dostęp do istotnych ustaleń.

Automatyzacja nie powinna też traktować braku logowania jako braku wartościowego udziału ani promować samej liczby wiadomości jako miary zaangażowania.

## 2.6. Etapy dalszej pracy

1. **Obserwowalność:** przygotować raport zagregowanych wskaźników bez wpływu na zachowanie aplikacji. Oddzielnie pokazać liczebność, udział obywateli i natężenie zdarzeń.
2. **Bezpieczne dostosowania:** poprawić agregację powiadomień, przypomnienia o terminach oraz przeglądalność feedu.
3. **Regulacja lokalna:** ocenić opcjonalny slow mode per pokój i jawne sygnały zainteresowania zespołami zadań.
4. **Polityka demokratyczna:** dopiero po konsultacji określić, czy i jak niska frekwencja ma wpływać na przyszłe okresy głosowań, quorum lub progi.
5. **Skalowanie:** zmierzyć koszt tworzenia pokoi DM i rozsyłania powiadomień przy rosnącej liczebności przed zmianą architektury.

## 2.7. Decyzje wymagane przed wdrożeniem

- Które miary mają oznaczać aktywność obywatelską, a które wyłącznie ruch techniczny?
- Czy użytkownicy chcą, by aplikacja sama zmieniała wybrane zachowania, czy tylko sugerowała ustawienia do zatwierdzenia?
- Które zmiany są akceptowalne bez referendum, a które zawsze wymagają decyzji grupy?
- Jak obywatel może poznać powód, czas trwania i skutki aktywnego dostosowania?
- Jak obsługiwać okresy sezonowe, nowych członków i małe grupy, dla których wskaźniki procentowe mogą być niestabilne?
