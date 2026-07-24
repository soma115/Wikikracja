# Powiadomienia w Wikikracji

Wikikracja wysyła powiadomienia o nowych wiadomościach czatu i wydarzeniach przez dwie ścieżki:

- **Web Push** — dla przeglądarek na komputerze i na Androidzie (Chrome, Firefox, Edge).
- **Firebase Cloud Messaging (FCM)** — dla Androida, gdy jest skonfigurowany.

## Architektura

### Frontend

- `chat/static/chat/js/push-notifications.js` — rejestruje urządzenie po stronie użytkownika.
- `chat/static/chat/js/sw.js` — service worker Web Push, odbiera push i pokazuje powiadomienia.
- `chat/static/chat/js/firebase-messaging-sw.js` — service worker FCM. Jego konfiguracja jest wstrzykiwana dynamicznie przez widok `firebase_messaging_sw` w `home/views.py`.
- `home/static/home/js/app.js` — pokazuje baner z prośbą o uprawnienia do powiadomień i wywołuje `Notification.requestPermission()`.

### Backend

- `chat/push_api.py` — endpointy `POST /chat/api/push/register/` i `/chat/api/push/unregister/` zapisują tokeny w modelach `WebPushDevice` i `GCMDevice` z biblioteki `django-push-notifications`.
- `chat/services.py` — wysyła powiadomienia metodą `send_push_notification_sync` przy nowych wiadomościach i wzmiankach.
- `home/views.py` — serwuje `/sw.js`, `/firebase-messaging-sw.js`, `/dynamic-settings.js` i `/manifest.json`.
- `zzz/scheduler.py` — wysyła powiadomienia o rozpoczynających się wydarzeniach.

## Konfiguracja (`zzz/.env`)

### Web Push (VAPID)

```bash
VAPID_ADMIN_EMAIL=admin@example.com
VAPID_PUBLIC_KEY=BOA0...        # base64-url-safe, bez paddingu, bez nowych linii
VAPID_PRIVATE_KEY=...            # format zgodny z django-push-notifications
```

- Klucz publiczny musi być **base64-url-safe** (znaki `A-Z`, `a-z`, `0-9`, `-`, `_`). Wartość jest konwertowana na `Uint8Array` w przeglądarce.
- Klucz prywatny powinien być w formacie akceptowanym przez `django-push-notifications` — zazwyczaj base64-url-safe lub PEM.

### FCM (Android)

```bash
FIREBASE_CERT_PATH=firebase-service-account.json
FIREBASE_API_KEY=AIza...
FIREBASE_AUTH_DOMAIN=projekt.firebaseapp.com
FIREBASE_PROJECT_ID=projekt
FIREBASE_STORAGE_BUCKET=projekt.appspot.com
FIREBASE_MESSAGING_SENDER_ID=123456789
FIREBASE_APP_ID=1:123456789:web:...
FIREBASE_VAPID_KEY=BN...   # Web Push certificate z Firebase Console > Cloud Messaging
```

- `FIREBASE_CERT_PATH` to plik JSON z kluczem service account dla serwera (wysyłanie z backendu).
- `FIREBASE_*` to konfiguracja klienta dla SDK Firebase w przeglądarce.
- **`FIREBASE_VAPID_KEY`** to *Web Push certificate* (para kluczy) z Firebase Console → Cloud Messaging → Web configuration. Jest wymagany przez `messaging.getToken({ vapidKey })` w przeglądarce. To **inny** klucz niż nasze `VAPID_PUBLIC_KEY` (które służy własnemu Web Push). Bez niego FCM w przeglądarce (także Android Chrome) zawodzi.
- W Kubernetes plik JSON jest mountowany przez secret, a `GOOGLE_APPLICATION_CREDENTIALS` wskazuje na niego.

### Konfiguracja w Kubernetes (Flux)

- Zmienne `VAPID_*` i `FIREBASE_*` (w tym `FIREBASE_VAPID_KEY`) są w ConfigMap `wikikracja-common-config` (`flux-cluster/clusters/apps/wikikracja/wikikracja-common-config.yaml`), współdzielonym przez wszystkie instancje przez `envFrom`.
- Certyfikat service account jest w secrecie `wikikracja-shared-secret` pod kluczem `firebase-service-account.json`, montowany do `/etc/firebase/firebase-service-account.json`, a `GOOGLE_APPLICATION_CREDENTIALS` w deploymencie wskazuje na tę ścieżkę.
- Po zmianie ConfigMap należy zrestartować deploymenty instancji (Flux zsynchronizuje manifesty, ale pody muszą przeczytać nowe env).

## Wymagania

- Uprawnienie do powiadomień musi być udzielone przez użytkownika (baner na stronie głównej).
- Powiadomienia push działają tylko przez **HTTPS** (lub `localhost` w trybie deweloperskim).
- Service workery muszą być serwowane z **scope'u roota** (`/`), dlatego są pod `/sw.js` i `/firebase-messaging-sw.js`, a nie z katalogu `static`.

## Rejestracja urządzenia

1. Użytkownik klika *Włącz powiadomienia*.
2. `app.js` wywołuje `Notification.requestPermission()`.
3. Po zgodzie strona się przeładowuje.
4. `push-notifications.js` wybiera platformę:
   - **Web Push**: rejestruje `/sw.js` i wywołuje `pushManager.subscribe()` z `applicationServerKey`.
   - **FCM na Androidzie**: rejestruje `/firebase-messaging-sw.js`, inicjalizuje Firebase i pobiera token `messaging.getToken({ serviceWorkerRegistration: swRegistration })`.
5. Token/subskrypcja jest wysyłana na `/chat/api/push/register/` i zapisywana w bazie.

## Wysyłka

- `WebPushDevice.send_message(json)` wysyła ładunek JSON do przeglądarki. `sw.js` odbiera go w `push` i wywołuje `showNotification()`.
- `GCMDevice.send_message(message)` używa `firebase_admin.messaging` do wysyłki przez FCM. `firebase_admin` jest inicjalizowany w `zzz/settings.py` z certyfikatu service account.

## Troubleshooting

| Problem | Możliwa przyczyna |
|---|---|
| Na desktopie nie pojawia się prośba o zgodę | Banner może być odrzucony; sprawdź `localStorage` pod kluczem `notification-banner-dismissed` |
| `pushManager.subscribe()` zawodzi | `VAPID_PUBLIC_KEY` ma zły format lub zawiera nowe linie/cudzysłowy |
| Na Androidzie FCM nie działa | Brak `/firebase-messaging-sw.js` w roocie, brak `FIREBASE_API_KEY` w `.env` lub zły `serviceWorkerRegistration` |
| `messaging.getToken()` rzuca błąd / brak tokenu | Brak `FIREBASE_VAPID_KEY` (Web Push certificate) — dodaj go w Firebase Console i w konfiguracji |
| `firebase-messaging-sw.js` ma błąd składni | Widok `firebase_messaging_sw` musi zamieniać cały blok `const firebaseConfig = {...}` a nie tylko początek linii |
| Backend nie wysyła FCM | Brak certyfikatu `firebase-service-account.json` lub brak `GOOGLE_APPLICATION_CREDENTIALS` |
| Po zmianie subskrypcji nie przychodzą powiadomienia | `sw.js` musi wysłać `endpoint`, `p256dh` i `auth` do `/chat/api/push/register/` |

## Pliki objaśnione

- `chat/static/chat/js/push-notifications.js` — wybór platformy i rejestracja.
- `chat/static/chat/js/sw.js` — Web Push service worker.
- `chat/static/chat/js/firebase-messaging-sw.js` — szablon FCM SW z wstrzykiwaną konfiguracją.
- `home/views.py` — widoki `service_worker`, `firebase_messaging_sw`, `vapid_config`, `manifest`.
- `chat/services.py` — logika wysyłania powiadomień.
