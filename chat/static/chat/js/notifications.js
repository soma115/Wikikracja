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
 * Handles room unsee events (marks room as having unread messages)
 */
export function onRoomUnsee() {
    $(".nav-link[data-route='chat']")?.classList.add("chat-has-messages");
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
    } else if (data.unsee_room) {
        onRoomUnsee();
    }
}

// Initialize shared WebSocket connection for notifications when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (Notification?.permission !== 'granted') {
        console.debug('[NOTIFDBG] notification handler NOT registered: permission is', Notification?.permission);
        return;
    }

    // Get shared WebSocket connection and register handler
    let ws = getSharedWebSocket();
    ws.addMessageHandler(handleNotificationMessage);
    console.debug('[NOTIFDBG] WebSocket notification handler registered');
});