/**
 * @file form-autosave.js
 * Persist partially typed form data to localStorage so navigation or a page
 * reload does not lose the user's draft.  Drafts are cleared on submit or
 * when a form explicitly marks a cancel/back action.
 */

(function () {
    'use strict';

    let STORAGE = null;
    try {
        STORAGE = window.localStorage;
    } catch (error) {
        // Storage may be blocked by browser privacy settings.
    }
    const KEY_PREFIX = 'wk:form:v2:';
    const RICHTEXT_SELECTOR = '[data-richtext]';

    function storageKey(form, index) {
        const action = new URL(form.getAttribute('action') || window.location.href, window.location.href);
        action.hash = '';
        const userId = document.documentElement.dataset.userId || 'anonymous';
        return KEY_PREFIX + encodeURIComponent(userId + ':' + action.href) + ':' + index;
    }

    function isIgnored(form) {
        return form.dataset.autosaveIgnore === '1'
            || form.method.toLowerCase() === 'get'
            || form.closest('.tw-chat-page') !== null
            || form.closest('[data-chat-form]') !== null;
    }

    function isPassword(input) {
        return input.type && input.type.toLowerCase() === 'password';
    }

    function isSupported(input) {
        if (!input.name || input.name === 'csrfmiddlewaretoken' || isPassword(input)) return false;
        if (input.disabled || ['file', 'submit', 'button', 'reset', 'image'].includes(input.type)) return false;
        return ['input', 'textarea', 'select'].includes(input.tagName.toLowerCase());
    }

    function readValue(input) {
        const type = (input.type || '').toLowerCase();
        if (type === 'checkbox') return input.checked;
        if (type === 'radio') return input.checked ? input.value : undefined;
        if (input.tagName.toLowerCase() === 'select' && input.multiple) {
            return Array.from(input.selectedOptions).map(option => option.value);
        }
        return input.value;
    }

    function setValue(input, value) {
        const type = (input.type || '').toLowerCase();
        if (type === 'checkbox') {
            input.checked = Boolean(value);
        } else if (type === 'radio') {
            input.checked = input.value === String(value);
        } else if (input.tagName.toLowerCase() === 'select' && input.multiple) {
            const values = Array.isArray(value) ? value : [value];
            Array.from(input.options).forEach(option => {
                option.selected = values.includes(option.value);
            });
        } else {
            input.value = value == null ? '' : value;
        }
    }

    function readForm(form) {
        const values = {};
        form.querySelectorAll('input, textarea, select').forEach(input => {
            if (!isSupported(input)) return;
            const value = readValue(input);
            if (value !== undefined) values[input.name] = value;
        });

        form.querySelectorAll(`${RICHTEXT_SELECTOR} input[type="hidden"]`).forEach(input => {
            if (input.name && input.name !== 'csrfmiddlewaretoken' && !isPassword(input)) {
                values[input.name] = input.value;
            }
        });
        return values;
    }

    function restoreForm(form, values) {
        form.querySelectorAll('input, textarea, select').forEach(input => {
            if (isSupported(input) && Object.prototype.hasOwnProperty.call(values, input.name)) {
                setValue(input, values[input.name]);
            }
        });

        form.querySelectorAll(`${RICHTEXT_SELECTOR} input[type="hidden"]`).forEach(input => {
            const editable = input.closest(RICHTEXT_SELECTOR)?.querySelector('.tw-richtext-input');
            if (editable && Object.prototype.hasOwnProperty.call(values, input.name)) {
                input.value = values[input.name];
                editable.innerHTML = values[input.name];
            }
        });
    }

    function readDraft(key) {
        try {
            const draft = STORAGE.getItem(key);
            return draft ? JSON.parse(draft) : null;
        } catch (error) {
            return null;
        }
    }

    function saveDraft(key, form) {
        try {
            const values = readForm(form);
            if (Object.keys(values).length) STORAGE.setItem(key, JSON.stringify(values));
            else STORAGE.removeItem(key);
        } catch (error) {
            // Storage may be unavailable or full; form submission still works.
        }
    }

    function clearDraft(key) {
        try {
            STORAGE.removeItem(key);
        } catch (error) {
            // Storage may be unavailable.
        }
    }

    function initForm(form, index) {
        if (form.dataset.autosaveInit === '1' || isIgnored(form)) return;
        form.dataset.autosaveInit = '1';
        const key = storageKey(form, index);
        form.dataset.autosaveKey = key;
        const draft = readDraft(key);
        if (draft) restoreForm(form, draft);

        const persist = () => saveDraft(key, form);
        form.addEventListener('input', persist);
        form.addEventListener('change', persist);
        form.addEventListener('submit', () => clearDraft(key));
        form.addEventListener('click', event => {
            if (event.target.closest('[data-autosave-clear], [data-tw-back]')) clearDraft(key);
        });
    }

    function initAll(root) {
        const forms = Array.from((root || document).querySelectorAll('form'));
        const keys = new Map();
        forms.forEach(form => {
            const action = new URL(form.getAttribute('action') || window.location.href, window.location.href).href;
            const index = keys.get(action) || 0;
            keys.set(action, index + 1);
            initForm(form, index);
        });
    }

    function clearRelatedDrafts(control) {
        const scope = control.closest('form, .tw-card, main, body');
        scope.querySelectorAll('form[data-autosave-key]').forEach(form => clearDraft(form.dataset.autosaveKey));
    }

    document.addEventListener('click', event => {
        const control = event.target.closest('[data-autosave-clear], [data-tw-back]');
        if (control) clearRelatedDrafts(control);
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initAll());
    } else {
        initAll();
    }
})();
