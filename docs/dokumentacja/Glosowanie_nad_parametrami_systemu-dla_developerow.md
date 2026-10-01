# Parametry systemowe zarządzane przez referendum — dokumentacja techniczna

## Aktualny model

`site_settings.models.SiteParameters` jest singletonem przechowującym parametry instancji w bazie danych. `SiteParameters.get()` zwraca rekord o kluczu `1`, tworząc go przy pierwszym użyciu z wartościami domyślnymi modelu. `site_settings.params.get_param(name)` odczytuje wartość z tego rekordu; nie stosuje fallbacku do zmiennych środowiskowych.

`site_settings.params.PARAM_SPECS` jest źródłem prawdy dla parametrów, które można zaproponować w referendum. Rejestr napędza pola formularza, grupowanie, walidację zakresów i czytelną listę zmian. Bieżący zestaw:

| Kategoria | Parametry | Dozwolony zakres |
| --- | --- | --- |
| Głosowania | `wymaganych_podpisow` | 2–20 |
| Głosowania | `czas_na_zebranie_podpisow` | 1–3650 dni |
| Głosowania | `dyskusja`, `czas_trwania_referendum` | po 1–365 dni |
| Czat | `archive_public_chat_room`, `delete_public_chat_room` | po 1–3650 dni |
| Obywatele | `acceptance` | 1–100 |
| Obywatele | `delete_inactive_user_after` | 1–3650 dni |
| Grupa | `group_is_public` | wartość logiczna |
| Tożsamość | `site_name` | tekst, do 255 znaków |

Marka/logo (`SiteParameters.brand_mark`) jest przechowywana w tym samym modelu, ale nie należy do `PARAM_SPECS`; formularz obsługuje ją jako osobny element referendum. Opis strony i krótka nazwa PWA nie są obecnie parametrami referendum. `SITE_DOMAIN` pozostaje konfiguracją środowiskową używaną przy synchronizacji rekordu Django Sites.

## Główne elementy implementacji

- `site_settings/models.py` — singleton, domyślne wartości parametrów i plik marki.
- `site_settings/params.py` — `PARAM_SPECS`, konwersja i walidacja wartości, odczyt oraz zastosowanie zatwierdzonych zmian.
- `glosowania/forms.py::ParametersProposalForm` — formularz dynamiczny na podstawie `PARAM_SPECS`; dla istniejącej propozycji pokazuje proponowane wartości, a dla niezmienionych parametrów bieżące wartości.
- `glosowania/models.py::Decyzja` — przechowuje `proposed_parameters` i opcjonalny `proposed_brand_mark`; wersje edytowanej decyzji są zachowywane przez `DecyzjaWersja`.
- `glosowania/models.py::ReferendumEffect` i `glosowania/management/commands/vote.py` — wiążą zatwierdzone referendum z zastosowaniem parametrów lub marki.

## Złożenie i edycja propozycji

`ParametersProposalForm` wymaga uzasadnienia i co najmniej jednej zmiany parametru albo nowego pliku marki. Wartości numeryczne są ograniczane przez zakresy z `PARAM_SPECS`. Formularz tworzenia/edycji zapisuje zmienione parametry w `Decyzja.proposed_parameters`; nowy plik trafia do `proposed_brand_mark`. Przy edycji tworzy się migawkę poprzedniej wersji decyzji.

Proponowana marka w formularzu referendum musi być plikiem PNG o rozmiarze do 5 MB i najdłuższym boku 64–4096 px. Po normalizacji jest zapisywana jako kwadratowy PNG 1024×1024 px. Model i pipeline marki generują z niej favicon oraz ikony PWA; ograniczenie formularza referendum do PNG wynika z jego walidacji, mimo że niższa warstwa modelu obsługuje też inne formaty wejściowe.

## Zastosowanie zmian

Po zatwierdzeniu referendum komenda `vote` tworzy/obsługuje odpowiedni `ReferendumEffect`:

- dla parametrów `apply_parameters()` stosuje wyłącznie rozpoznane nazwy z `PARAM_SPECS`, ogranicza wartości do zadeklarowanych zakresów i zapisuje singleton;
- zmiana `site_name` synchronizuje nazwę rekordu Django Sites i czyści jego cache; domena pochodzi z `settings.SITE_DOMAIN`;
- dla marki `apply_brand_mark()` zapisuje zaakceptowany obraz w `SiteParameters.brand_mark`; zapis modelu normalizuje obraz i odtwarza pochodne ikon.

Odczyt parametrów biznesowych odbywa się z bazy przez `get_param()`, więc ich późniejsze użycie nie zależy od restartu procesu. Zmienne środowiskowe nadal służą do konfiguracji technicznej, ale nie są bieżącym źródłem zatwierdzonych wartości parametrów.

## Utrzymanie

Przy dodaniu lub usunięciu parametru referendum należy spójnie zaktualizować model `SiteParameters`, rejestr `PARAM_SPECS`, konsumentów `get_param()` oraz testy. Zmiany w zakresie członkostwa, głosowań, zastosowania efektów albo retencji danych wymagają osobnej decyzji; ten dokument opisuje bieżący kod i nie zmienia tych reguł.
