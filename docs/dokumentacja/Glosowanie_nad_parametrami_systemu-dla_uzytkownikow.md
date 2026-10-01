# Zmiana parametrów systemu przez referendum

## Co się zmieniło?

Wcześniej wiele ustawień systemu (jak nazwa strony, opis, czas trwania głosowań) było ustalane przez administratora w plikach konfiguracyjnych. Teraz te ustawienia mogą być zmieniane przez społeczność poprzez demokratyczne referendum.

## Jakie parametry można zmienić?

### Parametry głosowań
- **Wymaganych podpisów** - ile podpisów musi zebrać propozycja, aby trafiła do głosowania
- **Czas na zebranie podpisów** - ile dni jest na zbieranie podpisów pod propozycją
- **Czas na dyskusję** - ile dni propozycja czeka w kolejce przed rozpoczęciem referendum
- **Czas trwania referendum** - ile dni trwa głosowanie

### Ustawienia czatu
- **Archiwizuj publiczny pokój czatu po** - ile dni bez aktywności musi minąć, aby pokój został zarchiwizowany
- **Usuń publiczny pokój czatu po** - ile dni bez aktywności musi minąć, aby pokój został usunięty

### Ustawienia członkostwa
- **Próg akceptacji** - ile punktów reputacji jest potrzebne do akceptacji nowych członków
- **Usuń nieaktywnego użytkownika po** - ile dni nieaktywności powoduje usunięcie konta

### Ustawienia grupy
- **Grupa jest publiczna** - czy każdy może się zarejestrować i czy publiczny Inbox jest dostępny

### Tożsamość strony
- **Nazwa strony** - pełna nazwa widoczna w całej witrynie
- **Logo** - opcjonalna grafika marki; jest proponowana jako osobna zmiana w tym samym referendum

Krótka nazwa PWA i opis instancji nie są obecnie parametrami dostępnymi w tym formularzu.

## Jak zaproponować zmianę parametrów?

1. Wejdź do sekcji **Głosowania** → **Parametry**
2. Kliknij przycisk **"Utwórz referendum dotyczące zmiany parametrów systemu"**
3. Zobaczysz formularz z wszystkimi parametrami pogrupowanymi według kategorii
4. Zmień tylko te parametry, które chcesz zmienić
5. Opcjonalnie możesz dodać **nowe logo** (PNG, maks. 5 MB, najdłuższy bok 64–4096 px). Po zatwierdzeniu system normalizuje je do PNG 1024×1024 px i generuje z niego ikony.
6. Wypełnij pole **"Uzasadnienie"** - dlaczego te zmiany są potrzebne
7. Kliknij **"Utwórz referendum"**

Twój wniosek pojawi się w sekcji **Propozycje** jako zwykłe referendum. Musi zebrać wymaganą liczbę podpisów, przejść przez dyskusję i zostać zatwierdzony w głosowaniu.

## Jak edytować istniejącą propozycję?

Jeśli Twoja propozycja zmiany parametrów jest jeszcze w fazie zbierania podpisów (status "Propozycja"), możesz ją edytować:

1. Wejdź na stronę szczegółów referendum
2. Kliknij **"Edytuj"**
3. Zostaniesz przekierowany do formularza parametrów
4. Zmień wartości i zapisz
5. Stara wersja zostanie zachowana w historii

## Kiedy zmiany wchodzą w życie?

Zmiany wchodzą w życie **natychmiast po zatwierdzeniu referendum** przez społeczność. Nie jest wymagany restart aplikacji.

- **Nazwa strony** - zmiana jest synchronizowana z nazwą witryny Django
- **Logo** - po zatwierdzeniu aktualizuje markę strony oraz generowane ikony
- **Parametry głosowań** - dotyczą nowych referendów utworzonych po zatwierdzeniu
- **Parametry czatu** - dotyczą nowych operacji archiwizacji/usuwania
- **Parametry członkostwa** - dotyczą nowych akceptacji i usuwań

## Ważne uwagi

### Logo
- Formularz referendum przyjmuje plik PNG do 5 MB; najdłuższy bok obrazu źródłowego musi mieć 64–4096 pikseli.
- Po zatwierdzeniu obraz jest normalizowany do kwadratowego PNG 1024×1024 px, a system generuje ikony dla przeglądarki i PWA.
- Zmiana marki jest stosowana dopiero po zatwierdzeniu referendum.

### Nazwa strony
- Nazwa strony jest zmieniana przez referendum i synchronizowana z nazwą witryny Django.

### Zainstalowana aplikacja PWA
- System odświeża wygenerowane ikony, ale moment ich ponownego pobrania/zastosowania zależy od cache'u przeglądarki i systemu operacyjnego.

## Gdzie mogę zobaczyć bieżące wartości parametrów?

Bieżące wartości parametrów są wyświetlone na stronie **Głosowania → Parametry**. Są one pogrupowane według kategorii:
- Parametry głosowań
- Ustawienia czatu
- Ustawienia członkostwa
- Ustawienia grupy
- Tożsamość strony

## Co się dzieje, gdy zmieniam parametr?

1. Tworzysz referendum z listą zmian
2. Inni członkowie widzą, co się zmieni (np. "Wymaganych podpisów: 2 → 3")
3. Jeśli referendum zostanie zatwierdzone, zmiany są automatycznie stosowane
4. Wszystkie nowe operacje w systemie używają nowych wartości

## Czy mogę cofnąć zmianę?

Tak - możesz utworzyć nowe referendum, które przywróci poprzednie wartości. Wszystkie zmiany parametrów muszą być zatwierdzone przez społeczność, więc nie ma możliwości jednostronnej zmiany przez administratora.

## Jakie są ograniczenia?

- Każdy parametr ma dozwolony zakres (np. liczba dni musi być dodatnia)
- Tylko autor referendum może je edytować (dopóki jest w fazie propozycji)
- Logo jest walidowane pod kątem formatu i rozmiaru
- Zmiany wymagają zatwierdzenia przez większość głosów

## Dlaczego to jest ważne?

Ten system daje społeczności pełną kontrolę nad zasadami działania instancji. Zamiast polegać na administratorze, członkowie mogą sami decydować o:
- Jak długo trwają głosowania
- Jak łatwo jest dołączyć do grupy
- Jak długo nieaktywne konta są usuwane
- Jak nazywa się instancja

To jest kluczowy element demokratycznego zarządzania społecznością.
