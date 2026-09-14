# Uproszczenie 1 — ograniczenie duplikacji nawigacji

Dokument opisuje małą refaktoryzację istniejącego zalogowanego layoutu. Checkbox oznacza zadanie do wykonania albo decyzję do potwierdzenia; nie oznacza wykonania zmiany.

## 1. Cel i zakres

Najbardziej opłacalna zmiana to usunięcie powtórzeń nazw i identyfikacji modułów między sidebarem a breadcrumbem, bez budowy nowego systemu nawigacji.

1. [ ] Zachować obecny wygląd, kolejność, URL-e i zachowanie linków.
2. [ ] Utrzymywać nazwę i identyfikację modułu w jednym prostym miejscu.
3. [ ] Zachować `PagePrefs`, w tym `data-prefs-link-scope` i `data-prefs-base-href`.
4. [ ] Nie zmieniać routingu, uprawnień, uwierzytelniania ani logiki modułów.

### Poza zakresem

Nie obejmuje to:

- generalnego systemu nawigacji dla wszystkich layoutów;
- przebudowy nawigacji anonimowej, ustawień, wylogowania, wyszukiwania, motywu ani powiadomień;
- zmian w `PagePrefs` i kontraktach JavaScript;
- przenosin kodu z `zzz` do `core`;
- zmiany wyglądu lub responsywności.

## 2. Problem

W `home/templates/home/base.html` sidebar i breadcrumb niezależnie powtarzają namespace'y, nazwy modułów, ikony oraz wyjątki stron ustawień obywatela. Linki sidebara mają ponadto różne URL-e i opcjonalne atrybuty `PagePrefs`, więc nie wszystkie da się bezpiecznie uogólnić.

To uzasadnia współdzielenie wyłącznie danych prezentacyjnych i identyfikacyjnych. Nie uzasadnia jeszcze tworzenia nowego rejestru, context processora ani przenoszenia całej logiki linków.

## 3. Minimalne rozwiązanie

W istniejącej warstwie `home` ustalić małą definicję modułów zawierającą tylko dane wspólne dla sidebara i breadcrumbu:

```python
{
    "namespace": "tasks",
    "label": _("Activities"),
    "icon": "bolt",
}
```

URL-e, zakresy `PagePrefs`, wyjątki aktywności i elementy specjalne pozostają jawne tam, gdzie są obecnie potrzebne.

1. [ ] Zidentyfikować faktycznie wspólne dane oraz wyjątki.
2. [ ] Umieścić wspólną listę w istniejącym mechanizmie `home`, bez nowego modułu.
3. [ ] Użyć jej do nazwy bieżącego modułu w breadcrumbzie.
4. [ ] Użyć jej w sidebarze tylko wtedy, gdy pętla nie komplikuje obsługi URL-i, `PagePrefs` i klas aktywności.
5. [ ] Zachować osobną, jawną obsługę ustawień obywatela, czatu, ankiet oraz linków ustawień/wylogowania.
6. [ ] Nie zmieniać `home/static/home/js/app.js`.

Jeśli wspólna lista wymaga większej abstrakcji niż obecny szablon, pozostawić ją jako mały helper/partial albo ograniczyć zmianę do breadcrumbu. Nie budować infrastruktury na przyszłość.

## 4. Kolejność realizacji

1. [ ] Zainwentaryzować warunki sidebara i breadcrumbu w `base.html`.
2. [ ] Spisać wyjątki `url_name` dotyczące ustawień obywatela.
3. [ ] Wydzielić wyłącznie dane rzeczywiście wspólne.
4. [ ] Podłączyć breadcrumb, a następnie — tylko jeśli upraszcza kod — sidebar.
5. [ ] Porównać wyrenderowany HTML dla strony głównej, modułu, czatu i ustawień.
6. [ ] Uruchomić tylko testy dotyczące zmienionego renderowania, jeśli istniejące pokrycie nie wystarcza.

## 5. Kryteria akceptacji

1. [ ] Zmiana nazwy modułu nie wymaga poprawiania dwóch niezależnych warunków.
2. [ ] Sidebar i breadcrumb pokazują tę samą nazwę modułu.
3. [ ] Kolejność, URL-e, ikony, klasy aktywności i wygląd pozostają bez zmian.
4. [ ] Ustawienia obywatela nadal są oznaczane jako „Settings”.
5. [ ] Linki `PagePrefs` działają dokładnie jak przed zmianą.
6. [ ] Nie zmieniono routingu, autoryzacji ani logiki biznesowej.

## 6. Ryzyko i kontrola zakresu

1. [ ] Sprawdzić moduły bez `data-prefs-link-scope` oraz link czatu.
2. [ ] Sprawdzić layout zalogowany na desktopie i mobile.
3. [ ] Nie wykonywać przy okazji refaktoryzacji `zzz`/`core`, `PagePrefs` ani logiki domenowej.
4. [ ] Jeśli abstrakcja zwiększa złożoność, zachować obecny sidebar i ograniczyć zmianę do wspólnej nazwy breadcrumbu.
