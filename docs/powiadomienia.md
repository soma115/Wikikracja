# Powiadomienia w Wikikracji

Wikikracja wysyła powiadomienia o nowych wiadomościach czatu i wydarzeniach wyłącznie przez **Firebase Cloud Messaging (FCM)**. Web Push (VAPID) został usunięty.

## Architektura

### Frontend

- `chat/static/chat/js/push-notifications.js` — inicjalizuje Firebase i rejestruje token FCM po stronie użytkownika.
- `chat/static/chat/js/firebase-messaging-sw.js` — service worker FCM. Jego konfiguracja jest wstrzykiwana dynamicznie przez widok `firebase_messaging_sw` w `home/views.py`.
- `home/static/home/js/app.js` — pokazuje baner z prośbą o uprawnienia do powiadomień i wywołuje `Notification.requestPermission()`.

### Backend

- `chat/push_api.py` — endpointy `POST /chat/api/push/register/` i `/chat/api/push/unregister/` zapisują tokeny w modelu `GCMDevice` z biblioteki `django-push-notifications`.
- `chat/services.py` — wysyła powiadomienia metodą `send_push_notification_sync` przy nowych wiadomościach i wzmiankach.
- `chat/consumers.py` — `ChatConsumer._post_send_processing` / `_notify_mentions` decydują, komu wysłać push i WebSocket-owe powiadomienia.
- `home/views.py` — serwuje `/firebase-messaging-sw.js`, `/dynamic-settings.js` i `/manifest.json`.
- `zzz/scheduler.py` — wysyła powiadomienia o rozpoczynających się wydarzeniach.

## Konfiguracja (`zzz/.env`)

### FCM

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
- **`FIREBASE_VAPID_KEY`** to *Web Push certificate* (para kluczy) z Firebase Console → Cloud Messaging → Web configuration. Jest wymagany przez `messaging.getToken({ vapidKey })` w przeglądarce. Bez niego FCM w przeglądarce (także Android Chrome) zawodzi.
- W Kubernetes plik JSON jest mountowany przez secret, a `GOOGLE_APPLICATION_CREDENTIALS` wskazuje na niego.

### Konfiguracja w Kubernetes (Flux)

- Zmienne `FIREBASE_*` (w tym `FIREBASE_VAPID_KEY`) są w ConfigMap `wikikracja-common-config` (`flux-cluster/clusters/apps/wikikracja/wikikracja-common-config.yaml`), współdzielonym przez wszystkie instancje przez `envFrom`.
- Certyfikat service account jest w secrecie `wikikracja-firebase-secret` pod kluczem `service-account.json`. Secret jest montowany do `/etc/firebase/service-account.json` we wszystkich deploymentach Wikikracji za pomocą patcha w `kustomization.yaml`, a `GOOGLE_APPLICATION_CREDENTIALS` wskazuje na tę ścieżkę.
- Po zmianie ConfigMap lub Secretu należy zrestartować deploymenty instancji (Flux zsynchronizuje manifesty, ale pody muszą przeczytać nowe env).

## Wymagania

- Uprawnienie do powiadomień musi być udzielone przez użytkownika (baner na stronie głównej).
- Powiadomienia push działają tylko przez **HTTPS** (lub `localhost` w trybie deweloperskim).
- Service worker FCM musi być serwowany z **scope'u roota** (`/`), dlatego jest pod `/firebase-messaging-sw.js`, a nie z katalogu `static`.

## Rejestracja urządzenia

1. Użytkownik klika *Włącz powiadomienia*.
2. `app.js` wywołuje `Notification.requestPermission()`.
3. Po zgodzie strona się przeładowuje.
4. `push-notifications.js` rejestruje `/firebase-messaging-sw.js`, inicjalizuje Firebase i pobiera token `messaging.getToken({ serviceWorkerRegistration: swRegistration, vapidKey: FIREBASE_VAPID_KEY })`.
5. Token FCM jest wysyłany na `/chat/api/push/register/` i zapisywany w bazie jako `GCMDevice`.

## Wysyłka

- `GCMDevice.send_message(message)` używa `firebase_admin.messaging` do wysyłki przez FCM. `firebase_admin` jest inicjalizowany w `zzz/settings.py` z certyfikatu service account.
- `firebase-messaging-sw.js` odbiera wiadomości w tle i wywołuje `self.registration.showNotification()`.
- Wiadomości pierwszego planu są obsługiwane przez `messaging.onMessage` w `push-notifications.js` i przekazywane do service worker przez `postMessage`.

## Troubleshooting

| Problem | Możliwa przyczyna |
|---|---|
| Nie pojawia się prośba o zgodę | Banner może być odrzucony; sprawdź `localStorage` pod kluczem `notification-banner-dismissed` |
| Na Androidzie FCM nie działa | Brak `/firebase-messaging-sw.js` w roocie, brak `FIREBASE_API_KEY` w `.env` lub zły `serviceWorkerRegistration` |
| `messaging.getToken()` rzuca błąd / brak tokenu | Brak `FIREBASE_VAPID_KEY` (Web Push certificate) — dodaj go w Firebase Console i w konfiguracji |
| `firebase-messaging-sw.js` ma błąd składni | Widok `firebase_messaging_sw` musi zamieniać cały blok `const firebaseConfig = {...}` a nie tylko początek linii |
| Backend nie wysyła FCM | Brak certyfikatu service account lub brak `GOOGLE_APPLICATION_CREDENTIALS` |
| Po zmianie tokenu nie przychodzą powiadomienia | `/chat/api/push/register/` musi otrzymać nowy token FCM |

## Pliki objaśnione

- `chat/static/chat/js/push-notifications.js` — inicjalizacja Firebase i rejestracja tokenu FCM.
- `chat/static/chat/js/firebase-messaging-sw.js` — szablon FCM SW z wstrzykiwaną konfiguracją.
- `home/views.py` — widoki `firebase_messaging_sw`, `dynamic_settings_js`, `manifest`.
- `chat/services.py` — logika wysyłania powiadomień przez FCM.
