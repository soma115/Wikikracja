/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const SCRIPT_PATH = path.join(__dirname, '..', 'citizens_list.js');

function loadCitizensList() {
    const source = fs.readFileSync(SCRIPT_PATH, 'utf8');
    new Function(source)();
}

describe('citizens list presence refresh', () => {
    beforeEach(() => {
        jest.useFakeTimers();
        window.history.replaceState({}, '', '/obywatele/?aktywnosc=online');
        window.wkOnReady = callback => callback();
        window.debounce = callback => callback;
        window.PagePrefs = {applyView: jest.fn(), write: jest.fn()};
        document.body.innerHTML = `
            <input id="citizens-search" value="">
            <div data-view-container>
                <div id="citizens-list-view"><div class="tw-user-row" data-user-id="1" data-search="Old user"></div></div>
                <div id="citizens-grid-view"><div class="tw-citizen-card" data-user-id="1" data-search="Old user"></div></div>
            </div>
        `;
    });

    afterEach(() => {
        jest.clearAllTimers();
        jest.useRealTimers();
        jest.restoreAllMocks();
    });

    test('refreshes both views after a presence update without reloading the page', async () => {
        const responseHtml = `
            <div data-view-container>
                <div id="citizens-list-view"><div class="tw-user-row" data-user-id="2" data-search="New user"></div></div>
                <div id="citizens-grid-view"><div class="tw-citizen-card" data-user-id="2" data-search="New user"></div></div>
            </div>
        `;
        const fetchMock = jest.fn().mockResolvedValue({ok: true, text: async () => responseHtml});
        window.fetch = fetchMock;
        global.fetch = fetchMock;
        loadCitizensList();

        document.dispatchEvent(new CustomEvent('wk:presence-update', {detail: {user_id: 2}}));
        jest.advanceTimersByTime(250);
        await Promise.resolve();
        await Promise.resolve();

        expect(fetchMock).toHaveBeenCalledWith(
            expect.objectContaining({search: '?aktywnosc=online&partial=1'}),
            expect.objectContaining({credentials: 'same-origin'}),
        );
        expect(document.querySelector('#citizens-list-view [data-user-id="2"]')).not.toBeNull();
        expect(document.querySelector('#citizens-grid-view [data-user-id="2"]')).not.toBeNull();
        expect(window.PagePrefs.applyView).toHaveBeenCalledWith('list');
    });
});
