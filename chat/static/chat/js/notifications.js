/**
 * @file
 * WebSocket notification handling module.
 * Manages WebSocket connection for receiving real-time notifications
 * and handles displaying them to the user.
 */

import { $, makeNotification } from './utility.js';
import { getSharedWebSocket } from './websocket-manager.js';

/**
 * Handles incoming WebSocket notifications
 * @param {Object} notification - Notification data object
 * @param {string} notification.title - Notification title
 * @param {string} notification.body - Notification body text
 * @param {number} [notification.room_id] - Optional room ID associated with notification
 */
export function onReceiveNotification(notification) {
    console.debug('[NOTIFDBG] WebSocket notification received', {
        notification_id: notification?.notification_id,
        title: notification?.title,
        room_id: notification?.room_id,
    });
    makeNotification(notification);
}

/**
 * Updates the chat nav badge from the authoritative unread count.
 * The server pushes `unread_count` on connect and after every
 * see/unsee transition, so this covers initial state, live updates
 * and removal when the counter drops to 0. Also refreshes the
 * dashboard tile (`#chat-unread-badge` on home.html) — labels come
 * from `data-*` attributes so translations stay server-side.
 */
export function onUnreadCount(count) {
    $("a[data-nav='chat']")?.classList.toggle("tw-chat-has-messages", count > 0);
    const badge = document.getElementById('chat-unread-badge');
    const label = document.getElementById('chat-unread-label');
    if (badge && label) {
        badge.classList.toggle('tw-has-count', count > 0);
        label.textContent = count > 0 ? `${count} ${label.dataset.unreadLabel}` : label.dataset.emptyLabel;
    }
}

/**
 * Message handler for notification events
 * Registers with shared WebSocket manager to receive relevant messages
 * @param {Object} data - WebSocket message data
 */
function handleNotificationMessage(data) {
    // Handle errors
    if (data.error) {
        console.error('[NOTIFDBG] WebSocket error:', data.error);
        return;
    }

    if (data.notification) {
        let notif = data.notification;
        onReceiveNotification(notif);
    } else if (data.unread_count !== undefined) {
        onUnreadCount(data.unread_count);
    }
}

// Initialize shared WebSocket connection for notifications when DOM is ready.
// Rejestracja jest bezwarunkowa — makeNotification sam sprawdza
// Notification.permission i zawsze wysyła delivery ack do serwera, a handler
// `unread_count` obsługuje też badge "chat-has-messages" na belce nawigacji,
// który nie powinien zależeć od zgody na powiadomienia systemowe.
document.addEventListener('DOMContentLoaded', function() {
    // Get shared WebSocket connection and register handler
    let ws = getSharedWebSocket();
    ws.subscribeMessages(handleNotificationMessage);
    console.debug('[NOTIFDBG] WebSocket notification handler registered, permission:', Notification?.permission);
});

// Fallback dla bfcache/powrotu na kartę: gdy strona ma kafelek dashboardu
// (#chat-unread-badge z data-count-url), dociągamy licznik przez REST.
document.addEventListener('visibilitychange', function() {
    if (document.hidden) return;
    const badge = document.getElementById('chat-unread-badge');
    if (!badge?.dataset.countUrl) return;
    fetch(badge.dataset.countUrl, { credentials: 'same-origin' })
        .then(r => r.json())
        .then(d => onUnreadCount(d.count))
        .catch(() => {});
});