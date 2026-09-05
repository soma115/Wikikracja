const fs = require('fs');
const path = require('path');

function source(name) {
    return fs.readFileSync(path.join(__dirname, '..', name), 'utf8')
        .replace(/^import .*?;\s*$/gm, '')
        .replace(/export\s*\{[^}]*\}\s*from\s*['"][^'"]+['"];?/g, '')
        .replace(/export\s+(default\s+)?/g, '');
}

class MockXHR {
    static instances = [];

    constructor() {
        this.headers = {};
        MockXHR.instances.push(this);
    }

    open(method, url, async) {
        Object.assign(this, { method, url, async });
    }

    setRequestHeader(name, value) {
        this.headers[name] = value;
    }

    send(body) {
        this.body = body;
    }

    respond(status, body) {
        this.status = status;
        this.responseText = body;
        this.readyState = 4;
        this.onreadystatechange?.();
        this.onload?.();
    }
}

async function flush() {
    for (let i = 0; i < 12; i++) await Promise.resolve();
}

async function start(upload, files, url) {
    const result = { state: 'pending' };
    upload(files, url).then(
        value => Object.assign(result, { state: 'resolved', value }),
        error => Object.assign(result, { state: 'rejected', error })
    );
    await flush();
    return { result, xhr: MockXHR.instances.at(-1) };
}

let core;
let ws;
let files;
const originalXHR = global.XMLHttpRequest;

beforeEach(() => {
    MockXHR.instances = [];
    global.XMLHttpRequest = MockXHR;
    document.body.innerHTML = '';
    document.cookie.split(';').forEach(cookie => {
        document.cookie = `${cookie.split('=')[0].trim()}=; Max-Age=0; path=/`;
    });
    delete window.SITE_SETTINGS;
    core = new Function(`${source('chat-core.js')}; return { uploadFiles, UPLOAD_MAX_BYTES };`)();
    const WsApi = new Function('uploadFiles', 'UPLOAD_MAX_BYTES', `${source('wsapi.js')}; return WsApi;`)(core.uploadFiles, core.UPLOAD_MAX_BYTES);
    ws = Object.create(WsApi.prototype);
    files = [new File(['image'], 'photo.gif', { type: 'image/gif' })];
    files.item = index => files[index];
});

afterEach(() => {
    global.XMLHttpRequest = originalXHR;
    jest.restoreAllMocks();
    delete window.showToast;
});

describe.each(['embedded', 'full-page'])('%s upload', mode => {
    const upload = (files, url) => mode === 'embedded' ? core.uploadFiles(files, url) : ws.uploadFiles(files);

    test('empty selection skips transport', async () => {
        await expect(upload([])).resolves.toEqual({ filenames: [] });
        expect(MockXHR.instances).toHaveLength(0);
    });

    test.each([200, 201])('accepts HTTP %i with filenames and sends multipart headers', async status => {
        document.cookie = 'csrftoken=real-token; path=/';
        const { result, xhr } = await start(upload, files);
        expect(xhr.method).toBe('POST');
        expect(xhr.url).toBe(mode === 'embedded' ? '/chat/upload/' : 'upload/');
        expect(xhr.headers).toEqual({ 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': 'real-token' });
        expect(xhr.body.getAll('images')).toEqual(files.slice());
        xhr.respond(status, '{"filenames":["photo.gif"]}');
        await flush();
        expect(result).toMatchObject({ state: 'resolved', value: { filenames: ['photo.gif'] } });
    });

    test.each([400, 403, 413, 500])('rejects HTTP %i instead of hanging', async status => {
        const { result, xhr } = await start(upload, files);
        xhr.respond(status, '<html>Error</html>');
        await flush();
        expect(result.state).toBe('rejected');
        expect(result.error.message).toContain(String(status));
    });

    test.each(['not json', 'null', '{}', '{"filenames":"bad"}', '{"filenames":[4]}', '{"filenames":[""]}', '{"error":"Upload denied","filenames":[]}'])('rejects invalid response %s', async body => {
        const { result, xhr } = await start(upload, files);
        expect(() => xhr.respond(200, body)).not.toThrow();
        await flush();
        expect(result.state).toBe('rejected');
        expect(result.error).toBeInstanceOf(Error);
        if (body.includes('Upload denied')) expect(result.error.message).toBe('Upload denied');
    });

    test.each(['error', 'timeout', 'abort'])('rejects %s and releases event handlers', async event => {
        const { result, xhr } = await start(upload, files);
        expect(xhr.timeout).toBeGreaterThan(0);
        expect(typeof xhr[`on${event}`]).toBe('function');
        xhr[`on${event}`]();
        await flush();
        expect(result.state).toBe('rejected');
        expect(result.error).toBeInstanceOf(Error);
        for (const handler of ['onload', 'onerror', 'ontimeout', 'onabort']) {
            expect(xhr[handler]).toBeNull();
        }
    });

    test('cleans up after success and synchronous send failure', async () => {
        const { result, xhr } = await start(upload, files);
        xhr.respond(200, '{"filenames":[]}');
        await flush();
        expect(result.state).toBe('resolved');
        expect(xhr.onload).toBeNull();
        jest.spyOn(MockXHR.prototype, 'send').mockImplementation(() => { throw new Error('send failed'); });
        const failed = await start(upload, files);
        expect(failed.result.state).toBe('rejected');
        expect(failed.xhr.onerror).toBeNull();
    });

    test('does not mistake a cookie suffix for the CSRF cookie', async () => {
        document.cookie = 'notcsrftoken=wrong-token; path=/';
        const { xhr } = await start(upload, files);
        expect(xhr.headers['X-CSRFToken']).toBeUndefined();
    });

    test('finds the exact CSRF cookie after another cookie', async () => {
        document.cookie = 'notcsrftoken=wrong-token; path=/';
        document.cookie = 'csrftoken=right-token; path=/';
        const { xhr } = await start(upload, files);
        expect(xhr.headers['X-CSRFToken']).toBe('right-token');
    });

    test('skips oversized files with existing notification', async () => {
        window.showToast = jest.fn();
        Object.defineProperty(files[0], 'size', { value: core.UPLOAD_MAX_BYTES + 1 });
        const { xhr } = await start(upload, files);
        expect(xhr.body.getAll('images')).toEqual([]);
        expect(window.showToast).toHaveBeenCalledWith('Image is too large (max 5 MB).');
    });
});

test.each(['https://other.example/upload/', '//other.example/upload/'])('does not send CSRF token to %s', async url => {
    document.cookie = 'csrftoken=secret; path=/';
    const { xhr } = await start(core.uploadFiles, files, url);
    expect(xhr.headers['X-CSRFToken']).toBeUndefined();
});

test('sends CSRF token to an absolute same-origin URL', async () => {
    document.cookie = 'csrftoken=secret; path=/';
    const { xhr } = await start(core.uploadFiles, files, `${window.location.origin}/chat/upload/`);
    expect(xhr.headers['X-CSRFToken']).toBe('secret');
});

test('embedded compresses images while full-page keeps raw files', async () => {
    const bitmap = { width: 2000, height: 1000, close: jest.fn() };
    const createBitmap = jest.fn().mockResolvedValue(bitmap);
    const compressedCore = new Function('createImageBitmap', `${source('chat-core.js')}; return uploadFiles;`)(createBitmap);
    jest.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage: jest.fn() });
    jest.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(callback => callback(new Blob(['webp'], { type: 'image/webp' })));
    files[0] = new File(['png'], 'photo.png', { type: 'image/png' });
    const embedded = await start(compressedCore, files);
    expect(embedded.xhr.body.get('images').name).toBe('photo.webp');
    expect(createBitmap).toHaveBeenCalledTimes(1);
    const WsApi = new Function('uploadFiles', `${source('wsapi.js')}; return WsApi;`)(compressedCore);
    const fullPageApi = Object.create(WsApi.prototype);
    const fullPage = await start(fullPageApi.uploadFiles.bind(fullPageApi), files);
    expect(fullPage.xhr.body.get('images')).toBe(files[0]);
    expect(createBitmap).toHaveBeenCalledTimes(1);
});

test.each([null, 42].flatMap(id => ['http', 'json', 'error', 'timeout', 'abort'].map(event => [id, event])))('upload failure restores send button and retains draft for editing ID %s on %s', async (editingId, event) => {
    document.body.innerHTML = '<button class="send-message" disabled></button><textarea>draft</textarea>';
    const dom = {
        getFiles: () => files,
        clearFiles: jest.fn(),
        stopEditing: jest.fn(),
    };
    const api = { uploadFiles: ws.uploadFiles.bind(ws), sendMessage: jest.fn(), editMessage: jest.fn() };
    const submitSource = source('chat.js').split('async function onSubmitMessage(')[1];
    const submit = new Function('DOM_API', 'WS_API', `return async function onSubmitMessage(${submitSource}`)(dom, api);
    jest.spyOn(console, 'error').mockImplementation(() => {});
    const submission = submit('draft', editingId);
    const outcome = submission.then(() => 'resolved', () => 'rejected');
    await flush();
    MockXHR.instances.at(-1).respond(500, 'failed');
    await flush();
    expect(document.querySelector('.send-message').disabled).toBe(false);
    expect(await outcome).toBe('resolved');
    expect(api.sendMessage).not.toHaveBeenCalled();
    expect(api.editMessage).not.toHaveBeenCalled();
    expect(dom.clearFiles).not.toHaveBeenCalled();
    expect(dom.stopEditing).not.toHaveBeenCalled();
    expect(document.querySelector('textarea').value).toBe('draft');
});
