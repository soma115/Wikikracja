# Plan cutoveru PhysicalAsset i ResourceListing do Entity

## Cel i gwarancje

Usunąć modele/tabele `bookkeeping.PhysicalAsset` i `bookkeeping.ResourceListing` po zapewnieniu, że ich dane są w `resources.Entity`. Zachować stare URL-e przez `LegacyEntityReference`, mapę opartą wyłącznie na encjach oraz dotychczasową kaskadę członkowskich wpisów legacy przy usuwaniu przypisanego profilu.

Migracja nie dopisuje autora ani właściciela, których źródło nie potwierdza. Brak lokalizacji wymaganej przez encję fizyczną, niezgodne mapowanie lub konflikt integralności zatrzymuje migrację przed usunięciem tabel.

Przy istniejących mapowaniach `Entity` pozostaje źródłem prawdy o czasie ostatniej zmiany; dla niesparowanych wpisów daty źródłowe są kopiowane. `LegacyEntityReference.source_profile_id` zachowuje pierwotny profil starego shadow row wyłącznie na potrzeby rollbacku, nie jako bieżące przypisanie.

## Faza 1 — runtime tylko na Entity

- [x] Przełączyć fizyczny CRUD i formularz na `Entity`; stare ścieżki rozwiązać przez `LegacyEntityReference`, nowe ścieżki przez PK encji.
- [x] Przełączyć mapę na wszystkie encje `physical_asset` i usunąć fallback odczytujący `PhysicalAsset`.
- [x] Przełączyć zarządzanie, stare URL-e, archiwizację i usuwanie wpisów na `Entity`; usunąć dual-write do `ResourceListing`.
- [x] Zastąpić kaskadę `ResourceListing.profile` sygnałem `pre_delete` ograniczonym do nie-wspólnotowych encji legacy przypisanych usuwanemu profilowi.
- [x] Zachować `LegacyEntityReference` oraz historyczne źródła mapowania potrzebne starym URL-om i migracjom.

## Faza 2 — migracja i zgodność danych

- [x] Dla fizycznych rekordów bez mapowania skopiować nazwę i pełną lokalizację do `Entity`, bez fikcyjnego autora/przypisania.
- [x] Dla wpisów bez mapowania skopiować nazwę, opis, typ, status, daty i potwierdzone przypisanie; autor historyczny pozostaje nieznany.
- [x] Sprawdzić istniejące mapowania i odrzucić niezgodne lub osierocone referencje przed usunięciem modeli.
- [x] Usunąć tabele w migracji dopiero po udanym transferze i preflight.
- [x] Odtworzyć dane shadow i referencje w rollbacku; historyczny profil wspólnotowego wpisu jest snapshotem w `source_profile_id`. Jeśli profil już nie istnieje, pełne odtworzenie wymaga zweryfikowanego backupu SQLite.

## Faza 3 — testy i dokumentacja

- [x] Testować transfer i rollback, niezgodne/osierocone mapowania, niepoprawną lokalizację, stare URL-e, payload mapy i kaskadę usunięcia profilu.
- [x] Uruchomić dotknięte testy przez `.venv` na bazie tymczasowej, Django check, kontrolę migracji i Ruff.
- [x] Zaktualizować `PLAN_ZASOBY_UŻYTKOWNIKÓW.md`, `PLAN_MAPA.md`, `SECURITY_EXCEPTIONS.md` i `LOG_AI.md`.
- [x] Nie uruchamiać migracji na lokalnej bazie deweloperskiej ani żadnej bazie trwałej.
