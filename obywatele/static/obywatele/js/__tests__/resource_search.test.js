/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const SCRIPT_PATH = path.join(__dirname, '..', 'profile.js');

function loadProfileScript() {
    const source = fs.readFileSync(SCRIPT_PATH, 'utf8');
    new Function(source)();
}

function suggestionsMenu() {
    return document.querySelector('[data-resource-suggestions]');
}

async function flushFetch() {
    for (let i = 0; i < 6; i++) await Promise.resolve();
}

describe('resource item search', () => {
    beforeEach(() => {
        jest.useFakeTimers();
        window.wkOnReady = callback => callback();
    });

    afterEach(() => {
        jest.clearAllTimers();
        jest.useRealTimers();
        jest.restoreAllMocks();
    });

    // assets.html: the <form> element itself is the resource section —
    // regression test for resourceForm being null and killing the handler.
    test('attaches search when the section is the form itself', async () => {
        document.body.innerHTML = `
            <form data-resource-section data-resource-search-url="/search/" data-resource-kind-required="false">
                <select name="kind"><option value="">All types</option><option value="give">Give</option></select>
                <div class="tw-dropdown">
                    <input type="search" data-resource-name="true">
                    <div class="tw-dropdown-menu tw-w-full" data-resource-suggestions></div>
                </div>
            </form>
        `;
        const fetchMock = jest.fn().mockResolvedValue({json: async () => ({items: [{id: 1, name: 'Drill'}]})});
        global.fetch = fetchMock;
        loadProfileScript();

        const input = document.querySelector('[data-resource-name]');
        input.value = 'dri';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        jest.advanceTimersByTime(250);
        await flushFetch();

        expect(fetchMock).toHaveBeenCalledWith('/search/?q=dri');
        expect(suggestionsMenu().classList.contains('tw-show')).toBe(true);
        expect(suggestionsMenu().textContent).toContain('Drill');
    });

    test('selecting a suggestion fills the input and hides the menu', async () => {
        document.body.innerHTML = `
            <form data-resource-section data-resource-search-url="/search/" data-resource-kind-required="false">
                <select name="kind"><option value="">All types</option></select>
                <div class="tw-dropdown">
                    <input type="search" data-resource-name="true">
                    <div class="tw-dropdown-menu tw-w-full" data-resource-suggestions></div>
                </div>
            </form>
        `;
        global.fetch = jest.fn().mockResolvedValue({json: async () => ({items: [{id: 1, name: 'Drill'}]})});
        loadProfileScript();

        const input = document.querySelector('[data-resource-name]');
        input.value = 'dri';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        jest.advanceTimersByTime(250);
        await flushFetch();

        suggestionsMenu().querySelector('button').click();
        expect(input.value).toBe('Drill');
        expect(suggestionsMenu().classList.contains('tw-show')).toBe(false);
    });

    // my_assets.html: kind is required, so the name field starts disabled
    // and the search only runs after a kind is chosen.
    test('requires a kind before enabling the name field', async () => {
        document.body.innerHTML = `
            <section data-resource-section data-resource-search-url="/search/">
                <form>
                    <select name="kind"><option value="">Select type</option><option value="need">I need</option></select>
                    <input data-resource-name="true">
                    <div class="tw-dropdown-menu tw-w-full" data-resource-suggestions></div>
                </form>
            </section>
        `;
        global.fetch = jest.fn().mockResolvedValue({json: async () => ({items: []})});
        loadProfileScript();

        const input = document.querySelector('[data-resource-name]');
        const kind = document.querySelector('[name="kind"]');
        expect(input.disabled).toBe(true);

        input.dispatchEvent(new Event('input', {bubbles: true}));
        jest.advanceTimersByTime(250);
        expect(global.fetch).not.toHaveBeenCalled();

        kind.value = 'need';
        kind.dispatchEvent(new Event('change', {bubbles: true}));
        expect(input.disabled).toBe(false);

        input.value = 'dri';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        jest.advanceTimersByTime(250);
        await flushFetch();

        expect(global.fetch).toHaveBeenCalledWith('/search/?q=dri&kind=need');
    });
});
