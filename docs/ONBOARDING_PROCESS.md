# Proces przyjmowania nowej osoby

Ten dokument opisuje kompletny proces przyjmowania nowych członków do społeczności Wikikracja.

## Przegląd procesu

Proces przyjmowania nowej osoby składa się z następujących etapów:

1. **Rejestracja** - Wprowadzenie adresu email
2. **Potwierdzenie email** - Weryfikacja adresu email
3. **Formularz onboarding** - Wypełnienie szczegółowych danych
4. **Poczekalnia** - Głosowanie przez obywateli
5. **Akceptacja** - Przyjęcie do społeczności

## Szczegółowy opis etapów

### 1. Rejestracja (Signup)

**Działania:**
- Użytkownik wypełnia formularz rejestracyjny zawierający:
  - Adres email
  - CAPTCHA (zabezpieczenie przed botami)
- Hasło jest generowane automatycznie (12 znaków, alfanumeryczne)
- Użytkownik nigdy nie widzi hasła - logowanie odbywa się wyłącznie przez email

**Status:** `EMAIL_ENTERED`

**Wymagane pola:**
- Email (wymagany, unikalny)

**Powiadomienia:**
- Email z linkiem potwierdzającym jest wysyłany za pomocą `CustomSignupForm.save()` (AllAuth nie wysyła automatycznie dla custom form)
- Po potwierdzeniu emaila wysyłany jest drugi email z linkiem do formularzu onboarding (signal handler `email_confirmed`)
- Wszyscy aktywni obywatele z włączonymi powiadomieniami otrzymują informację o nowym kandydacie

**Konfiguracja:**
- `EMAIL_BACKEND` - konfiguracja SMTP (dla produkcji)
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` - ustawienia serwera email

### 2. Potwierdzenie email

**Działania:**
- Użytkownik klika w link potwierdzający otrzymany w emailu
- System weryfikuje autentyczność linku (podpis HMAC)
- Po potwierdzeniu użytkownik otrzymuje drugi email z linkiem do formularzu onboarding
- Wyświetlany jest komunikat o pomyślnym potwierdzeniu email

**Status:** `EMAIL_CONFIRMED`

**Bezpieczeństwo:**
- Linki potwierdzające są podpisywane cyfrowo (EmailConfirmationHMAC)
- Linki mają ograniczony czas ważności: 7 dni (konfigurowalne przez `ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS`)
- Po potwierdzeniu emaila użytkownik jest przekierowany do formularza onboarding z podpisanym tokenem

### 3. Formularz onboarding

**Działania:**
- Użytkownik wypełnia szczegółowy formularz z danymi osobowymi
- Dane są zapisywane w profilu użytkownika

**Wymagane pola:**
- Imię (first_name)
- Nazwisko (last_name)
- Telefon / komunikator (phone)
- Miejscowość (city)
- Zawód (job)
- Dlaczego chcesz dołączyć? (why)

**Opcjonalne pola:**
- Hobby
- Umiejętności (skills)
- Wiedza (knowledge)
- Chcę się nauczyć (want_to_learn)
- Biznes
- Obowiązki (responsibilities)
- Do oddania za darmo (to_give_away)
- Do pożyczenia (to_borrow)
- Na sprzedaż (for_sale)
- Potrzebuję (i_need)
- Prezent (gift)
- Inne (other)

**Status:** `FORM_COMPLETED`

**Dostęp do formularza:**
- Przez sesję (natychmiast po rejestracji)
- Przez link w drugim emailu (wysyłanym po potwierdzeniu emaila)
- Fallback dla aktywnych użytkowników z nieukończonym onboarding

### 4. Poczekalnia (Waiting Room)

**Działania:**
- Kandydaci są wyświetleni na liście w sekcji "Poczekalnia"
- Istniejący obywatele mogą głosować na kandydatów
- Każdy obywatel może oddać jeden głos na kandydata:
  - +1 (Akceptuję)
  - 0 (Neutralny - domyślny)
  - -1 (Odrzucam)

**Wymagania do głosowania:**
- Kandydat musi mieć potwierdzony email LUB być poleconym przez istniejącego obywatela
- Kandydat musi mieć ukończony formularz onboarding

**Próg akceptacji:**
- Wymagana liczba akceptacji: `ACCEPTANCE` (domyślnie 3)
- Próg jest dynamiczny i zależy od populacji:
  - Jeśli populacja ≤ 2 × ACCEPTANCE: próg = populacja - ACCEPTANCE
  - Jeśli populacja > 2 × ACCEPTANCE: próg = ACCEPTANCE
- Mechanizm ten zapobiega sytuacji, w której mała grupa nie może przyjąć nowych członków

**Czas oczekiwania:**
- Maksymalny czas w poczekalni: `DELETE_INACTIVE_USER_AFTER` dni (domyślnie 30)
- Po tym czasie konto kandydata jest automatycznie usuwane

**Powiadomienia:**
- Każdy obywatel otrzymuje powiadomienie o nowych kandydatach (jeśli ma włączone powiadomienia `email_notifications_obywatele`)

### 5. Akceptacja

**Działania:**
- Gdy kandydat uzyska wymaganą liczbę akceptacji:
  - Konto jest aktywowane (`is_active = True`)
  - Data przyjęcia jest zapisywana (`data_przyjecia`)
  - Wszyscy inni obywatele zyskują +1 punkt reputacji
- Użytkownik otrzymuje pełny dostęp do funkcji platformy

**Status:** `ACTIVE` (obywatel)

**Reputacja:**
- Nowy obywatel startuje z reputacją 0
- Reputacja jest obliczana na podstawie głosów innych obywateli
- Reputacja może się zmieniać w czasie (głosy mogą być wycofywane)

## Alternatywna ścieżka: Polecenie przez obywatela

Istnieje możliwość polecenia nowej osoby przez istniejącego obywatela:

**Proces:**
1. Obywatel wypełnia formularz "Zaproponuj osobę" z danymi kandydata
2. Konto kandydata jest tworzone jako nieaktywne
3. Pole `polecajacy` jest ustawiane na nazwę polecającego
4. Polecający automatycznie przyznaje kandydatowi +1 akceptację
5. Wszyscy obywatele otrzymują powiadomienie o nowym kandydacie
6. Kandydat nie musi potwierdzać email (jeśli jest polecony)
7. EmailAddress jest tworzony z `verified=True` dla poleconych użytkowników
8. Pozostałe kroki są takie same jak w standardowym procesie

## Konfiguracja

Kluczowe ustawienia w pliku `.env`:

```bash
# Liczba wymaganych akceptacji (domyślnie 3)
ACCEPTANCE=3

# Maksymalny czas w poczekalni w dniach (domyślnie 30)
DELETE_INACTIVE_USER_AFTER=30

# Ustawienia email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

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

# Custom components
ACCOUNT_FORMS = {'signup': 'obywatele.forms.CustomSignupForm'}
ACCOUNT_ADAPTER = 'obywatele.adapter.CustomAccountAdapter'
```

## Modele danych

### Uzytkownik (Citizen)

Kluczowe pola związane z onboarding:

- `onboarding_status` - Status procesu onboarding (EMAIL_ENTERED, EMAIL_CONFIRMED, FORM_COMPLETED)
- `polecajacy` - Nazwa użytkownika polecającego (jeśli dotyczy)
- `data_przyjecia` - Data przyjęcia do społeczności
- `reputation` - Punkty reputacji

### EmailAddress (AllAuth)

Model AllAuth do zarządzania emailami użytkowników:

- `user` - FK do User
- `email` - adres email
- `verified` - boolean (czy email został potwierdzony)
- `primary` - boolean (czy to główny email)

**Uwaga:** Migracja `0027_auto_verify_email_addresses` naprawia brakujące rekordy EmailAddress dla aktywnych użytkowników.

### Rate (Głos)

Relacja między obywatelem a kandydatem:

- `kandydat` - Kandydat (ForeignKey do Uzytkownik)
- `obywatel` - Obywatel głosujący (ForeignKey do Uzytkownik)
- `rate` - Głos (+1, 0, -1)

### CitizenActivity

Śledzenie aktywności związanych z obywatelami:

- `activity_type` - Typ aktywności (NEW_CANDIDATE, USER_ACTIVATED, USER_BLOCKED)
- `timestamp` - Czas aktywności
- `description` - Opis aktywności

## Powiadomienia email

System wysyła powiadomienia email w następujących sytuacjach:

1. **Nowa rejestracja** - Email z linkiem potwierdzającym email
2. **Potwierdzenie email** - Drugi email z linkiem do formularzu onboarding
3. **Polecenie osoby** - Wszyscy obywatele z włączonymi powiadomieniami o obywatelach
4. **Akceptacja kandydata** - Informacja o nowym obywatelu

Użytkownicy mogą zarządzać preferencjami powiadomień w swoim profilu:
- `email_notifications_obywatele` - Powiadomienia o nowych obywatelach i prośbach o członkostwo
- `email_notifications_glosowania` - Powiadomienia o propozycjach praw i głosowaniach
- `email_notifications_chat` - Powiadomienia o nowych wiadomościach w czacie
- `email_notifications_chat_participated` - Powiadomienia tylko o pokojach, w których użytkownik uczestniczył

## Bezpieczeństwo

### Ochrona przed duplikatami
- Unikalne ograniczenie na polu `email` w bazie danych (migracja `0012_alter_user_email_unique`)
- Obsługa błędu `MultipleObjectsReturned` w `CaseInsensitiveEmailBackend`
- Mechanizm usuwania duplikatów w migracji `0011_remove_duplicate_emails`
- Migracja `0027_auto_verify_email_addresses` naprawia brakujące EmailAddress dla aktywnych użytkowników

### Ochrona przed botami
- CAPTCHA w formularzu rejestracyjnym
- Weryfikacja email przed akceptacją

### Ochrona przed abuse
- Limit czasu w poczekalni (automatyczne usuwanie nieaktywnych kont)
- Dynamiczny próg akceptacji (zapobieganie szybkim przyjęciom)
- Wymagane potwierdzenie email LUB polecenie przez istniejącego obywatela

## Zarządzanie procesem

### Widoki dla administratorów

- **Poczekalnia** (`/obywatele/poczekalnia/`) - Lista wszystkich kandydatów
- **Parametry** (`/obywatele/parameters/`) - Podgląd ustawień systemu
- **Lista obywateli** (`/obywatele/`) - Lista wszystkich aktywnych obywateli

### Komendy zarządzania

```bash
# Liczba zarejestrowanych obywateli
python manage.py count_citizens

# Migracje bazy danych
python manage.py migrate
```

## Troubleshooting

### Kandydat nie otrzymuje emaila potwierdzającego
- Sprawdź konfigurację SMTP w `.env`
- Sprawdź logi aplikacji pod kątem błędów wysyłania email
- Upewnij się, że `EMAIL_BACKEND` jest poprawnie skonfigurowany

### Kandydat nie pojawia się w poczekalni
- Upewnij się, że kandydat ukończył formularz onboarding
- Sprawdź, czy email został potwierdzony LUB czy kandydat jest polecony
- Sprawdź status `onboarding_status` w bazie danych

### Kandydat nie może zostać zaakceptowany
- Sprawdź, czy kandydat ma wymaganą liczbę akceptacji
- Sprawdź, czy kandydat ma potwierdzony email LUB jest polecony
- Sprawdź, czy kandydat ukończył formularz onboarding

### Konto kandydata zostało usunięte
- Sprawdź, czy minął czas `DELETE_INACTIVE_USER_AFTER` dni
- Kandydat musi zarejestrować się ponownie

## Podsumowanie

Proces przyjmowania nowych osób w Wikikracja jest zaprojektowany tak, aby:

1. **Zapewnić bezpieczeństwo** - Weryfikacja email, CAPTCHA, dynamiczny próg akceptacji
2. **Zachować kontrolę społeczności** - Głosowanie przez istniejących obywateli
3. **Zapobiegać abuse** - Limity czasowe, wymagania weryfikacji
4. **Być elastyczny** - Alternatywna ścieżka przez polecenie, dynamiczny próg akceptacji
5. **Być wygodny dla użytkownika** - Dwa kroki z osobnymi emailami (potwierdzenie + formularz)

Proces ten jest kluczowy dla utrzymania zdrowej i zaufanej społeczności demokratycznej.
