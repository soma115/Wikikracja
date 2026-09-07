/**
 * @jest-environment jsdom
 *
 * Testy parseChatLocation — czystego parsera zamieniajacego URL /chat/
 * na deklaratywna intencje widoku. Zastepuje dawny decideStartupAction:
 * router utrzymuje URL stabilny (bez stripParam), wiec parser czyta
 * zarowno query (?view=rooms / ?view=unread / ?unread=1) jak i hash
 * (#room_id=X / #room_id=X&message_id=Y).
 *
 * Kontrakt z chat.js (synchronizowac przy zmianie — funkcje kopiowane 1:1):
 *   - hash z room_id zawsze bije query params (uzytkownik prosi o pokoj)
 *   - ?view=rooms       — lista pokoi, brak auto-joina
 *   - ?view=unread      — lista pokoi z filtrem nieprzeczytanych
 *   - ?unread=1         — legacy alias ?view=unread (stare bookmarki/pushe)
 *   - brak parametrow   — view 'default' (przy starcie: auto-join)
 */

// ── wierne kopie z utility.js / chat.js (synchronizowac przy zmianie!) ────────

function parseParms(str) {
    let pieces = str.split("&"),
        data = {},
        i, parts;
    for (i = 0; i < pieces.length; i++) {
        parts = pieces[i].split("=");
        if (parts.length < 2) {
            parts.push("");
        }
        data[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
    }
    return data;
}

function parseChatLocation({ search = '', hash = '' } = {}) {
    const hashParams = parseParms(hash.startsWith('#') ? hash.slice(1) : hash);
    const roomId = hashParams.room_id ? parseInt(hashParams.room_id, 10) : null;
    const messageId = hashParams.message_id ? parseInt(hashParams.message_id, 10) : null;
    if (roomId) return { view: 'room', roomId, messageId };

    const params = new URLSearchParams(search.startsWith('?') ? search.slice(1) : search);
    const view = params.get('view');
    if (view === 'unread' || params.get('unread') === '1') {
        return { view: 'unread', roomId: null, messageId: null };
    }
    if (view === 'rooms') {
        return { view: 'rooms', roomId: null, messageId: null };
    }
    return { view: 'default', roomId: null, messageId: null };
}

// ── hash #room_id=X — priorytet nad query params ─────────────────────────────

describe('hash #room_id=X', () => {

    test('sam hash -> view room z roomId', () => {
        const route = parseChatLocation({ hash: '#room_id=42' });
        expect(route.view).toBe('room');
        expect(route.roomId).toBe(42);
        expect(route.messageId).toBeNull();
    });

    test('hash z message_id -> przekazuje oba', () => {
        const route = parseChatLocation({ hash: '#room_id=42&message_id=777' });
        expect(route.roomId).toBe(42);
        expect(route.messageId).toBe(777);
    });

    test('hash bije ?view=rooms', () => {
        const route = parseChatLocation({ search: '?view=rooms', hash: '#room_id=42' });
        expect(route.view).toBe('room');
    });

    test('hash bije ?view=unread', () => {
        const route = parseChatLocation({ search: '?view=unread', hash: '#room_id=42' });
        expect(route.view).toBe('room');
    });

    test('hash bez room_id (np. sam message_id) nie jest traktowany jak pokoj', () => {
        const route = parseChatLocation({ hash: '#message_id=777' });
        expect(route.view).toBe('default');
        expect(route.roomId).toBeNull();
    });
});

// ── ?view=rooms (sidebar) ────────────────────────────────────────────────────

describe('?view=rooms', () => {

    test('-> view rooms, bez pokoju', () => {
        const route = parseChatLocation({ search: '?view=rooms' });
        expect(route.view).toBe('rooms');
        expect(route.roomId).toBeNull();
    });

    test('?view=rooms bez wiodacego ? (bezposrednio "view=rooms")', () => {
        expect(parseChatLocation({ search: 'view=rooms' }).view).toBe('rooms');
    });

    test('parametr zostaje w URL — parser niczego nie usuwa', () => {
        // Router nie kasuje ?view: refresh ma odtwarzac ten sam widok.
        expect(parseChatLocation({ search: '?view=rooms' })).not.toHaveProperty('stripParam');
    });
});

// ── ?view=unread oraz ?unread=1 ───────────────────────────────────────────────

describe('?view=unread / ?unread=1', () => {

    test('?view=unread -> view unread', () => {
        expect(parseChatLocation({ search: '?view=unread' }).view).toBe('unread');
    });

    test('?unread=1 to legacy alias -> view unread', () => {
        expect(parseChatLocation({ search: '?unread=1' }).view).toBe('unread');
    });

    test('?unread=1 + inne params nadal dziala', () => {
        expect(parseChatLocation({ search: '?foo=bar&unread=1' }).view).toBe('unread');
    });
});

// ── brak parametrow / nieznane ────────────────────────────────────────────────

describe('domyslny widok', () => {

    test('czyste /chat/ -> default', () => {
        expect(parseChatLocation({}).view).toBe('default');
    });

    test('nieznany param ignorowany', () => {
        expect(parseChatLocation({ search: '?foo=bar' }).view).toBe('default');
    });

    test('nieznany view ignorowany', () => {
        expect(parseChatLocation({ search: '?view=whatever' }).view).toBe('default');
    });

    test('pusty hash nie zmienia widoku', () => {
        expect(parseChatLocation({ search: '?view=rooms', hash: '#' }).view).toBe('rooms');
    });
});
