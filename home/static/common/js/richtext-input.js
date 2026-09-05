/**
 * @file richtext-input.js
 * Self-initializing rich-text widget for Django forms.
 *
 * Loaded as a regular (non-module) <script> via Django Widget Media so it can
 * also drive forms whose templates don't opt into ES modules. The actual
 * sanitization/serialization logic is dynamic-imported from richtext-core.js
 * (the canonical module shared with chat) to avoid duplication.
 *
 * Auto-discovers any element marked with `data-richtext` on the page, wires up
 * a B/I/U toolbar with Ctrl+B/I/U shortcuts, and keeps a sibling hidden input
 * in sync so the contenteditable's HTML is submitted as a normal form field.
 */

(function () {
    'use strict';

    const CORE_URL = '/static/common/js/richtext-core.js';
    let corePromise = null;
    function loadCore() {
        if (!corePromise) corePromise = import(CORE_URL);
        return corePromise;
    }

    async function initOne(wrapper) {
        if (wrapper.dataset.richtextInit === '1') return;
        wrapper.dataset.richtextInit = '1';

        const { getInputHtml, updateCounter, insertPlainTextAtCaret } = await loadCore();

        const input = wrapper.querySelector('.richtext-input');
        const hidden = wrapper.querySelector('input[type="hidden"]');
        const toolbar = wrapper.querySelector('.fmt-toolbar');
        const counterEl = wrapper.querySelector('.msg-counter');
        const counterVal = wrapper.querySelector('.msg-counter-val');
        const maxLength = parseInt(wrapper.dataset.maxLength || '0', 10) || Infinity;

        if (!input || !hidden) return;

        function sync() {
            hidden.value = getInputHtml(input);
            if (counterEl) updateCounter(input, counterEl, counterVal, null, maxLength);
        }

        function updateToolbarState() {
            if (!toolbar) return;
            toolbar.querySelectorAll('.fmt-btn[data-cmd]').forEach(btn => {
                try {
                    btn.classList.toggle('active', document.queryCommandState(btn.dataset.cmd));
                } catch (_) { /* queryCommandState can throw on some browsers */ }
            });
        }

        input.addEventListener('input', sync);
        input.addEventListener('blur', sync);

        // Block typing/pasting beyond maxLength; formatting commands and deletions are allowed.
        input.addEventListener('beforeinput', (e) => {
            if (!maxLength || maxLength === Infinity) return;
            if (!e.inputType || e.inputType.startsWith('delete') || e.inputType.startsWith('format') ||
                e.inputType === 'historyUndo' || e.inputType === 'historyRedo' ||
                e.inputType === 'insertFromPaste' || e.inputType === 'insertFromDrop') {
                return;
            }
            const sel = window.getSelection();
            const selLen = sel ? sel.toString().length : 0;
            const currentLen = getInputHtml(input).length;
            let extra = 0;
            if (e.data) {
                extra = e.data.length;
            } else if (e.inputType === 'insertLineBreak' || e.inputType === 'insertParagraph') {
                extra = 4; // <br>
            }
            if (currentLen - selLen + extra > maxLength) {
                e.preventDefault();
            }
        });

        document.addEventListener('selectionchange', () => {
            if (document.activeElement === input) updateToolbarState();
        });

        // Plain-text paste — strips formatting from clipboard, respecting maxLength.
        // insertPlainTextAtCaret turns \n into explicit <br> nodes (not browser-wrapped
        // <div> blocks that serialize to extra <br>s) and fires its own 'input' event
        // so the existing input listener handles sync.
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const pasted = (e.clipboardData || window.clipboardData).getData('text');
            insertPlainTextAtCaret(input, pasted, maxLength);
        });

        input.addEventListener('keydown', (e) => {
            const mod = e.ctrlKey || e.metaKey;
            if (mod && e.key === 'b') { e.preventDefault(); document.execCommand('bold'); updateToolbarState(); sync(); return; }
            if (mod && e.key === 'i') { e.preventDefault(); document.execCommand('italic'); updateToolbarState(); sync(); return; }
            if (mod && e.key === 'u') { e.preventDefault(); document.execCommand('underline'); updateToolbarState(); sync(); return; }
        });

        if (toolbar) {
            toolbar.addEventListener('click', (e) => {
                const btn = e.target.closest('.fmt-btn[data-cmd]');
                if (!btn) return;
                e.preventDefault();
                input.focus();
                document.execCommand(btn.dataset.cmd);
                updateToolbarState();
                sync();
            });
        }

        // On submit of the parent form, ensure latest HTML is in the hidden input.
        const form = wrapper.closest('form');
        if (form) form.addEventListener('submit', sync, { capture: true });

        sync();
    }

    function initAll(root) {
        (root || document).querySelectorAll('[data-richtext]').forEach(initOne);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initAll());
    } else {
        initAll();
    }

    window.RichTextInput = { initAll, initOne };
})();
