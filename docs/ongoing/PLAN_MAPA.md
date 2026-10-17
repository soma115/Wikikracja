# Mapa społeczności

Status: w realizacji

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

## Powiazanie z planem zasobow

- Mapa pokazuje lokalizacje obywateli, partnerow i fizycznych aktywow. Wpisy ofert i potrzeb `bookkeeping.ResourceListing` z `docs/ongoing/PLAN_ZASOBY_UŻYTKOWNIKÓW.md` nie sa markerami mapy.
- Fizyczne aktywa pozostaja odrebnym zrodlem w `bookkeeping`; nie utozsamiac ich ani z finansowym `Asset`, ani z wpisami `ResourceListing`.
- Pola kraju i szczegolowego adresu obywatela sa czescia wspolnego profilu. Rozszerzyc istniejacy `ProfileForm` w ustawieniach oraz formularz onboardingu, zamiast tworzyc kolejny formularz danych kontaktowych.
- Szczegolowy adres moze byc uzyty i pokazany na mapie wylacznie zgodnie z regulami dostepu tej mapy. Katalog zasobow nadal filtruje po miejscowosci i wojewodztwie i nie wyswietla adresu szczegolowego ani telefonu.
- Lokalizacja profilu na mapie nie oznacza zasiegu oferty. Wyszukiwanie zasobow po zasiegu lub promieniu pozostaje poza zakresem tego planu i wymaga osobnej decyzji.

## Etap 1 — widoczność i dostawca mapy

- [x] Używać miasta i kraju jako lokalizacji orientacyjnej, a szczegółowego adresu jako dokładniejszej lokalizacji, jeśli został podany i potwierdzony przez geokoder. Nie używać GPS.
- [x] Udostępnić mapę publicznie w trybie samych punktów. Pełne dane i interakcje pokazywać wyłącznie zalogowanym, aktywnym obywatelom.
- [x] Przyjąć Leaflet, kafelki OpenStreetMap i Nominatim jako stos mapy/geokodowania.
- [x] Sprawdzić oficjalne warunki [kafelków OSM](https://operations.osmfoundation.org/policies/tiles/) i [Nominatim](https://operations.osmfoundation.org/policies/nominatim/): kafelki wymagają HTTPS, widocznej atrybucji, respektowania nagłówków cache (minimum 7 dni bez nich) i braku prefetchu; Nominatim ogranicza ruch do 1 żądania/s i wymaga rozpoznawalnego `User-Agent`. Kafelków używamy bez nagłówków `no-cache`; jeśli wybrana usługa nie dostarczy nagłówków cache, należy dodać zgodny cache/proxy.
- [ ] Potwierdzić, że przewidywany ruch i liczba unikalnych lokalizacji mieszczą się w warunkach usług. Geokodowanie pozostaje wyłączone domyślnie przez `MAP_GEOCODING_ENABLED`; w razie przekroczenia limitów wybrać zgodnego dostawcę.
- [x] Zachować istniejące uprawnienia stron szczegółów; mapa nie pokazuje transakcji ani kwot.
- [x] Dla gościa nie renderować steppera obywateli, jego liczników ani innych elementów przeznaczonych dla zalogowanych.

## Etap 2 — przygotowanie danych

- [x] Dodać wybór kraju do profilu użytkownika, formularza profilu i formularza onboardingu, korzystając z istniejącego modelu `Country`; domyślna wartość to Polska.
- [x] Dodać do profilu opcjonalne pola ulicy, numeru domu i numeru mieszkania.
- [x] Zapewnić dostępność obsługiwanych krajów w katalogu `Country`; region pozostawić opcjonalny i ograniczać jego wybór do regionów wybranego kraju.
- [x] Dodać migrację pola kraju: istniejącym profilom przypisać kraj ich regionu, jeśli go mają, a pozostałym Polskę. Użyć stabilnego kodu kraju (`PL`), nie identyfikatora rekordu.
- [x] Walidować zgodność wybranego regionu z krajem; zmiana kraju nie może pozostawić regionu z innego kraju.
- [x] Dodać osobny model fizycznego aktywa w `bookkeeping`, bez zmiany istniejącego `Asset` (jednostki finansowej); użyć wspólnego katalogu krajów zamiast duplikować dane krajów.
- [x] Dodać do fizycznego aktywa wymagane pola kraju i miasta oraz opcjonalne pola ulicy, numeru domu i numeru mieszkania.
- [x] Dodać takie same opcjonalne pola adresu szczegółowego do partnera. Zachować istniejące wartości `Partner.address`; przenosić je do nowych pól tylko wtedy, gdy da się je rozdzielić jednoznacznie.
- [x] Utworzyć migrację dla nowego modelu i pól adresowych.
- [x] Dodać formularze oraz widoki listy, szczegółów, tworzenia i edycji aktywów, korzystając z istniejących wzorców Finansów.
- [x] Pokazywać pełny zapisany adres na stronach szczegółów obywatela, partnera i fizycznego aktywa; numer mieszkania wyświetlać wyłącznie w szczegółach dla zalogowanych, aktywnych obywateli.
- [x] Wybierać najdokładniejszą dostępną lokalizację obywatela, partnera i fizycznego aktywa: pełny adres ulicy i numer domu, jeśli zostały podane i geokoder potwierdzi wynik; w innym przypadku miasto i kraj. Numer mieszkania jest przechowywany i widoczny w trybie zalogowanym, ale nie zmienia współrzędnych ani nie jest wysyłany do geokodera.
- [x] Zebrać rekordy partnerów, aktywnych obywateli i fizycznych aktywów w istniejącej warstwie widoku/agregacji, bez pobierania całych modeli do przeglądarki.
- [x] Obywateli filtrować po aktywnym koncie oraz niepustym mieście i kraju.
- [x] Pokazywać na mapie wszystkich partnerów mających miasto i kraj; nie dołączać danych finansowych ani prywatnych pól partnera.
- [x] Pokazywać fizyczne aktywa z kompletnym miastem i krajem; nie ujawniać danych finansowych powiązanych z aktywem.
- [x] Zbudować dwa zakresy odpowiedzi: gość otrzymuje wyłącznie unikalne współrzędne, a zalogowany, aktywny obywatel typ, nazwę, pełny adres, link i współrzędne. Nie dołączać transakcji, kwot ani danych kontaktowych.
- [x] Punkty gościa nie mogą zawierać kategorii, etykiet, liczników, identyfikatorów, adresów ani linków i nie mogą obsługiwać kliknięć ani popupów.
- [x] Geokoderowi przekazywać kraj, miasto oraz — jeśli podane — ulicę i numer domu. Stare `Partner.address` wykorzystać tylko wtedy, gdy ulicę i numer domu można z niego wydzielić bez zgadywania; w innym przypadku użyć lokalizacji miejskiej. Nie wysyłać nazwisk, nazw obiektów, numeru mieszkania, kontaktów ani notatek finansowych.
- [x] Normalizować tekstowy `Partner.country` do istniejącego katalogu `Country` przez dokładne dopasowanie nazwy lub kodu (bez zgadywania/fuzzy match); używać kodu kraju jako kanonicznej wartości geokodowania.
- [x] Normalizować miasto tylko do porównania (trim, ujednolicenie wielkości liter); grupować wyłącznie zgodne pary miasto + kraj. Nie łączyć podobnie zapisanych, ale niepotwierdzonych miast automatycznie.
- [x] Wpisy z nierozpoznanym krajem lub niedostępnym wynikiem geokodowania pozostawić na liście lokalizacji jako „nieoznaczone na mapie”, zamiast przypisywać błędny punkt.
- [x] Dla każdej najdokładniejszej lokalizacji utworzyć maksymalnie dwa markery zbiorcze: obywateli i partnerów. Fizyczne aktywa otrzymują osobne markery lokalizacyjne.

## Etap 3 — geokodowanie i współrzędne

- [x] Geokodować unikalną lokalizację obywatela, partnera i fizycznego aktywa: kraj + miasto, rozszerzone o ulicę i numer domu, gdy są podane. Nie wykonywać osobnego zapytania dla każdego rekordu o tej samej lokalizacji ani przy każdym wyświetleniu mapy.
- [x] Numer mieszkania nie jest częścią zapytania geokodującego; niejednoznacznych starych wartości `Partner.address` nie używać do wyznaczania dokładnego punktu.
- [x] Za dokładny uznać wyłącznie wynik jednoznacznie potwierdzający ulicę i numer domu. Jeśli szczegółowy adres nie pasuje lub jest niejednoznaczny, użyć punktu miasta; jeśli nie da się ustalić miasta, pozostawić rekord jako nieoznaczony.
- [x] Ustawić rozpoznawalny `User-Agent` i ograniczyć częstotliwość żądań zgodnie z aktualną polityką Nominatim.
- [x] Cache'ować wyniki zgodnie z warunkami usługi: lokalizacje miejskie po kraju + mieście, adresowe po kraju + mieście + ulicy + numerze domu. Nie zapisywać współrzędnych w bazie w MVP.
- [x] Zmiana kraju/miasta/adresu musi używać nowego klucza cache, a stary wynik nie może być przypisany do zmienionej lokalizacji.
- [x] Zapamiętywać niejednoznaczne i błędne wyniki z krótkim czasem cache, by nie ponawiać bez końca tych samych żądań; pozwolić na ponowną próbę po wygaśnięciu cache.
- [x] Nie wysyłać geokoderowi numeru mieszkania ani nazw, kontaktów lub innych danych identyfikujących osoby i aktywa.

## Etap 4 — mapa i interakcje

- [x] Umieścić mapę jako nową zakładkę istniejącego steppera na `/obywatele/`, pod adresem `/obywatele/mapa/`; nie dodawać osobnej pozycji menu.
- [x] Dodać publicznie dostępną trasę i widok mapy w aplikacji `obywatele`. Dla zalogowanych, aktywnych obywateli strona korzysta z `obywatele/menu.html`; gościom renderuje tylko mapę bez steppera i jego liczników.
- [x] Rozszerzyć `obywatele_stepper` w `obywatele/templatetags/profile_tags.py` o krok „Mapa” prowadzący do nowej trasy. Umieścić go obok „Obywatele”, oznaczać jako aktywny na stronie mapy i użyć ikony lokalizacji ze słownika UI (`map-marker-alt`).
- [x] Użyć wspólnego partiala `home/templates/home/includes/stepper.html`; zachować istniejące zachowanie zakładek, CTA i responsywnego zwijania.
- [x] Dodać mapę w istniejącej strukturze widoku, używając Leaflet i kafelków OSM z wymaganą atrybucją.
- [x] Przy pierwszym otwarciu ustawić kadr mapy na Polskę; po wybraniu punktu miasta przybliżyć mapę do tego miasta. Nie dodawać wyszukiwarki ani filtrów kategorii w MVP.
- [x] Przy braku punktów pokazać wspólny pusty stan zamiast pustej mapy.
- [x] Dla zalogowanych obywateli pokazywać markery z rozróżnieniem obywateli (`fa-user`), partnerów (`fa-handshake`) i fizycznych aktywów; użyć najdokładniejszych potwierdzonych współrzędnych każdego wpisu.
- [x] Markery obywateli, partnerów i aktywów pokazywać w najdokładniejszym potwierdzonym punkcie adresu; w przypadku braku lub niejednoznaczności adresu szczegółowego używać punktu miasta.
- [x] Kliknięcie markera zalogowanego użytkownika pokazuje nazwę, pełny podany adres i link do istniejącego profilu lub szczegółów; numer mieszkania może być widoczny tylko w tym trybie. Nie ujawniać transakcji, kwot ani danych kontaktowych.
- [x] Dla gościa renderować wyłącznie nieklikalne, jednakowe punkty. Zlać identyczne współrzędne do jednego punktu i nie zdradzać liczby ani rodzaju wpisów.
- [x] Grupować bliskie/nakładające się markery dla zalogowanych bez zmiany ich współrzędnych; po kliknięciu klastra pokazać jego elementy lub przybliżyć mapę.
- [x] Przy błędzie lub blokadzie SDK pokazać listę lokalizacji i rekordów, w tym wpisy nieoznaczone na mapie, jako użyteczny fallback. Dostosować widok do standardów UI i urządzeń mobilnych.

## Etap 5 — testy i uruchomienie

- [x] Testować dopasowanie tekstowego kraju partnera do katalogu, obsługę nieznanego kraju, brakujących pól oraz rozróżnienie tego samego miasta w różnych krajach.
- [x] Testować jednokrotne geokodowanie unikalnej lokalizacji, cache, zmianę klucza po zmianie adresu oraz obsługę błędów i niejednoznacznych wyników.
- [x] Testować tryb gościa: publiczny widok zawiera tylko unikalne współrzędne, nie pokazuje steppera, liczników, kategorii, nazw, adresów ani linków i nie reaguje na kliknięcie punktu.
- [x] Testować tryb zalogowanego aktywnego obywatela: widoczne są wszystkie kwalifikujące się wpisy ze szczegółami i interakcjami.
- [x] Testować widok początkowy Polski, przybliżenie po wybraniu miasta oraz grupowanie/rozwijanie nakładających się markerów.
- [x] Testować grupowanie markerów obywateli i partnerów według dokładnego adresu lub miasta oraz markery aktywów i listę wpisów nieoznaczonych.
- [x] Testować wymagane pola kraju/miasta oraz opcjonalne szczegóły adresu profilu, partnera i fizycznego aktywa; zachować stare wartości `Partner.address`.
- [x] Testować dokładność geokodowania każdego typu: adres szczegółowy przy potwierdzonym dopasowaniu, w pozostałych przypadkach punkt miasta; numer mieszkania nie wpływa na współrzędne ani zapytanie geokodujące.
- [x] Testować, że geokoder dostaje wyłącznie dane lokalizacyjne, a payload mapy nie zawiera kontaktów ani danych finansowych.
- [x] Testować linki do istniejących profili, partnerów i szczegółów aktywów.
- [x] Udokumentować atrybucję OSM i ustawienia/limity Nominatim wymagane przez wybraną usługę.
- [x] Po implementacji UI uruchomić `npm run build:css`, `python scripts/regression_scan.py` i `python scripts/ui_guard.py` (jeśli istnieje), a potem testy dotkniętego fragmentu.

## Konfiguracja dostawcy kafelków

- `DEBUG=True` używa lokalnie Stadia Alidade Smooth — jej dokumentacja dopuszcza bezkluczowy development z `localhost`/`127.0.0.1`, z limitami ruchu i atrybucją Stadia/OpenMapTiles/OSM.
- `DEBUG=False` pozostawia OSM jako domyślny dostawcę. `MAP_TILES_URL` i `MAP_TILES_ATTRIBUTION` mogą go nadpisać, ale przed wdrożeniem nadal trzeba potwierdzić przewidywany ruch i warunki usługi.
- Nie obchodzimy blokad OSM przez fałszowanie nagłówków. Geokodowanie Nominatim pozostaje wyłączone domyślnie, dopóki nie zostanie oceniona liczba lokalizacji.

## Poza zakresem MVP

- Lokalizowanie GPS.
- Automatyczne dopowiadanie kraju, masowe poprawianie danych profilu lub partnera.
- Zapisywanie współrzędnych w bazie bez osobnej decyzji.
- Trasy, wiele warstw mapowych i rozbudowane wyszukiwanie.