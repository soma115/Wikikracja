# Plan katalogu miejscowości

## Status i cel

Plan projektowy — **niezaimplementowany**. Celem jest umożliwienie wyszukiwania i wyboru miejscowości z lokalnego katalogu, zawsze w kontekście wybranego kraju. Nowe i edytowane lokalizacje nie mogą być zapisywane jako dowolny tekst poza katalogiem.

## Ustalone wymagania

- Katalog obejmuje miejscowości przypisane do kraju.
- Miejscowość jest obowiązkowo wybierana z katalogu, jeśli formularz przyjmuje miejscowość. Nie dodajemy obejścia „wpisz własną nazwę”.
- Rozwiązanie obejmuje lokalizacje profili użytkowników, partnerów oraz zasobów.
- Akceptowany jest model `Locality` powiązany z `Country` oraz migracja obecnych danych.
- Kraj i miejscowość numeru telefonu pozostają niezależne od kraju i miejscowości adresu.
- Wybór z katalogu służy do identyfikacji lokalizacji, a nie do geokodowania adresu ani ujawniania dokładniejszej lokalizacji.

## Stan obecny

- `Country` i `Region` istnieją w `obywatele`, ale osobny katalog miejscowości jeszcze nie istnieje.
- `Uzytkownik.city` oraz `Entity.city` są polami tekstowymi. `Partner.city` i `Partner.country` także są tekstem.
- Wspólny `ProfileForm` jest używany w ustawieniach profilu, onboardingu, formularzu zaproszenia oraz edycji profilu kandydata.
- `ResourceEntityForm` przyjmuje kraj i miasto dla lokalizowanych zasobów. Partnerzy mają oddzielny `PartnerForm`.
- Wyszukiwanie wpisów po mieście, wyświetlanie lokalizacji i mapa korzystają z obecnych pól; po zmianie modelu muszą nadal działać.
- Nominatim w obsłudze mapy służy do uzyskiwania współrzędnych, a nie do dostarczania katalogu ani podpowiedzi w formularzu.
- Pola wyszukiwania/filtrowania po mieście nie są formularzami wyboru lokalizacji i pozostają poza zakresem tej zmiany.

## Etapy

### Etap 1 — źródło i format katalogu

- [ ] Porównać źródła danych obejmujące kraje dostępne w `Country`, w tym jakość nazw, warianty językowe, administracyjne nazwy pomocnicze i aktualność.
- [ ] Zweryfikować licencję, wymagania atrybucji, możliwość lokalnego przechowywania danych i zasady ich aktualizacji.
- [ ] Ustalić, które typy osad są wybieralne (np. miasta, miasteczka, wsie) i jak rozróżniać powtarzające się nazwy w obrębie kraju.
- [ ] Zapisać wybrane źródło, wersję danych i warunki użycia w dokumentacji projektu.

### Etap 2 — model i import danych

- [ ] Dodać model `Locality` powiązany z `Country`, z nazwą kanoniczną, identyfikatorem źródłowym oraz informacją administracyjną potrzebną do rozróżniania wyników.
- [ ] Zastąpić tekstowe pola `city` relacją do `Locality` w profilach, partnerach i lokalizowanych zasobach; ujednolicić tekstowe pole kraju partnera do relacji `Country`.
- [ ] Zdefiniować stabilne klucze i indeksy dla identyfikatora źródłowego oraz wyszukiwania nazw w obrębie kraju; uwzględnić normalizację wielkości liter i znaków diakrytycznych.
- [ ] Przygotować idempotentny import katalogu, działający z lokalnego pliku danych, bez pobierania lub odpytywania zewnętrznego dostawcy przy obsłudze formularzy.
- [ ] Ustalić bezpieczną aktualizację katalogu: nie usuwać miejscowości używanych przez zapisane rekordy; nieaktualne pozycje oznaczać lub obsługiwać tak, aby istniejące relacje pozostały poprawne.
- [ ] Sprawdzić rozmiar danych i czas importu na używanej bazie SQLite.

### Etap 3 — migracja istniejących rekordów

- [ ] Zinwentaryzować lokalizacje profili, partnerów i zasobów wraz z krajem oraz liczbą powtórzeń.
- [ ] Dla partnerów ujednolicić zapis kraju względem `Country`, uwzględniając rozpoznawane nazwy i kody oraz istniejące błędne lub niejednoznaczne wartości.
- [ ] Przygotować migrację schematu tak, aby zachować obecne wartości do czasu ich rozstrzygnięcia i umożliwić bezpieczne wdrożenie.
- [ ] Automatycznie przypisać tylko jednoznaczne dopasowania miejscowości w obrębie danego kraju.
- [ ] Wygenerować raport brakujących i niejednoznacznych dopasowań; rozstrzygnąć je przed zakończeniem migracji bez cichej zmiany lub utraty danych.
- [ ] Zweryfikować liczbę rekordów przed i po migracji oraz przygotować odwracalny plan wdrożenia.

### Etap 4 — wyszukiwanie i walidacja

- [ ] Udostępnić ograniczone, stronicowane lub limitowane wyszukiwanie miejscowości, wymagające wybranego kraju i krótkiego zapytania.
- [ ] Zwracać nazwę kanoniczną i kontekst administracyjny, gdy jest potrzebny do rozróżnienia podobnych wyników.
- [ ] Użyć istniejącego podejścia UI/HTTP w projekcie; nie dodawać biblioteki JavaScript bez potrzeby.
- [ ] Zapewnić dostępność pola i listy podpowiedzi: obsługę klawiatury, czytników ekranu, stanu ładowania, braku wyników i błędów.
- [ ] Po zmianie kraju wyczyścić wybór miejscowości z poprzedniego kraju i ponownie wyszukiwać tylko w nowym kraju.
- [ ] Po stronie serwera walidować, że przesłana miejscowość istnieje i należy do przesłanego kraju; nie ufać samemu identyfikatorowi z przeglądarki.
- [ ] Przy braku kraju lub miejscowości zachować dotychczasową opcjonalność adresu w formularzach partnerów i zasobów; profil zachowuje swoją dotychczasową wymagalność.

### Etap 5 — formularze i użycia lokalizacji

- [ ] Zintegrować wybór z `ProfileForm`, obejmując ustawienia profilu, onboarding, zapraszanie osoby oraz edycję profilu kandydata.
- [ ] Zintegrować wybór z `PartnerForm`; powiązać zapis kraju partnera z tym samym rekordem `Country`, aby nie utrzymywać dwóch niespójnych źródeł kraju.
- [ ] Zintegrować wybór z `ResourceEntityForm` dla lokalizowanych zasobów; nie dodawać lokalizacji do finansowych aktywów, jeśli nie obsługują jej obecnie.
- [ ] Zaktualizować odczyt, listy, szczegóły, wyszukiwanie i mapę, aby korzystały z wybranej miejscowości i nadal prezentowały nazwę w dotychczasowym formacie.
- [ ] Zachować krajową izolację także wtedy, gdy w kilku krajach występuje miejscowość o tej samej nazwie.
- [ ] Zaktualizować tłumaczenia i dokumentację wspólnego komponentu UI, jeśli wdrożenie wprowadzi nowy wzorzec podpowiedzi/wyboru.

### Etap 6 — testy i wdrożenie

- [ ] Dodać testy modelu, importu, normalizacji, unikalności oraz zachowania przypisań przy aktualizacji katalogu.
- [ ] Dodać testy formularzy i widoków dla każdego zakresu: profil, partnerzy i zasoby.
- [ ] Sprawdzić odrzucanie miejscowości nieistniejącej, nieaktywnej lub należącej do innego kraju.
- [ ] Sprawdzić migrację na kopii reprezentatywnych danych, w tym rekordy niejednoznaczne i bez dopasowania.
- [ ] Sprawdzić wyszukiwanie, filtrowanie, widoki szczegółów i mapę po zmianie relacji.
- [ ] Dla zmian UI wykonać wymagane kontrole projektu: build CSS, skan regresji i UI guard; uruchomić testy dotkniętych formularzy, endpointu i migracji.
- [ ] Udokumentować procedurę pierwszego importu i aktualizacji katalogu oraz warunki licencji.

## Kryteria ukończenia

- Każda zapisywana miejscowość pochodzi z katalogu i jest powiązana z krajem rekordu.
- Formularze profilu, partnerów i zasobów umożliwiają wyszukanie i wybranie miejscowości w wybranym kraju.
- Zmiana kraju nie pozwala zachować lokalizacji z poprzedniego kraju.
- Istniejące dane są zachowane lub jawnie rozstrzygnięte; migracja nie przypisuje niejednoznacznych miejscowości automatycznie.
- Listy, wyszukiwanie, widoki szczegółów i mapa zachowują oczekiwane działanie.
- Katalog nie wymaga zapytań do zewnętrznego dostawcy w czasie obsługi formularza.
