/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const APP_JS_PATH = path.join(__dirname, '..', 'app.js');

function loadAppScript() {
    const src = fs.readFileSync(APP_JS_PATH, 'utf8');
    new Function(src)();
}

function createActivityRow(isRead, isBookmarked) {
    document.body.innerHTML = `
        <div id="activity-list" class="tw-activity-list"></div>
    `;
    const container = document.getElementById('activity-list');
    const row = document.createElement('div');
    row.className = 'tw-feed-row' + (isRead ? '' : ' tw-unread-row');
    row.setAttribute('data-url', '/post/42/');
    row.setAttribute('data-content-type', 'post');
    row.setAttribute('data-object-id', '42');

    const title = document.createElement('a');
    title.className = 'tw-feed-title-text';
    title.href = '/post/42/';
    title.textContent = 'Test post';

    const bookmark = document.createElement('span');
    bookmark.className = 'tw-feed-toggle';
    bookmark.setAttribute('role', 'button');
    bookmark.setAttribute('tabindex', '0');
    bookmark.setAttribute('data-action', 'bookmark');
    bookmark.setAttribute('data-content-type', 'post');
    bookmark.setAttribute('data-object-id', '42');
    bookmark.setAttribute('data-is-bookmarked', isBookmarked ? 'true' : 'false');
    bookmark.setAttribute('data-add-title', 'Add bookmark');
    bookmark.setAttribute('data-remove-title', 'Remove bookmark');
    const bookmarkIcon = document.createElement('i');
    bookmarkIcon.className = isBookmarked ? 'fas fa-star' : 'far fa-star';
    bookmark.appendChild(bookmarkIcon);

    const read = document.createElement('span');
    read.className = 'tw-feed-toggle';
    read.setAttribute('role', 'button');
    read.setAttribute('tabindex', '0');
    read.setAttribute('data-action', 'read');
    read.setAttribute('data-content-type', 'post');
    read.setAttribute('data-object-id', '42');
    read.setAttribute('data-is-read', isRead ? 'true' : 'false');
    read.setAttribute('data-mark-read-title', 'Mark as read');
    read.setAttribute('data-mark-unread-title', 'Mark as unread');
    const readIcon = document.createElement('i');
    readIcon.className = isRead ? 'fas fa-eye-slash' : 'fas fa-eye';
    read.appendChild(readIcon);

    row.appendChild(title);
    row.appendChild(bookmark);
    row.appendChild(read);
    container.appendChild(row);

    return { container, row, bookmark, read, bookmarkIcon, readIcon };
}

describe('activity feed interactions', () => {
    beforeAll(() => {
        loadAppScript();
    });

    beforeEach(() => {
        document.body.innerHTML = '';
        delete window.MARK_AS_READ_URL;
        delete window.MARK_UNREAD_URL;
        delete window.TOGGLE_BOOKMARK_URL;
        delete window.ACTIVITY_FILTER_UNREAD;
        delete window.ACTIVITY_FILTER_BOOKMARKS;
        window.apiFetch = jest.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ success: true, is_bookmarked: true }),
        }));
    });

    afterEach(() => {
        delete window.apiFetch;
    });

    test('mark read on row click and navigate', () => {
        window.MARK_AS_READ_URL = '/mark-as-read/';
        const { row } = createActivityRow(false, false);
        row.setAttribute('data-url', '#navigate');
        window.initActivityFeedMarkRead('#activity-list', '.tw-feed-row');

        const click = new MouseEvent('click', { bubbles: true, cancelable: true });
        row.dispatchEvent(click);

        expect(window.apiFetch).toHaveBeenCalledTimes(1);
        expect(window.apiFetch).toHaveBeenCalledWith('/mark-as-read/', expect.objectContaining({
            method: 'POST',
            body: expect.any(URLSearchParams),
        }));
    });

    test('row click does not mark read when a toggle is clicked', () => {
        window.MARK_AS_READ_URL = '/mark-as-read/';
        window.TOGGLE_BOOKMARK_URL = '/toggle-bookmark/';

        const { bookmark } = createActivityRow(false, false);
        window.initActivityFeedMarkRead('#activity-list', '.tw-feed-row');
        window.initActivityFeedToggleBookmark('#activity-list');
        bookmark.click();

        expect(window.apiFetch).toHaveBeenCalledTimes(1);
        expect(window.apiFetch).toHaveBeenCalledWith('/toggle-bookmark/', expect.objectContaining({
            method: 'POST',
            body: expect.any(URLSearchParams),
        }));
    });

    test('toggle read updates data attribute and icon', async () => {
        window.MARK_AS_READ_URL = '/mark-as-read/';
        window.MARK_UNREAD_URL = '/mark-unread/';
        const jsonFn = jest.fn(() => Promise.resolve({ success: true }));
        window.apiFetch = jest.fn(() => Promise.resolve({ ok: true, json: jsonFn }));

        const { read, readIcon, row } = createActivityRow(false, false);
        window.initActivityFeedToggleRead('#activity-list');
        read.click();

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(window.apiFetch).toHaveBeenCalledWith('/mark-as-read/', expect.objectContaining({
            method: 'POST',
            body: expect.any(URLSearchParams),
        }));
        expect(jsonFn).toHaveBeenCalled();
        expect(read.getAttribute('data-is-read')).toBe('true');
        expect(readIcon.classList.contains('fa-eye-slash')).toBe(true);
        expect(row.classList.contains('tw-unread-row')).toBe(false);
    });

    test('toggle bookmark updates data attribute and icon', async () => {
        window.TOGGLE_BOOKMARK_URL = '/toggle-bookmark/';

        const { bookmark, bookmarkIcon } = createActivityRow(false, false);
        window.initActivityFeedToggleBookmark('#activity-list');
        bookmark.click();

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(window.apiFetch).toHaveBeenCalledWith('/toggle-bookmark/', expect.objectContaining({
            method: 'POST',
            body: expect.any(URLSearchParams),
        }));
        expect(bookmark.getAttribute('data-is-bookmarked')).toBe('true');
        expect(bookmarkIcon.classList.contains('fas')).toBe(true);
        expect(bookmarkIcon.classList.contains('fa-star')).toBe(true);
        expect(bookmarkIcon.classList.contains('far')).toBe(false);
    });

    test('toggle bookmark removes bookmark and switches to empty star', async () => {
        window.TOGGLE_BOOKMARK_URL = '/toggle-bookmark/';
        window.apiFetch = jest.fn(() => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({ success: true, is_bookmarked: false }),
        }));

        const { bookmark, bookmarkIcon } = createActivityRow(false, true);
        window.initActivityFeedToggleBookmark('#activity-list');
        bookmark.click();

        await new Promise(resolve => setTimeout(resolve, 0));

        expect(bookmark.getAttribute('data-is-bookmarked')).toBe('false');
        expect(bookmarkIcon.classList.contains('far')).toBe(true);
        expect(bookmarkIcon.classList.contains('fa-star')).toBe(true);
        expect(bookmarkIcon.classList.contains('fas')).toBe(false);
    });
});
