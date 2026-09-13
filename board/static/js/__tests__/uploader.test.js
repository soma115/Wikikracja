/**
 * @jest-environment jsdom
 */
const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(path.join(__dirname, '..', 'uploader.js'), 'utf8');

class MockDataTransfer {
    constructor() {
        this.items = { add: file => this.files.push(file) };
        this.files = [];
    }
}

function loadUploader() {
    const tinymce = { init: jest.fn() };
    return new Function('tinymce', 'DataTransfer', `${source}; return initAttachmentUploader;`)(tinymce, MockDataTransfer);
}

function createUploader() {
    document.body.innerHTML = `
        <div>
            <label data-file-upload data-max-size-mb="1" data-max-size-error="File is too large">
                <input class="tw-file-upload-input" type="file" multiple>
            </label>
            <div data-file-upload-list></div>
            <div data-file-upload-error hidden></div>
        </div>
    `;
    const input = document.querySelector('input');
    Object.defineProperty(input, 'files', { configurable: true, writable: true, value: [] });
    loadUploader()(document.querySelector('[data-file-upload]'));
    return { input, dropzone: document.querySelector('[data-file-upload]'), list: document.querySelector('[data-file-upload-list]') };
}

test('keeps files from repeated selection and allows removing one', () => {
    const { input, list } = createUploader();
    const first = new File(['a'], 'first.txt', { type: 'text/plain', lastModified: 1 });
    const second = new File(['bb'], 'second.txt', { type: 'text/plain', lastModified: 2 });

    input.files = [first];
    input.dispatchEvent(new Event('change'));
    input.files = [second];
    input.dispatchEvent(new Event('change'));

    expect([...list.querySelectorAll('.tw-file-upload-name')].map(node => node.textContent)).toEqual(['first.txt', 'second.txt']);

    list.querySelector('[data-file-index="0"]').click();
    expect([...list.querySelectorAll('.tw-file-upload-name')].map(node => node.textContent)).toEqual(['second.txt']);
});

test('replaces the current file in single-file mode', () => {
    document.body.innerHTML = `
        <div>
            <label data-file-upload data-file-upload-single data-max-size-mb="1">
                <input class="tw-file-upload-input" type="file">
            </label>
            <div data-file-upload-list></div>
            <div data-file-upload-error hidden></div>
            <div data-file-upload-current></div>
        </div>
    `;
    const input = document.querySelector('input');
    Object.defineProperty(input, 'files', { configurable: true, writable: true, value: [] });
    loadUploader()(document.querySelector('[data-file-upload]'));
    const first = new File(['a'], 'first.png');
    const second = new File(['b'], 'second.png');

    input.files = [first];
    input.dispatchEvent(new Event('change'));
    input.files = [second];
    input.dispatchEvent(new Event('change'));

    expect(document.querySelectorAll('.tw-file-upload-name')).toHaveLength(1);
    expect(document.querySelector('.tw-file-upload-name').textContent).toBe('second.png');
});

test('adds dropped files and rejects oversized files', () => {
    const { dropzone, list } = createUploader();
    const accepted = new File(['ok'], 'accepted.txt');
    const oversized = new File(['too big'], 'oversized.txt');
    Object.defineProperty(oversized, 'size', { value: 1_000_001 });

    const drop = new Event('drop', { bubbles: true });
    Object.defineProperty(drop, 'dataTransfer', { value: { files: [accepted, oversized] } });
    dropzone.dispatchEvent(drop);

    expect(list.querySelector('.tw-file-upload-name').textContent).toBe('accepted.txt');
    expect(document.querySelector('[data-file-upload-error]').hidden).toBe(false);
});
