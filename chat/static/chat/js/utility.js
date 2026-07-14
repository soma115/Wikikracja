/**
 * @file
 * Utility functions and helper classes for the chat application.
 * Includes: notification handling, date/time formatting, HTML escaping, Lock class, and more.
 */

/**
 * Helper function to query elements
 * @param {string} selector - CSS selector
 * @param {Element|Document} [context=document] - Context to search within
 * @returns {Element|null}
 */
export function $(selector, context = document) {
    return context.querySelector(selector);
}

/**
 * Helper function to query all elements
 * @param {string} selector - CSS selector
 * @param {Element|Document} [context=document] - Context to search within
 * @returns {NodeList}
 */
export function $$(selector, context = document) {
    return context.querySelectorAll(selector);
}

/**
 * Displays a desktop notification for chat events
 * @param {Object} notif - Notification data
 * @param {string} notif.title - Notification title
 * @param {string} notif.body - Notification body text
 * @param {string} notif.link - Notification icon image link
 * @param {number} [notif.room_id] - Optional room ID
 */
export function makeNotification(notif) {
    changeIcon('/static/chat/images/notification-on.ico');
    try {
        new Audio('/static/chat/sounds/notification.mp3').play();
    } catch (e) { }

    if (Notification?.permission === 'granted') {
        let notification = new Notification(notif.title, {
            body: notif.body,
            icon: notif.link ?? '/favicon.ico',
            badge: notif.badge ?? '/favicon.ico',
            requireInteraction: true,
        });
        notification.onclick = function() {
            if (window.location.pathname !== "/chat/") {
                window.location.href = "/chat/#room_id=" + notif.room_id;
            }
        };
    }
}

// Favicon href as rendered by the server (respects custom brand mark) — captured lazily
// on first use, before any notification badge overwrites it.
let originalIconHref = null;

/**
 * Removes notification indicator (restores the site's original favicon,
 * which may be a custom brand mark instead of the default icon)
 */
export function removeNotification() {
    if (originalIconHref === null) {
        originalIconHref = $("link[rel~='icon']")?.href ?? '/static/chat/images/notification-off.ico';
    }
    changeIcon(originalIconHref);
}

/**
 * Changes the page favicon
 * @param {string} resource - URL to the icon image
 */
export function changeIcon(resource) {
    let link = $("link[rel~='icon']");
    if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.getElementsByTagName('head')[0].appendChild(link);
    }
    if (originalIconHref === null) {
        originalIconHref = link.href;
    }
    link.href = resource;
}

/**
 * Formats a timestamp into a human-readable date string
 * Shows relative dates (Today, Yesterday) for recent dates
 * @param {number|string|Date} someDateTimeStamp - Unix timestamp or Date object
 * @returns {string} - Formatted date string (e.g., "Today", "Yesterday", "Jan 15")
 */
export function formatDate(someDateTimeStamp) {
    let fulldays = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    let months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    let dt = new Date(someDateTimeStamp),
        date = dt.getDate(),
        month = _(months[dt.getMonth()]),
        timeDiff = someDateTimeStamp - Date.now(),
        diffDays = new Date().getDate() - date,
        diffMonths = new Date().getMonth() - dt.getMonth(),
        diffYears = new Date().getFullYear() - dt.getFullYear();

    if (diffYears === 0 && diffDays === 0 && diffMonths === 0) {
        return _("Today");
    } else if (diffYears === 0 && diffMonths === 0 && diffDays === 1) {
        return _("Yesterday");
    } else if (diffYears === 0 && diffMonths === 0 && diffDays === -1) {
        return _("Tomorrow");
    } else if (diffYears === 0 && diffMonths === 0 && (diffDays > 1 && diffDays < 7)) {
        return _(fulldays[dt.getDay()]);
    } else if (diffYears >= 1) {
        return month + " " + date + ", " + new Date(someDateTimeStamp).getFullYear();
    } else {
        return month + " " + date;
    }
}

/**
 * Formats a timestamp into a time string (HH:MM)
 * @param {number|string|Date} ts - Unix timestamp or Date object
 * @returns {string} - Formatted time string (e.g., "14:30")
 */
export function formatTime(ts) {
    let date = new Date(ts);
    let hours = date.getHours();
    let minutes = "0" + date.getMinutes();
    return hours + ':' + minutes.substr(-2);
}

/**
 * Formats a timestamp into date and time string
 * @param {number|string|Date} ts - Unix timestamp or Date object
 * @returns {string} - Formatted date and time (e.g., "Jan 15 14:30")
 */
export function formatDateTime(ts) {
    let date = formatDate(ts);
    let time = formatTime(ts);
    return date + ' ' + time;
}

/**
 * Escapes HTML special characters to prevent XSS
 * @param {string} unsafe - Unsafe string that may contain HTML
 * @returns {string} - HTML-safe string
 */
export function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/**
 * Lock class for managing asynchronous mutual exclusion
 * Prevents concurrent operations on shared resources (e.g., room joins)
 * @class
 */
export class Lock {
    /**
     * Constructs a new Lock instance
     */
    constructor() {
        this.__locked = false;
        this.promises = [];
    }

    /**
     * Acquires the lock
     * @throws {Error} If lock is already locked
     */
    lock() {
        if (this.__locked) {
            throw new Error("[LockError] Locking locked lock");
        }
        this.__locked = true;
    }

    /**
     * Releases the lock and resolves all waiting promises
     * @throws {Error} If lock is not currently locked
     */
    unlock() {
        if (!this.__locked) {
            throw new Error("[LockError] Unlocking unlocked lock");
        }
        this.__locked = false;
        for (let resolver of this.promises) {
            resolver();
        }
        this.promises = [];
    }

    /**
     * Checks if lock is currently held
     * @returns {boolean} - true if locked, false otherwise
     */
    locked() {
        return this.__locked;
    }

    /**
     * Waits for lock to become available
     * @returns {Promise<void>} - Resolves when lock is acquired
     */
    wait() {
        let ctx = this;
        return new Promise((resolve, reject) => {
            ctx.promises.push(resolve);
        })
    }
}

/**
 * Asynchronously gets the dimensions of an image
 * @param {string} src - Image URL
 * @returns {Promise<{w: number, h: number}>} - Promise resolving to width and height
 */
export async function getImageSize(src) {
    const img = new Image();
    return new Promise((resolve, reject) => {
        img.onload = function() {
            resolve({ w: this.width, h: this.height });
        }
        img.src = src;
    })
}

/**
 * Parses a query string into an object
 * @param {string} str - Query string (e.g., "key1=value1&key2=value2")
 * @returns {Object.<string, string>} - Parsed key-value pairs (decoded)
 */
export function parseParms(str) {
    let pieces = str.split("&"),
        data = {},
        i, parts;
    // process each query pair
    for (i = 0; i < pieces.length; i++) {
        parts = pieces[i].split("=");
        if (parts.length < 2) {
            parts.push("");
        }
        data[decodeURIComponent(parts[0])] = decodeURIComponent(parts[1]);
    }
    return data;
}

/**
 * Translation function for i18n
 * Returns translated string if available, otherwise original
 * @param {string} s - String to translate
 * @returns {string} - Translated string or original if translation not found
 */
export function _(s) {
    // typeof never throws for undeclared vars — safe in modules without TRANSLATIONS defined
    const T = typeof TRANSLATIONS !== 'undefined' ? TRANSLATIONS : {};
    const translation = T[s];
    if (translation !== undefined) {
        return translation;
    }
    return s;
}

/**
 * Sets the caret (cursor) position within a text input or textarea
 * @param {HTMLInputElement|HTMLTextAreaElement} elem - The input element
 * @param {number} caretPos - Desired caret position (character offset)
 */
export function setCaretPosition(elem, caretPos) {
    if (elem == null) {
        return
    }

    if (elem.createTextRange) {
        var range = elem.createTextRange();
        range.move('character', caretPos);
        range.select();
    } else {
        if (elem.selectionStart) {
            elem.focus();
            elem.setSelectionRange(caretPos, caretPos);
        } else {
            elem.focus();
        }
    }
}