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

describe('PagePrefs patchSidebarLinks', () => {
    beforeAll(() => {
        loadAppScript();
    });

    beforeEach(() => {
        document.body.innerHTML = '';
        document.documentElement.removeAttribute('data-prefs-scope');
        if (typeof localStorage !== 'undefined') localStorage.clear();
    });

    afterEach(() => {
        jest.restoreAllMocks();
        document.documentElement.removeAttribute('data-prefs-scope');
    });

    test('applies saved filters to sidebar links', () => {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem('wikikracja:prefs:obywatele', JSON.stringify({ filters: '?aktywnosc=online&sort=last_name' }));
        document.body.innerHTML = '<a id="citizens-link" href="/obywatele/" data-prefs-link-scope="obywatele" data-prefs-base-href="/obywatele/">Citizens</a>';
        window.PagePrefs.patchSidebarLinks();
        const link = document.getElementById('citizens-link');
        expect(link.getAttribute('href')).toBe('/obywatele/?aktywnosc=online&sort=last_name');
    });

    test('skips links when base href already contains a query string', () => {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem('wikikracja:prefs:tasks', JSON.stringify({ filters: '?tab=awaiting&category=1' }));
        document.body.innerHTML = '<a id="tasks-link" href="/tasks/?tab=mine" data-prefs-link-scope="tasks" data-prefs-base-href="/tasks/?tab=mine">Tasks</a>';
        window.PagePrefs.patchSidebarLinks();
        const link = document.getElementById('tasks-link');
        expect(link.getAttribute('href')).toBe('/tasks/?tab=mine');
    });

    test('leaves base href unchanged when no saved filters', () => {
        if (typeof localStorage === 'undefined') return;
        document.body.innerHTML = '<a id="tasks-link" href="/tasks/" data-prefs-link-scope="tasks" data-prefs-base-href="/tasks/">Tasks</a>';
        window.PagePrefs.patchSidebarLinks();
        const link = document.getElementById('tasks-link');
        expect(link.getAttribute('href')).toBe('/tasks/');
    });

    test('works for glosowania subpage scope', () => {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem('wikikracja:prefs:glosowania:approved', JSON.stringify({ filters: '?category=3&sort=newest' }));
        document.body.innerHTML = '<a id="votings-link" href="/glosowania/approved/" data-prefs-link-scope="glosowania:approved" data-prefs-base-href="/glosowania/approved/">Votings</a>';
        window.PagePrefs.patchSidebarLinks();
        const link = document.getElementById('votings-link');
        expect(link.getAttribute('href')).toBe('/glosowania/approved/?category=3&sort=newest');
    });

    test('uses saved lastUrl when present', () => {
        if (typeof localStorage === 'undefined') return;
        localStorage.setItem('wikikracja:prefs:glosowania', JSON.stringify({ lastUrl: '/glosowania/discussion/?sort=date' }));
        document.body.innerHTML = '<a id="votings-link" href="/glosowania/approved/" data-prefs-link-scope="glosowania" data-prefs-base-href="/glosowania/approved/">Votings</a>';
        window.PagePrefs.patchSidebarLinks();
        const link = document.getElementById('votings-link');
        expect(link.getAttribute('href')).toBe('/glosowania/discussion/?sort=date');
    });

    test('saveCurrentFilters writes lastUrl under base scope for multi-page scope', () => {
        if (typeof localStorage === 'undefined') return;
        document.documentElement.setAttribute('data-prefs-scope', 'bookkeeping');
        const locationSpy = jest.spyOn(window, 'location', 'get').mockReturnValue({
            pathname: '/bookkeeping/transaction/',
            search: '?sort=date&order=asc',
            href: 'http://localhost/bookkeeping/transaction/?sort=date&order=asc',
        });

        window.PagePrefs.saveCurrentFilters();

        const parentData = JSON.parse(localStorage.getItem('wikikracja:prefs:bookkeeping') || '{}');
        const subData = JSON.parse(localStorage.getItem('wikikracja:prefs:bookkeeping:transaction') || '{}');
        expect(parentData.lastUrl).toBe('/bookkeeping/transaction/?sort=date&order=asc');
        expect(subData.filters).toBe('?sort=date&order=asc');

        locationSpy.mockRestore();
    });

    test('saveCurrentFilters writes lastUrl for subpage without query', () => {
        if (typeof localStorage === 'undefined') return;
        document.documentElement.setAttribute('data-prefs-scope', 'glosowania');
        const locationSpy = jest.spyOn(window, 'location', 'get').mockReturnValue({
            pathname: '/glosowania/proposition/',
            search: '',
            href: 'http://localhost/glosowania/proposition/',
        });

        window.PagePrefs.saveCurrentFilters();

        const parentData = JSON.parse(localStorage.getItem('wikikracja:prefs:glosowania') || '{}');
        const subData = JSON.parse(localStorage.getItem('wikikracja:prefs:glosowania:proposition') || '{}');
        expect(parentData.lastUrl).toBe('/glosowania/proposition/');
        expect(subData.filters).toBeUndefined();

        locationSpy.mockRestore();
    });

    test('saveCurrentFilters writes lastUrl for obywatele subpage', () => {
        if (typeof localStorage === 'undefined') return;
        document.documentElement.setAttribute('data-prefs-scope', 'obywatele');
        const locationSpy = jest.spyOn(window, 'location', 'get').mockReturnValue({
            pathname: '/obywatele/poczekalnia/',
            search: '',
            href: 'http://localhost/obywatele/poczekalnia/',
        });

        window.PagePrefs.saveCurrentFilters();

        const parentData = JSON.parse(localStorage.getItem('wikikracja:prefs:obywatele') || '{}');
        const subData = JSON.parse(localStorage.getItem('wikikracja:prefs:obywatele:poczekalnia') || '{}');
        expect(parentData.lastUrl).toBe('/obywatele/poczekalnia/');
        expect(subData.filters).toBeUndefined();

        locationSpy.mockRestore();
    });

    test('saveCurrentFilters does not overwrite lastUrl on base scope with empty query', () => {
        if (typeof localStorage === 'undefined') return;
        document.documentElement.setAttribute('data-prefs-scope', 'tasks');
        localStorage.setItem('wikikracja:prefs:tasks', JSON.stringify({ lastUrl: '/tasks/?tab=mine&category=1' }));
        const locationSpy = jest.spyOn(window, 'location', 'get').mockReturnValue({
            pathname: '/tasks/',
            search: '',
            href: 'http://localhost/tasks/',
        });

        window.PagePrefs.saveCurrentFilters();

        const data = JSON.parse(localStorage.getItem('wikikracja:prefs:tasks') || '{}');
        expect(data.lastUrl).toBe('/tasks/?tab=mine&category=1');

        locationSpy.mockRestore();
    });
});
