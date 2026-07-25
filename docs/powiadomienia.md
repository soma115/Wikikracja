# Powiadomienia w Wikikracji

Wikikracja wysyła powiadomienia o nowych wiadomościach czatu i wydarzeniach wyłącznie przez **Web Push** (standard `PushManager`/VAPID). Firebase Cloud Messaging (FCM) zostało całkowicie usunięte — zarówno z frontendu/backendu, jak i z konfiguracji Kubernetes.

## Architektura

### Frontend

- `chat/static/chat/js/push-notifications.js` — rejestruje urządzenie po stronie użytkownika (Web Push, `PushManager.subscribe()`).
- `chat/static/chat/js/sw.js` — service worker Web Push, odbiera push i pokazuje powiadomienia.
- `home/static/home/js/app.js` — pokazuje baner z prośbą o uprawnienia do powiadomień i wywołuje `Notification.requestPermission()`.

### Backend

- `chat/push_api.py` — endpointy `POST /chat/api/push/register/` i `/chat/api/push/unregister/` zapisują tokeny w modelu `WebPushDevice` z biblioteki `django-push-notifications`.
- `chat/services.py` — wysyła powiadomienia metodą `send_push_notification_sync` przy nowych wiadomościach i wzmiankach.
- `chat/consumers.py` — `ChatConsumer._post_send_processing` / `_notify_mentions` decydują, komu wysłać push i WebSocket-owe "chat.notification"/"chat.mention".
- `home/views.py` — serwuje `/sw.js`, `/dynamic-settings.js` i `/manifest.json`.
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

### Konfiguracja w Kubernetes (Flux)

- Zmienne `VAPID_*` są w ConfigMap `wikikracja-common-config` (`flux-cluster/clusters/apps/wikikracja/wikikracja-common-config.yaml`), współdzielonym przez wszystkie instancje przez `envFrom`.
- Po zmianie ConfigMap należy zrestartować deploymenty instancji (Flux zsynchronizuje manifesty, ale pody muszą przeczytać nowe env).

## Instalacja jako PWA (iOS/Android)

- `home/views.py::manifest` serwuje dynamiczny `manifest.json` (nazwa, ikony, `display: standalone`) pod `/manifest.json`.
- `home/templates/home/base.html` zawiera komplet meta-tagów PWA:
  - `<link rel="manifest">` — manifest dla Chrome/Android (obsługuje "Add to Home Screen" / instalację).
  - `<meta name="mobile-web-app-capable">` — tryb standalone na Androidzie/Chrome.
  - `<meta name="apple-mobile-web-app-capable">`, `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title` oraz `<link rel="apple-touch-icon">` — Safari na iOS **ignoruje** `manifest.json` przy "Dodaj do ekranu początkowego", więc te meta-tagi są wymagane osobno, aby ikona, nazwa i tryb pełnoekranowy działały poprawnie po instalacji na iOS.
- Service worker (`/sw.js`) nie jest wymagany do samej instalacji na iOS, ale jest potrzebny do odbierania Web Pushy po instalacji.

## Logika wysyłki (kiedy i co)

- Powiadomienie push wysyłane jest **zawsze** przy nowej wiadomości od innego użytkownika w pokoju — niezależnie od tego, czy odbiorca ma akurat otwartą przeglądarkę/kartę czatu, czy jest w danym pokoju. Jedyny wyjątek to **wyciszony pokój** (`Room.get_membership_preferences_bulk` → `muted`) lub sytuacja, gdy wiadomość jest bezpośrednią wzmianką (`@username`) — wtedy obsługuje ją osobna ścieżka `_notify_mentions`, która **pomija wyciszenie**.
- Wcześniej istniała logika "nie wysyłaj, jeśli user jest obecny w pokoju" (`is_present`) — została świadomie usunięta z warunku wysyłki na życzenie użytkownika (powiadomienia mają wyskakiwać zawsze). Zmienna `is_present` nadal jest liczona w `_post_send_processing`, ale wyłącznie do logiki "unseen/badge" (odznaczanie pokoju jako przeczytanego), **nie** do bramkowania push. **Uwaga:** jeśli kiedyś usuniesz tę zmienną całkowicie, kod niżej (`if is_present: continue`) rzuci `NameError` i wyjątek przerwie **całą** pętlę `_post_send_processing` — czyli część odbiorców w ogóle nie dostanie powiadomienia. Taki bug już raz wystąpił i objawiał się jako "brak wszelkich powiadomień" w logach (`Error in post-send processing for message N: name 'is_present' is not defined`).
- Do tytułu powiadomienia doklejana jest nazwa pokoju (`room.title` dla pokoi publicznych, nazwa nadawcy dla czatów prywatnych) — ale tylko jeśli różni się od tytułu bazowego, żeby uniknąć np. `Robert — Robert` w czacie 1-na-1.
- **Własny dźwięk powiadomień został usunięty** (`makeNotification` w `utility.js` już nie odtwarza `notification.mp3` ani nie woła `new Notification()` — tylko podmienia favicon jako wskaźnik nieprzeczytanych). Systemowy dźwięk/wibrację zapewnia teraz wyłącznie natywna notyfikacja przeglądarki wyświetlana przez `showNotification()`.

## Wymagania

- Uprawnienie do powiadomień musi być udzielone przez użytkownika (baner na stronie głównej).
- Powiadomienia push działają tylko przez **HTTPS** (lub `localhost` w trybie deweloperskim).
- Service worker musi być serwowany z **scope'u roota** (`/`), dlatego jest pod `/sw.js`, a nie z katalogu `static`.

## Rejestracja urządzenia

1. Użytkownik klika *Włącz powiadomienia*.
2. `app.js` wywołuje `Notification.requestPermission()`.
3. Po zgodzie strona się przeładowuje.
4. `push-notifications.js` rejestruje `/sw.js` i wywołuje `pushManager.subscribe()` z `applicationServerKey` (VAPID public key).
5. Subskrypcja jest wysyłana na `/chat/api/push/register/` i zapisywana w bazie jako `WebPushDevice`.

### Deduplikacja tokenów (`chat/push_api.py`)

`registration_id` (endpoint Web Push) identyfikuje **fizyczną przeglądarkę/urządzenie**, a nie konto — więc jeśli na tym samym urządzeniu logowały się różne konta (np. konta testowe), ten sam endpoint mógł zostać zapisany pod różnymi userami. Efekt: wysyłka push do "innego" użytkownika i tak trafiała na to samo fizyczne urządzenie (wyglądało to jak "dostaję powiadomienie, gdy sam wysyłam wiadomość"). Dlatego przy rejestracji usuwamy wszystkie wpisy `WebPushDevice` z tym samym `registration_id` należące do **innych** userów (przenosimy "własność" endpointu na aktualnie zalogowanego).

## Wysyłka

- `WebPushDevice.send_message(json)` wysyła ładunek JSON do przeglądarki. `sw.js` odbiera go w `push` i wywołuje `showNotification()`.

## Troubleshooting

| Problem | Możliwa przyczyna |
|---|---|
| Na desktopie nie pojawia się prośba o zgodę | Banner może być odrzucony; sprawdź `localStorage` pod kluczem `notification-banner-dismissed` |
| `pushManager.subscribe()` zawodzi | `VAPID_PUBLIC_KEY` ma zły format lub zawiera nowe linie/cudzysłowy |
| Po zmianie subskrypcji nie przychodzą powiadomienia | `sw.js` musi wysłać `endpoint`, `p256dh` i `auth` do `/chat/api/push/register/` |
| W logach `NameError: name 'is_present' is not defined` w `_post_send_processing` | Wyjątek przerywa całą pętlę po wiadomości — sprawdź, czy zmienna `is_present` jest nadal liczona w pętli w `chat/consumers.py` (patrz sekcja "Logika wysyłki") |
| Powiadomienie przychodzi na urządzenie nadawcy / "sam sobie" | Ten sam `registration_id` (endpoint) był wcześniej zarejestrowany pod innym kontem na tym samym urządzeniu — sprawdź logikę czyszczenia w `chat/push_api.py` (sekcja "Deduplikacja tokenów") |
| Brak przycisku "Dodaj do ekranu początkowego" na iOS | Sprawdź obecność `apple-mobile-web-app-capable`, `apple-touch-icon` w `home/templates/home/base.html` oraz że strona jest serwowana przez HTTPS |

## Pliki objaśnione

- `chat/static/chat/js/push-notifications.js` — rejestracja Web Push.
- `chat/static/chat/js/sw.js` — Web Push service worker.
- `home/views.py` — widoki `service_worker`, `vapid_config`, `manifest`.
- `chat/services.py` — logika wysyłania powiadomień.
