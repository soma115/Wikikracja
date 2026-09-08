/**
 * @file toast.js
 * Shared lightweight toast helper: window.showToast(message).
 * Renders a transient `tw-toast` element (auto-dismiss ~2.5s).
 * Used by chat modules and app.js — single global implementation.
 */
(function () {
    'use strict';

    window.showToast = function showToast(message) {
        const existing = document.getElementById('tw-toast');
        if (existing) existing.remove();
        const toast = document.createElement('div');
        toast.id = 'tw-toast';
        toast.className = 'tw-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('tw-toast--visible'));
        setTimeout(() => {
            toast.classList.remove('tw-toast--visible');
            setTimeout(() => toast.remove(), 300);
        }, 2500);
    };
})();
