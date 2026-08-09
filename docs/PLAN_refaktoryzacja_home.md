# Plan naprawy: coupling w `home/views.py`

> Kontekst: przegląd architektury wykazał, że `home/views.py` jest głównym punktem
> tight-coupling w projekcie — importuje modele bezpośrednio z 8 aplikacji
> (`board`, `bookkeeping`, `chat`, `events`, `glosowania`, `obywatele`,
> `site_settings`, `tasks`), a `home/signals.py` z kolejnych 6. Ten dokument to
> plan naprawy, rozbity na fazy o rosnącym ryzyku/nakładzie. Każda faza jest
> samodzielnie mergowalna i nie wymaga wykonania kolejnych.

## Stan wyjściowy (fakty)

- `home/views.py` — ~988 linii, 15 widoków/funkcji pomocniczych w jednym module.
- `home()` (linie 69–243): buduje dashboard bezpośrednio z `Decyzja`, `Task`,
  `Event`, `Asset`/`asset_balances`, `Uzytkownik`, `Message`, `QuickLink`.
- `_generate_feed_raw()` / `generate_feed_items()` (linie 246–419): agregują
  `Post`, `Task`, `Event`, `Room`/`Message`, `Decyzja`, `CitizenActivity` w jedną
  listę feedu, cache'owaną globalnie w Redis (`FEED_CACHE_KEY`, TTL 1h).
- `global_search()` (linie 642–793): przeszukuje `Decyzja`, `DecyzjaArgument`,
  `Event`, `User`, `Room`, `Message`.
- `home/signals.py`: nasłuchuje `post_save`/`post_delete` na 6 modelach z innych
  aplikacji tylko, aby zawołać `invalidate_feed_cache()`.
- **Druga, odrębna oś coupling** (nieoczywista, łatwo przeoczyć): `mark_as_read`,
  `mark_all_read`, `mark_unread` (linie 470–636) importują `chat.models.Room`
  i `chat.services.CHAT_UNREAD_CACHE_KEY` i specjalnie traktują
  `content_type in ['message', 'room_messages']` jako wyjątek — dla czatu
  `Room.seen_by` jest "single source of truth" zamiast generycznego
  `ReadStatus`. To osobny mechanizm od generowania feedu i osobny punkt
  coupling z `chat`, który plan musi adresować niezależnie od Fazy 2.
- Istniejący wzorzec w projekcie: `board`, `chat`, `tasks`, `obywatele` i
  `glosowania` już mają `AppConfig.ready()` importujący `<app>.signals` (np.
  `board/apps.py:8-10`, `chat/apps.py:7-9`). `home/apps.py` też już to robi
  (`import home.signals`). Faza 2 rozszerza ten istniejący wzorzec, a nie
  wprowadza nowy. `events`, `bookkeeping`, `site_settings`, `categories` nie
  mają jeszcze `ready()` — dla `events` trzeba go dopisać od zera.
- Testy: `home/tests.py` (feed + badge + zgodność liczników unread) — niezłe
  pokrycie zachowania, ale zero testów jednostkowych samej logiki agregacji
  bez przechodzenia przez `TestCase`/request.

## Cel

Odwrócić kierunek zależności: dziś **home zależy od 8 innych aplikacji**.
Docelowo **inne aplikacje rejestrują się w home** (przez mały, wspólny
kontrakt), a `home` nie importuje ich modeli wprost. Po drodze: wydzielić
logikę biznesową z widoków do przetestowalnych funkcji.

## Faza 0 — siatka bezpieczeństwa (przed jakimkolwiek refaktorem)

1. Dodać testy charakteryzujące bieżące zachowanie tam, gdzie go nie ma:
   - `_generate_feed_raw()` — kolejność sortowania (events chronologicznie
     rosnąco, resztę malejąco), obcinanie opisów do 125 znaków, cache hit/miss.
   - `global_search()` — po jednym teście na każdą kategorię (`decision`,
     `event`, `citizen`, `chat`) + test na `active_cats` filtrujący kategorie.
   - `home()` — test na `active_referendum` (kolory progress bara wg
     `time_pct`) i na `default_asset is None` (ścieżka onboardingu finansów).
2. Uruchomić `pytest home` i zanotować bieżący czas/wynik jako baseline.

Bez tego refaktor rozproszonej logiki (feed, search, dashboard) jest zbyt
ryzykowny — dużo gałęzi warunkowych bez testów.

## Faza 1 — wydzielenie service layer (thin views), bez zmiany zależności

Nie usuwa jeszcze coupling, ale odseparowuje logikę biznesową od Django
request/response, więc staje się łatwa do testowania i do dalszej faktoryzacji.

Nowe pliki:
- `home/services/feed.py` — przenieść `_generate_feed_raw`,
  `generate_feed_items`, `build_read_status_map`, `get_unread_count`,
  `invalidate_feed_cache`.
- `home/services/search.py` — przenieść ciało `global_search` jako
  `run_global_search(query, active_cats, user) -> list[dict]`.
- `home/services/dashboard.py` — przenieść budowanie widgetów z `home()`
  (`active_referendum`, `upcoming_events`, `default_*`, `community stats`)
  jako `build_dashboard_context(user) -> dict`.

`home/views.py` po tej fazie:
```python
from home.services.feed import generate_feed_items, get_unread_count
from home.services.dashboard import build_dashboard_context

def home(request):
    ...
    feed_items = generate_feed_items(request.user)
    context = build_dashboard_context(request.user)
    context.update(feed_items=feed_items, ...)
    return render(request, 'home/home.html', context)
```

**Efekt:** te same importy z 8 aplikacji nadal istnieją, ale są teraz w 3
skoncentrowanych modułach `services/*`, a nie rozmyte w widoku. Widoki
(`home()`, `global_search()`) spadają do rozmiaru "request in → context out".
Testy jednostkowe (`home/services/tests/test_feed.py` itd.) nie potrzebują
już `self.client.get(...)`.

**Ryzyko:** niskie — czysty przenos kodu (`git mv` logiki), bez zmiany
zachowania. Testy z Fazy 0 muszą przejść bez zmian.

## Faza 2 — registry pattern dla feedu (realna dekompozycja coupling)

To jest właściwa naprawa problemu #1: `home` przestaje wiedzieć, że istnieją
`Post`, `Task`, `Event`, `Decyzja`, `CitizenActivity`, `Room`/`Message`.

1. Zdefiniować kontrakt w `home/feed_registry.py`. Element feedu to zwykły
   `dict` w formacie już używanym w `_generate_feed_raw` (`content_type`,
   `title`, `description`, `author`, `timestamp`, `url`, `object_id`, ...) —
   na tym etapie nie trzeba wprowadzać nowego typu, ewentualny `TypedDict`
   to osobna, kosmetyczna zmiana:
   ```python
   FeedProvider = Callable[[datetime], list[dict]]  # since -> items
   _providers: list[FeedProvider] = []


   def register_feed_provider(fn: FeedProvider) -> FeedProvider:
       _providers.append(fn)
       return fn


   def collect_feed_items(since: datetime) -> list[FeedItem]:
       items = []
       for provider in _providers:
           items.extend(provider(since))
       return items
   ```
2. Każda aplikacja-właściciel danych (board, tasks, events, glosowania,
   obywatele, chat) dostaje `feed.py` z funkcją `get_feed_items(since)`,
   zwracającą listę słowników w ujednoliconym formacie (już używanym w
   `_generate_feed_raw`), i rejestruje ją w `apps.py::ready()`:
   ```python
   # board/apps.py
   def ready(self):
       from home.feed_registry import register_feed_provider
       from board.feed import get_feed_items

       register_feed_provider(get_feed_items)
   ```
3. `home/services/feed.py::_generate_feed_raw()` zamienia 6 bloków
   `Post.objects.filter(...)` / `Task.objects.filter(...)` / ... na jedno
   wywołanie `collect_feed_items(since=timezone.now() - td(days=30))`.
4. Analogicznie dla cache invalidation: `home/signals.py` przestaje importować
   modele z 6 aplikacji. Zamiast tego każda aplikacja, zmieniając swój model
   feedowy, woła generyczny sygnał `home.signals.feed_changed.send(sender=...)`
   we własnym `signals.py` (albo — prościej — `home` udostępnia publiczną
   funkcję `home.services.feed.invalidate_feed_cache()`, a każda aplikacja
   podłącza się do niej w swoim `apps.py::ready()` tak jak w punkcie 2).

**Rezultat:** zależność `home → {board, tasks, events, glosowania,
obywatele, chat}` znika. Zależność odwraca się do
`{board, tasks, events, glosowania, obywatele, chat} → home` (każda aplikacja
zna kontrakt `home.feed_registry`, ale `home` nie zna ich modeli). To jest
akceptowalne, bo `home` staje się "core"/agregatorem, a zależność od
kontraktu (interfejsu) jest dużo słabsza niż zależność od konkretnych modeli.

**Ryzyko:** średnie — zmienia się miejsce importów i moment ich wykonania
(`AppConfig.ready()`), trzeba uważać na kolejność ładowania aplikacji
(`INSTALLED_APPS`) i na to, żeby `ready()` nie importował modeli przed
gotowością rejestru aplikacji. Wymaga pełnego przebiegu testów z Fazy 0/1
oraz manualnego sprawdzenia dashboardu i strony `/activity`.

## Faza 2b — coupling przez `mark_as_read`/`mark_all_read`/`mark_unread`

Te trzy widoki mają odrębny, mniej oczywisty problem: zamiast generycznie
zapisywać `ReadStatus`, dla `content_type in ['message', 'room_messages']`
bezpośrednio operują na `chat.models.Room.seen_by` i czyszczą
`chat.services.CHAT_UNREAD_CACHE_KEY`. To osobna zależność od `chat` — nawet
po Fazie 2 (registry dla *odczytu* feedu) `home` nadal będzie znać `Room`
przy *zapisie* stanu przeczytania.

Dwie opcje, od najprostszej:

1. **Zaakceptować jako świadomy wyjątek i udokumentować.** Czat i tak ma
   specjalny status w `ReadStatus.ContentType`/`_CONTENT_TYPE_MAP` (mapa już
   wie o `room_messages`), więc jedna dodatkowa zależność `home → chat` w
   miejscu odczytu/zapisu stanu przeczytania jest mniejszym złem niż
   dodawanie kolejnej warstwy abstrakcji dla pojedynczego przypadku. To
   rekomendowana opcja na start — nie blokuje Fazy 2.
2. **Rozszerzyć kontrakt registry o hooki zapisu** (`mark_read(object_id, user)`
   / `mark_unread(object_id, user)`) analogicznie do `FeedProvider`, które
   `chat` (i w przyszłości inne aplikacje o niestandardowym mechanizmie
   read/unread) rejestrowałby tak jak `get_feed_items`. Ma sens tylko jeśli
   pojawi się druga aplikacja z podobną potrzebą — inaczej to
   nadinżynieria dla jednego przypadku.

## Faza 3 — to samo dla `global_search` (opcjonalnie, mniejszy priorytet)

Analogiczny registry: `SearchProvider = Callable[[str, User], list[dict]]`,
każda aplikacja rejestruje `search(query, user)`. Można zrobić dopiero po
Fazie 2, gdy wzorzec jest już sprawdzony na feedzie — search jest używany
rzadziej i ma mniejszy blast radius niż feed.

## Co pozostaje w `home/views.py` po refaktorze

Rzeczy specyficzne dla samego `home` (nie cross-cutting): `manifest()`,
`firebase_messaging_sw()`, `dynamic_settings_js()`, `RememberLoginView`,
`haslo()`, `site_admin()`, `activity_page()`, `save_filter_state()`. Te już
nie mają problematycznych importów i nie wymagają zmian. `mark_as_read()`,
`mark_all_read()`, `mark_unread()` zostają z jedną świadomą, udokumentowaną
zależnością od `chat.Room`/`chat.services` (patrz Faza 2b, opcja 1) — to
akceptowalny, opisany wyjątek, nie regresja.

## Zakres i szacowany nakład

| Faza | Zakres plików | Ryzyko | Wartość |
|---|---|---|---|
| 0 | `home/tests.py` (nowe testy) | brak (tylko dodanie testów) | wysoka — baza pod dalsze zmiany |
| 1 | `home/views.py` → `home/services/{feed,search,dashboard}.py` | niskie | średnia — testowalność |
| 2 | `home/feed_registry.py`; `apps.py` w `board`, `tasks`, `glosowania`, `obywatele`, `chat` (rozszerzenie istniejącego `ready()`) i w `events` (nowy `ready()`); `home/signals.py` | średnie | wysoka — usuwa realny coupling |
| 2b | `home/views.py::mark_as_read/mark_all_read/mark_unread` — decyzja: udokumentowany wyjątek (zalecane) albo rozszerzenie registry | niskie (opcja 1) / średnie (opcja 2) | niska — porządkuje, nie usuwa krytycznego ryzyka |
| 3 | `home/search_registry.py`, analogicznie | średnie | niska/średnia |

## Kryteria akceptacji

- `home/views.py` nie importuje żadnego modelu z `board`, `bookkeeping`,
  `chat`, `events`, `glosowania`, `obywatele`, `tasks` do generowania feedu
  i wyszukiwania. Wyjątki dopuszczone i opisane w tym dokumencie:
  `site_settings` przy `manifest()` (config, nie dane feedu) oraz `chat.Room`
  w `mark_as_read`/`mark_all_read`/`mark_unread` (Faza 2b, opcja 1).
- `pytest home board tasks events glosowania obywatele chat` — zielone,
  bez regresji w testach z Fazy 0.
- Dodanie nowej aplikacji do feedu (hipotetyczny `polls`) wymaga tylko
  dodania `polls/feed.py` + rejestracji w `polls/apps.py::ready()` (wzorem
  istniejącego `board/apps.py`) — zero zmian w `home/`.
