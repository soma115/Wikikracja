# Plan: zgodność TinyMCE i standardy UI

## Decyzje zakresu

- [x] Obsłużyć cały HTML5 zgodny ze schematem TinyMCE.
- [x] Dopasować cały interfejs edytora do standardów UI Wikikracji.
- [x] Nie wykonywać migracji istniejących treści.
- [x] Zastosować minimalną ochronę techniczną: usuwać skrypty, event handlery i niebezpieczne protokoły URL.
- [x] Zaktualizować TinyMCE oraz kompatybilne zależności.

## Faza 1 — Inwentaryzacja i aktualizacja TinyMCE

- [x] Ustalić aktualną wersję TinyMCE dostarczaną przez `django-tinymce`: 7.8.0.
- [x] Sprawdzić najnowszą bezpieczną wersję zgodną z projektem i Pythonem/Django: `django-tinymce` 5.0.0 jest aktualnie najnowsze.
- [x] Potwierdzić brak wymaganej aktualizacji pakietu; nie wykonywać ręcznej podmiany plików vendorowych.
- [x] Dodać `tinycss2`, wymagane przez Bleach do bezpiecznego zachowania stylów CSS TinyMCE.
- [x] Zweryfikować zgodność API, pluginów, skinu i aktualnej konfiguracji.
- [x] Sprawdzić, czy aktualizacja wymaga zmian w konfiguracji lub szablonach; zaktualizować konfigurację treści i CSS dla TinyMCE 7.

## Faza 2 — Rozdzielenie prostego edytora i TinyMCE

- [x] Zachować prosty `RichTextWidget` i jego wąski kontrakt.
- [x] Wydzielić osobny kontrakt dla treści `board.Post`.
- [x] Nie rozszerzać globalnego prostego sanitizera na potrzeby TinyMCE.
- [x] Zapewnić osobne renderowanie treści TinyMCE.

## Faza 3 — Zgodność z HTML TinyMCE

- [x] Oprzeć obsługę na schemacie HTML5 TinyMCE, nie na ręcznej kopii toolbaru.
- [x] Zachować strukturę akapitów, nagłówków, list, tabel, kodu, obrazów, mediów i formatowania.
- [x] Zastosować minimalną ochronę techniczną po stronie serwera.
- [x] Usuwać wyłącznie skrypty, event handlery i niebezpieczne protokoły URL.
- [x] Zachować istniejące dokumenty bez masowej migracji.
- [x] Zapewnić poprawne wyświetlanie starszych treści tekstowych.

## Faza 4 — Uporządkowanie konfiguracji

- [x] Utrzymywać konfigurację TinyMCE w jednym autorytatywnym miejscu (`board/static/js/uploader.js`).
- [x] Zachować rozdział konfiguracji TinyMCE i obsługi uploadu w jednym istniejącym pliku bez nowych modułów.
- [x] Zachować możliwość zmiany toolbaru i pluginów bez przepisywania backendowego kontraktu HTML.
- [x] Usunąć zbędne duplikowanie konfiguracji.

## Faza 5 — Dopasowanie całego edytora do UI

- [x] Dopasować obszar treści przez `content_css` i wspólną klasę `tw-post-content`.
- [x] Dopasować toolbar, przyciski i stany aktywne w zakresie wspieranym przez istniejący skin TinyMCE.
- [x] Wykorzystać istniejące tokeny i wspólny pipeline CSS.
- [x] Nie tworzyć modułowego arkusza CSS dla boarda.
- [x] Zachować prefiks `tw-` dla nowych klas aplikacji.
- [x] Nie aktualizować dokumentacji standardów, ponieważ nie powstał nowy wzorzec UI.

## Faza 6 — Stylowanie wynikowego dokumentu

- [x] Przygotować wspólne style treści dokumentu dla edytora i widoku artykułu.
- [x] Ujednolicić akapity, nagłówki, listy, cytaty, kod, tabele, obrazy i multimedia.
- [x] Zapewnić responsywność treści na małych ekranach.
- [x] Wygenerować CSS przez `npm run build:css`.
- [x] Nie modyfikować ręcznie `tailwind.build.css`.

## Faza 7 — Testy regresji

- [x] Dodać testy zachowania dokumentów z pełną strukturą TinyMCE.
- [x] Sprawdzić zachowanie list, nagłówków, akapitów, tabel, obrazów i mediów.
- [x] Sprawdzić minimalną ochronę HTML.
- [x] Sprawdzić niezależność prostego widgetu od konfiguracji TinyMCE.
- [x] Sprawdzić istniejące dokumenty bez migracji.

## Faza 8 — Weryfikacja

- [x] Sprawdzić wersję repozytoryjnego interpretera `.venv` (Python 3.14.3).
- [x] Uruchomić właściwe testy backendowe i frontendowe.
- [x] Uruchomić `npm run build:css`.
- [x] Uruchomić `scripts/regression_scan.py`.
- [x] Uruchomić `scripts/ui_guard.py`.
- [x] Przejrzeć diff pod kątem duplikacji, wyjątków CSS i ręcznie zmienionych plików generowanych.
