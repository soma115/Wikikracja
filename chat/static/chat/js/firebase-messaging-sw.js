// Firebase Messaging Service Worker
// This file must be at the root of your domain (scope: /)

importScripts('https://www.gstatic.com/firebasejs/12.10.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/12.10.0/firebase-messaging-compat.js');

// Firebase configuration will be injected by Django view (home/views.py firebase_messaging_sw)
// The view reads FIREBASE_CONFIG from settings and embeds it here as: const firebaseConfig = {...};
// If not injected, use empty object as fallback
const firebaseConfig = {};
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Activate the new service worker immediately so updates (e.g. data-only FCM handling)
// take effect without the user having to close the tab/app first.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

// Handle background messages
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


// Display a notification triggered by the foreground page via postMessage.
// This is more reliable than showing from the page context on Android Chrome.
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SHOW_NOTIFICATION') {
        const { title, options } = event.data;
        self.registration.showNotification(title, options);
    }
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const clickAction = event.notification.data?.click_action;
    if (clickAction) {
        event.waitUntil(
            clients.openWindow(clickAction)
        );
    }
});
