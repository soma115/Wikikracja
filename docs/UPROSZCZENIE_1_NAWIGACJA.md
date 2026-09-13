# Uproszczenie 1 — jedna nawigacja i globalna powłoka

Dokument opisuje największą propozycję uproszczenia globalnego layoutu aplikacji. Checkbox oznacza zadanie do wykonania albo decyzję do potwierdzenia; nie oznacza wykonania zmiany.

## 1. Cel

1. [ ] Zdefiniować jedną listę elementów nawigacji dla wszystkich wariantów layoutu.
2. [ ] Używać tej samej definicji do renderowania sidebara, topbara mobilnego i nazwy bieżącego modułu.
3. [ ] Usunąć duplikację reguł aktywnego linku, ikon, etykiet i zakresów `PagePrefs`.
4. [ ] Zachować istniejące URL-e, wyjątki stron ustawień i kontrakty JavaScript.

## 2. Znaleziony problem

1. [ ] Potwierdzić, że `home/templates/home/base.html` ręcznie definiuje kilka reprezentacji tej samej nawigacji:
   - sidebar desktopowy;
   - topbar z breadcrumbem;
   - nawigację mobilną;
   - osobne linki ustawień i wylogowania.
2. [ ] Potwierdzić, że aktywność linków jest wyliczana przez długie warunki zależne od `namespace`, `url_name` i wyjątków stron.
3. [ ] Potwierdzić, że nazwy modułów i logo są renderowane niezależnie w sidebarze i topbarze.
4. [ ] Uwzględnić, że część linków posiada dodatkowy kontrakt `data-prefs-link-scope` / `data-prefs-base-href`.

Główne miejsca:

- `home/templates/home/base.html:111-249` — sidebar i linki modułów;
- `home/templates/home/base.html:275-301` — breadcrumb i nazwa bieżącego modułu;
- `home/templates/home/base.html:305-341` — wyszukiwanie, motyw i aktywność;
- `home/static/home/js/app.js` — obsługa `PagePrefs` i patchowanie linków sidebaru.

## 3. Docelowe uproszczenie

Jedna definicja elementu nawigacji powinna zawierać wyłącznie dane potrzebne do prezentacji i identyfikacji modułu, na przykład:

```python
{"url": "tasks:list", "label": _("Activities"), "icon": "bolt", "namespace": "tasks", "prefs_scope": "tasks"}
```

1. [ ] Ustalić minimalny kontrakt elementu nawigacji.
2. [ ] Przenieść listę modułów do istniejącej warstwy `home` zamiast tworzyć nowy moduł infrastrukturalny.
3. [ ] Zastąpić powtarzające się fragmenty HTML pętlą w istniejącym partialu.
4. [ ] Wyprowadzać etykietę breadcrumb z tej samej listy.
5. [ ] Wyprowadzać stan aktywny z jednej funkcji albo jednego filtra, z jawną listą wyjątków.
6. [ ] Nie zmieniać nazw tras ani znaczenia istniejących scope'ów `PagePrefs`.

## 4. Powiązane uproszczenie architektoniczne

Pakiet `zzz` powinien pozostać warstwą ustawień, routingu i procesów startowych. Tymczasem wspólne funkcje prezentacyjne są implementowane w `zzz.templatetags.citizen_filters` i importowane przez wiele aplikacji.

1. [ ] Przenieść kanoniczną implementację funkcji wyświetlania obywatela do istniejącej warstwy `core`.
2. [ ] Zachować tymczasowy adapter w `zzz.templatetags.citizen_filters`, aby nie łamać istniejących template tagów i importów.
3. [ ] Stopniowo zmienić importy aplikacji domenowych z `zzz` na `core`.
4. [ ] Dopiero po migracji wszystkich użytkowników usunąć adapter, jeśli nie jest już potrzebny.
5. [ ] Nie scalać mechanicznie `feed_registry`, `search_registry` i `dashboard_registry`; ich rozdzielenie jest świadomą granicą modułów.

## 5. Kolejność realizacji

1. [ ] Zainwentaryzować wszystkie linki renderowane przez `base.html`.
2. [ ] Zidentyfikować wyjątki dla stron ustawień i zapisać je w jednym miejscu.
3. [ ] Przygotować listę nawigacji bez zmiany wyglądu.
4. [ ] Podłączyć sidebar do wspólnej listy.
5. [ ] Podłączyć breadcrumb/topbar do wspólnej listy.
6. [ ] Podłączyć linki mobilne i zakresy `PagePrefs`.
7. [ ] Usunąć nieużywane ręczne warunki dopiero po porównaniu wyrenderowanego HTML.
8. [ ] Dodać focused test renderowania aktywnego modułu i stron ustawień.

## 6. Kryteria akceptacji

1. [ ] Dodanie nowego modułu wymaga zmiany tylko jednej listy nawigacji.
2. [ ] Sidebar i breadcrumb pokazują tę samą nazwę oraz ikonę modułu.
3. [ ] Strony ustawień nie są oznaczane jako zwykły moduł obywateli.
4. [ ] Linki zachowują zapisane filtry i zakładki.
5. [ ] Użytkownik anonimowy nadal widzi wyłącznie dozwoloną nawigację publiczną.
6. [ ] Nie zmieniono uwierzytelniania, autoryzacji ani routingu.

## 7. Ryzyko

1. [ ] Przetestować wszystkie wyjątki `url_name` w aplikacji `obywatele`.
2. [ ] Przetestować moduły bez `data-prefs-link-scope`.
3. [ ] Przetestować layout anonimowy, desktopowy i mobilny.
4. [ ] Nie wykonywać refaktoryzacji logiki głosowań, członkostwa ani autoryzacji w ramach tego zadania.
