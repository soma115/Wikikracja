/**
 * @jest-environment jsdom
 *
 * Testy modelu i sortowania listy pokoi (Etap H, CHAT_REWORK_PLAN §10).
 * Pokrywa:
 *   - komparator data-last-activity (newest/oldest, brak danych = 0),
 *   - widoczność linku (ukryte archiwum wyklucza z płaskiej listy),
 *   - model pozycji domowych: capture + deterministyczny restore po indeksie,
 *     niezależny od przypadkowego nextSibling,
 *   - pełny cykl applyRoomSort/resetRoomSort wraz z preferencją localStorage,
 *   - re-sort płaskiej listy po zmianie data-last-activity (updateRoomListForMessage).
 *
 * Kontrakt z chat.js (synchronizowac przy zmianie — funkcje kopiowane 1:1).
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── wierne kopie z chat.js (synchronizowac przy zmianie!) ──────────────────

function roomLinkSortKey(link) {
    return parseInt(link.dataset.lastActivity || '0', 10);
}

function roomLinkComparator(mode) {
    return (a, b) => mode === 'oldest'
        ? roomLinkSortKey(a) - roomLinkSortKey(b)
        : roomLinkSortKey(b) - roomLinkSortKey(a);
}

function isRoomListLinkVisible(link) {
    const archive = link.closest('.tw-archive-section');
    return !archive || archive.classList.contains('tw-visible');
}

function captureRoomHomes(links) {
    return new Map(links.map(link => [link, {
        parent: link.parentElement,
        index: Array.prototype.indexOf.call(link.parentElement.children, link),
    }]));
}

function restoreRoomHomes(homes) {
    const byParent = new Map();
    homes.forEach((pos, link) => {
        if (!byParent.has(pos.parent)) byParent.set(pos.parent, []);
        byParent.get(pos.parent).push([pos.index, link]);
    });
    byParent.forEach((entries, parent) => {
        entries.sort((a, b) => a[0] - b[0]);
        entries.forEach(([index, link]) => {
            parent.insertBefore(link, parent.children[index] || null);
        });
    });
}

let roomHomes = null;
let roomSortMode = null;
let flatListEl = null;

function applyRoomSort(mode) {
    const roomListEl = $('#room-list');
    const groups = roomListEl?.querySelector('.tw-room-list-groups');
    if (!roomListEl || !groups) return;

    if (!flatListEl) {
        const links = [...$$('.tw-room-link[data-room-id]')].filter(isRoomListLinkVisible);
        roomHomes = captureRoomHomes(links);
        flatListEl = document.createElement('div');
        flatListEl.id = 'room-list-flat';
        links.forEach(link => flatListEl.appendChild(link));
        groups.style.display = 'none';
        roomListEl.appendChild(flatListEl);
    }

    resortFlatRoomList(mode);

    const btn = $('#sort-activity-btn');
    btn?.classList.add('tw-active');
    const dirIcon = btn?.querySelector('.tw-sort-dir-icon');
    if (dirIcon) dirIcon.className = `tw-sort-dir-icon fas fa-arrow-${mode === 'oldest' ? 'up' : 'down'}`;
    localStorage.setItem('chat-sort-mode', mode);
}

function resetRoomSort() {
    if (!flatListEl || !roomHomes) return;

    restoreRoomHomes(roomHomes);
    flatListEl.remove();
    flatListEl = null;
    roomHomes = null;
    roomSortMode = null;

    const groups = $('#room-list')?.querySelector('.tw-room-list-groups');
    if (groups) groups.style.display = '';

    const btn = $('#sort-activity-btn');
    btn?.classList.remove('tw-active');
    const dirIcon = btn?.querySelector('.tw-sort-dir-icon');
    if (dirIcon) dirIcon.className = 'tw-sort-dir-icon fas fa-arrow-down';
    localStorage.removeItem('chat-sort-mode');
}

function resortFlatRoomList(mode = roomSortMode) {
    if (!flatListEl || !mode) return;
    roomSortMode = mode;
    [...flatListEl.querySelectorAll('.tw-room-link[data-room-id]')]
        .sort(roomLinkComparator(mode))
        .forEach(link => flatListEl.appendChild(link));
}

// ── pomocnicze ──────────────────────────────────────────────────────────────

function roomLink(id, lastActivity) {
    const el = document.createElement('a');
    el.className = 'tw-room-link';
    el.dataset.roomId = String(id);
    if (lastActivity !== undefined) el.dataset.lastActivity = String(lastActivity);
    return el;
}

/** DOM z dwiema kategoriami + sekcją archiwum, wzorowany na chat.html. */
function buildRoomListDom() {
    document.body.innerHTML = `
      <button id="sort-activity-btn"><i class="tw-sort-dir-icon fas fa-arrow-down"></i></button>
      <div id="room-list">
        <div class="tw-room-list-groups">
          <div class="tw-chat-cat-content" id="cat-a"></div>
          <div class="tw-chat-cat-content" id="cat-b"></div>
          <div class="tw-archive-section" id="archive"></div>
        </div>
      </div>`;
    return {
        catA: document.getElementById('cat-a'),
        catB: document.getElementById('cat-b'),
        archive: document.getElementById('archive'),
    };
}

function flatOrder() {
    return [...flatListEl.querySelectorAll('.tw-room-link')]
        .map(l => l.dataset.roomId);
}

beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
    roomHomes = null;
    roomSortMode = null;
    flatListEl = null;
});

// ── komparator ──────────────────────────────────────────────────────────────

describe('roomLinkComparator', () => {
    test('newest: malejąco po data-last-activity', () => {
        const rooms = [roomLink(1, 100), roomLink(2, 300), roomLink(3, 200)];
        rooms.sort(roomLinkComparator('newest'));
        expect(rooms.map(r => r.dataset.roomId)).toEqual(['2', '3', '1']);
    });

    test('oldest: rosnąco po data-last-activity', () => {
        const rooms = [roomLink(1, 300), roomLink(2, 100), roomLink(3, 200)];
        rooms.sort(roomLinkComparator('oldest'));
        expect(rooms.map(r => r.dataset.roomId)).toEqual(['2', '3', '1']);
    });

    test('brak data-last-activity traktowany jako 0', () => {
        const rooms = [roomLink(1), roomLink(2, 50)];
        rooms.sort(roomLinkComparator('newest'));
        expect(rooms.map(r => r.dataset.roomId)).toEqual(['2', '1']);
    });
});

// ── widoczność ──────────────────────────────────────────────────────────────

describe('isRoomListLinkVisible', () => {
    test('pokój poza archiwum jest widoczny', () => {
        const { catA } = buildRoomListDom();
        const link = roomLink(1, 10);
        catA.appendChild(link);
        expect(isRoomListLinkVisible(link)).toBe(true);
    });

    test('pokój w ukrytym archiwum jest pomijany', () => {
        const { archive } = buildRoomListDom();
        const link = roomLink(1, 10);
        archive.appendChild(link);
        expect(isRoomListLinkVisible(link)).toBe(false);
    });

    test('pokój w rozwiniętym archiwum jest widoczny', () => {
        const { archive } = buildRoomListDom();
        archive.classList.add('tw-visible');
        const link = roomLink(1, 10);
        archive.appendChild(link);
        expect(isRoomListLinkVisible(link)).toBe(true);
    });
});

// ── model pozycji domowych ──────────────────────────────────────────────────

describe('captureRoomHomes + restoreRoomHomes', () => {
    test('restore odtwarza oryginalną kolejność w różnych rodzicach', () => {
        const { catA, catB } = buildRoomListDom();
        const r1 = roomLink(1, 10), r2 = roomLink(2, 20), r3 = roomLink(3, 30);
        const spacer = document.createElement('p'); // nie-room rodzeństwo
        catA.append(r1, spacer, r2);
        catB.appendChild(r3);

        const homes = captureRoomHomes([r1, r2, r3]);
        // spłaszczenie — wszystkie trafiają do jednego kontenera
        const flat = document.createElement('div');
        [r1, r2, r3].forEach(r => flat.appendChild(r));

        restoreRoomHomes(homes);

        expect([...catA.children]).toEqual([r1, spacer, r2]);
        expect([...catB.children]).toEqual([r3]);
    });

    test('restore jest odporny na zmianę rodzeństwa w międzyczasie', () => {
        const { catA } = buildRoomListDom();
        const r1 = roomLink(1, 10), r2 = roomLink(2, 20);
        catA.append(r1, r2);

        const homes = captureRoomHomes([r1, r2]);
        const flat = document.createElement('div');
        [r2, r1].forEach(r => flat.appendChild(r));

        // w międzyczasie ktoś dodał element na początku rodzica
        catA.prepend(document.createElement('div'));

        restoreRoomHomes(homes);

        // pokoje lądują na swoich pozycjach modelu — względem siebie zachowują kolejność
        expect(catA.children[0].classList.contains('tw-room-link')).toBe(true);
        expect([...catA.querySelectorAll('.tw-room-link')]).toEqual([r1, r2]);
    });
});

// ── pełny cykl sort/reset ───────────────────────────────────────────────────

describe('applyRoomSort / resetRoomSort', () => {
    test('spłaszcza widoczne pokoje, sortuje i ukrywa drzewo kategorii', () => {
        const { catA, catB, archive } = buildRoomListDom();
        const r1 = roomLink(1, 100), r2 = roomLink(2, 300), r3 = roomLink(3, 200);
        const archived = roomLink(9, 999);
        catA.append(r1, r2);
        catB.appendChild(r3);
        archive.appendChild(archived);

        applyRoomSort('newest');

        expect(flatOrder()).toEqual(['2', '3', '1']); // archiwum pominięte
        expect($('#room-list .tw-room-list-groups').style.display).toBe('none');
        expect($('#sort-activity-btn').classList.contains('tw-active')).toBe(true);
        expect(localStorage.getItem('chat-sort-mode')).toBe('newest');
    });

    test('przełączenie trybu nie buduje drugiego kontenera', () => {
        const { catA, catB } = buildRoomListDom();
        catA.append(roomLink(1, 100), roomLink(2, 300));
        catB.appendChild(roomLink(3, 200));

        applyRoomSort('newest');
        const firstFlat = flatListEl;
        applyRoomSort('oldest');

        expect(flatListEl).toBe(firstFlat);
        expect(flatOrder()).toEqual(['1', '3', '2']);
        expect($('#sort-activity-btn .tw-sort-dir-icon').className).toContain('fa-arrow-up');
        expect(localStorage.getItem('chat-sort-mode')).toBe('oldest');
    });

    test('reset przywraca kategorie i sprząta stan', () => {
        const { catA, catB } = buildRoomListDom();
        const r1 = roomLink(1, 100), r2 = roomLink(2, 300), r3 = roomLink(3, 200);
        catA.append(r1, r2);
        catB.appendChild(r3);

        applyRoomSort('newest');
        resetRoomSort();

        expect($('#room-list-flat')).toBeNull();
        expect([...catA.children]).toEqual([r1, r2]);
        expect([...catB.children]).toEqual([r3]);
        expect($('#room-list .tw-room-list-groups').style.display).toBe('');
        expect($('#sort-activity-btn').classList.contains('tw-active')).toBe(false);
        expect(localStorage.getItem('chat-sort-mode')).toBeNull();
        expect(roomSortMode).toBeNull();
    });

    test('reset bez aktywnego sortu jest no-op', () => {
        buildRoomListDom();
        expect(() => resetRoomSort()).not.toThrow();
        expect($('#room-list-flat')).toBeNull();
    });
});

// ── aktualizacja modelu po wiadomości (10.5) ────────────────────────────────

describe('resortFlatRoomList po zmianie last-activity', () => {
    test('nowa aktywność przesuwa pokój zgodnie z bieżącym trybem', () => {
        const { catA } = buildRoomListDom();
        const r1 = roomLink(1, 100), r2 = roomLink(2, 200), r3 = roomLink(3, 300);
        catA.append(r1, r2, r3);

        applyRoomSort('oldest'); // [r1, r2, r3]
        // symulacja updateSidebarForMessage: pokój 1 dostał nową wiadomość
        r1.dataset.lastActivity = '400';
        resortFlatRoomList();

        expect(flatOrder()).toEqual(['2', '3', '1']); // oldest: r1 spada na koniec
    });

    test('bez aktywnego sortu jest no-op', () => {
        expect(() => resortFlatRoomList()).not.toThrow();
    });
});
