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

## ⚠️ DWA NIEZALEŻNE MECHANIZMY DOSTARCZANIA — NIE MYL ICH

To jest źródło większości nieporozumień przy debugowaniu. System ma **dwie oddzielne ścieżki**,
obie muszą działać niezależnie:

| Ścieżka | Kiedy działa | Gdzie w kodzie | Co pokazuje |
|---|---|---|---|
| **WebSocket (pierwszy plan)** | Karta jest otwarta i połączona przez WS (obojętnie: w tle karty przeglądarki czy aktywna) | `consumers.py::chat_notification` / `chat_mention` → JS `notifications.js` / `chat.js::onReceiveNotification` → `utility.js::makeNotification()` → `registration.showNotification()` | Natychmiastowe powiadomienie, dopóki karta żyje |
| **FCM Push (tło/zamknięta karta)** | Karta/przeglądarka zamknięta, brak połączenia WS | `consumers.py::send_push_notification_async` → `services.py::send_push_notification_sync` → `firebase_admin.messaging` → `firebase-messaging-sw.js::onBackgroundMessage` | Powiadomienie systemowe nawet bez otwartej karty |

**Log `"No push devices active for user X"` dotyczy WYŁĄCZNIE ścieżki FCM.** Jeśli WS-owa
ścieżka też nie działa, przyczyna jest zupełnie inna (błąd w `chat_notification`/`makeNotification`,
brak zgody `Notification.permission`, SW nie aktywny) — nie szukaj jej w kodzie FCM.

## ⚠️ NAJCZĘSTSZA PUŁAPKA PRZY TESTOWANIU: jeden token FCM = jedno urządzenie/przeglądarka

`chat/push_api.py::PushDeviceRegisterView` celowo robi:
```python
GCMDevice.objects.filter(registration_id=registration_id).exclude(user=user).delete()
```
Token FCM (`registration_id`) jest przypisany do **instalacji przeglądarki**, nie do loginu.
Jeśli testujesz dwa konta (np. `robert` i `robert.fialek+a`) **w tej samej przeglądarce**
(nawet w osobnych kartach, logując się na przemian), to przy drugiej rejestracji token
zostaje **odebrany pierwszemu kontu i skasowany**. Efekt: pierwsze konto przestaje mieć
aktywne `GCMDevice` i log pokaże `"No push devices active for user <pierwsze konto>"`.
**To nie jest błąd w kodzie — to zamierzone zachowanie chroniące przed tym, żeby dwóch
użytkowników na tym samym urządzeniu dostawało nawzajem swoje powiadomienia.**

Żeby przetestować push dla dwóch kont jednocześnie, użyj:
- dwóch **różnych przeglądarek** (np. Chrome + Firefox), albo
- **osobnego profilu/okna incognito** dla drugiego konta, albo
- dwóch fizycznych urządzeń.

Zanim uznasz FCM za zepsute, sprawdź w bazie stan urządzeń:
```python
from push_notifications.models import GCMDevice
GCMDevice.objects.filter(user__username="nazwa_konta").values("id", "active", "cloud_message_type", "registration_id", "date_created")
```

## Historia zmian i wnioski (żeby nie kręcić się w kółko)

Poniższe problemy zostały już zdiagnozowane i naprawione. **Nie cofaj tych zmian bez wyraźnego powodu.**

1. **`cloud_message_type` był `GCM` zamiast `FCM`** → biblioteka `django-push-notifications`
   po cichu pomijała wysyłkę. Naprawione w `push_api.py` (rejestracja zawsze ustawia
   `cloud_message_type='FCM'`) i w `services.py` (migracja starych `GCM` → `FCM` przy wysyłce).
2. **`send_push_notification_sync` nie sprawdzał wyniku wysyłki** — zawsze zwracał sukces,
   nawet gdy FCM nic nie dostarczył. Naprawione: sprawdzamy `BatchResponse.success_count`
   i logujemy błędy per-token.
3. **Brak `gcm_sender_id` w `manifest.json`** — wymagane przez Chrome/Android, gdy PWA jest
   dodana do ekranu głównego (tryb standalone), inaczej push potrafi nie dochodzić mimo
   poprawnego tokenu. Naprawione w `home/views.py::manifest` (`"gcm_sender_id": "103953800507"`
   — to stała wartość Google, nie ID projektu Firebase).
4. **Komunikat "Ta witryna została zaktualizowana w tle" zamiast właściwego powiadomienia** —
   przyczyna: wiadomość FCM miała jednocześnie `notification` (title/body) i
   `webpush.notification` z samym `icon` (bez title/body). Przeglądarka próbowała wyświetlić
   powiadomienie natywnie z niekompletnego payloadu i cicho się wywalała, więc Chrome
   pokazywał generyczny fallback. **Naprawione: FCM wysyłane jest teraz WYŁĄCZNIE jako
   `data`-only** (`chat/services.py::send_push_notification_sync`) — bez pól `notification`
   i `webpush.notification`. Dzięki temu ZAWSZE wywołuje się nasz `onBackgroundMessage`
   w `firebase-messaging-sw.js`, który sam buduje powiadomienie (title, body, icon, tag,
   click_action). **NIE dodawaj z powrotem pola `notification` do `messaging.Message` —
   to spowoduje powrót tego samego, już naprawionego błędu.**
5. **Powiadomienia działały tylko w tle, nie na pierwszym planie karty** — poleganie
   wyłącznie na `messaging.onMessage()` (foreground routing FCM) jest zawodne między
   przeglądarkami. Naprawione: dodano niezależną ścieżkę przez WebSocket (patrz tabela
   wyżej) — `utility.js::makeNotification()` teraz faktycznie wywołuje
   `registration.showNotification()` zamiast tylko zmieniać favicon. **Android nie
   wspiera `new Notification()` wywołanego z kontekstu strony (rzuca "Illegal
   constructor") — trzeba używać `ServiceWorkerRegistration.showNotification()`.**
6. **Deduplikacja** — obie ścieżki (WS i FCM) używają tego samego `tag: chat-${room_id}`,
   więc jeśli obie zadziałają dla tej samej wiadomości, przeglądarka scala je w jedno
   powiadomienie zamiast pokazywać duplikat.

## ⚠️ ZDIAGNOZOWANE 2026-07-25: FCM + Firefox = niewiarygodne, traktuj jako ograniczenie platformy

**Objaw:** świeżo zarejestrowany token FCM jest w ciągu kilku sekund oznaczany jako
`active=False` w bazie, backend loguje `FCM response 0 failed for user X: Device unregistered.`
mimo że rejestracja (`/chat/api/push/register/`) zakończyła się sukcesem.

**Sprawdzone i wykluczone jako przyczyna:**
- Niezgodność projektu Firebase między backendem a frontendem — sprawdzone: `service-account.json`
  (`project_id`) i `FIREBASE_PROJECT_ID` w ConfigMap wskazują na ten sam projekt (`wikikracja-2b4ec`).
- Niezgodność klucza VAPID — sprawdzone w Firebase Console, klucz w `wikikracja-common-config.yaml`
  (`FIREBASE_VAPID_KEY`) zgadza się z certyfikatem Web Push w konsoli.
- Zła treść wiadomości FCM (payload) — błąd to `UnregisteredError`, nie `InvalidArgumentError`,
  więc nie chodzi o format wiadomości (patrz `chat/services.py::send_push_notification_sync`,
  wysyłka data-only jest poprawna).

**Rzeczywista przyczyna:** subskrypcja push w przeglądarce testowej (`robert`) miała endpoint
`https://updates.push.services.mozilla.com/wpush/v2/...` — to **usługa push Firefoksa**, nie
Google (`fcm.googleapis.com`). Sprawdzone przez:
```js
navigator.serviceWorker.ready.then(r => r.pushManager.getSubscription()).then(s => console.log(JSON.stringify(s)))
```
Firebase Cloud Messaging w Firefoksie musi przekazywać wiadomość przez usługę push Mozilli.
To znany, długoletni problem w ekosystemie Firebase (błędna konstrukcja JWT VAPID z wymaganym
przez Mozillę `aud` przy przekazywaniu), przez co token bywa natychmiast odrzucany jako
`UNREGISTERED`, mimo że jest poprawnie wygenerowany po stronie przeglądarki. **To ograniczenie
FCM na Firefoksie, nie błąd w naszym kodzie.**

**Wniosek praktyczny:**
- Do testowania i realnego użytku polegaj na **Chrome / Edge / innych przeglądarkach opartych
  na Chromium** (endpoint `fcm.googleapis.com`) oraz na **Android Chrome**.
- Firefox może działać niestabilnie lub wcale — nie trać czasu na "naprawianie" tego po stronie
  naszego kodu, dopóki nie pojawi się dowód, że problem NIE jest po stronie relayu Firefox↔FCM.
- Mechanizm WebSocket (pierwszy plan, patrz sekcja "Dwa niezależne mechanizmy" wyżej) działa
  niezależnie od FCM/Firefox, więc dopóki karta jest otwarta, powiadomienia i tak dojdą —
  problem dotyczy tylko powiadomień w tle/po zamknięciu karty na Firefoksie.

## ⚠️ ZDIAGNOZOWANE 2026-07-25 (cd.): Android Chrome — wielokrotna rejestracja w ciągu sekund → "Device unregistered"

**To była faktyczna przyczyna zgłoszonego buga** (telefon Android + Chrome), NIE Firefox
(Firefox to był inny test, na innym urządzeniu — patrz sekcja wyżej, to osobny, też realny,
ale niezwiązany problem).

**Dowód z logów** (3 niezależne testy, identyczny wzorzec za każdym razem):
```
18:39:04 User 1 registered push device: fcm
18:39:05 User 1 registered push device: fcm
18:39:08 FCM response 0 failed for user 1: Device unregistered.

18:47:40 User 1 registered push device: fcm
18:47:41 User 1 registered push device: fcm
18:47:45 FCM response 0 failed for user 1: Device unregistered.

19:05:18 User 1 registered push device: fcm
19:05:19 User 1 registered push device: fcm
19:05:24 User 1 registered push device: fcm
19:05:30 FCM response 0 failed for user 1: Device unregistered.
```
Za każdym razem: 2-3 rejestracje w ciągu 1-6 sekund, potem token martwy przy pierwszej wysyłce.
100% powtarzalne, więc to nie "token czasem wygasa" — to deterministyczny błąd wywoływany przez
samą sekwencję zdarzeń.

**Hipoteza (najbardziej prawdopodobna):** Android agresywnie usypia/przeładowuje karty w tle,
więc `push-notifications.js::initFCM()` odpalał się wielokrotnie w krótkim odstępie czasu.
Każde wywołanie robiło `await swRegistration.update()` — wymuszone sprawdzenie/instalacja SW.
Nakładające się na siebie wywołania `update()` powodowały wyścig w cyklu życia service workera,
który rotował/unieważniał subskrypcję push tuż po jej utworzeniu — więc token, który dopiero
co się zarejestrował, był już martwy, zanim backend zdążył go użyć.

**Zastosowana poprawka** (`chat/static/chat/js/push-notifications.js`):
1. Usunięto `swRegistration.update()` — przeglądarka i tak sama sprawdza aktualizacje SW,
   wymuszanie tego przy każdym `initFCM()` nie było potrzebne i było głównym podejrzanym.
2. Dodano blokadę re-entrancy (`_initPromise`) — jeśli coś wywoła `initFCM()` wielokrotnie
   w tym samym kontekście strony, wszystkie wywołania czekają na TEN SAM token zamiast
   równolegle wywoływać `getToken()`/`registerDevice()`.

**Jak zweryfikować, że to zadziałało:** powtórz test na tym samym telefonie/koncie i sprawdź
logi — `User 1 registered push device: fcm` powinno pojawić się **raz**, nie 2-3 razy, i NIE
powinno być kolejnego `Device unregistered` dla świeżo zarejestrowanego tokenu.
```bash
kubectl logs -n wikikracja <pod> --since=10m | grep -i -e FCM -e Unregistered
```
**Jeśli nadal widać wielokrotną rejestrację** mimo tej poprawki, to znaczy, że przyczyną są
faktycznie osobne, niezależne przeładowania strony (Android tab lifecycle), a nie wyścig
wewnątrz jednej strony — blokada `_initPromise` tego nie naprawi (działa tylko w obrębie
jednego załadowania strony). W takim wypadku trzeba by dodać debounce po stronie
`/chat/api/push/register/` (np. ignorować drugą rejestrację tego samego tokenu w oknie
kilku sekund) albo zbadać dalej przez zdalne debugowanie USB (`chrome://inspect#devices`).

## Checklist debugowania (rób po kolei, nie zgaduj)

Gdy powiadomienia "nie przychodzą", zanim zmienisz kod:

0. **Sprawdź, jakiej przeglądarki używa odbiorca.** Jeśli to Firefox, sprawdź endpoint
   subskrypcji (komenda niżej) — jeśli to `updates.push.services.mozilla.com`, patrz sekcja
   "FCM + Firefox" wyżej, zanim zaczniesz cokolwiek zmieniać w kodzie:
   ```js
   navigator.serviceWorker.ready.then(r => r.pushManager.getSubscription()).then(s => console.log(JSON.stringify(s)))
   ```
1. **Ustal, której ścieżki dotyczy problem** — WS (pierwszy plan / otwarta karta) czy
   FCM (karta zamknięta)? To zupełnie inny kod.
2. **Sprawdź konsolę przeglądarki PO STRONIE ODBIORCY** (nie nadawcy!) — szukaj:
   - `Push notifications enabled: true/false`
   - `Device registered successfully: {...}` z `device_id`
   - błędów z `initFCM`, `makeNotification`, `firebase-messaging-sw.js`
3. **Sprawdź czy odbiorca ma aktywne `GCMDevice`** w bazie (patrz zapytanie wyżej).
   Jeśli nie — sprawdź, czy nie testujesz dwóch kont w jednej przeglądarce (patrz pułapka wyżej).
4. **Sprawdź logi serwera** dla obu ścieżek:
   - `chat.consumers` → `Push notification sent to user X` / `No push devices active for user X`
   - `chat.services` (jeśli podniesiesz log level) → `FCM sent X notification(s)` / `FCM failed...` / `FCM response N failed...`
5. **Dopiero teraz**, jeśli powyższe nie wyjaśnia problemu, patrz w kod — i zacznij od
   sekcji "Historia zmian" wyżej, żeby nie naprawiać czegoś, co już zostało naprawione
   (albo przypadkiem cofnąć naprawę).
