/**
 * @file char-counter.js
 * Shared state contract for message-length counters:
 *   remaining <= 10  -> tw-msg-counter--error
 *   remaining <= 50  -> tw-msg-counter--warn
 * Single source for richtext-core.js, textarea-counter.js and chat handlers.
 */
(function () {
    'use strict';

    window.applyCounterState = function (counterEl, remaining) {
        counterEl.classList.remove('tw-msg-counter--warn', 'tw-msg-counter--error');
        if (remaining <= 10) counterEl.classList.add('tw-msg-counter--error');
        else if (remaining <= 50) counterEl.classList.add('tw-msg-counter--warn');
    };
})();
