/**
 * @file richtext-core.js
 * Pure functions for sanitizing/rendering minimal rich text (b/i/u/br + auto-links).
 * Single source of truth shared by chat input and form RichTextWidget.
 *
 * Allowed tags must stay in sync with `zzz/richtext.py::ALLOWED_TAGS` on the backend.
 */

const ALLOWED_TAGS = ['b', 'i', 'u', 'br', 'a'];
const ALLOWED_ATTR = ['href', 'rel', 'target'];

/**
 * Serialize contenteditable HTML to sanitized HTML string.
 * Block elements (DIV/P/SECTION/...) are converted to <br> to preserve newlines.
 * @param {HTMLElement} inputEl
 * @returns {string}
 */
export function getInputHtml(inputEl) {
    if (!inputEl) return '';

    const BLOCK = new Set(['DIV', 'P', 'SECTION', 'BLOCKQUOTE', 'LI']);

    function escapeAttr(s) {
        return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    }

    function isBr(node) {
        return node && node.nodeType === Node.ELEMENT_NODE && node.tagName.toUpperCase() === 'BR';
    }

    // Serialize a list of sibling nodes, tracking whether the previous sibling
    // already emitted a trailing <br> so a following block doesn't double it.
    function serializeChildren(nodes) {
        return nodes.map((c, i) => serialize(c, i === 0, isBr(nodes[i - 1]))).join('');
    }

    function serialize(node, isFirst, prevWasBr) {
        if (node.nodeType === Node.TEXT_NODE) {
            // Legacy DB content (sprzed paste fix-a) może mieć surowe \n w tekście —
            // normalizujemy na <br>, żeby render po save nie produkował ghost empty lines.
            return node.textContent.replace(/\n/g, '<br>');
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        if (isBr(node)) return '<br>';
        const tag = node.tagName.toUpperCase();

        let children = Array.from(node.childNodes);
        if (BLOCK.has(tag)) {
            // Block-with-only-filler-<br>(s) = empty line (user pressed Enter on a blank line).
            // Without this special case, <div><br></div> would serialize to "<br><br>" and
            // produce ghost empty lines when pasted text is re-rendered.
            const isEmpty = children.every(c =>
                isBr(c) || (c.nodeType === Node.TEXT_NODE && !c.textContent)
            );
            if (isEmpty) return '<br>';
            // Non-empty block: strip trailing <br> filler the browser auto-inserts.
            while (children.length > 0 && isBr(children[children.length - 1])) {
                children.pop();
            }
        }

        const inner = serializeChildren(children);
        // A block opens a new line — but only if the previous sibling didn't already
        // emit a <br>. Browsers mix <br> and <div> when editing (e.g. "A<br><div>B</div>"),
        // which would otherwise serialize to "A<br><br>B" → ghost line above edited line.
        if (BLOCK.has(tag)) return ((isFirst || prevWasBr) ? '' : '<br>') + inner;
        if (tag === 'B') return `<b>${inner}</b>`;
        if (tag === 'I') return `<i>${inner}</i>`;
        if (tag === 'U') return `<u>${inner}</u>`;
        if (tag === 'A') {
            const href = node.getAttribute('href') || '';
            return `<a href="${escapeAttr(href)}">${inner}</a>`;
        }
        return inner;
    }

    const html = serializeChildren(Array.from(inputEl.childNodes));
    return (typeof DOMPurify !== 'undefined')
        ? DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR })
        : html.replace(/<(?!\/?(?:b|i|u|br|a)\b)[^>]*>/gi, '');
}

/**
 * Insert plain text at the current caret in a contenteditable, converting `\n`
 * (and normalized `\r\n` / `\r`) directly into <br> elements via DOM API.
 *
 * Bypasses execCommand('insertText'), which lets the browser auto-wrap pasted
 * text in <div> blocks with filler <br>s — that wrapping later serializes to
 * extra <br>s in getInputHtml and produces ghost empty lines on render.
 *
 * @param {HTMLElement} inputEl - contenteditable target
 * @param {string} text - plain text to insert (line endings get normalized)
 * @param {number} [maxLength=Infinity] - truncate to fit; counts current textContent
 */
export function insertPlainTextAtCaret(inputEl, text, maxLength = Infinity) {
    if (!inputEl) return;
    const sel = window.getSelection();
    if (!sel) return;

    const normalized = String(text ?? '').replace(/\r\n?/g, '\n');
    const selLen = sel.toString().length;
    const currentLen = (inputEl.textContent || '').length;
    const available = maxLength - currentLen + selLen;
    const toInsert = normalized.slice(0, Math.max(0, available));
    if (!toInsert) return;

    if (!sel.rangeCount) {
        inputEl.focus();
        const r = document.createRange();
        r.selectNodeContents(inputEl);
        r.collapse(false);
        sel.removeAllRanges();
        sel.addRange(r);
    }
    const range = sel.getRangeAt(0);
    range.deleteContents();

    const frag = document.createDocumentFragment();
    const lines = toInsert.split('\n');
    lines.forEach((line, i) => {
        if (i > 0) frag.appendChild(document.createElement('br'));
        if (line) frag.appendChild(document.createTextNode(line));
    });

    const lastChild = frag.lastChild;
    range.insertNode(frag);

    if (lastChild) {
        const newRange = document.createRange();
        newRange.setStartAfter(lastChild);
        newRange.collapse(true);
        sel.removeAllRanges();
        sel.addRange(newRange);
    }

    // Mirror execCommand behaviour: fire bubbling 'input' so existing listeners
    // (counter, draft autosave, hidden-input sync) update without per-call wiring.
    inputEl.dispatchEvent(new InputEvent('input', { bubbles: true }));
}

/**
 * Sanitize HTML for display + auto-linkify plain URLs.
 * @param {string} raw
 * @returns {string}
 */
export function formatMessage(raw) {
    const clean = (typeof DOMPurify !== 'undefined')
        ? DOMPurify.sanitize(raw, { ALLOWED_TAGS, ALLOWED_ATTR })
        : String(raw ?? '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // Linkify only URLs that are not already inside an <a> element.
    // `&amp;` matched as a unit (listed before char class) — keeps trailing ';' out of plain URL matches.
    const URL_REGEX = /(?:<a\b[^>]*>[^<]*<\/a>)|(https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:&amp;|[-a-zA-Z0-9()@:%_+.~#?&/=])*)/g;
    return clean.replace(URL_REGEX, (match, url) => {
        if (!url) return match; // pre-existing <a>...</a>, leave untouched
        const isInternal = url.replace(/^https?/, 'http').startsWith(window.location.origin.replace(/^https?/, 'http'));
        return `<a href="${url}"${isInternal ? '' : ' target="_blank" rel="noopener"'}>${url}</a>`;
    });
}

/**
 * Update char counter UI for an input element.
 * @param {HTMLElement} inputEl
 * @param {HTMLElement} counterEl
 * @param {HTMLElement} counterVal
 * @param {HTMLButtonElement} sendBtn
 * @param {number} maxLength
 */
export function updateCounter(inputEl, counterEl, counterVal, sendBtn, maxLength) {
    const len = (inputEl?.textContent || '').length;
    const rem = maxLength - len;
    if (counterVal) counterVal.textContent = rem;
    if (!counterEl) return;
    counterEl.classList.remove('counter--warn', 'counter--error');
    if (rem <= 0 || rem <= 10) counterEl.classList.add('counter--error');
    else if (rem <= 50) counterEl.classList.add('counter--warn');
    if (sendBtn) sendBtn.disabled = rem <= 0;
}

/**
 * Enter handling:
 *   Enter                  → new line (insertLineBreak)
 *   Ctrl/Cmd+Enter, Shift+Enter → send
 * @returns {boolean} true if handled
 */
export function handleEnterKey(e, submitCallback) {
    if (e.key !== 'Enter') return false;
    e.preventDefault();
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
        submitCallback();
    } else {
        document.execCommand('insertLineBreak');
    }
    return true;
}

/**
 * Visible text length for either contenteditable or textarea.
 * @returns {number}
 */
export function getVisibleTextLength(inputEl) {
    if (!inputEl) return 0;
    return inputEl.isContentEditable ? (inputEl.textContent || '').length : (inputEl.value || '').length;
}

let _pasteHandlerReady = false;

/**
 * Global clipboard image paste handler for all .message-input-rich elements.
 * Detects image in clipboard → injects into nearest .file-input within the same
 * .compose-box → triggers existing file preview/upload pipeline via change event.
 * Safe to call from multiple modules — registers only once.
 */
export function initGlobalPasteImageHandler() {
    if (_pasteHandlerReady) return;
    _pasteHandlerReady = true;
    document.addEventListener('paste', (e) => {
        if (!e.target.classList.contains('message-input-rich')) return;
        const imageItem = Array.from(e.clipboardData?.items ?? []).find(it => it.type.startsWith('image/'));
        if (!imageItem) return;
        e.preventDefault();
        const blob = imageItem.getAsFile();
        if (!blob) return;
        const fileInput = e.target.closest('.compose-box')?.querySelector('.file-input');
        if (!fileInput) return;
        const ext = blob.type.split('/')[1]?.split('+')[0] || 'png';
        const dt = new DataTransfer();
        // Preserve existing files so pasted images append rather than replace.
        for (const f of fileInput.files || []) dt.items.add(f);
        dt.items.add(new File([blob], `paste-${Date.now()}.${ext}`, { type: blob.type }));
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    });
}
