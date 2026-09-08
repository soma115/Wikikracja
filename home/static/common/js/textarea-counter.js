/**
 * @file textarea-counter.js
 * Live character counter for plain <textarea> fields with a `maxlength`
 * attribute. Counts `.value.length` directly — exactly what gets submitted,
 * so it always matches the backend's max_length validation.
 *
 * Auto-discovers `textarea[data-charcounter]` on the page.
 */

(function () {
    'use strict';

    function initOne(textarea) {
        if (textarea.dataset.charcounterInit === '1') return;
        textarea.dataset.charcounterInit = '1';

        const wrapper = textarea.closest('.tw-textarea-counter-wrapper');
        const counterEl = wrapper ? wrapper.querySelector('.tw-msg-counter') : null;
        const counterVal = wrapper ? wrapper.querySelector('.tw-msg-counter-val') : null;
        const maxLength = parseInt(textarea.getAttribute('maxlength') || '0', 10) || Infinity;
        if (!counterVal) return;

        function sync() {
            const rem = maxLength - textarea.value.length;
            counterVal.textContent = rem;
            if (counterEl) window.applyCounterState(counterEl, rem);
        }

        textarea.addEventListener('input', sync);
        sync();
    }

    function initAll(root) {
        (root || document).querySelectorAll('textarea[data-charcounter]').forEach(initOne);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => initAll());
    } else {
        initAll();
    }

    window.TextareaCounter = { initAll, initOne };
})();
