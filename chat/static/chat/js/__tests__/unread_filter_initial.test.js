/**
 * @jest-environment jsdom
 *
 * Testy inicjalizacji filtra nieprzeczytanych pokoi przy wejściu na czat:
 *   - jeśli nie ma nieprzeczytanych pokoi, filtr wyłącza się automatycznie
 *     (niezależnie od localStorage/URL),
 *   - gdy filtr jest aktywny, kategorie i archiwa z nieprzeczytanymi
 *     pokojami rozwijają się automatycznie.
 *
 * Kontrakt z chat.js (synchronizować przy zmianie — funkcje kopiowane 1:1).
 */

// ── minimalne stub'y ─────────────────────────────────────────────────────────

const $ = (selector, context = document) => context.querySelector(selector);
const $$ = (selector, context = document) => [...context.querySelectorAll(selector)];
const _ = (s) => s;

let isUnreadFilterActive = false;
let userToggledFilter = false;
let rafOriginal;

// ── wierne kopie z chat.js (synchronizować przy zmianie!) ───────────────────

function showUnreadEmptyState() {
    const roomList = document.querySelector('#room-list');
    if (!roomList || document.getElementById('chat-no-unread-empty-state')) return;

    const div = document.createElement('div');
    div.id = 'chat-no-unread-empty-state';
    div.className = 'tw-chat-no-unread-empty-state';

    const iconBig = document.createElement('i');
    iconBig.className = 'fas fa-envelope-open tw-chat-no-unread-icon';
    iconBig.setAttribute('aria-hidden', 'true');

    const title = document.createElement('p');
    title.className = 'tw-chat-no-unread-title';
    title.textContent = _('No unread messages');

    const hint = document.createElement('p');
    hint.className = 'tw-chat-no-unread-hint';
    const [before, after = ''] = _('Tap {icon} above the list to disable the unread filter').split('{icon}');
    hint.appendChild(document.createTextNode(before));
    const inlineBtn = document.createElement('button');
    inlineBtn.type = 'button';
    inlineBtn.className = 'tw-chat-no-unread-inline-btn';
    inlineBtn.setAttribute('aria-label', _('Disable the unread filter'));
    const inlineIcon = document.createElement('i');
    inlineIcon.className = 'fas fa-eye-slash';
    inlineIcon.setAttribute('aria-hidden', 'true');
    inlineBtn.appendChild(inlineIcon);
    inlineBtn.addEventListener('click', () => {
        document.getElementById('unread-filter-btn')?.click();
    });
    hint.appendChild(inlineBtn);
    hint.appendChild(document.createTextNode(after));

    div.append(iconBig, title, hint);
    roomList.appendChild(div);
}

function hideUnreadEmptyState() {
    document.getElementById('chat-no-unread-empty-state')?.remove();
}

/** Zwraca linki pokoi z nieprzeczytanymi wiadomościami — źródło prawdy dla filtra. */
function getUnreadRoomLinks() {
    return $$('.tw-room-link.tw-room-link--not-seen[data-room-id]');
}

function applyUnreadFilter() {
    const allRoomLinks = $$('.tw-room-link[data-room-id]');
    allRoomLinks.forEach(roomLink => {
        if (!roomLink.classList.contains('tw-room-link--not-seen')) {
            roomLink.classList.add('tw-room-link--filtered-out');
        } else {
            roomLink.classList.remove('tw-room-link--filtered-out');
        }
    });
    const unreadCount = getUnreadRoomLinks().length;
    if (unreadCount === 0) {
        showUnreadEmptyState();
    } else {
        hideUnreadEmptyState();
        expandCategoriesForUnreadRooms();
        scheduleExpandCategoriesForUnreadRooms();
    }
}

function removeUnreadFilter() {
    const allRoomLinks = $$('.tw-room-link[data-room-id]');
    allRoomLinks.forEach(roomLink => {
        roomLink.classList.remove('tw-room-link--filtered-out');
    });
    hideUnreadEmptyState();
}

function scheduleExpandCategoriesForUnreadRooms() {
    if (typeof requestAnimationFrame === 'function') {
        requestAnimationFrame(expandCategoriesForUnreadRooms);
    } else {
        expandCategoriesForUnreadRooms();
    }
}

function expandCategoriesForUnreadRooms() {
    const unreadLinks = getUnreadRoomLinks();
    for (const roomLink of unreadLinks) {
        const navCatContent = roomLink.closest('.tw-chat-cat-content');
        if (navCatContent && !navCatContent.classList.contains('tw-open')) {
            navCatContent.classList.add('tw-open');
            const catId = navCatContent.id;
            const catBtn = catId ? document.querySelector(`[data-cat-content="${catId}"]`) : null;
            if (catBtn) catBtn.setAttribute('aria-expanded', 'true');
        }

        const archiveSection = roomLink.closest('.tw-archive-section');
        if (archiveSection) {
            archiveSection.classList.add('tw-visible');
        }
    }
}

function setUnreadFilter(wantedActive) {
    const unreadCount = getUnreadRoomLinks().length;
    const active = wantedActive && (unreadCount > 0 || userToggledFilter);
    isUnreadFilterActive = active;
    document.getElementById('unread-filter-btn')?.classList.toggle('tw-active', active);
    if (active) {
        localStorage.setItem('chat-unread-filter', 'active');
        applyUnreadFilter();
    } else {
        localStorage.removeItem('chat-unread-filter');
        removeUnreadFilter();
    }
}

// ── helpers testowe ──────────────────────────────────────────────────────────

function resetState() {
    isUnreadFilterActive = false;
    userToggledFilter = false;
    document.body.innerHTML = '';
    localStorage.clear();
}

function makeRoomLink({ id, unread = false, archived = false } = {}) {
    const div = document.createElement('div');
    div.className = 'tw-room-link' + (unread ? ' tw-room-link--not-seen' : '');
    div.dataset.roomId = String(id);
    div.dataset.roomArchived = String(archived);
    return div;
}

function makeCategory({ id, open = false, withArchive = false } = {}) {
    const cat = document.createElement('div');
    cat.className = 'tw-chat-category';
    cat.innerHTML = `
        <div class="tw-chat-cat-header">
            <button class="tw-chat-cat-btn" data-cat-content="${id}" aria-expanded="${open ? 'true' : 'false'}"></button>
        </div>
        <div class="tw-chat-cat-content${open ? ' tw-open' : ''}" id="${id}"></div>
    `;
    const content = cat.querySelector('.tw-chat-cat-content');
    if (withArchive) {
        const archive = document.createElement('div');
        archive.className = 'tw-archive-section';
        archive.id = `${id}-archive`;
        content.appendChild(archive);
    }
    return cat;
}

function getCategoryContent(id) {
    return document.getElementById(id);
}

function getCategoryButton(id) {
    return document.querySelector(`[data-cat-content="${id}"]`);
}

// ── setup ────────────────────────────────────────────────────────────────────

beforeEach(() => {
    rafOriginal = global.requestAnimationFrame;
    global.requestAnimationFrame = (cb) => cb();
    resetState();
});
afterEach(() => {
    resetState();
    global.requestAnimationFrame = rafOriginal;
});

// ── Auto-wyłączenie filtra przy braku nieprzeczytanych ───────────────────────

describe('setUnreadFilter — auto-wyłączenie przy braku nieprzeczytanych', () => {

    test('przywrócony filtr z localStorage wyłącza się, gdy nie ma nieprzeczytanych', () => {
        localStorage.setItem('chat-unread-filter', 'active');
        document.body.innerHTML = `
            <button id="unread-filter-btn" class="tw-active"></button>
            <div id="room-list">
                <div class="tw-room-list-groups">
                    <div class="tw-room-link" data-room-id="1"></div>
                    <div class="tw-room-link" data-room-id="2"></div>
                </div>
            </div>
        `;

        setUnreadFilter(true);

        expect(isUnreadFilterActive).toBe(false);
        expect(document.getElementById('unread-filter-btn').classList.contains('tw-active')).toBe(false);
        expect(localStorage.getItem('chat-unread-filter')).toBeNull();
        expect($$('.tw-room-link--filtered-out').length).toBe(0);
        expect(document.getElementById('chat-no-unread-empty-state')).toBeNull();
    });

    test('wejście z ?view=unread bez nieprzeczytanych nie włącza pustego filtra', () => {
        document.body.innerHTML = `
            <button id="unread-filter-btn"></button>
            <div id="room-list">
                <div class="tw-room-list-groups">
                    <div class="tw-room-link" data-room-id="1"></div>
                </div>
            </div>
        `;

        setUnreadFilter(true);

        expect(isUnreadFilterActive).toBe(false);
        expect(document.getElementById('unread-filter-btn').classList.contains('tw-active')).toBe(false);
        expect(document.getElementById('chat-no-unread-empty-state')).toBeNull();
    });

    test('ręczne włączenie filtra przy braku nieprzeczytanych zostawia pusty stan', () => {
        document.body.innerHTML = `
            <button id="unread-filter-btn"></button>
            <div id="room-list"><div class="tw-room-list-groups"></div></div>
        `;
        userToggledFilter = true;

        setUnreadFilter(true);

        expect(isUnreadFilterActive).toBe(true);
        expect(document.getElementById('unread-filter-btn').classList.contains('tw-active')).toBe(true);
        expect(document.getElementById('chat-no-unread-empty-state')).not.toBeNull();
        expect(localStorage.getItem('chat-unread-filter')).toBe('active');
    });
});

// ── Auto-rozwinięcie kategorii z nieprzeczytanymi pokojami ───────────────────

describe('setUnreadFilter — auto-rozwinięcie kategorii', () => {

    test('rozwija kategorię zawierającą nieprzeczytany pokój, pozostawia pozostałe', () => {
        const catA = makeCategory({ id: 'cat-a', open: false });
        const catB = makeCategory({ id: 'cat-b', open: false });

        const unreadLink = makeRoomLink({ id: 1, unread: true });
        catA.querySelector('.tw-chat-cat-content').appendChild(unreadLink);

        const readLink = makeRoomLink({ id: 2 });
        catB.querySelector('.tw-chat-cat-content').appendChild(readLink);

        const roomList = document.createElement('div');
        roomList.id = 'room-list';
        const groups = document.createElement('div');
        groups.className = 'tw-room-list-groups';
        groups.append(catA, catB);
        roomList.appendChild(groups);

        document.body.innerHTML = '<button id="unread-filter-btn"></button>';
        document.body.appendChild(roomList);

        setUnreadFilter(true);

        expect(isUnreadFilterActive).toBe(true);
        expect(getCategoryContent('cat-a').classList.contains('tw-open')).toBe(true);
        expect(getCategoryButton('cat-a').getAttribute('aria-expanded')).toBe('true');
        expect(getCategoryContent('cat-b').classList.contains('tw-open')).toBe(false);

        // Nieprzeczytany widoczny, przeczytany schowany
        expect(unreadLink.classList.contains('tw-room-link--filtered-out')).toBe(false);
        expect(readLink.classList.contains('tw-room-link--filtered-out')).toBe(true);
    });

    test('rozwija archiwum zawierające nieprzeczytany pokój', () => {
        const cat = makeCategory({ id: 'cat-archive', open: false, withArchive: true });
        const archive = cat.querySelector('.tw-archive-section');
        const unreadArchived = makeRoomLink({ id: 7, unread: true, archived: true });
        archive.appendChild(unreadArchived);

        const roomList = document.createElement('div');
        roomList.id = 'room-list';
        const groups = document.createElement('div');
        groups.className = 'tw-room-list-groups';
        groups.appendChild(cat);
        roomList.appendChild(groups);

        document.body.innerHTML = '<button id="unread-filter-btn"></button>';
        document.body.appendChild(roomList);

        setUnreadFilter(true);

        expect(archive.classList.contains('tw-visible')).toBe(true);
        expect(getCategoryContent('cat-archive').classList.contains('tw-open')).toBe(true);
    });

    test('nie modyfikuje localStorage kategorii przy rozwinięciu', () => {
        const cat = makeCategory({ id: 'cat-no-persist', open: false });
        const unread = makeRoomLink({ id: 9, unread: true });
        cat.querySelector('.tw-chat-cat-content').appendChild(unread);

        const roomList = document.createElement('div');
        roomList.id = 'room-list';
        const groups = document.createElement('div');
        groups.className = 'tw-room-list-groups';
        groups.appendChild(cat);
        roomList.appendChild(groups);

        document.body.innerHTML = '<button id="unread-filter-btn"></button>';
        document.body.appendChild(roomList);

        setUnreadFilter(true);

        expect(localStorage.getItem('chat-cat-cat-no-persist')).toBeNull();
    });
});

// ── applyUnreadFilter reaktywnie rozwija kategorie ───────────────────────────

describe('applyUnreadFilter — reaktywne rozwijanie kategorii', () => {

    test('po pojawieniu się nowego nieprzeczytanego pokoju kategoria się rozwija', () => {
        const cat = makeCategory({ id: 'cat-live', open: false });
        const content = cat.querySelector('.tw-chat-cat-content');

        const roomList = document.createElement('div');
        roomList.id = 'room-list';
        const groups = document.createElement('div');
        groups.className = 'tw-room-list-groups';
        groups.appendChild(cat);
        roomList.appendChild(groups);

        document.body.innerHTML = '<button id="unread-filter-btn" class="tw-active"></button>';
        document.body.appendChild(roomList);

        isUnreadFilterActive = true;

        // symulacja nowej wiadomości — link staje się nieprzeczytany
        const newLink = makeRoomLink({ id: 5, unread: true });
        content.appendChild(newLink);

        applyUnreadFilter();

        expect(getCategoryContent('cat-live').classList.contains('tw-open')).toBe(true);
        expect(getCategoryButton('cat-live').getAttribute('aria-expanded')).toBe('true');
    });
});
