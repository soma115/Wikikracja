# Plan cutoveru jednostek finansowych do Entity

## Cel i granice

Usunąć shadow model `bookkeeping.Asset` i legacy FK `Transaction.asset`, pozostawiając `resources.Entity` jedynym źródłem prawdy o jednostkach finansowych. Zachować stare adresy URL przez `LegacyEntityReference`. Nie zmieniać istniejących kwot, transakcji, walut ani ich domyślności.

Migracja nie może usuwać danych, jeśli brakuje mapowania shadow `Asset` → finansowa `Entity` albo `Transaction.entity` nie odpowiada encji przypisanej przez dotychczasowe `Transaction.asset`. Takie przypadki mają zatrzymać migrację z czytelnym błędem, a nie być automatycznie rozstrzygane.

## Faza 1 — runtime tylko na Entity

- [x] Przełączyć zapis transakcji na wymagane `Transaction.entity`; usunąć dwukierunkową synchronizację FK z `Transaction.save()`.
- [x] Usunąć odczytowe fallbacki do `Transaction.asset` z feedu, powiadomień, listy transakcji i innych konsumentów.
- [x] Przełączyć agregacje, seed danych i testy z `bookkeeping.Asset` na `resources.Entity`.
- [x] Przełączyć CRUD jednostek finansowych na `Entity`; zachować stare URL-e przez mapowanie istniejących ID w `LegacyEntityReference` i osobne ścieżki dla nowych encji.
- [x] Zachować ochronę `PROTECT` dla jednostki użytej przez transakcję, walidację kodów i pojedynczej jednostki domyślnej.

## Faza 2 — weryfikacja danych przed cutoverem

- [x] Test migracji potwierdza, że każdy legacy `Asset` ma dokładnie jedno mapowanie do finansowej `Entity`, a pola kodu, nazwy, symbolu, precyzji, waluty i domyślności są zgodne.
- [x] Test migracji potwierdza, że każda transakcja ma `entity` zgodne z mapowaniem starego `asset`.
- [x] Migracja zatrzymuje się na brakującym lub sprzecznym mapowaniu bez usuwania ani nadpisywania danych.

## Faza 3 — odwracalna migracja schematu

- [x] Ustawić `Transaction.entity` jako wymagane.
- [x] Usunąć `Transaction.asset` i model/tabelę `bookkeeping.Asset` dopiero po pomyślnym preflight.
- [x] Zapewnić odwrócenie migracji odtwarzające model, wiersze shadow `Asset` i FK transakcji z zachowaniem dotychczasowych PK; nowe encje dostają mapowane ID przy rollbacku.
- [x] Zachować `LegacyEntityReference` potrzebne starym URL-om; nie usuwać innych adapterów ani modeli z tego cutoveru.

## Faza 4 — weryfikacja i dokumentacja

- [x] Uruchomić testy modeli, usług, widoków, feedu, powiadomień i migracji przez `.venv` na bazie testowej w pamięci.
- [x] Uruchomić Ruff, Django check i kontrolę migracji.
- [x] Zaktualizować `PLAN_ZASOBY_UŻYTKOWNIKÓW.md` i `LOG_AI.md`.
- [x] Agent nie uruchamiał migracji. Operator później wykonał `start_dev.py --full`; odczyt `db/db.sqlite3` potwierdza `bookkeeping.0040` i `0041` oraz brak tabel legacy. Stan produkcji pozostaje niezweryfikowany.
