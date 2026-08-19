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

    const rows = ['<div class="cat-filter__item cat-filter__all" id="catAllRow" data-key="" data-label="All"></div>'];
    allCategories.forEach(function(k) {
        rows.push('<div class="cat-filter__item" data-key="' + k + '" data-label="' + k + '"></div>');
    });

    return `
        <div class="cat-filter" id="catFilter">
            <button type="button" id="catFilterBtn" aria-expanded="false">
                <span id="catFilterLabel">Category</span>
            </button>
            <div class="cat-filter__panel" id="catFilterPanel" hidden>
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
        jest.spyOn(history, 'pushState').mockImplementation(() => {});
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    test('toggles the dropdown panel for task-card items', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="task-card" data-category="urgent">Urgent task</div>
                <div class="task-card" data-category="later">Later task</div>
            </div>
        `;
        const items = document.querySelectorAll('.task-card');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();
        const btn = document.getElementById('catFilterBtn');
        const panel = document.getElementById('catFilterPanel');

        expect(panel.hidden).toBe(true);
        click(btn);
        expect(panel.hidden).toBe(false);
        expect(btn.getAttribute('aria-expanded')).toBe('true');
    });

    test('filters task-card items by category and hides empty sections', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tasks-section-label">Active</div>
                <div class="task-card" data-category="urgent">Urgent task</div>
                <div class="task-card" data-category="later">Later task</div>
                <div class="tasks-section-label">Done</div>
                <div class="task-card" data-category="done">Done task</div>
            </div>
        `;
        const items = document.querySelectorAll('.task-card');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.cat-filter__item:not(.cat-filter__all)');
        const urgentRow = Array.from(rows).find(function(r) { return r.dataset.key === 'urgent'; });

        click(urgentRow);

        const cards = Array.from(document.querySelectorAll('.task-card'));
        expect(cards[0].style.display).toBe('');
        expect(cards[1].style.display).toBe('none');
        expect(cards[2].style.display).toBe('none');

        const sections = Array.from(document.querySelectorAll('.tasks-section-label'));
        expect(sections[0].style.display).toBe('');
        expect(sections[1].style.display).toBe('none');
    });

    test('recognizes proposal-card items', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="tasks-section-label">Proposals</div>
                <div class="proposal-card" data-category="budget">Budget proposal</div>
                <div class="proposal-card" data-category="rules">Rules proposal</div>
            </div>
        `;
        const items = document.querySelectorAll('.proposal-card');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.cat-filter__item:not(.cat-filter__all)');
        click(rows[0]);

        const cards = Array.from(document.querySelectorAll('.proposal-card'));
        expect(cards[0].style.display).toBe('');
        expect(cards[1].style.display).toBe('none');
    });

    test('recognizes board-category-group items by data-category-pk', () => {
        document.body.innerHTML = `
            <div class="board-category-group" data-category-pk="1">Board group 1</div>
            <div class="board-category-group" data-category-pk="2">Board group 2</div>
        `;
        const items = document.querySelectorAll('.board-category-group');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.cat-filter__item:not(.cat-filter__all)');
        click(rows[0]);

        const groups = Array.from(document.querySelectorAll('.board-category-group'));
        expect(groups[0].style.display).toBe('');
        expect(groups[1].style.display).toBe('none');
    });

    test('clicking "All" shows every item again', () => {
        document.body.innerHTML = `
            <div class="proposals-list">
                <div class="task-card" data-category="a">A</div>
                <div class="task-card" data-category="b">B</div>
            </div>
        `;
        const items = document.querySelectorAll('.task-card');
        document.body.insertAdjacentHTML('beforeend', buildCatFilter(items));

        window.initCategoryFilter();

        const rows = document.querySelectorAll('.cat-filter__item:not(.cat-filter__all)');
        click(rows[0]);

        const allRow = document.getElementById('catAllRow');
        click(allRow);

        const cards = Array.from(document.querySelectorAll('.task-card'));
        expect(cards[0].style.display).toBe('');
        expect(cards[1].style.display).toBe('');
    });
});
