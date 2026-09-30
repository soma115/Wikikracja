# Udokumentowane wyjątki i założenia bezpieczeństwa

Ten dokument opisuje świadomie zaakceptowane zachowania, które mogą wyglądać na zbyt liberalne podczas audytu. Nie znosi obowiązku ochrony kont, sekretów, sesji ani granic sieciowych. Zmiany wymienione niżej należy traktować jako decyzje produktowe, a nie jako ogólną zgodę na pomijanie walidacji.

## Zaufani członkowie i edycja dokumentów

Członkowie działają w modelu wzajemnego zaufania i współdecydowania; aplikacja nie ma wbudowanej hierarchii administratorów/redaktorów. Zalogowani członkowie mogą wspólnie edytować oraz archiwizować dokumenty, w tym dokumenty utworzone przez innych członków. To zachowanie jest celowe i pozostaje bez zmian.

Treści dokumentów korzystają z HTML i stylów tworzonych w TinyMCE. Nadmierne ograniczenie dozwolonych tagów i atrybutów powoduje utratę formatowania i nieprawidłowe wyświetlanie dokumentów. Obecna szeroka obsługa HTML jest świadomym kompromisem opartym na założeniu, że zalogowani członkowie są zaufani. Nie należy zawężać jej ani odbierać członkom wspólnej edycji bez decyzji produktowej i migracji/naprawy istniejących treści.

Stopka systemowa jest wspólną treścią edytowaną w tym samym modelu. Jej renderowanie zachowujące HTML jest częścią tego założenia. Zmiana sposobu jej wyświetlania wymaga zachowania dotychczasowego formatowania i nie jest objęta bieżącymi poprawkami.

To założenie dotyczy wyłącznie członków dopuszczonych do aplikacji. Nie stanowi podstawy do logowania haseł, przyjmowania nieuwierzytelnionych żądań federacyjnych ani omijania walidacji przekierowań, sesji czy formularzy.

## Publiczna skrzynka kontaktowa

Publiczna skrzynka kontaktowa może przyjmować wiadomości od osób niezalogowanych również wtedy, gdy `group_is_public` jest wyłączone. Ustawienie to nie ma wyłączać kanału kontaktowego; wiadomość gościa jest przeznaczona do kontaktu z grupą, a nie do uzyskania członkostwa lub przeglądania jej zawartości. Link kontaktowy i endpoint gościnny pozostają dostępne. Ochrona przed spamem i nadużyciami powinna być oceniana osobno, bez zmiany tej funkcji.

## Zmiany wymagające ponownego przeglądu

- Jeśli zmieni się model zaufania, pojawi się rejestracja otwarta bez akceptacji społeczności albo treści będą importowane od niezaufanych nadawców, należy ponownie ocenić sanitizację HTML i uprawnienia dokumentów.
- Jeśli dokumenty zaczną zawierać treści federowane od niezależnych instancji, założenie zaufania członków lokalnych nie może być automatycznie rozszerzone na treści zdalne.
- Każda nowa kategoria HTML/atrybutów powinna zachować bezpieczne zachowanie przeglądarki i zostać sprawdzona pod kątem aktywnej zawartości; zachowanie formatowania nie oznacza akceptacji skryptów wykonywalnych.
