/**
 * @file dom-utils.js
 * Shared DOM/network helpers and declarative `data-tw-*` click/submit actions.
 * Loaded before app.js and ES modules — classic script, exposes window.* API.
 *
 * Attributes:
 *   data-tw-stop-propagation          - click does not bubble to delegated handlers
 *                                       (e.g. [data-detail-url] card navigation)
 *   data-tw-back                      - history.back(); combined with
 *     data-tw-back-skip-referrer="/edit/" it goes history.go(-2) when the
 *     referrer contains the given fragment
 *   data-tw-remove="selector"         - removes closest matching ancestor
 *   data-tw-submit-once               - disables the button and submits its form
 *   data-tw-confirm="message"         - on a <form>: cancels submit unless confirmed
 */
(function () {
    'use strict';

    /** Escapes HTML special characters for safe interpolation into markup. */
    window.escapeHtml = function escapeHtml(unsafe) {
        return String(unsafe == null ? '' : unsafe)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    };

    /** Reads the Django CSRF token from the `csrftoken` cookie. */
    window.getCSRFToken = function getCSRFToken() {
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
        return match ? decodeURIComponent(match[1]) : '';
    };

    /**
     * fetch() with CSRF header and same-origin credentials.
     * `body`: plain object → JSON; FormData/URLSearchParams/string → sent as-is.
     */
    window.apiFetch = function apiFetch(url, options) {
        const opts = options || {};
        const body = opts.body;
        const headers = Object.assign({'X-CSRFToken': window.getCSRFToken()}, opts.headers);
        const fetchOpts = Object.assign({
            method: 'GET',
            credentials: 'same-origin',
            headers: headers,
        }, opts.fetchOptions);
        if (body !== undefined && body !== null) {
            if (body instanceof FormData || body instanceof URLSearchParams || typeof body === 'string') {
                fetchOpts.body = body;
            } else {
                headers['Content-Type'] = 'application/json';
                fetchOpts.body = JSON.stringify(body);
            }
        }
        return fetch(url, fetchOpts);
    };

    /**
     * Reads a `{% json_script %}` / `<script type="application/json">` payload.
     * Returns `fallback` (default null) when the element is missing or invalid.
     */
    window.readJsonScript = function readJsonScript(id, fallback) {
        const el = document.getElementById(id);
        if (!el) return fallback === undefined ? null : fallback;
        try {
            return JSON.parse(el.textContent);
        } catch (err) {
            return fallback === undefined ? null : fallback;
        }
    };

    /** Classic debounce: delays fn until `ms` after the last call. */
    window.debounce = function debounce(fn, ms) {
        let timer = null;
        return function debounced() {
            const args = arguments;
            const self = this;
            clearTimeout(timer);
            timer = setTimeout(function () { fn.apply(self, args); }, ms);
        };
    };

    // ── Delegated data-tw-* actions ─────────────────────────────────────────
    // Registered before app.js: stopImmediatePropagation keeps clicks on
    // [data-tw-stop-propagation] away from later document-level delegates
    // (e.g. [data-detail-url] card navigation) — same as the old inline
    // onclick="event.stopPropagation()".
    document.addEventListener('click', function (e) {
        const stopEl = e.target.closest && e.target.closest('[data-tw-stop-propagation]');
        if (stopEl) {
            e.stopImmediatePropagation();
            return;
        }
        const backEl = e.target.closest && e.target.closest('[data-tw-back]');
        if (backEl) {
            e.preventDefault();
            const skip = backEl.getAttribute('data-tw-back-skip-referrer');
            if (skip && document.referrer.indexOf(skip) !== -1) window.history.go(-2);
            else window.history.back();
            return;
        }
        const removeEl = e.target.closest && e.target.closest('[data-tw-remove]');
        if (removeEl) {
            const target = removeEl.closest(removeEl.getAttribute('data-tw-remove'));
            if (target) target.remove();
            return;
        }
        const onceEl = e.target.closest && e.target.closest('[data-tw-submit-once]');
        if (onceEl) {
            e.preventDefault();
            onceEl.disabled = true;
            if (onceEl.form) onceEl.form.submit();
        }
    });

    document.addEventListener('submit', function (e) {
        const msg = e.target.getAttribute && e.target.getAttribute('data-tw-confirm');
        if (msg && !window.confirm(msg)) e.preventDefault();
    });
})();
