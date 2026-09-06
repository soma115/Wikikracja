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
 * Reads the Django CSRF token from the `csrftoken` cookie.
 * @returns {string}
 */
export function getCSRFToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]*)/);
    return match ? decodeURIComponent(match[1]) : '';
}

/**
 * Sends a "delivery ack" back to the server so notification reliability can be
 * debugged: the server logs a `notification_id` when it builds/sends a
 * notification (see zzz/notifications.py, chat/consumers.py), and this tells it
 * what actually happened on the client (shown, skipped, errored, or clicked).
 * Fire-and-forget — never throws, never blocks the caller.
 * @param {Object} info
 * @param {string} [info.notification_id] - Server-assigned notification ID.
 * @param {string} [info.tag] - Notification tag, if known.
 * @param {'shown'|'skipped'|'error'|'clicked'} info.status
 * @param {string} info.source - Which code path produced this ack, e.g. 'ws-foreground'.
 * @param {string} [info.reason] - Free-form explanation (mainly for skipped/error).
 */
export function sendNotificationAck(info) {
    try {
        fetch('/chat/api/push/ack/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({ user_agent: navigator.userAgent, ...info }),
            keepalive: true,
        }).catch((e) => console.debug('[NOTIFDBG] ack failed to send:', e));
    } catch (e) {
        console.debug('[NOTIFDBG] ack failed to send:', e);
    }
}

/**
 * Updates the favicon as an in-app unread indicator and shows an OS
 * notification via the service worker. Shown over the shared WebSocket
 * connection so it appears immediately even while the tab is focused
 * (foreground) — FCM's foreground routing is unreliable across browsers.
 * Uses the same `tag` scheme as the FCM-triggered notifications so the two
 * paths de-duplicate instead of stacking if both happen to fire.
 * @param {Object} notif - Notification data
 * @param {string} notif.title - Notification title
 * @param {string} notif.body - Notification body text
 * @param {string} [notif.icon] - Notification icon URL
 * @param {string} [notif.click_action] - URL to open on notification click
 * @param {number} [notif.room_id] - Optional room ID associated with notification
 * @param {string} [notif.notification_id] - Server-assigned ID, echoed back in the delivery ack.
 */
export async function makeNotification(notif) {
    showUnreadIcon();

    const notificationId = notif.notification_id || null;
    const ack = (status, extra = {}) =>
        sendNotificationAck({ notification_id: notificationId, status, source: 'ws-foreground', ...extra });

    console.debug('[NOTIFDBG] makeNotification called', { notificationId, title: notif.title, room_id: notif.room_id });

    if (!('Notification' in window)) {
        console.debug('[NOTIFDBG] skipped: Notification API unsupported');
        ack('skipped', { reason: 'notification-api-unsupported' });
        return;
    }
    if (Notification.permission !== 'granted') {
        console.debug('[NOTIFDBG] skipped: permission is', Notification.permission);
        ack('skipped', { reason: `permission-${Notification.permission}` });
        return;
    }
    if (!('serviceWorker' in navigator)) {
        console.debug('[NOTIFDBG] skipped: no serviceWorker support');
        ack('skipped', { reason: 'no-service-worker-support' });
        return;
    }
    try {
        // Android Chrome does not support `new Notification(...)` from page context
        // (throws "Illegal constructor"); showing via the SW registration works on
        // both desktop and mobile.
        const registration = await navigator.serviceWorker.ready;
        const roomId = notif.room_id || 0;
        const eventId = notif.event_id || 0;
        const voteId = notif.vote_id || 0;
        const citizenId = notif.citizen_id || 0;

        let tag;
        if (notif.tag) {
            tag = notif.tag;
        } else if (citizenId) {
            tag = `citizen-${citizenId}`;
        } else if (voteId) {
            tag = `vote-${voteId}`;
        } else if (eventId) {
            tag = `event-${eventId}`;
        } else {
            tag = `chat-${roomId || 'general'}`;
        }

        let clickAction;
        if (notif.click_action) {
            clickAction = notif.click_action;
        } else if (citizenId) {
            clickAction = `/obywatele/poczekalnia/${citizenId}/`;
        } else if (voteId) {
            clickAction = `/glosowania/details/${voteId}/`;
        } else if (eventId) {
            clickAction = `/events/${eventId}/`;
        } else {
            clickAction = '/chat';
        }

        console.debug('[NOTIFDBG] showing via service worker', { tag, registrationScope: registration.scope });
        await registration.showNotification(notif.title || _('Chat'), {
            body: notif.body || '',
            icon: notif.icon || '/favicon.ico',
            badge: '/favicon.ico',
            tag: tag,
            requireInteraction: true,
            data: {
                notification_id: notificationId,
                room_id: roomId,
                event_id: eventId,
                vote_id: voteId,
                citizen_id: citizenId,
                click_action: clickAction,
            },
        });
        console.debug('[NOTIFDBG] shown', { tag, notificationId });
        ack('shown', { tag });
    } catch (e) {
        console.error('[NOTIFDBG] Error showing notification:', e);
        ack('error', { reason: String(e && e.message || e) });
    }
}

// Favicon href as rendered by the server (respects custom brand mark) — captured lazily
// on first use, before any notification badge overwrites it.
let originalIconHref = null;
// Data URL of the favicon with an "unread" dot, rendered once from originalIconHref
let unreadIconHref = null;

// Green dot color — same as the legacy notification-on.ico badge
const UNREAD_BADGE_COLOR = '#7cb342';
const FALLBACK_ICON = '/static/chat/images/notification-off.ico';
const FALLBACK_UNREAD_ICON = '/static/chat/images/notification-on.ico';

/**
 * Returns the page favicon link element, creating it when absent
 * @returns {HTMLLinkElement}
 */
function getIconLink() {
    let link = $("link[rel~='icon']");
    if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.getElementsByTagName('head')[0].appendChild(link);
    }
    return link;
}

/**
 * Captures the favicon href currently rendered by the server so it can be
 * restored later. Falls back to the bundled default icon when no href is set.
 */
function captureOriginalIcon() {
    if (originalIconHref === null) {
        originalIconHref = getIconLink().href || FALLBACK_ICON;
    }
}

/**
 * Removes notification indicator (restores the site's original favicon,
 * which may be a custom brand mark instead of the default icon)
 */
export function removeNotification() {
    captureOriginalIcon();
    changeIcon(originalIconHref);
}

/**
 * Changes the page favicon
 * @param {string} resource - URL to the icon image
 */
export function changeIcon(resource) {
    const link = getIconLink();
    captureOriginalIcon();
    link.href = resource;
}

/**
 * Renders the given favicon with a green "unread" dot into a data URL, so the
 * indicator preserves a custom brand mark instead of reverting to the default icon.
 * @param {string} href - Source favicon URL
 * @returns {Promise<string|null>} - data: URL, or null when the icon can't be drawn
 */
async function renderUnreadIcon(href) {
    try {
        const img = new Image();
        img.src = href;
        await img.decode();
        const size = 64;
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = size;
        const ctx = canvas.getContext('2d');
        // contain-fit — the favicon may be non-square (default icon is 49x57)
        const scale = Math.min(size / img.naturalWidth, size / img.naturalHeight);
        const w = img.naturalWidth * scale;
        const h = img.naturalHeight * scale;
        ctx.drawImage(img, (size - w) / 2, (size - h) / 2, w, h);
        const r = Math.round(size * 0.15);
        ctx.beginPath();
        ctx.arc(size - r, r, r, 0, Math.PI * 2);
        ctx.fillStyle = UNREAD_BADGE_COLOR;
        ctx.fill();
        return canvas.toDataURL('image/png');
    } catch (e) {
        console.debug('[NOTIFDBG] unread favicon render failed:', e);
        return null;
    }
}

/**
 * Switches the page favicon to the "unread" variant — the site's own favicon
 * (possibly a custom brand mark) with a green dot drawn on a canvas.
 * Falls back to the bundled static icon when runtime rendering fails.
 */
export async function showUnreadIcon() {
    captureOriginalIcon();
    if (unreadIconHref === null) {
        unreadIconHref = (await renderUnreadIcon(originalIconHref)) || FALLBACK_UNREAD_ICON;
    }
    changeIcon(unreadIconHref);
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