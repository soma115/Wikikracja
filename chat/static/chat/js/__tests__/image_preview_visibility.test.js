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

function loadEditingAttachments(previewContainer, previewDiv, attachments) {
    previewDiv.innerHTML = '';
    if (!attachments?.images?.length) {
        previewContainer.classList.add('d-none');
        return;
    }
    previewContainer.classList.remove('d-none');
    for (let i = 0; i < attachments.images.length; i++) {
        const filename = attachments.images[i];
        previewDiv.insertAdjacentHTML('beforeend', `<div class="image-preview-wrapper">
            <img class='image-preview' id='preview-existing-${i}' src='/media/uploads/${filename}' data-filename='${filename}'>
            <button class="btn btn-sm btn-danger remove-existing-attachment image-preview-remove"
                data-filename="${filename}" type="button">×</button>
        </div>`);
    }
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
