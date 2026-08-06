/**
 * @file form-autosave.js
 * Persist partially typed form data to sessionStorage so a page reload does
 * not lose the user's draft.  The draft is cleared when the form is actually
 * submitted.
 *
 * Usage: add `data-autosave="<unique-key>"` to the <form> element.
 */

(function () {
    'use strict';

    const STORAGE = window.sessionStorage;
    const KEY_PREFIX = 'wk:form:';
    const RICHTEXT_SELECTOR = '[data-richtext]';

    function storageKey(formKey, name) {
        return KEY_PREFIX + formKey + ':' + name;
    }

    function getRichTextEditable(hiddenInput) {
        const wrapper = hiddenInput.closest(RICHTEXT_SELECTOR);
        if (!wrapper) return null;
        return wrapper.querySelector('.richtext-input');
    }

    function getRichTextHidden(editable) {
        const wrapper = editable.closest(RICHTEXT_SELECTOR);
        if (!wrapper) return null;
        return wrapper.querySelector('input[type="hidden"]');
    }

    function saveValue(formKey, name, value) {
        if (value === undefined || value === null || value === '') {
            try {
                STORAGE.removeItem(storageKey(formKey, name));
            } catch (e) { /* storage unavailable */ }
            return;
        }
        try {
            STORAGE.setItem(storageKey(formKey, name), JSON.stringify(value));
        } catch (e) { /* quota / private mode */ }
    }

    function getValue(formKey, name) {
        try {
            const raw = STORAGE.getItem(storageKey(formKey, name));
            if (raw === null) return undefined;
            return JSON.parse(raw);
        } catch (e) {
            return undefined;
        }
    }

    function clearForm(formKey) {
        try {
            const prefix = storageKey(formKey, '');
            for (let i = STORAGE.length - 1; i >= 0; i--) {
                const key = STORAGE.key(i);
                if (key && key.startsWith(prefix)) {
                    STORAGE.removeItem(key);
                }
            }
        } catch (e) { /* storage unavailable */ }
    }

    function setInputValue(input, value) {
        const tag = input.tagName.toLowerCase();
        const type = input.type;

        if (tag === 'select') {
            if (input.multiple) {
                const values = Array.isArray(value) ? value : [value];
                Array.from(input.options).forEach(function (opt) {
                    opt.selected = values.indexOf(opt.value) !== -1;
                });
            } else {
                input.value = value;
            }
        } else if (type === 'checkbox') {
            input.checked = Boolean(value);
        } else if (type === 'radio') {
            input.checked = (input.value === String(value));
        } else if (type === 'file') {
            // File inputs cannot be restored programmatically.
        } else {
            input.value = (value == null) ? '' : value;
        }
    }

    function readInputValue(input) {
        const tag = input.tagName.toLowerCase();
        const type = input.type;

        if (tag === 'select') {
            if (input.multiple) {
                return Array.from(input.selectedOptions).map(function (o) { return o.value; });
            }
            return input.value;
        } else if (type === 'checkbox') {
            return input.checked;
        } else if (type === 'radio') {
            return input.checked ? input.value : undefined;
        } else if (type === 'file') {
            return undefined;
        }
        return input.value;
    }

    function initRichTextInput(formKey, input, editable) {
        const name = input.name;

        // Restore previously saved draft into both the hidden input and the
        // visible contenteditable.  richtext-input.js keeps them in sync on the
        // next user interaction.
        const stored = getValue(formKey, name);
        if (stored !== undefined && stored !== null) {
            input.value = stored;
            editable.innerHTML = stored;
        }

        function persist() {
            // richtext-input.js keeps the hidden input in sync on the same
            // contenteditable 'input' event.  Defer the save by one tick so we
            // always read the already-updated hidden value, regardless of the
            // order in which the two listeners were attached.
            setTimeout(function () {
                saveValue(formKey, name, input.value);
            }, 0);
        }

        editable.addEventListener('input', persist);
        editable.addEventListener('blur', persist);
    }

    function initPlainInput(formKey, input) {
        const name = input.name;

        const stored = getValue(formKey, name);
        if (stored !== undefined) {
            setInputValue(input, stored);
        }

        function persist() {
            const value = readInputValue(input);
            saveValue(formKey, name, value);
        }

        input.addEventListener('input', persist);
        input.addEventListener('change', persist);
    }

    function initForm(form) {
        if (form.dataset.autosaveInit === '1') return;
        const formKey = form.dataset.autosave;
        if (!formKey) return;
        form.dataset.autosaveInit = '1';

        const inputs = Array.from(form.querySelectorAll('input, textarea, select'));
        inputs.forEach(function (input) {
            if (input.name === 'csrfmiddlewaretoken') return;
            if (!input.name) return;

            const editable = getRichTextEditable(input);
            if (editable) {
                initRichTextInput(formKey, input, editable);
            } else {
                initPlainInput(formKey, input);
            }
        });

        form.addEventListener('submit', function () {
            clearForm(formKey);
        });
    }

    function initAll(root) {
        (root || document).querySelectorAll('form[data-autosave]').forEach(initForm);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () { initAll(); });
    } else {
        initAll();
    }
})();
