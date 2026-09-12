/**
 * @jest-environment jsdom
 *
 * Testy początkowego stanu zwijania/rozwijania kategorii czatu
 * (implementacja w chat/static/chat/js/handlers.js).
 *
 * Kontrakt z handlers.js (synchronizować przy zmianie — funkcje kopiowane 1:1).
 */

// ── wierne kopie z handlers.js (synchronizować przy zmianie!) ───────────────

function categoryHasUnreadRoom(content) {
    return !!content.querySelector('.tw-room-link.tw-room-link--not-seen');
}

function closeOtherCategories(content) {
    document.querySelectorAll('.tw-chat-cat-content').forEach(otherContent => {
        if (otherContent === content) return;
        otherContent.classList.remove('tw-open');
        const otherBtn = document.querySelector(`[data-cat-content="${otherContent.id}"]`);
        otherBtn?.setAttribute('aria-expanded', 'false');
    });
}

let globalArchiveBtn;

function toggleCategory(btn, content) {
    const isOpen = content.classList.contains('tw-open');
    if (!isOpen && !globalArchiveBtn?.classList.contains('tw-active')) {
        closeOtherCategories(content);
    }
    content.classList.toggle('tw-open', !isOpen);
    btn.setAttribute('aria-expanded', String(!isOpen));
}

function applyInitialCategoryState(btn, content) {
    const contentId = btn.dataset.catContent;
    if (!contentId || !content) return;

    const savedState = localStorage.getItem(`chat-cat-${contentId}`);
    let isOpen;
    if (savedState === 'expanded') {
        isOpen = true;
    } else if (savedState === 'collapsed') {
        isOpen = false;
    } else {
        isOpen = categoryHasUnreadRoom(content);
    }

    if (isOpen) closeOtherCategories(content);
    content.classList.toggle('tw-open', isOpen);
    btn.setAttribute('aria-expanded', String(isOpen));

    if (!savedState && isOpen) {
        content.querySelectorAll('.tw-archive-section').forEach(archive => {
            if (archive.querySelector('.tw-room-link.tw-room-link--not-seen')) {
                archive.classList.add('tw-visible');
            }
        });
    }
}

function expandCategoriesWithArchivedRooms() {
    document.querySelectorAll('.tw-chat-cat-content').forEach(content => {
        if (!content.querySelector('.tw-archive-section .tw-room-link')) return;
        content.classList.add('tw-open');
        const catBtn = document.querySelector(`[data-cat-content="${content.id}"]`);
        catBtn?.setAttribute('aria-expanded', 'true');
    });
}

// ── helpers testowe ──────────────────────────────────────────────────────────

beforeEach(() => {
    document.body.innerHTML = '';
    globalArchiveBtn = null;
    localStorage.clear();
});

function makeRoomLink({ id, unread = false, archived = false } = {}) {
    const div = document.createElement('div');
    div.className = 'tw-room-link' + (unread ? ' tw-room-link--not-seen' : '');
    div.dataset.roomId = String(id);
    div.dataset.roomArchived = String(archived);
    return div;
}

function makeCategory({ id, withArchive = false } = {}) {
    const cat = document.createElement('div');
    cat.className = 'tw-chat-category';
    cat.innerHTML = `
        <div class="tw-chat-cat-header">
            <button class="tw-chat-cat-btn" data-cat-content="${id}" aria-expanded="true"></button>
        </div>
        <div class="tw-chat-cat-content tw-open" id="${id}"></div>
    `;
    const content = cat.querySelector('.tw-chat-cat-content');
    if (withArchive) {
        const archive = document.createElement('div');
        archive.className = 'tw-archive-section';
        archive.id = `${id}-archive`;
        content.appendChild(archive);
    }
    return { cat, content, btn: cat.querySelector('.tw-chat-cat-btn') };
}

// ── domyślny stan na podstawie nieprzeczytanych ──────────────────────────────

describe('expandCategoriesWithArchivedRooms', () => {
    test('rozwija wszystkie działy zawierające zarchiwizowane pokoje', () => {
        const withArchivedRooms = makeCategory({ id: 'cat-archived' });
        const withoutArchivedRooms = makeCategory({ id: 'cat-empty' });
        withoutArchivedRooms.content.classList.remove('tw-open');
        withoutArchivedRooms.btn.setAttribute('aria-expanded', 'false');
        const archive = document.createElement('div');
        archive.className = 'tw-archive-section';
        archive.appendChild(makeRoomLink({ id: 1, archived: true }));
        withArchivedRooms.content.appendChild(archive);
        document.body.append(withArchivedRooms.cat, withoutArchivedRooms.cat);

        expandCategoriesWithArchivedRooms();

        expect(withArchivedRooms.content.classList.contains('tw-open')).toBe(true);
        expect(withArchivedRooms.btn.getAttribute('aria-expanded')).toBe('true');
        expect(withoutArchivedRooms.content.classList.contains('tw-open')).toBe(false);
        expect(withoutArchivedRooms.btn.getAttribute('aria-expanded')).toBe('false');
    });
});

describe('toggleCategory', () => {
    test('po włączeniu archiwum pozwala otworzyć wiele działów', () => {
        const first = makeCategory({ id: 'cat-first' });
        const second = makeCategory({ id: 'cat-second' });
        first.content.classList.remove('tw-open');
        first.btn.setAttribute('aria-expanded', 'false');
        second.content.classList.remove('tw-open');
        second.btn.setAttribute('aria-expanded', 'false');
        globalArchiveBtn = document.createElement('button');
        globalArchiveBtn.classList.add('tw-active');
        document.body.append(first.cat, second.cat, globalArchiveBtn);

        toggleCategory(first.btn, first.content);
        toggleCategory(second.btn, second.content);

        expect(first.content.classList.contains('tw-open')).toBe(true);
        expect(second.content.classList.contains('tw-open')).toBe(true);
    });

    test('po wyłączeniu archiwum zachowuje wyłączność otwartego działu', () => {
        const first = makeCategory({ id: 'cat-first' });
        const second = makeCategory({ id: 'cat-second' });
        first.content.classList.remove('tw-open');
        first.btn.setAttribute('aria-expanded', 'false');
        second.content.classList.remove('tw-open');
        second.btn.setAttribute('aria-expanded', 'false');
        document.body.append(first.cat, second.cat);

        toggleCategory(first.btn, first.content);
        toggleCategory(second.btn, second.content);

        expect(first.content.classList.contains('tw-open')).toBe(false);
        expect(second.content.classList.contains('tw-open')).toBe(true);
    });
});

describe('applyInitialCategoryState — wykluczające się kategorie', () => {
    test('pozostawia otwartą najwyżej jedną kategorię', () => {
        const first = makeCategory({ id: 'cat-first' });
        const second = makeCategory({ id: 'cat-second' });
        document.body.append(first.cat, second.cat);
        localStorage.setItem('chat-cat-cat-first', 'expanded');

        applyInitialCategoryState(first.btn, first.content);
        applyInitialCategoryState(second.btn, second.content);

        expect(first.content.classList.contains('tw-open')).toBe(true);
        expect(second.content.classList.contains('tw-open')).toBe(false);
        expect(second.btn.getAttribute('aria-expanded')).toBe('false');
    });
});

describe('applyInitialCategoryState — domyślny stan od nieprzeczytanych', () => {

    test('rozwija kategorię z nieprzeczytanym pokojem i nie zapisuje localStorage', () => {
        const { content, btn } = makeCategory({ id: 'cat-a' });
        content.appendChild(makeRoomLink({ id: 1, unread: true }));

        applyInitialCategoryState(btn, content);

        expect(content.classList.contains('tw-open')).toBe(true);
        expect(btn.getAttribute('aria-expanded')).toBe('true');
        expect(localStorage.getItem('chat-cat-cat-a')).toBeNull();
    });

    test('zwija kategorię bez nieprzeczytanych pokoi', () => {
        const { content, btn } = makeCategory({ id: 'cat-b' });
        content.appendChild(makeRoomLink({ id: 2, unread: false }));

        applyInitialCategoryState(btn, content);

        expect(content.classList.contains('tw-open')).toBe(false);
        expect(btn.getAttribute('aria-expanded')).toBe('false');
    });

    test('rozwija kategorię i archiwum, gdy nieprzeczytany pokój jest w archiwum', () => {
        const { content, btn } = makeCategory({ id: 'cat-c', withArchive: true });
        const archive = content.querySelector('.tw-archive-section');
        archive.appendChild(makeRoomLink({ id: 3, unread: true, archived: true }));

        applyInitialCategoryState(btn, content);

        expect(content.classList.contains('tw-open')).toBe(true);
        expect(btn.getAttribute('aria-expanded')).toBe('true');
        expect(archive.classList.contains('tw-visible')).toBe(true);
        expect(localStorage.getItem('chat-archive-global')).toBeNull();
    });

    test('nie dotyka archiwum bez nieprzeczytanych pokoi', () => {
        const { content, btn } = makeCategory({ id: 'cat-d', withArchive: true });
        const archive = content.querySelector('.tw-archive-section');
        content.appendChild(makeRoomLink({ id: 4, unread: true }));
        archive.appendChild(makeRoomLink({ id: 5, unread: false, archived: true }));

        applyInitialCategoryState(btn, content);

        expect(archive.classList.contains('tw-visible')).toBe(false);
    });
});

// ── localStorage nadrzędny nad domyślnym stanem ─────────────────────────────

describe('applyInitialCategoryState — localStorage nadrzędny', () => {

    test("zapisany 'expanded' otwiera nawet bez nieprzeczytanych", () => {
        localStorage.setItem('chat-cat-cat-e', 'expanded');
        const { content, btn } = makeCategory({ id: 'cat-e' });
        content.appendChild(makeRoomLink({ id: 6, unread: false }));

        applyInitialCategoryState(btn, content);

        expect(content.classList.contains('tw-open')).toBe(true);
        expect(btn.getAttribute('aria-expanded')).toBe('true');
    });

    test("zapisany 'collapsed' zamyka mimo nieprzeczytanych", () => {
        localStorage.setItem('chat-cat-cat-f', 'collapsed');
        const { content, btn } = makeCategory({ id: 'cat-f' });
        content.appendChild(makeRoomLink({ id: 7, unread: true }));

        applyInitialCategoryState(btn, content);

        expect(content.classList.contains('tw-open')).toBe(false);
        expect(btn.getAttribute('aria-expanded')).toBe('false');
    });

    test("zapisany 'collapsed' nie otwiera archiwum z nieprzeczytanym", () => {
        localStorage.setItem('chat-cat-cat-g', 'collapsed');
        const { content, btn } = makeCategory({ id: 'cat-g', withArchive: true });
        const archive = content.querySelector('.tw-archive-section');
        archive.appendChild(makeRoomLink({ id: 8, unread: true, archived: true }));

        applyInitialCategoryState(btn, content);

        expect(content.classList.contains('tw-open')).toBe(false);
        expect(archive.classList.contains('tw-visible')).toBe(false);
    });
});
