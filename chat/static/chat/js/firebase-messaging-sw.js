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
    console.error('Firebase SDK scripts failed to load in service worker:', e);
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
    console.warn('Firebase config incomplete or SDK not loaded; service worker will not handle FCM.');
}

// Activate the new service worker immediately so updates take effect
// without the user having to close the tab/app first.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

// Handle background messages only if FCM was initialized
if (messaging) {
    messaging.onBackgroundMessage((payload) => {
        console.log('FCM background message:', payload);

        const notification = payload.notification || {};
        const data = payload.data || {};
        // title = author, body = room name (server no longer sends message content)
        let notificationTitle = notification.title || data.title || 'Chat Message';
        if (data.room_name && data.room_name !== notificationTitle) {
            notificationTitle += ' — ' + data.room_name;
        }
        const notificationOptions = {
            body: notification.body || data.body || '',
            icon: data.icon || '/favicon.ico',
            badge: '/favicon.ico',
            tag: `chat-${data.room_id || 'general'}`,
            data: {
                room_id: data.room_id ? parseInt(data.room_id, 10) : 0,
                click_action: data.click_action || '/chat',
            },
            requireInteraction: true
        };

        self.registration.showNotification(notificationTitle, notificationOptions);
    });
}


// Display a notification triggered by the foreground page via postMessage.
// This is more reliable than showing from the page context on Android Chrome.
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SHOW_NOTIFICATION') {
        const { title, options } = event.data;
        self.registration.showNotification(title, options);
    }
});

// Handle notification click: focus an already-open tab/PWA window if one exists,
// otherwise open a new one. Important on Android where the PWA is often already
// running in the background.
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

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
