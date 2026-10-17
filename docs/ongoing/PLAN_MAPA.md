# Mapa społeczności

Status: plan

## Cel i zasady MVP

Jedna mapa pokazuje obywateli, partnerów i fizyczne aktywa. Dla każdego typu, jeśli podano szczegółowy adres, mapa używa lokalizacji adresowej; w przeciwnym razie pokazuje lokalizację orientacyjną na poziomie miasta. Szczegółowe pola adresowe są opcjonalne. Nie używamy GPS.

Przyjęte decyzje:

- Zalogowani, aktywni obywatele widzą wszystkie kwalifikujące się punkty, typy, nazwy, adresy i linki.
- Goście widzą wyłącznie punkty mapy: bez typów, nazw, adresów, liczników, linków i interakcji. Punkty o tych samych współrzędnych są scalone.
- Kraj profilu wybiera się z katalogu `Country`; domyślnie Polska.
- Stos mapowy: Leaflet + kafelki OpenStreetMap + geokodowanie Nominatim.
- Obywatele i partnerzy mają osobne markery grupowane według najdokładniejszej dostępnej lokalizacji.
- Fizyczne aktywa są odrębnym typem danych w `bookkeeping`, niezależnym od istniejącego `Asset`, który oznacza jednostkę finansową. Kraj i miasto fizycznego aktywa są wymagane; ulica, numer domu i numer mieszkania są opcjonalne.
- Kraj i miasto są podstawą lokalizacji wszystkich typów. Ulica, numer domu i numer mieszkania są opcjonalnymi szczegółami adresu obywatela, partnera i fizycznego aktywa.
- Pełny adres używa punktu adresowego, jeśli geokoder potwierdzi dopasowanie; bez szczegółowego adresu używany jest środek miasta. Numer mieszkania nie wpływa na współrzędne.

Źródła danych:

- Partner: istniejące `Partner.city`, `Partner.country` i tekstowe `Partner.address`; plan zakłada opcjonalne pola ulicy, numeru domu i numeru mieszkania, bez utraty dotychczasowych adresów. Stare wartości rozdzielać tylko wtedy, gdy można to zrobić jednoznacznie.
- Obywatel: `Uzytkownik.city` + nowe pole `Uzytkownik.country` (relacja do istniejącego modelu `Country`), domyślnie Polska, oraz opcjonalne pola ulicy, numeru domu i numeru mieszkania. `phone_country` dotyczy wyłącznie numeru telefonu i nie może być użyte jako kraj lokalizacji.
- Fizyczne aktywo: nowe dane w `bookkeeping`, niezależne od modelu `Asset`. Wymagane: kraj i miasto. Opcjonalne: ulica, numer domu i numer mieszkania.
- Brak miasta lub kraju oznacza brak punktu. Nie zgadujemy kraju z nazwy miasta ani numeru telefonu. Opcjonalny region musi być zgodny z wybranym krajem; nie jest źródłem zastępczym dla kraju.

## Etap 1 — widoczność i dostawca mapy

- [x] Używać miasta i kraju jako lokalizacji orientacyjnej, a szczegółowego adresu jako dokładniejszej lokalizacji, jeśli został podany i potwierdzony przez geokoder. Nie używać GPS.
- [x] Udostępnić mapę publicznie w trybie samych punktów. Pełne dane i interakcje pokazywać wyłącznie zalogowanym, aktywnym obywatelom.
- [x] Przyjąć Leaflet, kafelki OpenStreetMap i Nominatim jako stos mapy/geokodowania.
- [ ] Przed wdrożeniem sprawdzić aktualne warunki użycia publicznych kafelków OSM i publicznej usługi Nominatim oraz potwierdzić, że przewidywany ruch i liczba lokalizacji mieszczą się w tych warunkach. Jeśli nie, znaleźć zgodny hosting/usługę Nominatim.
- [ ] Zachować istniejące uprawnienia stron szczegółów; mapa nie pokazuje transakcji ani kwot.
- [ ] Dla gościa nie renderować steppera obywateli, jego liczników ani innych elementów przeznaczonych dla zalogowanych.

## Etap 2 — przygotowanie danych

- [ ] Dodać wybór kraju do profilu użytkownika, formularza profilu i formularza onboardingu, korzystając z istniejącego modelu `Country`; domyślna wartość to Polska.
- [ ] Dodać do profilu opcjonalne pola ulicy, numeru domu i numeru mieszkania.
- [ ] Zapewnić dostępność obsługiwanych krajów w katalogu `Country`; region pozostawić opcjonalny i ograniczać jego wybór do regionów wybranego kraju.
- [ ] Dodać migrację pola kraju: istniejącym profilom przypisać kraj ich regionu, jeśli go mają, a pozostałym Polskę. Użyć stabilnego kodu kraju (`PL`), nie identyfikatora rekordu.
- [ ] Walidować zgodność wybranego regionu z krajem; zmiana kraju nie może pozostawić regionu z innego kraju.
- [ ] Dodać osobny model fizycznego aktywa w `bookkeeping`, bez zmiany istniejącego `Asset` (jednostki finansowej); użyć wspólnego katalogu krajów zamiast duplikować dane krajów.
- [ ] Dodać do fizycznego aktywa wymagane pola kraju i miasta oraz opcjonalne pola ulicy, numeru domu i numeru mieszkania.
- [ ] Dodać takie same opcjonalne pola adresu szczegółowego do partnera. Zachować istniejące wartości `Partner.address`; przenosić je do nowych pól tylko wtedy, gdy da się je rozdzielić jednoznacznie.
- [ ] Utworzyć migrację dla nowego modelu i pól adresowych.
- [ ] Dodać formularze oraz widoki listy, szczegółów, tworzenia i edycji aktywów, korzystając z istniejących wzorców Finansów.
- [ ] Pokazywać pełny zapisany adres na stronach szczegółów obywatela, partnera i fizycznego aktywa; numer mieszkania wyświetlać wyłącznie w szczegółach dla zalogowanych, aktywnych obywateli.
- [ ] Wybierać najdokładniejszą dostępną lokalizację obywatela, partnera i fizycznego aktywa: pełny adres ulicy i numer domu, jeśli zostały podane i geokoder potwierdzi wynik; w innym przypadku miasto i kraj. Numer mieszkania jest przechowywany i widoczny w trybie zalogowanym, ale nie zmienia współrzędnych ani nie jest wysyłany do geokodera.
- [ ] Zebrać rekordy partnerów, aktywnych obywateli i fizycznych aktywów w istniejącej warstwie widoku/agregacji, bez pobierania całych modeli do przeglądarki.
- [ ] Obywateli filtrować po aktywnym koncie oraz niepustym mieście i kraju.
- [ ] Pokazywać na mapie wszystkich partnerów mających miasto i kraj; nie dołączać danych finansowych ani prywatnych pól partnera.
- [ ] Pokazywać fizyczne aktywa z kompletnym miastem i krajem; nie ujawniać danych finansowych powiązanych z aktywem.
- [ ] Zbudować dwa zakresy odpowiedzi: gość otrzymuje wyłącznie unikalne współrzędne, a zalogowany, aktywny obywatel typ, nazwę, pełny adres, link i współrzędne. Nie dołączać transakcji, kwot ani danych kontaktowych.
- [ ] Punkty gościa nie mogą zawierać kategorii, etykiet, liczników, identyfikatorów, adresów ani linków i nie mogą obsługiwać kliknięć ani popupów.
- [ ] Geokoderowi przekazywać kraj, miasto oraz — jeśli podane — ulicę i numer domu. Stare `Partner.address` wykorzystać tylko wtedy, gdy ulicę i numer domu można z niego wydzielić bez zgadywania; w innym przypadku użyć lokalizacji miejskiej. Nie wysyłać nazwisk, nazw obiektów, numeru mieszkania, kontaktów ani notatek finansowych.
- [ ] Normalizować tekstowy `Partner.country` do istniejącego katalogu `Country` przez dokładne dopasowanie nazwy lub kodu (bez zgadywania/fuzzy match); używać kodu kraju jako kanonicznej wartości geokodowania.
- [ ] Normalizować miasto tylko do porównania (trim, ujednolicenie wielkości liter); grupować wyłącznie zgodne pary miasto + kraj. Nie łączyć podobnie zapisanych, ale niepotwierdzonych miast automatycznie.
- [ ] Wpisy z nierozpoznanym krajem lub niedostępnym wynikiem geokodowania pozostawić na liście lokalizacji jako „nieoznaczone na mapie”, zamiast przypisywać błędny punkt.
- [ ] Dla każdej najdokładniejszej lokalizacji utworzyć maksymalnie dwa markery zbiorcze: obywateli i partnerów. Fizyczne aktywa otrzymują osobne markery lokalizacyjne.

## Etap 3 — geokodowanie i współrzędne

- [ ] Geokodować unikalną lokalizację obywatela, partnera i fizycznego aktywa: kraj + miasto, rozszerzone o ulicę i numer domu, gdy są podane. Nie wykonywać osobnego zapytania dla każdego rekordu o tej samej lokalizacji ani przy każdym wyświetleniu mapy.
- [ ] Numer mieszkania nie jest częścią zapytania geokodującego; niejednoznacznych starych wartości `Partner.address` nie używać do wyznaczania dokładnego punktu.
- [ ] Za dokładny uznać wyłącznie wynik jednoznacznie potwierdzający ulicę i numer domu. Jeśli szczegółowy adres nie pasuje lub jest niejednoznaczny, użyć punktu miasta; jeśli nie da się ustalić miasta, pozostawić rekord jako nieoznaczony.
- [ ] Ustawić rozpoznawalny `User-Agent` i ograniczyć częstotliwość żądań zgodnie z aktualną polityką Nominatim.
- [ ] Cache'ować wyniki zgodnie z warunkami usługi: lokalizacje miejskie po kraju + mieście, adresowe po kraju + mieście + ulicy + numerze domu. Nie zapisywać współrzędnych w bazie w MVP.
- [ ] Zmiana kraju/miasta/adresu musi używać nowego klucza cache, a stary wynik nie może być przypisany do zmienionej lokalizacji.
- [ ] Zapamiętywać niejednoznaczne i błędne wyniki z krótkim czasem cache, by nie ponawiać bez końca tych samych żądań; pozwolić na ponowną próbę po wygaśnięciu cache.
- [ ] Nie wysyłać geokoderowi numeru mieszkania ani nazw, kontaktów lub innych danych identyfikujących osoby i aktywa.

## Etap 4 — mapa i interakcje

- [ ] Umieścić mapę jako nową zakładkę istniejącego steppera na `/obywatele/`, pod adresem `/obywatele/mapa/`; nie dodawać osobnej pozycji menu.
- [ ] Dodać publicznie dostępną trasę i widok mapy w aplikacji `obywatele`. Dla zalogowanych, aktywnych obywateli strona korzysta z `obywatele/menu.html`; gościom renderuje tylko mapę bez steppera i jego liczników.
- [ ] Rozszerzyć `obywatele_stepper` w `obywatele/templatetags/profile_tags.py` o krok „Mapa” prowadzący do nowej trasy. Umieścić go obok „Obywatele”, oznaczać jako aktywny na stronie mapy i użyć ikony lokalizacji ze słownika UI (`map-marker-alt`).
- [ ] Użyć wspólnego partiala `home/templates/home/includes/stepper.html`; zachować istniejące zachowanie zakładek, CTA i responsywnego zwijania.
- [ ] Dodać mapę w istniejącej strukturze widoku, używając Leaflet i kafelków OSM z wymaganą atrybucją.
- [ ] Przy pierwszym otwarciu ustawić kadr mapy na Polskę; po wybraniu punktu miasta przybliżyć mapę do tego miasta. Nie dodawać wyszukiwarki ani filtrów kategorii w MVP.
- [ ] Przy braku punktów pokazać wspólny pusty stan zamiast pustej mapy.
- [ ] Dla zalogowanych obywateli pokazywać markery z rozróżnieniem obywateli (`fa-user`), partnerów (`fa-handshake`) i fizycznych aktywów; użyć najdokładniejszych potwierdzonych współrzędnych każdego wpisu.
- [ ] Markery obywateli, partnerów i aktywów pokazywać w najdokładniejszym potwierdzonym punkcie adresu; w przypadku braku lub niejednoznaczności adresu szczegółowego używać punktu miasta.
- [ ] Kliknięcie markera zalogowanego użytkownika pokazuje nazwę, pełny podany adres i link do istniejącego profilu lub szczegółów; numer mieszkania może być widoczny tylko w tym trybie. Nie ujawniać transakcji, kwot ani danych kontaktowych.
- [ ] Dla gościa renderować wyłącznie nieklikalne, jednakowe punkty. Zlać identyczne współrzędne do jednego punktu i nie zdradzać liczby ani rodzaju wpisów.
- [ ] Grupować bliskie/nakładające się markery dla zalogowanych bez zmiany ich współrzędnych; po kliknięciu klastra pokazać jego elementy lub przybliżyć mapę.
- [ ] Przy błędzie lub blokadzie SDK pokazać listę lokalizacji i rekordów, w tym wpisy nieoznaczone na mapie, jako użyteczny fallback. Dostosować widok do standardów UI i urządzeń mobilnych.

## Etap 5 — testy i uruchomienie

- [ ] Testować dopasowanie tekstowego kraju partnera do katalogu, obsługę nieznanego kraju, brakujących pól oraz rozróżnienie tego samego miasta w różnych krajach.
- [ ] Testować jednokrotne geokodowanie unikalnej lokalizacji, cache zgodny z warunkami dostawcy, zmianę klucza po zmianie adresu oraz obsługę błędów i niejednoznacznych wyników.
- [ ] Testować tryb gościa: publiczny widok zawiera tylko unikalne współrzędne, nie pokazuje steppera, liczników, kategorii, nazw, adresów ani linków i nie reaguje na kliknięcie punktu.
- [ ] Testować tryb zalogowanego aktywnego obywatela: widoczne są wszystkie kwalifikujące się wpisy ze szczegółami i interakcjami.
- [ ] Testować widok początkowy Polski, przybliżenie po wybraniu miasta oraz grupowanie/rozwijanie nakładających się markerów.
- [ ] Testować grupowanie markerów obywateli i partnerów według dokładnego adresu lub miasta oraz markery aktywów, liczniki i listę wpisów nieoznaczonych.
- [ ] Testować wymagane pola kraju/miasta oraz opcjonalne szczegóły adresu profilu, partnera i fizycznego aktywa; zachować stare wartości `Partner.address`.
- [ ] Testować dokładność geokodowania każdego typu: adres szczegółowy przy potwierdzonym dopasowaniu, w pozostałych przypadkach punkt miasta; numer mieszkania nie wpływa na współrzędne ani zapytanie geokodujące.
- [ ] Testować, że geokoder dostaje wyłącznie dane lokalizacyjne, a payload mapy nie zawiera kontaktów ani danych finansowych.
- [ ] Testować linki do istniejących profili, partnerów i szczegółów aktywów.
- [ ] Udokumentować atrybucję OSM i ustawienia/limity Nominatim wymagane przez wybraną usługę.
- [ ] Po implementacji UI uruchomić `npm run build:css`, `python scripts/regression_scan.py` i `python scripts/ui_guard.py` (jeśli istnieje), a potem testy dotkniętego fragmentu.

## Poza zakresem MVP

- Lokalizowanie GPS.
- Automatyczne dopowiadanie kraju, masowe poprawianie danych profilu lub partnera.
- Zapisywanie współrzędnych w bazie bez osobnej decyzji.
- Trasy, wiele warstw mapowych i rozbudowane wyszukiwanie.