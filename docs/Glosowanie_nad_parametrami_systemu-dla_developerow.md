# System parametrów systemowych zarządzanych przez referendum

## Przegląd zmian

Wprowadzono kompleksowy system zarządzania parametrami systemowymi przez referendum. Parametry, które wcześniej były zahardcodowane w `settings.py`, są teraz przechowywane w bazie danych i mogą być zmieniane przez społeczność poprzez głosowanie.

Opis poszczególnych parametrów dla użytkowników końcowych znajduje się w [Glosowanie_nad_parametrami_systemu-dla_uzytkownikow.md](Glosowanie_nad_parametrami_systemu-dla_uzytkownikow.md). Ten dokument opisuje implementację.

## Główne komponenty

### 1. Model `SiteParameters` (singleton)

**Nowy plik**: `site_settings/models.py`

Model singleton przechowujący wszystkie parametry systemowe w bazie danych:

```python
class SiteParameters(models.Model):
    # Parametry głosowań
    wymaganych_podpisow = models.PositiveIntegerField(default=2)
    czas_na_zebranie_podpisow = models.PositiveIntegerField(default=365)
    dyskusja = models.PositiveIntegerField(default=3)
    czas_trwania_referendum = models.PositiveIntegerField(default=3)
    
    # Ustawienia czatu
    archive_public_chat_room = models.PositiveIntegerField(default=9)
    delete_public_chat_room = models.PositiveIntegerField(default=360)
    
    # Ustawienia obywateli
    acceptance = models.PositiveIntegerField(default=3)
    delete_inactive_user_after = models.PositiveIntegerField(default=30)
    
    # Ustawienia grupy
    group_is_public = models.BooleanField(default=True)
    
    # Tożsamość strony
    site_name = models.CharField(max_length=255, blank=True, default='')
    site_name_max_12_chars = models.CharField(max_length=12, blank=True, default='')
    site_description = models.CharField(max_length=500, blank=True, default='')
```

Metoda `get()` tworzy singleton przy pierwszym dostępie i inicjalizuje go wartościami domyślnymi z `settings.py`.

### 2. Rejestr parametrów `PARAM_SPECS`

**Plik**: `site_settings/params.py`

Rejestr wszystkich parametrów z ich specyfikacjami:

```python
PARAM_SPECS = [
    # Parametry głosowań
    ParamSpec('wymaganych_podpisow', 'WYMAGANYCH_PODPISOW', 'int', CATEGORY_VOTING, ...),
    ParamSpec('czas_na_zebranie_podpisow', 'CZAS_NA_ZEBRANIE_PODPISOW', 'int', CATEGORY_VOTING, ...),
    # ... inne parametry
]
```

Każdy `ParamSpec` zawiera:
- Nazwę pola w bazie
- Nazwę zmiennej środowiskowej (fallback)
- Typ danych (`int`, `bool`, `str`)
- Kategorię (do grupowania w UI)
- Etykietę i opis
- Opcjonalne ograniczenia (`min_value`, `max_value`)

### 3. Funkcje pomocnicze

**`get_param(name)`** - odczytuje parametr z bazy lub z settings jako fallback
**`apply_parameters(changes)`** - stosuje zatwierdzone zmiany do singletonu
**`apply_brand_mark(image)`** - stosuje nowe logo
**`_sync_django_site(sp)`** - synchronizuje domenę i nazwę z modelem Django Sites

### 4. Formularz `ParametersProposalForm`

**Plik**: `glosowania/forms.py`

Dynamiczny formularz budowany z `PARAM_SPECS`:

- Wstępnie wypełniony bieżącymi wartościami
- W trybie edycji wypełniony z poprzednio proponowanych wartości
- Pole `uzasadnienie` - dlaczego zmieniamy parametry
- Pole `brand_mark` - opcjonalne nowe logo
- Metoda `changed_parameters()` - zwraca tylko zmienione parametry
- Walidacja - wymaga zmiany przynajmniej jednego parametru lub logo

### 5. Rozszerzenie modelu `Decyzja`

**Plik**: `glosowania/models.py`

Dodane pola do identyfikacji referendów parametrów:

```python
proposed_parameters = models.JSONField(null=True, blank=True, editable=False)
proposed_brand_mark = models.ImageField(upload_to='site_branding/proposed/', null=True, blank=True, editable=False)
```

### 6. Widok `parameters_propose`

**Plik**: `glosowania/views.py`

Nowy widok obsługujący:
- **Tworzenie** nowego referendum parametrów
- **Edycję** istniejącego referendum (z migawką `DecyzjaWersja`)

Logika:
1. Pobiera formularz z bieżącymi/proponowanymi wartościami
2. Na submit tworzy opis zmian w formacie czytelnym dla człowieka
3. Zapisuje `Decyzja` z `proposed_parameters` i ewentualnie `proposed_brand_mark`
4. W trybie edycji tworzy migawkę przed zapisem

### 7. Zastosowanie zmian w commandzie `vote`

**Plik**: `glosowania/management/commands/vote.py`

Po zatwierdzeniu referendum:
1. Jeśli `proposed_parameters` jest ustawione - wywołuje `apply_parameters()`
2. Jeśli `proposed_brand_mark` jest ustawione - wywołuje `apply_brand_mark()`

### 8. Zmiany w context processors

**Plik**: `zzz/context_processors.py`

- `site_description` - teraz odczytuje `site_name` i `site_description` z bazy
- `group_is_public` - teraz odczytuje z bazy zamiast z settings

### 9. Zmiany w szablonach

**`glosowania/templates/glosowania/parameters.html`**:
- Wyświetla wszystkie parametry pogrupowane według kategorii
- Przycisk do tworzenia referendum

**`glosowania/templates/glosowania/parameters_propose.html`**:
- Formularz z polami pogrupowanymi według kategorii
- W trybie edycji pokazuje obecnie proponowane logo
- Dynamiczny tytuł i przycisk (utwórz/edytuj)

**`glosowania/templates/glosowania/szczegoly.html`**:
- Wyświetla proponowane logo w referendum

**`home/templates/home/base.html`**:
- Zamieniono `request.site.name` na `site_name` z kontekstu

**`obywatele/templates/obywatele/parameters.html`**:
- Dodano przycisk do tworzenia referendum parametrów

### 10. Zmiany w widokach i commandach

Wszystkie miejsca, które wcześniej odczytywały parametry z `settings.*`, teraz używają `get_param()`:

- `chat/management/commands/chat_rooms.py` - archiwizacja/usuwanie pokoi
- `chat/management/commands/create_inbox.py` - tworzenie Inbox
- `chat/views.py` - wyświetlanie parametrów w czacie
- `obywatele/adapter.py` - kontrola publiczności grupy
- `obywatele/management/commands/count_citizens.py` - akceptacja nowych członków
- `obywatele/views.py` - próg akceptacji, usuwanie nieaktywnych
- `home/views.py` - manifest PWA, site_admin
- `zzz/scheduler.py` - powiadomienia o wydarzeniach

### 11. Aktualizacja parametrów bez restartu

**Problem**: Nazwa strony była odczytywana z `request.site.name` (Django Sites), które jest cache'owane per-proces.

**Rozwiązanie**:
1. Context processor `site_description` teraz udostępnia `site_name` czytane bezpośrednio z bazy
2. Szablony używają `site_name` z kontekstu zamiast `request.site.name`
3. `_sync_django_site()` wywołuje `Site.objects.clear_cache()` po aktualizacji
4. Manifest PWA ma `Cache-Control: no-cache` dla natychmiastowych zmian

### 12. Powiadomienia w iframe

**Plik**: `chat/static/chat/js/push-notifications.js`

Dodano obsługę powiadomień w iframe:
- Jeśli aplikacja działa w iframe (`window !== window.parent`), powiadomienie jest wysyłane przez `postMessage` do rodzica
- Pozwala to na wyświetlanie powiadomień czatu w osadzonych aplikacjach
- Format wiadomości: `{type: 'wikikracja_notification', title, body, icon, room_id, click_action}`

### 13. Testy

**Plik**: `chat/tests/test_commands.py`

Zaktualizowano test `CreateInboxCommandTest.test_skips_when_group_is_not_public`:
- Zamiast `@override_settings(GROUP_IS_PUBLIC=False)` używa `SiteParameters.get()`
- Ustawia `sp.group_is_public = False` i zapisuje

## Przepływ danych

### Tworzenie referendum parametrów

1. Użytkownik wchodzi na `/glosowania/parameters/propose/`
2. Formularz jest wstępnie wypełniony bieżącymi wartościami z `SiteParameters.get()`
3. Użytkownik zmienia wybrane parametry i/lub dodaje logo
4. Formularz waliduje - wymaga zmiany przynajmniej jednego parametru
5. Na submit tworzy `Decyzja` z:
   - `title = "System parameters change"`
   - `tresc =` lista zmian w formacie "Parametr: stara → nowa"
   - `proposed_parameters =` JSON ze zmienionymi wartościami
   - `proposed_brand_mark =` nowe logo (jeśli wgrano)

### Edycja referendum parametrów

1. Użytkownik wchodzi na `/glosowania/parameters/propose/<pk>/`
2. Formularz jest wstępnie wypełniony z `decyzja.proposed_parameters`
3. Parametry niezmienione w propozycji mają bieżące wartości systemowe
4. Na submit tworzy `DecyzjaWersja` (migawkę) przed zapisem
5. Aktualizuje istniejącą `Decyzja` z nowymi zmianami

### Zatwierdzenie referendum

1. Command `vote` wykrywa zatwierdzone referendum
2. Jeśli `proposed_parameters` jest ustawione:
   - Wywołuje `apply_parameters(changes)`
   - Zapisuje zmiany do `SiteParameters` singleton
   - Wywołuje `_sync_django_site()` (aktualizuje Django Sites i czyści cache)
3. Jeśli `proposed_brand_mark` jest ustawione:
   - Wywołuje `apply_brand_mark(image)`
   - Kopiuje obraz do `site_branding/brand_mark.png`

### Odczyt parametrów w aplikacji

1. Kod wywołuje `get_param('param_name')`
2. Funkcja odczytuje `SiteParameters.get()` (singleton z bazy)
3. Jeśli wartość w bazie jest pusta/null, używa `settings.PARAM_NAME` (env var)
4. Wszystkie parametry są teraz dynamiczne i aktualizowane bez restartu

## Priorytety wartości

### Nazwa strony w UI

1. `site_name` z `SiteParameters` (referendum)
2. `settings.SITE_NAME` (env var) - fallback

### Opis i krótka nazwa PWA

1. Parametr z `SiteParameters` (referendum)
2. `settings.SITE_DESCRIPTION` / `settings.SITE_NAME_MAX_12_CHARS` (env var) - fallback

### Inne parametry

1. Wartość z `SiteParameters` (referendum)
2. Wartość domyślna z definicji modelu
3. Wartość z `settings.*` (env var) - tylko przy inicjalizacji

## Ograniczenia

- **Zainstalowane PWA**: Nazwa i ikona w już zainstalowanej aplikacji PWA mogą pozostać stare do ponownej instalacji (ograniczenie systemu operacyjnego)
- **Nazwa strony**: Zmiana `site_name` wchodzi w życie po zatwierdzeniu referendum i synchronizuje się z Django Sites

## Migracje

Wymagane migracje:
1. `site_settings/migrations/XXXX_add_siteparameters.py` - tworzy model `SiteParameters`
2. Po pierwszym uruchomieniu singleton jest tworzony i inicjowany z `settings.py`

## Tłumaczenia

Dodano nowe komunikaty w `locale/pl/LC_MESSAGES/django.po`:
- Etykiety parametrów
- Komunikaty formularza
- Komunikaty sukcesu/błędu
- Opisy parametrów

## Bezpieczeństwo

- Tylko autor może edytować referendum (status=1)
- Parametry mają ograniczenia (`min_value`, `max_value`) zdefiniowane w `PARAM_SPECS`
- Logo jest walidowane (format PNG, wymiary, rozmiar)
- Zmiany są stosowane tylko po zatwierdzeniu referendum (głosowanie społeczności)
