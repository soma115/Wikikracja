# Proces przyjmowania nowej osoby

Ten dokument opisuje kompletny proces przyjmowania nowych członków do społeczności Wikikracja.

## Przegląd procesu

Proces przyjmowania nowej osoby składa się z następujących etapów:

1. **Rejestracja** - Wprowadzenie adresu email i CAPTCHA
2. **Potwierdzenie email** - Weryfikacja adresu email
3. **Formularz onboarding** - Wypełnienie danych osobowych
4. **Poczekalnia** - Głosowanie przez obywateli
5. **Akceptacja** - Przyjęcie do społeczności

## Szczegółowy opis etapów

### 1. Rejestracja (Signup)

**Działania:**
- Użytkownik wypełnia formularz rejestracyjny zawierający:
  - Adres email
  - CAPTCHA (zabezpieczenie przed botami)
- Hasło jest generowane automatycznie (12 znaków, alfanumeryczne) w `CustomSignupForm.clean_password1`
- Użytkownik nigdy nie widzi hasła wygenerowanego przy rejestracji; logowanie jest skonfigurowane przez email. Po przyjęciu ustawia własne hasło przez link do resetu hasła w wiadomości powitalnej.
- Konto kandydata jest nieaktywne (`is_active = False`) do czasu spełnienia warunków przyjęcia

**Status:** `EMAIL_ENTERED`

**Wymagane pola:**
- Email (wymagany; formularz odrzuca adres już używany, porównując bez rozróżniania wielkości liter)

**Powiadomienia:**
- Email z linkiem potwierdzającym jest wysyłany ręcznie w `CustomSignupForm.save()` za pomocą `EmailConfirmationHMAC` i `adapter.send_confirmation_mail`
- Po potwierdzeniu emaila wysyłany jest drugi email z linkiem do formularzu onboarding (signal handler `set_onboarding_email_confirmed`)
- Wszyscy aktywni obywatele z włączonymi powiadomieniami `obywatele` otrzymują powiadomienie o nowym kandydacie (sygnał `citizen_proposed`)

**Konfiguracja:**
- `EMAIL_BACKEND` - konfiguracja SMTP (dla produkcji)
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` - ustawienia serwera email

### 2. Potwierdzenie email

**Działania:**
- Użytkownik klika w link potwierdzający otrzymany w emailu
- System weryfikuje autentyczność linku (podpis HMAC z `allauth.account.models.EmailConfirmationHMAC`)
- Po potwierdzeniu status onboarding zmienia się na `EMAIL_CONFIRMED`
- Wysyłany jest drugi email z linkiem do formularzu onboarding (token podpisany `TimestampSigner`)
- Wyświetlany jest komunikat o pomyślnym potwierdzeniu email

**Status:** `EMAIL_CONFIRMED`

**Bezpieczeństwo:**
- Linki potwierdzające są podpisywane cyfrowo (EmailConfirmationHMAC)
- Linki mają ograniczony czas ważności: 7 dni (konfigurowalne przez `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`)
- Po potwierdzeniu emaila użytkownik jest przekierowany do formularza onboarding z podpisanym tokenem

### 3. Formularz onboarding

**Działania:**
- Użytkownik wypełnia formularz z danymi osobowymi (`OnboardingDetailsForm`)
- Dane są zapisywane w profilu `Uzytkownik` oraz w polach `first_name` / `last_name` modelu `User`

**Wymagane pola:**
- Imię (`first_name`)
- Nazwisko (`last_name`)
- Miejscowość (`city`)

**Pozostałe pola formularza:**
- Telefon (`phone`) jest opcjonalny; formularz oferuje także kraj numeru, preferowaną metodę kontaktu i link do profilu. Wybrana metoda może wymagać numeru telefonu lub właściwego linku.
- Województwo (`voivodeship`) — opcjonalna lista regionów Polski (`country__code='PL'`)
- Zawód (`job`), umiejętności/wiedza/hobby (`skills_knowledge_hobby`) i rzeczy do nauczenia (`want_to_learn`)
- Prowadzę swój biznes (`business_active`), adres strony (`business_website`) i opis działalności (`business_description`)
- Dlaczego chcesz dołączyć? (`why`)

**Status:** `FORM_COMPLETED` (po zapisaniu formularza, niezależnie od procentu wypełnienia)

**Dostęp do formularza:**
- Przez sesję (natychmiast po rejestracji, `onboarding_user_id`)
- Przez link w drugim emailu (wysyłanym po potwierdzeniu emaila)
- Fallback dla aktywnych użytkowników z nieukończonym onboarding (`EMAIL_ENTERED` lub `EMAIL_CONFIRMED`)

**Formularz pełny profilu (dla polecenia):**
Widok `obywatele.views.dodaj` ("Zaproponuj osobę") używa pełnego `ProfileForm` z dodatkowymi polami: `want_to_learn`, `business_active`, `business_website`, `business_description`.

### 4. Poczekalnia (Waiting Room)

**Działania:**
- Kandydaci są wyświetleni na liście w sekcji `/obywatele/poczekalnia/`
- Istniejący obywatele mogą głosować na kandydatów w widoku szczegółów `/obywatele/poczekalnia/<pk>/`
- Każdy obywatel może oddać jeden głos na kandydata:
  - +1 (Akceptuję)
  - 0 (Neutralny — domyślny, nie tworzy się automatycznie przy otwarciu listy)
  - -1 (Odrzucam)

**Wymagania do głosowania:**
- Kandydat musi mieć potwierdzony email LUB być poleconym przez istniejącego obywatela (`polecajacy`)
- Formularz onboarding jest wyświetlany jako procent wypełnienia (`form_completion_percent`), ale nie blokuje możliwości głosowania w kodzie

**Próg akceptacji:**
- Parametr progowy to `acceptance` z singletonu `SiteParameters`; zmienia się go przez referendum.
- Wymagana reputacja jest dynamiczna i zależy od populacji (funkcja `required_reputation()`):
  - Jeśli populacja < 2 × `acceptance`: próg = populacja - `acceptance`
  - Jeśli populacja >= 2 × `acceptance`: próg = `acceptance`
- Komenda przyjmuje kandydata, gdy jego reputacja jest większa od wyliczonego progu.
- Mechanizm ten zapobiega sytuacji, w której mała grupa nie może przyjąć nowych członków

**Czas oczekiwania:**
- Maksymalny okres nieaktywności: `delete_inactive_user_after` dni z `SiteParameters`; parametr zmienia się przez referendum.
- Po tym czasie konto kandydata jest automatycznie usuwane przez komendę `count_citizens` (patrz `delete_inactive_users`)
- Licznik opiera się na `last_login`; jeśli kandydat nigdy się nie logował, `last_login` jest ustawiane na `now()` przy pierwszym sprawdzeniu

**Powiadomienia:**
- Każdy obywatel z włączonymi powiadomieniami `obywatele` (push/email/WebSocket) otrzymuje powiadomienie o nowych kandydatach

### 5. Akceptacja

**Działania:**
- Akceptacja odbywa się automatycznie przez scheduler/komendę `count_citizens` (`activate_eligible_users`)
- Gdy reputacja kandydata przekroczy dynamiczny próg wymagany przez `required_reputation()`:
  - Konto jest aktywowane (`is_active = True`)
  - Data przyjęcia jest zapisywana (`data_przyjecia`)
  - Odbiorcy sygnału `citizen_accepted` tworzą pokoje 1-to-1 i przyznają dostęp do istniejących pokoi publicznych
  - Wysyłany jest email powitalny na podstawie postu systemowego `welcome_email`, z linkiem do ustawienia hasła przez reset hasła; komenda nie generuje ani nie wysyła nowego hasła
  - Pozostali obywatele zyskują +1 punkt reputacji, ale tylko gdy populacja nie przekracza 2 × `acceptance` (`grant_automatic_reputation`)
- Użytkownik otrzymuje pełny dostęp do funkcji platformy

**Status:** `ACTIVE` (obywatel)

**Reputacja:**
- Nowy obywatel startuje z reputacją 0
- Reputacja jest obliczana na podstawie sumy głosów innych obywateli z modelu `Rate`
- Reputacja może się zmieniać w czasie (głosy mogą być wycofywane)

## Alternatywna ścieżka: Polecenie przez obywatela

Istnieje możliwość polecenia nowej osoby przez istniejącego obywatela:

**Proces:**
1. Obywatel wypełnia formularz "Zaproponuj osobę" (`/obywatele/nowy/`)
2. Konto kandydata jest tworzone jako nieaktywne
3. Pole `polecajacy` jest ustawiane na nazwę użytkownika polecającego
4. Polecający automatycznie zapisuje kandydatowi ocenę +1 (`Rate.rate = 1`)
5. Wszyscy obywatele otrzymują powiadomienie o nowym kandydacie (`citizen_proposed`)
6. Kandydat nie musi potwierdzać email (`EmailAddress` tworzony z `verified=True`)
7. Pozostałe kroki są takie same jak w standardowym procesie

## Konfiguracja

Parametry członkostwa (`acceptance`, `delete_inactive_user_after`) są przechowywane w singletonie `SiteParameters` i zmieniane przez referendum. Aktualny opis dla użytkowników znajduje się w [przewodniku parametrów](Glosowanie_nad_parametrami_systemu-dla_uzytkownikow.md), a szczegóły implementacji w [dokumentacji technicznej](Glosowanie_nad_parametrami_systemu-dla_developerow.md).

Podstawowa konfiguracja SMTP i zmiennych środowiskowych (`EMAIL_*`, `SECRET_KEY`, `REDIS_HOST` itp.) opisana jest w [DEPLOYMENT_INSTRUCTIONS.md](DEPLOYMENT_INSTRUCTIONS.md).

Ustawienie specyficzne dla onboarding:

```bash
# Opóźnienie wysyłania email w sekundach (dla uniknięcia race conditions)
EMAIL_SEND_DELAY_SECONDS=2
```

Kluczowe ustawienia AllAuth w `settings.py`:

```python
# Email verification
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Wymaga potwierdzenia emaila
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 7  # Linki ważne 7 dni
ACCOUNT_CONFIRM_EMAIL_ON_GET = True  # Pozwala na GET requests

# Login
ACCOUNT_LOGIN_METHODS = {'email'}  # Logowanie tylko przez email

# Signup
ACCOUNT_SIGNUP_PASSWORD_GENERATION = True  # Auto-generuj hasło
ACCOUNT_SIGNUP_PASSWORD_VERIFICATION = False  # Nie wymaga powtórnego hasła
ACCOUNT_SIGNUP_REDIRECT_URL = '/obywatele/onboarding/'  # Bezpośrednio do onboarding

# Custom components
ACCOUNT_FORMS = {'signup': 'obywatele.forms.CustomSignupForm'}
ACCOUNT_ADAPTER = 'obywatele.adapter.CustomAccountAdapter'
```

## Modele danych

### Uzytkownik (Citizen)

Kluczowe pola związane z onboarding:

- `onboarding_status` — Status procesu onboarding (`EMAIL_ENTERED`, `EMAIL_CONFIRMED`, `FORM_COMPLETED`)
- `polecajacy` — Nazwa użytkownika polecającego (jeśli dotyczy)
- `data_przyjecia` — Data przyjęcia do społeczności
- `reputation` — Punkty reputacji
- `form_completion_percent` — Właściwość obliczana z `ONBOARDING_FORM_FIELDS` oraz imienia i nazwiska
- `email_frequency` — Częstotliwość digestu email (`daily`/`weekly`/`monthly`/`never`)
- `email_notifications_*` — Preferencje email (m.in. `obywatele`, `glosowania`, `chat`, `events`)
- `push_notifications_*` — Preferencje push (m.in. `obywatele`, `glosowania`, `chat`, `events`, `post`, `task`, `survey`)

### EmailAddress (AllAuth)

Model AllAuth do zarządzania emailami użytkowników:

- `user` — FK do User
- `email` — adres email
- `verified` — boolean (czy email został potwierdzony)
- `primary` — boolean (czy to główny email)

**Uwaga:** Migracja `0027_auto_verify_email_addresses` naprawia brakujące rekordy `EmailAddress` dla aktywnych użytkowników.

### Rate (Głos)

Relacja między obywatelem a kandydatem:

- `kandydat` — Kandydat (ForeignKey do `Uzytkownik`)
- `obywatel` — Obywatel głosujący (ForeignKey do `Uzytkownik`)
- `rate` — Głos (+1, 0, -1)

### CitizenActivity

Śledzenie aktywności związanych z obywatelami:

- `uzytkownik` — FK do `Uzytkownik`
- `activity_type` — Typ aktywności (`NEW_CANDIDATE`, `USER_ACTIVATED`, `USER_BLOCKED`, `DELETION_REQUESTED`)
- `timestamp` — Czas aktywności
- `description` — Opis aktywności

## Powiadomienia

System wysyła powiadomienia w następujących sytuacjach:

1. **Nowa rejestracja** — Email z linkiem potwierdzającym email
2. **Potwierdzenie email** — Drugi email z linkiem do formularzu onboarding
3. **Polecenie osoby** — Powiadomienie do wszystkich aktywnych obywateli (`citizen_proposed`, kategoria `obywatele`)
4. **Akceptacja kandydata** — Email powitalny z linkiem do ustawienia hasła przez reset hasła

Użytkownicy mogą zarządzać preferencjami powiadomień w swoim profilu (`/obywatele/settings/`):

- **Email:**
  - `email_frequency` — częstotliwość digestu aktywności (`daily`/`weekly`/`monthly`/`never`)
  - `email_notifications_obywatele` — nowi obywatele i prośby o członkostwo
  - `email_notifications_glosowania` — propozycje praw i głosowania
  - `email_notifications_chat` — nowe wiadomości w czacie
  - `email_notifications_events` — wydarzenia
- **Push:**
  - `push_notifications_obywatele`, `push_notifications_glosowania`, `push_notifications_chat`, `push_notifications_events`, `push_notifications_post`, `push_notifications_task`, `push_notifications_survey`

Wspólna wysyłka FCM/WebSocket/e-mail znajduje się w `core/notifications.py`; payloady czatu w `chat/notifications.py`, a obsługa workera Redis Stream w [instrukcji wdrożenia](DEPLOYMENT_INSTRUCTIONS.md#chat-notification-worker).

## Bezpieczeństwo

### Ochrona przed duplikatami
- Formularz rejestracji sprawdza istniejący adres e-mail bez rozróżniania wielkości liter; model konta może zawierać historyczne duplikaty.
- `CaseInsensitiveEmailBackend` obsługuje przypadki, w których dla adresu istnieje więcej niż jedno konto.
- Komenda `count_citizens` zawiera `cleanup_duplicate_users`, która porządkuje historyczne duplikaty.
- Migracja `0027_auto_verify_email_addresses` naprawia brakujące rekordy `EmailAddress` dla aktywnych użytkowników.

### Ochrona przed botami
- CAPTCHA w formularzu rejestracyjnym (`django-simple-captcha`)
- Weryfikacja email przed akceptacją (chyba że kandydat jest polecony)

### Ochrona przed abuse
- Limit czasu w poczekalni (automatyczne usuwanie nieaktywnych kont przez `count_citizens`)
- Dynamiczny próg akceptacji (zapobieganie szybkim przyjęciom)
- Wymagane potwierdzenie email LUB polecenie przez istniejącego obywatela

## Zarządzanie procesem

### Widoki

- **Poczekalnia** (`/obywatele/poczekalnia/`) — Lista wszystkich kandydatów
- **Szczegóły kandydata** (`/obywatele/poczekalnia/<pk>/`) — Głosowanie na kandydata
- **Edycja kandydata** (`/obywatele/poczekalnia/<pk>/edit/`) — Edycja profilu kandydata
- **Parametry** (`/obywatele/parameters/`) — Podgląd ustawień systemu
- **Lista obywateli** (`/obywatele/`) — Lista wszystkich aktywnych obywateli
- **Onboarding** (`/obywatele/onboarding/`) — Formularz onboarding (dostępny przez sesję/token)
- **Onboarding — oczekiwanie** (`/obywatele/onboarding/waiting/`) — Strona dla kandydata po wypełnieniu formularza

### Komendy zarządzania

```bash
# Liczenie reputacji, aktywacja, blokada i czyszczenie obywateli
python manage.py count_citizens

# Migracje bazy danych
python manage.py migrate
```

## Troubleshooting

### Kandydat nie otrzymuje emaila potwierdzającego
- Sprawdź konfigurację SMTP w `.env`
- Sprawdź logi aplikacji pod kątem błędów wysyłania email
- Upewnij się, że `EMAIL_BACKEND` jest poprawnie skonfigurowany
- Sprawdź czy `CustomSignupForm.save()` nie zgłasza wyjątku w logach

### Kandydat nie pojawia się w poczekalni
- Upewnij się, że konto ma `is_active = False`
- Sprawdź, czy email został potwierdzony LUB czy kandydat jest polecony
- Sprawdź status `onboarding_status` w bazie danych

### Kandydat nie może zostać zaakceptowany
- Sprawdź, czy kandydat ma wymaganą liczbę akceptacji (`reputation > required_reputation`)
- Sprawdź, czy kandydat ma potwierdzony email LUB jest polecony
- Sprawdź, czy `count_citizens` jest uruchamiany regularnie (scheduler lub ręcznie)

### Konto kandydata zostało usunięte
- Sprawdź wartość `delete_inactive_user_after` w parametrach instancji i czy upłynął wskazany okres
- Kandydat musi zarejestrować się ponownie

## Podsumowanie

Proces przyjmowania nowych osób w Wikikracja jest zaprojektowany tak, aby:

1. **Zapewnić bezpieczeństwo** — Weryfikacja email, CAPTCHA, dynamiczny próg akceptacji
2. **Zachować kontrolę społeczności** — Głosowanie przez istniejących obywateli
3. **Zapobiegać abuse** — Limity czasowe, wymagania weryfikacji
4. **Być elastyczny** — Alternatywna ścieżka przez polecenie, dynamiczny próg akceptacji
5. **Być wygodny dla użytkownika** — Dwa kroki z osobnymi emailami (potwierdzenie + formularz)

Proces ten jest kluczowy dla utrzymania zdrowej i zaufanej społeczności demokratycznej.
