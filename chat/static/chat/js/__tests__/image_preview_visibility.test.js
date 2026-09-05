/**
 * @jest-environment jsdom
 *
 * Testy regresyjne widoczności kontenera podglądu obrazków w czacie.
 *
 * Bug: .image-preview-container ma klasę Bootstrap d-none, która definiuje
 * `display: none !important` w darkly.css. Kod próbował pokazywać/chować
 * kontener przez `style.display = '' / 'none'`, co jest nadpisywane przez
 * `!important` z klasy. Skutek: podgląd obrazków przy dodawaniu oraz
 * istniejących załączników podczas edycji nie był widoczny, więc nie dało
 * się ich usunąć.
 *
 * Fix: używać `classList.remove('d-none')` / `classList.add('d-none')`.
 */

// ── wierna kopia logiki z domapi.js (synchronizować przy zmianie!) ─────────

const fs = require('fs');
const path = require('path');
const ejs = require('../ejs.min.js');

const domSource = fs.readFileSync(path.join(__dirname, '..', 'domapi.js'), 'utf8')
    .replace(/^import\s+[\s\S]*?from\s+['"][^'"]+['"];\s*/gm, '')
    .replace('export default class DomApi', 'class DomApi');
const DomApi = new Function('$', '$$', `${domSource}; return DomApi;`)(
    (selector, context = document) => context.querySelector(selector),
    (selector, context = document) => context.querySelectorAll(selector)
);
const templateSource = fs.readFileSync(path.join(__dirname, '..', 'templates.js'), 'utf8')
    .replace(/^import[^\n]+\n/gm, '').replace(/export const /g, 'const ');
const renderMessage = new Function('_', 'ejs', `${templateSource}; return Message;`)(text => text, ejs);

function loadEditingAttachments(previewContainer, previewDiv, attachments) {
    const api = new DomApi();
    api.getPreviewContainer = () => previewContainer;
    api.getPreviewDiv = () => previewDiv;
    api.loadEditingAttachments(1, attachments);
}

function clearFiles(previewContainer, previewDiv) {
    previewDiv.innerHTML = '';
    previewContainer.classList.add('d-none');
}

// ── setup ──────────────────────────────────────────────────────────────────

function setupPreview() {
    document.body.innerHTML = `
        <div class='image-preview-container d-none'>
            <div class='preview-images'></div>
        </div>
    `;
    return {
        previewContainer: document.querySelector('.image-preview-container'),
        previewDiv: document.querySelector('.preview-images'),
    };
}

beforeEach(() => { document.body.innerHTML = ''; });

// ── testy ──────────────────────────────────────────────────────────────────

test('loadEditingAttachments pokazuje kontener usuwając d-none', () => {
    const { previewContainer, previewDiv } = setupPreview();
    loadEditingAttachments(previewContainer, previewDiv, { images: ['foo.jpg'] });
    expect(previewContainer.classList.contains('d-none')).toBe(false);
    expect(previewDiv.children.length).toBe(1);
});

test('loadEditingAttachments chowa kontener gdy brak obrazków', () => {
    const { previewContainer, previewDiv } = setupPreview();
    loadEditingAttachments(previewContainer, previewDiv, { images: [] });
    expect(previewContainer.classList.contains('d-none')).toBe(true);
    expect(previewDiv.children.length).toBe(0);
});

test('clearFiles czyści podgląd i chowa kontener', () => {
    const { previewContainer, previewDiv } = setupPreview();
    previewDiv.innerHTML = '<div class="image-preview-wrapper">x</div>';
    clearFiles(previewContainer, previewDiv);
    expect(previewDiv.innerHTML).toBe('');
    expect(previewContainer.classList.contains('d-none')).toBe(true);
});

const unsafeFilename = `folder' data-review='marker/image.webp`;

function expectSafeImage(image, filename) {
    expect(image.hasAttribute('data-review')).toBe(false);
    const encoded = image.getAttribute('src').slice('/media/uploads/'.length);
    expect(encoded).not.toContain('/');
    expect(decodeURIComponent(encoded)).toBe(filename);
}

test('editing preview preserves filenames as data without injecting markup', () => {
    const { previewContainer, previewDiv } = setupPreview();
    loadEditingAttachments(previewContainer, previewDiv, { images: [unsafeFilename] });
    const image = previewDiv.querySelector('img');
    expectSafeImage(image, unsafeFilename);
    expect(image.dataset.filename).toBe(unsafeFilename);
    expect(previewDiv.querySelector('button').dataset.filename).toBe(unsafeFilename);
    expect(previewDiv.querySelectorAll('[data-review]')).toHaveLength(0);
});

test('live attachment updates encode filenames and do not inject attributes', () => {
    document.body.innerHTML = '<div class="message"><div class="attachment-image-container"></div></div>';
    const api = new DomApi();
    api.getMessageDiv = () => document.querySelector('.message');
    api.updateMessageAttachments(1, { images: [unsafeFilename] });
    expectSafeImage(document.querySelector('img'), unsafeFilename);
    expect(api.getMessageAttachments(1)).toEqual({ images: [unsafeFilename] });
});

test('initial message template safely renders attachment filenames', () => {
    document.body.innerHTML = renderMessage({
        own: false, message_id: 1, room_id: 1, reply_to: null,
        attachments: { images: [unsafeFilename] }, raw_message: '', message: '',
        username: 'user', latest_ts: '', edited: false, upvotes: 0, downvotes: 0,
        type: 'private', your_reactions: [], reactions: {}, read_by: [],
    });
    expectSafeImage(document.querySelector('.attached-image'), unsafeFilename);
});
