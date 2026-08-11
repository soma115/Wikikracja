/**
 * @jest-environment jsdom
 *
 * Testy updateSidebarForMessage — aktualizacja podgladu pokoju w sidebarze.
 * Pokrywa regresje #4: edycja ostatniej wiadomosci nie odswiezala preview.
 *
 * Testowane zachowania:
 *   - reorder=true (default): aktualizuje pola + przesuwa pokoj na gore listy
 *   - reorder=false: aktualizuje pola, NIE przesuwa (uzywane przy edycji — nie jest to nowa aktywnosc)
 *
 * Kontrakt z domapi.js (synchronizowac przy zmianie — funkcja kopiowana 1:1).
 */

// ── stub i18n ──────────────────────────────────────────────────────────────
const _ = (key) => key;

function _relativeChatDate(ts) { return 'today'; }

// ── wierna kopia z domapi.js (synchronizowac przy zmianie!) ───────────────
function updateSidebarForMessage(msg, {reorder = true, bumpActivity = reorder} = {}) {
    const roomLink = document.querySelector(`.room-link[data-room-id="${msg.room_id}"]`);
    if (!roomLink) return;

    // Pull the room out of archive as soon as a new message arrives.
    // `new` is true for other users; for the sender `new` is false and `own` is true.
    if ((msg.new || msg.own) && roomLink.dataset.roomArchived === 'true') {
        roomLink.dataset.roomArchived = 'false';
        if (msg.own) {
            roomLink.classList.remove('room-not-seen');
        } else {
            roomLink.classList.add('room-not-seen');
        }
        const statusEl = roomLink.querySelector('.room-link__status');
        if (statusEl) {
            if (msg.own) {
                statusEl.innerHTML = '<span class="nav-status nav-status--read" aria-hidden="true"></span>';
            } else {
                statusEl.innerHTML = '<span class="nav-status nav-status--unread" aria-label="' + _('Unread') + '"></span>';
            }
        }
    }

    if (bumpActivity) {
        roomLink.dataset.lastActivity = Math.floor(msg.timestamp / 1000);
        const dateEl = roomLink.querySelector('.room-link__date');
        if (dateEl) dateEl.textContent = _relativeChatDate(msg.timestamp);
    }

    const senderEl = roomLink.querySelector('.room-link__sender');
    if (senderEl) senderEl.textContent = (msg.username || '—') + ':';

    const snippetEl = roomLink.querySelector('.room-link__snippet');
    if (snippetEl) {
        const tmp = document.createElement('div');
        tmp.innerHTML = msg.message || '';
        const text = tmp.textContent.replace(/\s+/g, ' ').trim();
        snippetEl.textContent = text || _('attachment');
    }

    if (reorder) {
        const container = roomLink.closest('.nav-cat-content, #room-list-flat');
        if (container && container.firstElementChild !== roomLink) {
            container.prepend(roomLink);
        }
    }
}

// ── helpers ────────────────────────────────────────────────────────────────
function makeRoomLink(roomId, snippetText = 'old text', archived = false) {
    const div = document.createElement('div');
    div.className = 'room-link';
    div.dataset.roomId = String(roomId);
    div.dataset.roomArchived = archived ? 'true' : 'false';
    const statusIcon = archived
        ? '<i class="fas fa-lock nav-status nav-status--locked" aria-hidden="true"></i>'
        : '<span class="nav-status nav-status--read" aria-hidden="true"></span>';
    div.innerHTML = `
        <div class="room-link__status">${statusIcon}</div>
        <span class="room-link__date">yesterday</span>
        <span class="room-link__sender">Alice:</span>
        <span class="room-link__snippet">${snippetText}</span>
    `;
    return div;
}

function makeMsg(roomId, text = 'new text', {new: isNew = true, own = false, username = 'Bob'} = {}) {
    return { room_id: roomId, username, message: text, timestamp: Date.now(), new: isNew, own };
}

// ── testy ──────────────────────────────────────────────────────────────────
describe('updateSidebarForMessage', () => {
    let container;

    beforeEach(() => {
        document.body.innerHTML = '<div id="room-list-flat"></div>';
        container = document.getElementById('room-list-flat');
    });

    test('aktualizuje snippet i sender', () => {
        container.appendChild(makeRoomLink(1));
        updateSidebarForMessage(makeMsg(1, 'zaktualizowana tresc'));
        expect(container.querySelector('.room-link__snippet').textContent).toBe('zaktualizowana tresc');
        expect(container.querySelector('.room-link__sender').textContent).toBe('Bob:');
    });

    test('reorder=true (default): przesuwa pokoj na gore listy', () => {
        const first = makeRoomLink(1, 'room 1');
        const second = makeRoomLink(2, 'room 2');
        container.appendChild(first);
        container.appendChild(second);

        // Drugi pokoj dostaje nowa wiadomosc → powinien wskoczyc na gore
        updateSidebarForMessage(makeMsg(2));

        expect(container.firstElementChild.dataset.roomId).toBe('2');
    });

    test('reorder=false: aktualizuje snippet ale NIE przesuwa pokoju', () => {
        const first = makeRoomLink(1, 'room 1');
        const second = makeRoomLink(2, 'room 2');
        container.appendChild(first);
        container.appendChild(second);

        // Edycja ostatniej wiadomosci w drugim pokoju — nie jest to nowa aktywnosc
        updateSidebarForMessage(makeMsg(2, 'edytowana tresc'), {reorder: false});

        // Kolejnosc bez zmian — room 1 nadal pierwszy
        expect(container.firstElementChild.dataset.roomId).toBe('1');
        // Ale snippet zaktualizowany
        expect(container.children[1].querySelector('.room-link__snippet').textContent).toBe('edytowana tresc');
    });

    test('reorder=false nie aktualizuje daty ani dataset.lastActivity', () => {
        const link = makeRoomLink(1);
        link.dataset.lastActivity = '1000';
        link.querySelector('.room-link__date').textContent = 'yesterday';
        container.appendChild(link);

        const msg = makeMsg(1, 'nowy tekst');
        msg.timestamp = Date.now() + 999999;   // wyraznie pozniejszy niz 1000
        updateSidebarForMessage(msg, {reorder: false});

        // dataset.lastActivity i data NIE powinny sie zmienic
        expect(link.dataset.lastActivity).toBe('1000');
        expect(link.querySelector('.room-link__date').textContent).toBe('yesterday');
        // snippet nadal zaktualizowany
        expect(link.querySelector('.room-link__snippet').textContent).toBe('nowy tekst');
    });

    test('brak rooma w DOM: nie rzuca', () => {
        expect(() => updateSidebarForMessage(makeMsg(999))).not.toThrow();
    });

    test('zarchiwizowany pokój wraca do aktywnych po nowej wiadomości', () => {
        document.body.innerHTML = `
            <div class="nav-cat-content" id="cat-public">
                <p class="text-muted text-center small">None</p>
                <div class="archive-section visible" id="content-pub-rooms-archive"></div>
            </div>
        `;
        const cat = document.getElementById('cat-public');
        const archive = document.getElementById('content-pub-rooms-archive');
        const room = makeRoomLink(1, 'old text', true);
        archive.appendChild(room);

        updateSidebarForMessage(makeMsg(1, 'nowy tekst', { new: true, own: false }));

        expect(room.dataset.roomArchived).toBe('false');
        expect(room.closest('.archive-section')).toBeNull();
        expect(cat.firstElementChild).toBe(room);
        expect(room.querySelector('.nav-status--unread')).not.toBeNull();
        expect(room.classList.contains('room-not-seen')).toBe(true);
    });

    test('nowa własna wiadomość w archiwum pokazuje ikonę przeczytanej', () => {
        document.body.innerHTML = `
            <div class="nav-cat-content" id="cat-public">
                <div class="archive-section visible" id="content-pub-rooms-archive"></div>
            </div>
        `;
        const archive = document.getElementById('content-pub-rooms-archive');
        const room = makeRoomLink(2, 'old text', true);
        archive.appendChild(room);

        // Serwer dla nadawcy ustawia new=false, own=true.
        updateSidebarForMessage(makeMsg(2, 'nowy tekst', { new: false, own: true }));

        expect(room.dataset.roomArchived).toBe('false');
        expect(room.querySelector('.nav-status--read')).not.toBeNull();
        expect(room.classList.contains('room-not-seen')).toBe(false);
    });

    test('edycja nie wyjmuje pokoju z archiwum', () => {
        document.body.innerHTML = `
            <div class="nav-cat-content" id="cat-public">
                <div class="archive-section visible" id="content-pub-rooms-archive"></div>
            </div>
        `;
        const archive = document.getElementById('content-pub-rooms-archive');
        const room = makeRoomLink(3, 'old text', true);
        archive.appendChild(room);

        updateSidebarForMessage(makeMsg(3, 'edytowana tresc', { new: false }), { reorder: false });

        expect(room.dataset.roomArchived).toBe('true');
        expect(room.closest('.archive-section')).toBe(archive);
        expect(room.querySelector('.nav-status--locked')).not.toBeNull();
    });
});
