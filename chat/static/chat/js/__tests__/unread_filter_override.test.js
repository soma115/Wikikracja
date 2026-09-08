/**
 * @jest-environment jsdom
 *
 * Testy decideUnreadFilterOverride — czystej funkcji decydujacej, czy intencja
 * filtra z URL (z parseChatLocation: ?view=unread / ?view=rooms) ma przy
 * zastosowaniu trasy zmienic aktualny stan filtra.
 *
 * Kontrakt z chat.js (synchronizowac przy zmianie — funkcja kopiowana 1:1):
 *   - Reczny klik uzytkownika (userToggled) MA PIERWSZENSTWO nad intencja z URL.
 *     Bez tego wystepuje bug: wejscie z ?view=unread aplikuje filtr juz w
 *     DOMContentLoaded, user zdejmuje go zanim trasa zostanie zastosowana,
 *     a asynchroniczny syncRouteFromInitial (czytajace wciaz obecny
 *     ?view=unread) wlacza filtr z powrotem — "filtr wraca po odkliknieciu".
 *   - Bez recznego klikniecia: 'on' + filtr nieaktywny -> 'enable',
 *     'off' + filtr aktywny -> 'disable' — ?view=rooms deklaratywnie prosi
 *     o liste bez filtra (stan filtra nie jest juz persystowany).
 *   - W pozostalych przypadkach -> 'none' (nic nie zmieniamy).
 */

// ── wierna kopia z chat.js (synchronizowac przy zmianie!) ────────────────────

function decideUnreadFilterOverride({ urlFilter, isActive, userToggled }) {
    // Reczna decyzja usera jest ostateczna — nie nadpisujemy jej intencja z URL.
    if (userToggled) return 'none';
    if (urlFilter === 'on' && !isActive) return 'enable';
    if (urlFilter === 'off' && isActive) return 'disable';
    return 'none';
}

// ── Reczny klik bije intencje z URL (rdzen buga) ─────────────────────────────

describe('reczny klik usera ma pierwszenstwo nad URL', () => {

    test('?view=unread, ale user zdjal filtr przed zastosowaniem trasy -> nie wlaczamy z powrotem', () => {
        const decision = decideUnreadFilterOverride({
            urlFilter: 'on', isActive: false, userToggled: true,
        });
        expect(decision).toBe('none');
    });

    test('?view=rooms, ale user wlaczyl filtr recznie -> nie zdejmujemy', () => {
        const decision = decideUnreadFilterOverride({
            urlFilter: 'off', isActive: true, userToggled: true,
        });
        expect(decision).toBe('none');
    });

    test('userToggled blokuje override niezaleznie od stanu', () => {
        expect(decideUnreadFilterOverride({ urlFilter: 'on', isActive: true, userToggled: true })).toBe('none');
        expect(decideUnreadFilterOverride({ urlFilter: 'off', isActive: false, userToggled: true })).toBe('none');
    });
});

// ── Bez recznego klikniecia: intencja z URL dziala normalnie ─────────────────

describe('bez recznego klikniecia stosujemy intencje z URL', () => {

    test('?view=unread + filtr nieaktywny -> enable', () => {
        expect(decideUnreadFilterOverride({ urlFilter: 'on', isActive: false, userToggled: false })).toBe('enable');
    });

    test('?view=rooms + filtr aktywny -> disable (lista bez filtra)', () => {
        // ?view=rooms deklaratywnie prosi o liste pokoi bez filtra unread.
        expect(decideUnreadFilterOverride({ urlFilter: 'off', isActive: true, userToggled: false })).toBe('disable');
    });

    test('?view=unread + filtr juz aktywny -> none (nic do zrobienia)', () => {
        expect(decideUnreadFilterOverride({ urlFilter: 'on', isActive: true, userToggled: false })).toBe('none');
    });

    test('?view=rooms + filtr juz nieaktywny -> none', () => {
        expect(decideUnreadFilterOverride({ urlFilter: 'off', isActive: false, userToggled: false })).toBe('none');
    });

    test('brak intencji z URL (undefined) -> none', () => {
        expect(decideUnreadFilterOverride({ urlFilter: undefined, isActive: false, userToggled: false })).toBe('none');
        expect(decideUnreadFilterOverride({ urlFilter: undefined, isActive: true, userToggled: false })).toBe('none');
    });
});
