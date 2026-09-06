# Powiadomienia w Wikikracji

Wikikracja wysyła powiadomienia o nowych wiadomościach czatu, wydarzeniach, głosowaniach, obywatelach, dokumentach, zadaniach i ankietach wyłącznie przez **Firebase Cloud Messaging (FCM)**. Web Push (VAPID) został usunięty.

> Własna implementacja Web Push oparta na `PushManager` i `WebPushDevice` została zastąpiona FCM, bo FCM daje bardziej niezawodne powiadomienia na urządzeniach mobilnych (Android/PWA), lepiej obsługuje zabite aplikacje i ma gotową infrastrukturę do zarządzania tokenami. Sam VAPID nie zniknął całkowicie — FCM w przeglądarce wciąż wymaga `FIREBASE_VAPID_KEY` (Web Push certificate z Firebase Console).

## Architektura

### Frontend

- `chat/static/chat/js/push-notifications.js` — inicjalizuje Firebase, rejestruje `/firebase-messaging-sw.js`, pobiera token FCM i wysyła go na backend.
- `chat/static/chat/js/firebase-messaging-sw.js` — service worker FCM. Jego konfiguracja jest wstrzykiwana dynamicznie przez widok `firebase_messaging_sw` w `home/views.py`.
- `chat/static/chat/js/utility.js` — `makeNotification()` (WS → `showNotification()`), `sendNotificationAck()` oraz helpery czatu.
- `chat/static/chat/js/notifications.js` — odbiór powiadomień WebSocket i rejestracja handlera.
- `home/static/home/js/app.js` — pokazuje baner z prośbą o uprawnienia do powiadomień i wywołuje `Notification.requestPermission()`.

### Backend

- `chat/push_api.py` — endpointy `POST /chat/api/push/register/`, `/chat/api/push/unregister/` oraz `POST /chat/api/push/ack/`.
- `chat/services.py` — `send_message` tworzy wiadomość; `_dispatch_message_notifications` decyduje, komu wysłać push i WebSocket-owe powiadomienia; `_send_push_to_user` i `_send_mention` wysyłają FCM; `_build_chat_notification` buduje payload.
- `chat/consumers.py` — `chat_notification` / `chat_mention` odbierają zdarzenia kanałów i przekazują powiadomienie do klienta WebSocket.
- `zzz/notifications.py` — współdzielone funkcje budowania i wysyłki (`build_notification`, `send_fcm_to_*`, `send_websocket_to_*`); tu też żyje `NOTIF_LOG_TAG` oraz mapowanie kategorii na pola preferencji push (`_PUSH_FIELDS`).
- `home/views.py` — serwuje `/firebase-messaging-sw.js`, `/dynamic-settings.js` i `/manifest.json`.
- `zzz/scheduler.py` — wysyła powiadomienia o rozpoczynających się wydarzeniach.

## Konfiguracja (`zzz/.env`)

### FCM

```bash
FIREBASE_CERT_PATH=firebase-service-account.json
FIREBASE_CERT_JSON=          # opcjonalnie: surowy JSON klucza service account
FIREBASE_CERT_BASE64=        # opcjonalnie: base64 surowego JSON klucza service account
GOOGLE_APPLICATION_CREDENTIALS=/etc/firebase/service-account.json
FIREBASE_API_KEY=AIza...
FIREBASE_AUTH_DOMAIN=projekt.firebaseapp.com
FIREBASE_PROJECT_ID=projekt
FIREBASE_STORAGE_BUCKET=projekt.appspot.com
FIREBASE_MESSAGING_SENDER_ID=123456789
FIREBASE_APP_ID=1:123456789:web:...
FIREBASE_VAPID_KEY=BN...   # Web Push certificate z Firebase Console > Cloud Messaging
```

- `FIREBASE_CERT_PATH` / `GOOGLE_APPLICATION_CREDENTIALS` / `FIREBASE_CERT_JSON` / `FIREBASE_CERT_BASE64` to klucz service account dla serwera (wysyłanie z backendu). `zzz/settings.py::_load_firebase_credentials` próbuje kolejno: base64, JSON, ścieżkę.
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
5. Token FCM jest wysyłany na `POST /chat/api/push/register/` wraz z rozpoznanym typem urządzenia (`mobile`/`tablet`/`desktop` w polu `device_type`) i trybem wyświetlania (`browser`/`standalone`/`minimal-ui`/`fullscreen` w polu `display_mode`). Backend zapisuje token w modelu `GCMDevice` (`push_notifications`); `device_type` trafia do pola `name`, a `display_mode` do `application_id`. `cloud_message_type` jest zawsze ustawiane na `FCM`.
6. Użytkownik może mieć wiele aktywnych urządzeń jednocześnie (np. telefon i komputer). Tylko powtarzający się `registration_id` dla tego samego użytkownika jest deduplikowany; tokeny innych użytkowników na tym samym urządzeniu są usuwane przy rejestracji.
7. Martwe tokeny (błąd FCM `UnregisteredError`/`SenderIdMismatch`/`InvalidArgument`) są automatycznie dezaktywowane przez `django-push-notifications` przy kolejnej wysyłce.
8. **Re-entrancy i debounce.** Po stronie frontendu `push-notifications.js` blokuje równoległe wywołania `initFCM()` przez `_initPromise`. Po stronie backendu `chat/push_api.py::PushDeviceRegisterView` dodaje 30-sekundowy debounce w cache (`push_reg_debounce:<registration_id>`) dla tego samego tokena i tego samego użytkownika, żeby Android nie rotował subskrypcji przy szybkich rejestracjach.

Po każdej zmianie `firebase-messaging-sw.js` na produkcji użytkownik musi raz zamknąć PWA/przeglądarkę i wyczyścić jej pamięć podręczną (lub odinstalować/zainstalować PWA), żeby nowa wersja service workera zastąpiła starą. `skipWaiting()`/`clients.claim()` przyspieszają aktualizację, ale tylko gdy aplikacja jest otwarta; zabita aplikacja trzyma poprzedni SW aż do kolejnego uruchomienia z nowym źródłem.

## Wysyłka

- `GCMDevice.send_message(message)` używa `firebase_admin.messaging` do wysyłki przez FCM. `firebase_admin` jest inicjalizowany w `zzz/settings.py` z certyfikatu service account.
- `chat/services.py::send_push_notification_sync` buduje powiadomienie przez `zzz.notifications.build_notification` i woła `send_fcm_to_user_sync`.
- `zzz/notifications.py::_build_fcm_message` buduje `messaging.Message` z trzema warstwami:
  - `notification` (title/body) – wymagane, żeby FCM SDK w service workerze automatycznie wyświetliło powiadomienie.
  - `data` (title, body, room_id, room_name, icon, click_action, notification_id, event_id, vote_id, citizen_id, task_id, post_id, survey_id) – dla pierwszego planu (`onMessage`) i dla `onBackgroundMessage` gdy SW jest aktywny.
  - `webpush.notification` (title, body, icon, badge, tag, require_interaction, data) oraz `webpush.fcm_options.link` – dla natywnego wyświetlenia gdy przeglądarka/PWA jest zabita i FCM SDK nie może obudzić SW.
- `firebase-messaging-sw.js` odbiera wiadomości przez `onBackgroundMessage` (gdy FCM SDK jest załadowane) lub bezpośrednio przez `push` (fallback, gdy SDK nie startuje w zabitej przeglądarce). W obu przypadkach wywołuje `self.registration.showNotification()`.
- Wiadomości pierwszego planu są obsługiwane przez `messaging.onMessage` w `push-notifications.js` i przekazywane do service worker przez `postMessage`.

## Kategorie powiadomień i preferencje

Model `Uzytkownik` zawiera pola preferencji push dla każdej kategorii:

| Kategoria | Pole preferencji | Typ zdarzeń |
|---|---|---|
| `obywatele` | `push_notifications_obywatele` | nowi kandydaci, akceptacja, blokada |
| `glosowania` | `push_notifications_glosowania` | nowe referenda, zmiany stanu, ostatni dzień |
| `chat` | `push_notifications_chat` | nowe wiadomości i wzmianki w czacie |
| `events` | `push_notifications_events` | zbliżające się wydarzenia |
| `post` | `push_notifications_post` | ważne dokumenty (nowe/zmienione) |
| `task` | `push_notifications_task` | nowe zadania |
| `survey` | `push_notifications_survey` | nowe ankiety |

Mapowanie to jest zdefiniowane w `zzz/notifications.py::_PUSH_FIELDS`. Funkcja `_push_enabled_for_user` sprawdza preferencję przed wysyłką FCM do konkretnego użytkownika; `send_websocket_to_all_sync` używa tych samych preferencji do filtrowania WebSocket-owych odbiorców.

## Troubleshooting

| Problem | Możliwa przyczyna |
|---|---|
| Nie pojawia się prośba o zgodę | Banner może być odrzucony; sprawdź `localStorage` pod kluczem `notification-banner-dismissed` |
| Na Androidzie FCM nie działa | Brak `/firebase-messaging-sw.js` w roocie, brak `FIREBASE_API_KEY` w `.env` lub zły `serviceWorkerRegistration` |
| `messaging.getToken()` rzuca błąd / brak tokenu | Brak `FIREBASE_VAPID_KEY` (Web Push certificate) — dodaj go w Firebase Console i w konfiguracji |
| `firebase-messaging-sw.js` ma błąd składni | Widok `firebase_messaging_sw` musi zamieniać cały blok `const firebaseConfig = {...}` a nie tylko początek linii |
| Generyczny komunikat "Ta witryna została zaktualizowana w tle" po zamknięciu PWA | Stary service worker na urządzeniu — wyczyść pamięć podręczną lub odinstaluj/zainstaluj PWA ponownie |
| Backend nie wysyła FCM | Brak certyfikatu service account lub brak `GOOGLE_APPLICATION_CREDENTIALS` |
| Po zmianie tokenu nie przychodzą powiadomienia | `/chat/api/push/register/` musi otrzymać nowy token FCM |
| Nie wiadomo, czy powiadomienie faktycznie dotarło | Filtruj logi/konsolę po `NOTIFDBG` i śledź `notification_id` (patrz sekcja niżej) — ack ze statusem `shown`/`clicked` to twarde potwierdzenie |

## Pliki objaśnione

- `chat/static/chat/js/push-notifications.js` — inicjalizacja Firebase, rejestracja tokenu FCM, obsługa `onMessage` (pierwszy plan) oraz `_initPromise`.
- `chat/static/chat/js/firebase-messaging-sw.js` — szablon FCM SW z wstrzykiwaną konfiguracją. Obsługuje `onBackgroundMessage`, fallbackowy `push`, `postMessage` z karty i `notificationclick`; każda ścieżka wysyła ack.
- `chat/static/chat/js/utility.js` — `makeNotification()` (WS → `showNotification()`) i `sendNotificationAck()`.
- `chat/static/chat/js/notifications.js` — odbiór powiadomień WS i rejestracja handlera.
- `chat/push_api.py` — rejestracja/wyrejestrowanie urządzenia FCM, debounce rejestracji oraz `PushNotificationAckView`.
- `zzz/notifications.py` — budowanie (`notification_id`) i wysyłka FCM/WS, `NOTIF_LOG_TAG`, mapowanie kategorii preferencji.
- `home/views.py` — widoki `firebase_messaging_sw`, `dynamic_settings_js`, `manifest`.
- `chat/services.py` — logika wysyłania powiadomień czatu (WebSocket + FCM) przez `_dispatch_message_notifications`.

## Dwa niezależne mechanizmy dostarczania — nie myl ich

To jest źródło większości nieporozumień przy debugowaniu. System ma **dwie oddzielne ścieżki**, obie muszą działać niezależnie:

| Ścieżka | Kiedy działa | Gdzie w kodzie | Co pokazuje |
|---|---|---|---|
| **WebSocket (pierwszy plan)** | Karta jest otwarta i połączona przez WS (obojętnie: w tle karty przeglądarki czy aktywna) | `consumers.py::chat_notification` / `chat_mention` → JS `notifications.js` / `chat.js::onReceiveNotification` → `utility.js::makeNotification()` → `registration.showNotification()` | Natychmiastowe powiadomienie, dopóki karta żyje |
| **FCM Push (tło/zamknięta karta)** | Karta/przeglądarka zamknięta, brak połączenia WS | `services.py::_dispatch_message_notifications` → `_send_push_to_user` / `_send_mention` → `ChatRepository.send_push_notification_sync` → `firebase_admin.messaging` → `firebase-messaging-sw.js::onBackgroundMessage` | Powiadomienie systemowe nawet bez otwartej karty |

**Log `"No FCM devices for user X"` dotyczy WYŁĄCZNIE ścieżki FCM.** Jeśli WS-owa ścieżka też nie działa, przyczyna jest zupełnie inna (błąd w `chat_notification`/`makeNotification`, brak zgody `Notification.permission`, SW nie aktywny) — nie szukaj jej w kodzie FCM.

## Śledzenie po `notification_id` i potwierdzenie odbioru (ack)

Serwer sam z siebie widzi tylko wysyłkę — nie wie, czy powiadomienie faktycznie pojawiło się na ekranie użytkownika. Dlatego każde powiadomienie (czat, wzmianka, event, głosowanie, poczekalnia, dokument, zadanie, ankieta) dostaje unikalne **`notification_id`** (`zzz/notifications.py::build_notification` i `chat/services.py::_build_chat_notification`), które towarzyszy mu przez cały pipeline — WS i FCM — i wraca od klienta jako potwierdzenie.

**Ack.** Klient zgłasza rzeczywisty wynik do `POST /chat/api/push/ack/` (`chat/push_api.py::PushNotificationAckView`, bez CSRF bo woła go też service worker) z każdego miejsca, w którym próbuje pokazać powiadomienie: `utility.js::makeNotification` (WS, pierwszy plan), `push-notifications.js` (`onMessage`, FCM pierwszy plan) i `firebase-messaging-sw.js` (`onBackgroundMessage`, fallback `push`, `postMessage` z karty, `notificationclick`). Payload: `notification_id`, `status` (`shown` / `skipped` / `error` / `clicked`), `source` (skąd w pipeline), opcjonalnie `reason`. Serwer loguje `Notification ACK: user=... notification_id=... status=... source=...`.

**Tag logów `[NOTIFDBG]`.** Wszystkie logi związane z powiadomieniami — po stronie serwera (stała `NOTIF_LOG_TAG` w `zzz/notifications.py`, importowana w `consumers.py`/`push_api.py`/`services.py`) i w konsoli przeglądarki (wszystkie pliki JS z listy wyżej) — mają ten sam prefiks `[NOTIFDBG]`. Jedno wyszukanie w logach k8s i filtr `NOTIFDBG` w devtools pokazują komplet zdarzeń dla powiadomień, bez szumu z reszty aplikacji.

**Jak z tego korzystać:** znajdź `notification_id` w logu wysyłki (serwer) albo w logu ack (klient), potem `grep notification_id=<ID>` po obu stronach — zobaczysz całą podróż: zbudowane → wysłane (WS `group_send` / FCM) → pominięte / pokazane / błąd / kliknięte na kliencie. To zastępuje zgadywanie "czy w ogóle doszło" pewnym potwierdzeniem z przeglądarki odbiorcy.

## ⚠️ NAJCZĘSTSZA PUŁAPKA PRZY TESTOWANIU: jeden token FCM = jedno urządzenie/przeglądarka

`chat/push_api.py::PushDeviceRegisterView` celowo robi:
```python
GCMDevice.objects.filter(registration_id=registration_id).exclude(user=user).delete()
```
Token FCM (`registration_id`) jest przypisany do **instalacji przeglądarki**, nie do loginu. Jeśli testujesz dwa konta (np. `robert` i `robert.fialek+a`) **w tej samej przeglądarce** (nawet w osobnych kartach, logując się na przemian), to przy drugiej rejestracji token zostaje **odebrany pierwszemu kontu i skasowany**. Efekt: pierwsze konto przestaje mieć aktywne `GCMDevice` i log pokaże `"No FCM devices for user <pierwsze konto>"`.

**To nie jest błąd w kodzie — to zamierzone zachowanie chroniące przed tym, żeby dwóch użytkowników na tym samym urządzeniu dostawało nawzajem swoje powiadomienia.** Jednocześnie jeden użytkownik może mieć aktywnych wiele urządzeń (np. telefon i komputer); wysyłka FCM trafia wtedy do wszystkich aktywnych tokenów.

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

1. **`cloud_message_type` był `GCM` zamiast `FCM`** → biblioteka `django-push-notifications` po cichu pomijała wysyłkę. Naprawione w `push_api.py` (rejestracja zawsze ustawia `cloud_message_type='FCM'`) i w `services.py`/`zzz/notifications.py` (`_migrate_legacy_gcm_devices` migruje stare `GCM` → `FCM` przy wysyłce).
2. **`send_push_notification_sync` nie sprawdzał wyniku wysyłki** — zawsze zwracał sukces, nawet gdy FCM nic nie dostarczył. Naprawione: sprawdzamy `BatchResponse.success_count` i logujemy błędy per-token.
3. **Brak `gcm_sender_id` w `manifest.json`** — wymagane przez Chrome/Android, gdy PWA jest dodana do ekranu głównego (tryb standalone), inaczej push potrafi nie dochodzić mimo poprawnego tokenu. Naprawione w `home/views.py::manifest` (`"gcm_sender_id": "103953800507"` — to stała wartość Google, nie ID projektu Firebase).
4. **Komunikat "Ta witryna została zaktualizowana w tle" zamiast właściwego powiadomienia** — przyczyna: różne przeglądarki/PWA w różnych stanach (karta w tle, zabita przeglądarka, PWA zamknięte) potrzebują różnych pól FCM. Data-only działało, gdy SW był aktywny, ale przy zabitej przeglądarce Chrome/PWA nie zawsze obudził SW i pokazywał generyczny fallback. **Naprawione: FCM wysyła teraz pełny zestaw payloadów:**
   - top-level `notification` (title/body) – żeby FCM SDK wyświetliło powiadomienie, gdy tylko jest w stanie je przetworzyć;
   - `data` – dla `onMessage` na pierwszym planie i dla `onBackgroundMessage` w aktywnym SW;
   - `webpush.notification` (z title, body, icon, badge, tag, `requireInteraction`, `data`) oraz `webpush.fcm_options.link` – żeby Chrome/PWA potrafiły wyświetlić powiadomienie natywnie nawet bez obudzenia naszego kodu.
   Dodatkowo `firebase-messaging-sw.js` ma fallbackowy `push`, który sam parsuje payload i woła `showNotification()`, jeśli FCM SDK nie zdoła się załadować w zabitej aplikacji.
   Nie usuwaj żadnej z tych trzech warstw bez przetestowania na prawdziwym telefonie.
5. **Powiadomienia działały tylko w tle, nie na pierwszym planie karty** — poleganie wyłącznie na `messaging.onMessage()` (foreground routing FCM) jest zawodne między przeglądarkami. Naprawione: dodano niezależną ścieżkę przez WebSocket (patrz tabela wyżej) — `utility.js::makeNotification()` teraz faktycznie wywołuje `registration.showNotification()` zamiast tylko zmieniać favicon. **Android nie wspiera `new Notification()` wywołanego z kontekstu strony (rzuca "Illegal constructor") — trzeba używać `ServiceWorkerRegistration.showNotification()`.**
6. **Deduplikacja** — obie ścieżki (WS i FCM) używają tego samego `tag` (np. `chat-${room_id}`), więc jeśli obie zadziałają dla tej samej wiadomości, przeglądarka scala je w jedno powiadomienie zamiast pokazywać duplikat.
7. **Powiadomienia działają po zamknięciu przeglądarki/PWA** — po wdrożeniu punktu 4 oraz fallbackowego `push` w `firebase-messaging-sw.js` powiadomienia na Android Chrome pokazują poprawny tytuł i treść także wtedy, gdy przeglądarka lub PWA jest zabita. Kluczowe było wyczyszczenie pamięci podręcznej/ponowna instalacja PWA na urządzeniu, żeby nowa wersja SW została załadowana.
8. **Wielokrotna rejestracja FCM na Androidzie unieważniała token** — Android agresywnie usypia/przeładowuje karty w tle, co powodowało kilka wywołań `initFCM()` w ciągu sekund. Naprawione na dwóch poziomach:
   - frontend: `push-notifications.js` używa `_initPromise`, żeby równoległe wywołania w tym samym załadowaniu strony czekały na ten sam token;
   - backend: `chat/push_api.py::PushDeviceRegisterView` deduplikuje i debouncuje rejestrację tego samego tokena dla tego samego użytkownika przez 30 sekund w cache (`push_reg_debounce:<registration_id>`).

## ⚠️ ZDIAGNOZOWANE 2026-07-25: FCM + Firefox = niewiarygodne, traktuj jako ograniczenie platformy

**Objaw:** świeżo zarejestrowany token FCM jest w ciągu kilku sekund oznaczany jako `active=False` w bazie, backend loguje `FCM response 0 failed for user X: Device unregistered.` mimo że rejestracja (`/chat/api/push/register/`) zakończyła się sukcesem.

**Sprawdzone i wykluczone jako przyczyna:**
- Niezgodność projektu Firebase między backendem a frontendem — sprawdzone: `service-account.json` (`project_id`) i `FIREBASE_PROJECT_ID` w ConfigMap wskazują na ten sam projekt.
- Niezgodność klucza VAPID — sprawdzone w Firebase Console, klucz w `wikikracja-common-config.yaml` (`FIREBASE_VAPID_KEY`) zgadza się z certyfikatem Web Push w konsoli.
- Zła treść wiadomości FCM (payload) — błąd to `UnregisteredError`, nie `InvalidArgumentError`, więc nie chodzi o format wiadomości (patrz `chat/services.py::send_push_notification_sync` / `zzz/notifications.py::_build_fcm_message`).

**Rzeczywista przyczyna:** subskrypcja push w przeglądarce testowej (`robert`) miała endpoint `https://updates.push.services.mozilla.com/wpush/v2/...` — to **usługa push Firefoksa**, nie Google (`fcm.googleapis.com`). Sprawdzone przez:
```js
navigator.serviceWorker.ready.then(r => r.pushManager.getSubscription()).then(s => console.log(JSON.stringify(s)))
```
Firebase Cloud Messaging w Firefoksie musi przekazywać wiadomość przez usługę push Mozilli. To znany, długoletni problem w ekosystemie Firebase (błędna konstrukcja JWT VAPID z wymaganym przez Mozillę `aud` przy przekazywaniu), przez co token bywa natychmiast odrzucany jako `UNREGISTERED`, mimo że jest poprawnie wygenerowany po stronie przeglądarki. **To ograniczenie FCM na Firefoksie, nie błąd w naszym kodzie.**

**Wniosek praktyczny:**
- Do testowania i realnego użytku polegaj na **Chrome / Edge / innych przeglądarkach opartych na Chromium** (endpoint `fcm.googleapis.com`) oraz na **Android Chrome**.
- Firefox może działać niestabilnie lub wcale — nie trać czasu na "naprawianie" tego po stronie naszego kodu, dopóki nie pojawi się dowód, że problem NIE jest po stronie relayu Firefox↔FCM.
- Mechanizm WebSocket (pierwszy plan, patrz sekcja "Dwa niezależne mechanizmy" wyżej) działa niezależnie od FCM/Firefox, więc dopóki karta jest otwarta, powiadomienia i tak dojdą — problem dotyczy tylko powiadomień w tle/po zamknięciu karty na Firefoksie.

## ⚠️ ZDIAGNOZOWANE 2026-07-25 (cd.): Android Chrome — wielokrotna rejestracja w ciągu sekund → "Device unregistered"

**To była faktyczna przyczyna zgłoszonego buga** (telefon Android + Chrome), NIE Firefox (Firefox to był inny test, na innym urządzeniu — patrz sekcja wyżej, to osobny, też realny, ale niezwiązany problem).

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
Za każdym razem: 2-3 rejestracje w ciągu 1-6 sekund, potem token martwy przy pierwszej wysyłce. 100% powtarzalne, więc to nie "token czasem wygasa" — to deterministyczny błąd wywoływany przez samą sekwencję zdarzeń.

**Hipoteza (najbardziej prawdopodobna):** Android agresywnie usypia/przeładowuje karty w tle, więc `push-notifications.js::initFCM()` odpalał się wielokrotnie w krótkim odstępie czasu. Nakładające się wywołania `getToken()`/`registerDevice()` powodowały wyścig w cyklu życia service workera, który rotował/unieważniał subskrypcję push tuż po jej utworzeniu — więc token, który dopiero co się zarejestrował, był już martwy, zanim backend zdążył go użyć.

**Zastosowana poprawka:**
1. `push-notifications.js` — usunięto `swRegistration.update()` i dodano blokadę re-entrancy (`_initPromise`), żeby równoległe wywołania w obrębie jednego załadowania strony czekały na ten sam token.
2. `chat/push_api.py::PushDeviceRegisterView` — dodano 30-sekundowy debounce w cache (`push_reg_debounce:<registration_id>`) dla tego samego tokena i tego samego użytkownika, oraz deduplikację duplikatów `registration_id` dla tego użytkownika. Dzięki temu nawet jeśli przeglądarka wyśle kilka żądań rejestracji pod rząd, backend zachowa tylko jedno.

**Jak zweryfikować, że to zadziałało:** powtórz test na tym samym telefonie/koncie i sprawdź logi — `User 1 registered push device: fcm` powinno pojawić się **raz** na każde załadowanie strony, i NIE powinno być kolejnego `Device unregistered` dla świeżo zarejestrowanego tokenu.
```bash
kubectl logs -n wikikracja <pod> --since=10m | grep -i -e FCM -e Unregistered
```
**Jeśli nadal widać wielokrotną rejestrację** mimo tej poprawki, to znaczy, że przyczyną są faktycznie osobne, niezależne przeładowania strony (Android tab lifecycle), a nie wyścig wewnątrz jednej strony — blokada `_initPromise` tego nie naprawi (działa tylko w obrębie jednego załadowania strony). W takim wypadku backendowy debounce powinien wciąż zapobiec utworzeniu wielu rekordów, ale należy zbadać dalej przez zdalne debugowanie USB (`chrome://inspect#devices`).

## Checklist debugowania (rób po kolei, nie zgaduj)

Gdy powiadomienia "nie przychodzą", zanim zmienisz kod:

0. **Sprawdź, jakiej przeglądarki używa odbiorca.** Jeśli to Firefox, sprawdź endpoint subskrypcji (komenda niżej) — jeśli to `updates.push.services.mozilla.com`, patrz sekcja "FCM + Firefox" wyżej, zanim zaczniesz cokolwiek zmieniać w kodzie:
   ```js
   navigator.serviceWorker.ready.then(r => r.pushManager.getSubscription()).then(s => console.log(JSON.stringify(s)))
   ```
1. **Ustal, której ścieżki dotyczy problem** — WS (pierwszy plan / otwarta karta) czy FCM (karta zamknięta)? To zupełnie inny kod.
2. **Sprawdź konsolę przeglądarki PO STRONIE ODBIORCY** (nie nadawcy!) — odfiltruj po `NOTIFDBG`, zobaczysz cały pipeline: rejestrację FCM, odbiór WS/FCM, `showNotification()`, pominięcia i błędy z konkretnym powodem.
3. **Sprawdź czy odbiorca ma aktywne `GCMDevice`** w bazie (patrz zapytanie wyżej). Jeśli nie — sprawdź, czy nie testujesz dwóch kont w jednej przeglądarce (patrz pułapka wyżej).
4. **Sprawdź logi serwera pod kątem `NOTIFDBG`** — pokażą budowanie (`notification_id`), wysyłkę WS/FCM i przychodzące ack-i od klienta (`Notification ACK: ... status=...`). Weź `notification_id` z jednej linii i przefiltruj po nim, żeby zobaczyć całą podróż jednego powiadomienia (patrz sekcja "Śledzenie po `notification_id`" wyżej) — status `shown`/`clicked` w acku to twarde potwierdzenie, że dotarło; brak acku wskazuje, na którym etapie klienta utknęło.
5. **Dopiero teraz**, jeśli powyższe nie wyjaśnia problemu, patrz w kod — i zacznij od sekcji "Historia zmian" wyżej, żeby nie naprawiać czegoś, co już zostało naprawione (albo przypadkiem cofnąć naprawę).

## Kiedy użytkownik przestaje dostawać powiadomienia bez własnej akcji

Raz zarejestrowany push nie jest gwarantowany na zawsze. Bez żadnego działania samego użytkownika może on przestać dostawać powiadomienia z tych powodów:

1. **Ktoś inny zaloguje się na tym samym urządzeniu/przeglądarce i włączy powiadomienia.** Zamierzone zachowanie (`chat/push_api.py::PushDeviceRegisterView`): token FCM jest przypisany do instalacji przeglądarki, nie do konta, więc rejestracja push przez drugą osobę **kasuje** aktywne `GCMDevice` pierwszej (patrz sekcja "NAJCZĘSTSZA PUŁAPKA" wyżej).
2. **Token FCM zostaje unieważniony przez Google/przeglądarkę** — po dłuższej nieaktywności, przy czyszczeniu danych przez system (niska pamięć), aktualizacji przeglądarki. Backend dowiaduje się o tym dopiero przy próbie wysyłki (`Device unregistered`) i nie ma automatycznego mechanizmu odświeżenia tokenu — urządzenie zostaje martwe.
3. **Chrome/Android automatycznie cofa uprawnienie do powiadomień** dla stron rzadko odwiedzanych ("unused site permissions" / Safety Check) — poza kontrolą aplikacji.
4. **Konto zostaje dezaktywowane** (`is_active=False`) — filtrowane w `_push_enabled_for_user` / `send_fcm_to_all_sync`.
5. **Preferencje push (`push_notifications_chat` itp.) zmienią się nie przez użytkownika** — np. import danych albo błąd w innym miejscu kodu.
6. **Stary service worker po zmianie `firebase-messaging-sw.js`** — jeśli użytkownik długo nie otwiera aplikacji, przeglądarka może nie zdążyć pobrać nowej wersji SW.

Najczęstsze w praktyce: punkt 1 (współdzielone urządzenie) i punkt 2 (token po prostu padł).

### Czy instalacja jako PWA pomaga?

Tylko częściowo:

- **Pomaga na punkt 3** — zainstalowane PWA jest przez Chrome traktowane jako osobna aplikacja i **jest wyłączone** z automatycznego cofania uprawnień dla "nieużywanych" stron.
- **Pomaga częściowo na punkt 2** — system rzadziej agresywnie czyści dane zainstalowanej aplikacji niż zwykłej karty, a `gcm_sender_id` w `manifest.json` (patrz "Historia zmian", pkt. 3) jest wręcz **wymagany** przez Android Chrome w trybie standalone/PWA, żeby push w ogóle dochodził.
- **Nie pomaga na punkty 1, 4, 5, 6** — to sprawy współdzielonego profilu przeglądarki albo czysto serwerowe; instalacja jako PWA niczego tu nie zmienia.

Wniosek: warto rekomendować instalację jako PWA (zmniejsza ryzyko punktów 2 i 3), ale to nie rozwiązuje problemu współdzielonego urządzenia (pkt. 1), który i tak jest zamierzony.
