/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const APP_JS_PATH = path.join(__dirname, '..', 'app.js');

function loadAppScript() {
    const src = fs.readFileSync(APP_JS_PATH, 'utf8');
    const run = new Function(src);
    run();
}

function buildCatFilter(items, extraCategories) {
    const allCategories = new Set();
    Array.from(items).forEach(function(item) {
        const key = item.dataset.category || item.dataset.categoryPk;
        if (key) allCategories.add(key);
    });
    (extraCategories || []).forEach(function(k) { allCategories.add(k); });

    const rows = ['<div class="tw-cat-filter-item tw-cat-filter-all" id="catAllRow" data-key="" data-label="All"></div>'];
    allCategories.forEach(function(k) {
        rows.push('<div class="tw-cat-filter-item" data-key="' + k + '" data-label="' + k + '"></div>');
    });

    return `
        <div class="tw-cat-filter" id="catFilter">
            <button type="button" id="catFilterBtn" aria-expanded="false">
                <span id="catFilterLabel">Category</span>
            </button>
            <div class="tw-cat-filter-panel" id="catFilterPanel" hidden>
                ${rows.join('')}
            </div>
        </div>
    `;
}

function click(el) {
    el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
}

describe('initCategoryFilter', () => {
    beforeAll(() => {
        loadAppScript();
    });

    beforeEach(() => {
        document.body.innerHTML = '';
        document.documentElement.removeAttribute('data-prefs-scope');
        jest.spyOn(history, 'pushState').mockImplementation(() => {});
        if (typeof sessionStorage !== 'undefined') sessionStorage.clear();
        if (typeof localStorage !== 'undefined') localStorage.clear();
    });

    afterEach(() => {
        jest.restoreAllMocks();
        document.documentElement.removeAttribute('data-prefs-scope');
    });

    test('toggles the dropdown panel for task content-card items', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tw-content-card" data-card-type="task" data-category="urgent">Urgent task</div>
                <div class="tw-content-card" data-card-type="task" data-category="later">Later task</div>
            </div>
        `;
        const items = document.querySelectorAll('.tw-content-card[data-card-type="task"]');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();
        const btn = document.getElementById('catFilterBtn');
        const panel = document.getElementById('catFilterPanel');

        expect(panel.hidden).toBe(true);
        click(btn);
        expect(panel.hidden).toBe(false);
        expect(btn.getAttribute('aria-expanded')).toBe('true');
    });

    test('filters task content-card items by category and hides empty sections', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tw-tasks-section-label">Active</div>
                <div class="tw-content-card" data-card-type="task" data-category="urgent">Urgent task</div>
                <div class="tw-content-card" data-card-type="task" data-category="later">Later task</div>
                <div class="tw-tasks-section-label">Done</div>
                <div class="tw-content-card" data-card-type="task" data-category="done">Done task</div>
            </div>
        `;
        const items = document.querySelectorAll('.tw-content-card[data-card-type="task"]');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)');
        const urgentRow = Array.from(rows).find(function(r) { return r.dataset.key === 'urgent'; });

        click(urgentRow);

        const cards = Array.from(document.querySelectorAll('.tw-content-card[data-card-type="task"]'));
        expect(cards[0].classList.contains('tw-d-none')).toBe(false);
        expect(cards[1].classList.contains('tw-d-none')).toBe(true);
        expect(cards[2].classList.contains('tw-d-none')).toBe(true);

        const sections = Array.from(document.querySelectorAll('.tw-tasks-section-label'));
        expect(sections[0].classList.contains('tw-d-none')).toBe(false);
        expect(sections[1].classList.contains('tw-d-none')).toBe(true);
    });

    test('recognizes content-card items', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tw-tasks-section-label">Proposals</div>
                <div class="tw-content-card" data-category="budget">Budget proposal</div>
                <div class="tw-content-card" data-category="rules">Rules proposal</div>
            </div>
        `;
        const items = document.querySelectorAll('.tw-content-card');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)');
        click(rows[0]);

        const cards = Array.from(document.querySelectorAll('.tw-content-card'));
        expect(cards[0].classList.contains('tw-d-none')).toBe(false);
        expect(cards[1].classList.contains('tw-d-none')).toBe(true);
    });

    test('recognizes board-category-group items by data-category-pk', () => {
        document.body.innerHTML = `
            <div class="tw-board-category-group" data-category-pk="1">Board group 1</div>
            <div class="tw-board-category-group" data-category-pk="2">Board group 2</div>
        `;
        const items = document.querySelectorAll('.tw-board-category-group');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)');
        click(rows[0]);

        const groups = Array.from(document.querySelectorAll('.tw-board-category-group'));
        expect(groups[0].classList.contains('tw-d-none')).toBe(false);
        expect(groups[1].classList.contains('tw-d-none')).toBe(true);
    });

    test('initializes board filter state from URL query parameter', () => {
        var locationSpy = jest.spyOn(window, 'location', 'get');
        locationSpy.mockReturnValue({ search: '?category=1', pathname: '/' });

        document.body.innerHTML = `
            <div class="tw-board-category-group" data-category-pk="1">Board group 1</div>
            <div class="tw-board-category-group" data-category-pk="2">Board group 2</div>
        `;
        const items = document.querySelectorAll('.tw-board-category-group');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const groups = Array.from(document.querySelectorAll('.tw-board-category-group'));
        expect(groups[0].classList.contains('tw-d-none')).toBe(false);
        expect(groups[1].classList.contains('tw-d-none')).toBe(true);

        locationSpy.mockRestore();
    });

    test('clicking "All" shows every item again', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tw-content-card" data-card-type="task" data-category="a">A</div>
                <div class="tw-content-card" data-card-type="task" data-category="b">B</div>
            </div>
        `;
        const items = document.querySelectorAll('.tw-content-card[data-card-type="task"]');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)');
        click(rows[0]);

        const allRow = document.getElementById('catAllRow');
        click(allRow);

        const cards = Array.from(document.querySelectorAll('.tw-content-card[data-card-type="task"]'));
        expect(cards[0].classList.contains('tw-d-none')).toBe(false);
        expect(cards[1].classList.contains('tw-d-none')).toBe(false);
    });

    test('tasks scope reloads, saves filters and passes navigation to onNavigate', () => {
        document.documentElement.setAttribute('data-prefs-scope', 'tasks');
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tw-content-card" data-card-type="task" data-category="urgent">Urgent task</div>
                <div class="tw-content-card" data-card-type="task" data-category="later">Later task</div>
            </div>
        `;
        const items = document.querySelectorAll('.tw-content-card[data-card-type="task"]');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        const onNavigate = jest.fn();
        const writeSpy = jest.spyOn(window.PagePrefs, 'write').mockImplementation(() => {});
        window.initCategoryFilter({ onNavigate: onNavigate });

        const rows = document.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)');
        const urgentRow = Array.from(rows).find(function(r) { return r.dataset.key === 'urgent'; });

        click(urgentRow);

        expect(writeSpy).toHaveBeenCalledWith({ filters: '?category=urgent', lastUrl: '/?category=urgent' });
        expect(onNavigate).toHaveBeenCalledWith('/?category=urgent');

        const cards = Array.from(document.querySelectorAll('.tw-content-card[data-card-type="task"]'));
        expect(cards[0].classList.contains('tw-d-none')).toBe(false);
        expect(cards[1].classList.contains('tw-d-none')).toBe(true);
    });

    test('initializes and toggles panel even when there are no items to filter', () => {
        document.body.innerHTML = buildCatFilter([], ['foo']);

        window.initCategoryFilter();

        const btn = document.getElementById('catFilterBtn');
        const panel = document.getElementById('catFilterPanel');

        expect(panel.hidden).toBe(true);
        click(btn);
        expect(panel.hidden).toBe(false);
        expect(btn.getAttribute('aria-expanded')).toBe('true');

        const rows = document.querySelectorAll('.tw-cat-filter-item:not(.tw-cat-filter-all)');
        click(rows[0]);

        expect(history.pushState).toHaveBeenCalled();
    });

    test('reopens the panel on load when a category was just selected (sessionStorage flag)', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tw-content-card" data-card-type="task" data-category="urgent">Urgent task</div>
            </div>
        `;
        const items = document.querySelectorAll('.tw-content-card[data-card-type="task"]');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        sessionStorage.setItem('catFilterOpen', '1');

        window.initCategoryFilter();

        const panel = document.getElementById('catFilterPanel');
        const btn = document.getElementById('catFilterBtn');

        expect(panel.hidden).toBe(false);
        expect(btn.getAttribute('aria-expanded')).toBe('true');
        expect(sessionStorage.getItem('catFilterOpen')).toBeNull();
    });

    test('toolbar overflow does not auto-collapse the sidebar', () => {
        document.body.innerHTML = `
            <aside id="sidebar"><i id="sidebar-collapse-icon" class="fa-angles-left"></i></aside>
            <div class="tw-toolbar">
                <div data-responsive-controls data-responsive-toolbar-group></div>
            </div>
        `;
        const controls = document.querySelector('[data-responsive-controls]');
        Object.defineProperty(controls, 'clientWidth', { configurable: true, value: 100 });
        Object.defineProperty(controls, 'scrollWidth', { configurable: true, value: 200 });
        controls.getClientRects = () => [{ width: 100 }];
        window.matchMedia = () => ({ matches: true });
        jest.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => callback());

        window.initResponsiveControls(document);

        expect(document.getElementById('sidebar').classList.contains('tw-auto-collapsed')).toBe(false);
    });

    test('exclusive inputs uncheck the other input in their group', () => {
        document.body.innerHTML = `
            <input type="checkbox" data-exclusive-group="visibility" id="public">
            <input type="checkbox" data-exclusive-group="visibility" id="private">
        `;
        window.initExclusiveInputs();

        const publicInput = document.getElementById('public');
        const privateInput = document.getElementById('private');
        publicInput.checked = true;
        publicInput.dispatchEvent(new Event('change', { bubbles: true }));
        privateInput.checked = true;
        privateInput.dispatchEvent(new Event('change', { bubbles: true }));

        expect(privateInput.checked).toBe(true);
        expect(publicInput.checked).toBe(false);
    });

    test('PagePrefs saves view per tab', () => {
        document.documentElement.setAttribute('data-prefs-scope', 'tasks');
        document.body.innerHTML = `
            <div id="view-container" data-view-container>
                <button data-view="list"></button>
                <button data-view="compact"></button>
            </div>
        `;

        var locationSpy = jest.spyOn(window, 'location', 'get');
        locationSpy.mockReturnValue({ search: '?tab=mine', pathname: '/tasks/', href: 'http://localhost/tasks/?tab=mine' });
        window.PagePrefs.setView('compact');

        var data = window.PagePrefs.read();
        expect(data.views.mine).toBe('compact');
        expect(data.view).toBe('compact');
        expect(document.getElementById('view-container').classList.contains('tw-view-compact')).toBe(true);

        locationSpy.mockReturnValue({ search: '?tab=active', pathname: '/tasks/', href: 'http://localhost/tasks/?tab=active' });
        window.PagePrefs.setView('list');

        data = window.PagePrefs.read();
        expect(data.views.active).toBe('list');
        expect(data.views.mine).toBe('compact');

        locationSpy.mockRestore();
    });
});
