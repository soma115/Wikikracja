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

async function flushRequests() {
    jest.runOnlyPendingTimers();
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
}

describe('local link titles', () => {
    beforeAll(() => {
        loadAppScript();
    });

    beforeEach(() => {
        jest.useFakeTimers();
        document.body.innerHTML = '<main></main>';
        window.LINK_TITLES_URL = '/link-titles/';
        window.LINK_TITLES_CSRF_TOKEN = 'token';
        global.fetch = jest.fn(function(_, options) {
            const urls = JSON.parse(options.body).urls;
            const titles = Object.fromEntries(urls.map(url => [url, url.includes('/tasks/') ? 'Activity title' : 'Event title']));
            return Promise.resolve({ ok: true, json: () => Promise.resolve({ titles }) });
        });
    });

    afterEach(() => {
        jest.useRealTimers();
        delete global.fetch;
    });

    test('replaces only a raw local URL label', async () => {
        const main = document.querySelector('main');
        main.innerHTML = `
            <a class="raw" href="/tasks/42/">/tasks/42/</a>
            <a class="named" href="/tasks/42/">Custom label</a>
            <a class="external" href="https://example.com/tasks/42/">https://example.com/tasks/42/</a>
        `;

        const observer = window.initLocalLinkTitles(main);
        await flushRequests();

        expect(main.querySelector('.raw').textContent).toBe('Activity title');
        expect(main.querySelector('.named').textContent).toBe('Custom label');
        expect(main.querySelector('.external').textContent).toBe('https://example.com/tasks/42/');
        expect(fetch).toHaveBeenCalledTimes(1);
        observer.disconnect();
    });

    test('resolves a link inserted dynamically', async () => {
        const main = document.querySelector('main');
        const observer = window.initLocalLinkTitles(main);
        const anchor = document.createElement('a');
        anchor.href = '/events/5/';
        anchor.textContent = '/events/5/';
        main.appendChild(anchor);
        await Promise.resolve();
        await flushRequests();

        expect(anchor.textContent).toBe('Event title');
        observer.disconnect();
    });
});
