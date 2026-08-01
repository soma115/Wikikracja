// Firebase Messaging Service Worker
// This file must be at the root of your domain (scope: /)

// Firebase configuration will be injected by Django view (home/views.py firebase_messaging_sw)
// The view reads FIREBASE_CONFIG from settings and embeds it here as: const firebaseConfig = {...};
// If not injected, use empty object as fallback
const firebaseConfig = {};

let firebaseLoaded = false;
try {
    importScripts('https://www.gstatic.com/firebasejs/12.10.0/firebase-app-compat.js');
    importScripts('https://www.gstatic.com/firebasejs/12.10.0/firebase-messaging-compat.js');
    firebaseLoaded = true;
} catch (e) {
    console.error('[NOTIFDBG] Firebase SDK scripts failed to load in service worker:', e);
}

let messaging = null;
if (firebaseLoaded &&
    firebaseConfig.apiKey &&
    firebaseConfig.authDomain &&
    firebaseConfig.projectId &&
    firebaseConfig.storageBucket &&
    firebaseConfig.messagingSenderId &&
    firebaseConfig.appId) {
    firebase.initializeApp(firebaseConfig);
    messaging = firebase.messaging();
} else {
    console.warn('[NOTIFDBG] Firebase config incomplete or SDK not loaded; service worker will not handle FCM.');
}

// Activate the new service worker immediately so updates take effect
// without the user having to close the tab/app first.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

// Sends a delivery ack back to the server so notification reliability can be
// debugged from the server logs (correlated by `notification_id` — see
// chat/push_api.py PushNotificationAckView). No CSRF token: this endpoint is
// intentionally CSRF-exempt because a service worker has no simple way to read
// the CSRF cookie. Fire-and-forget; never throws.
function postAck(info) {
    try {
        fetch('/chat/api/push/ack/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_agent: self.navigator ? self.navigator.userAgent : '', ...info }),
        }).catch((e) => console.debug('[NOTIFDBG] ack failed to send:', e));
    } catch (e) {
        console.debug('[NOTIFDBG] ack failed to send:', e);
    }
}

// Handle background messages only if FCM was initialized
if (messaging) {
    messaging.onBackgroundMessage((payload) => {
        console.log('[NOTIFDBG] FCM background message:', payload);

        const notification = payload.notification || {};
        const data = payload.data || {};
        const notificationId = data.notification_id || null;

        // If the FCM SDK parsed a real notification payload, it already displays it
        // automatically in the background. Avoid a second duplicate notification.
        if (notification.title && notification.body) {
            console.debug('[NOTIFDBG] background message auto-displayed by FCM SDK', { notificationId });
            postAck({ notification_id: notificationId, tag: data.tag, status: 'shown', source: 'fcm-background-auto' });
            return;
        }

        const eventId = data.event_id ? parseInt(data.event_id, 10) : 0;
        const roomId = data.room_id ? parseInt(data.room_id, 10) : 0;
        const tag = data.tag || (eventId ? `event-${eventId}` : `chat-${data.room_id || 'general'}`);
        const clickAction = data.click_action || (eventId ? `/events/${eventId}/` : '/chat');

        const notificationTitle = data.title || (eventId ? 'Event' : 'Chat Message');
        const notificationOptions = {
            body: data.body || '',
            icon: data.icon || '/favicon.ico',
            badge: '/favicon.ico',
            tag: tag,
            data: {
                notification_id: notificationId,
                room_id: roomId,
                event_id: eventId,
                click_action: clickAction,
            },
            requireInteraction: true
        };

        console.debug('[NOTIFDBG] showing background message manually', { notificationId, tag });
        return self.registration.showNotification(notificationTitle, notificationOptions)
            .then(() => postAck({ notification_id: notificationId, tag, status: 'shown', source: 'fcm-background-manual' }))
            .catch((e) => {
                console.error('[NOTIFDBG] background showNotification failed:', e);
                postAck({ notification_id: notificationId, tag, status: 'error', source: 'fcm-background-manual', reason: String(e) });
            });
    });
}

// Fallback for the killed-browser case: if Firebase SDK did not load (or
// `messaging` could not be initialized), the FCM SDK `push` listener is not
// registered, and Chrome/Android shows the generic "site updated in the
// background" fallback. We register our own `push` listener when `messaging` is
// missing. It parses the raw Web Push payload and displays the notification.
if (!messaging) {
    self.addEventListener('push', (event) => {
        console.log('[NOTIFDBG] Fallback push handler received event:', event);
        let notificationId = null;
        let tag = 'unknown';
        try {
            const payload = event.data ? event.data.json() : {};
            const notification = payload.notification || {};
            const data = payload.data || {};
            notificationId = data.notification_id || null;
            const roomId = data.room_id ? parseInt(data.room_id, 10) : 0;
            const eventId = data.event_id ? parseInt(data.event_id, 10) : 0;
            const title = notification.title || data.title || (eventId ? 'Event' : 'Chat Message');
            const body = notification.body || data.body || '';
            const icon = data.icon || '/favicon.ico';
            tag = data.tag || (eventId ? `event-${eventId}` : `chat-${data.room_id || 'general'}`);
            const clickAction = data.click_action || (eventId ? `/events/${eventId}/` : '/chat');

            const options = {
                body: body,
                icon: icon,
                badge: '/favicon.ico',
                tag: tag,
                requireInteraction: true,
                data: {
                    notification_id: notificationId,
                    room_id: roomId,
                    event_id: eventId,
                    click_action: clickAction,
                },
            };

            console.debug('[NOTIFDBG] showing via fallback push handler', { notificationId, tag });
            event.waitUntil(
                self.registration.showNotification(title, options)
                    .then(() => postAck({ notification_id: notificationId, tag, status: 'shown', source: 'fallback-push' }))
                    .catch((e) => {
                        console.error('[NOTIFDBG] fallback showNotification failed:', e);
                        postAck({ notification_id: notificationId, tag, status: 'error', source: 'fallback-push', reason: String(e) });
                    })
            );
        } catch (e) {
            console.error('[NOTIFDBG] Fallback push handler error:', e);
            postAck({ notification_id: notificationId, tag, status: 'error', source: 'fallback-push', reason: String(e) });
        }
    });
}


// Display a notification triggered by the foreground page via postMessage.
// This is more reliable than showing from the page context on Android Chrome.
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SHOW_NOTIFICATION') {
        const { title, options } = event.data;
        const notificationId = options?.data?.notification_id || null;
        console.debug('[NOTIFDBG] SHOW_NOTIFICATION message received', { notificationId, tag: options?.tag });
        self.registration.showNotification(title, options)
            .then(() => postAck({ notification_id: notificationId, tag: options?.tag, status: 'shown', source: 'fcm-foreground-sw-postmessage' }))
            .catch((e) => {
                console.error('[NOTIFDBG] postMessage showNotification failed:', e);
                postAck({ notification_id: notificationId, tag: options?.tag, status: 'error', source: 'fcm-foreground-sw-postmessage', reason: String(e) });
            });
    }
});

// Handle notification click: focus an already-open tab/PWA window if one exists,
// otherwise open a new one. Important on Android where the PWA is often already
// running in the background.
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    console.debug('[NOTIFDBG] notification clicked', {
        notification_id: event.notification.data?.notification_id,
        tag: event.notification.tag,
    });
    postAck({
        notification_id: event.notification.data?.notification_id,
        tag: event.notification.tag,
        status: 'clicked',
        source: 'sw-click',
    });

    const clickAction = event.notification.data?.click_action;
    if (!clickAction) {
        return;
    }

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            for (const client of windowClients) {
                if ('focus' in client) {
                    if ('navigate' in client) {
                        client.navigate(clickAction);
                    }
                    return client.focus();
                }
            }
            return clients.openWindow(clickAction);
        })
    );
});
