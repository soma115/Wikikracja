/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const SCRIPT_PATH = path.join(__dirname, '..', 'resource-search.js');

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
    let originalTwModal;

    beforeEach(() => {
        jest.useFakeTimers();
        originalTwModal = window.TwModal;
        window.wkOnReady = callback => callback();
    });

    afterEach(() => {
        jest.clearAllTimers();
        jest.useRealTimers();
        jest.restoreAllMocks();
        if (typeof originalTwModal === 'undefined') delete window.TwModal;
        else window.TwModal = originalTwModal;
    });

    test('opens the resource modal after a form validation error', () => {
        document.body.innerHTML = '<div id="resource-form" data-open-on-load="true"></div>';
        window.TwModal = {show: jest.fn()};
        loadProfileScript();

        expect(window.TwModal.show).toHaveBeenCalledWith(document.getElementById('resource-form'));
    });

    // resource_list.html: the <form> element itself is the resource section -
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

    test('includes a selected type in catalog suggestions', async () => {
        document.body.innerHTML = `
            <form data-resource-section data-resource-search-url="/search/" data-resource-kind-required="false">
                    <select name="kind"><option value="">All types</option><option value="need">I need</option></select>
                    <input data-resource-name="true">
                    <div class="tw-dropdown-menu tw-w-full" data-resource-suggestions></div>
            </form>
        `;
        global.fetch = jest.fn().mockResolvedValue({json: async () => ({items: []})});
        loadProfileScript();

        const input = document.querySelector('[data-resource-name]');
        const kind = document.querySelector('[name="kind"]');
        expect(input.disabled).toBe(false);

        kind.value = 'need';
        input.value = 'dri';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        jest.advanceTimersByTime(250);
        await flushFetch();

        expect(global.fetch).toHaveBeenCalledWith('/search/?q=dri&kind=need');
    });

    test('only suggests resources when searching all entities or resources', async () => {
        document.body.innerHTML = `
            <form data-resource-section data-resource-search-url="/search/" data-resource-kind-required="false">
                <select name="entity_type">
                    <option value="all">All</option>
                    <option value="resource">Resources</option>
                    <option value="financial_asset">Financial assets</option>
                </select>
                <select name="kind"><option value="">All types</option></select>
                <input data-resource-name="true">
                <div data-resource-suggestions></div>
            </form>
        `;
        global.fetch = jest.fn().mockResolvedValue({json: async () => ({items: []})});
        loadProfileScript();

        const entityType = document.querySelector('[name="entity_type"]');
        const input = document.querySelector('[data-resource-name]');
        const suggestions = suggestionsMenu();
        entityType.value = 'financial_asset';
        entityType.dispatchEvent(new Event('change'));
        input.value = 'garage';
        input.dispatchEvent(new Event('input', {bubbles: true}));
        jest.advanceTimersByTime(250);
        await flushFetch();

        expect(global.fetch).not.toHaveBeenCalled();
        expect(suggestions.classList.contains('tw-show')).toBe(false);
    });
});
