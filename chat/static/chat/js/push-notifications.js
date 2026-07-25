import { FIREBASE_CONFIG, FIREBASE_VAPID_KEY } from '/dynamic-settings.js';

document.addEventListener('DOMContentLoaded', async function() {
    const enabled = await PushNotificationManager.initialize();
    console.log('Push notifications enabled:', enabled);
});

const PushNotificationManager = {
    async initialize() {
        if ('Notification' in window && 'serviceWorker' in navigator) {
            return await this.initFCM();
        }
        console.warn('No supported push notification platform detected');
        return false;
    },

    async initFCM() {
        try {
            if (Notification.permission !== 'granted') {
                console.log('Notification permission not granted yet; skipping FCM token retrieval.');
                return false;
            }
            if (!FIREBASE_CONFIG ||
                !FIREBASE_CONFIG.apiKey ||
                !FIREBASE_CONFIG.authDomain ||
                !FIREBASE_CONFIG.projectId ||
                !FIREBASE_CONFIG.storageBucket ||
                !FIREBASE_CONFIG.messagingSenderId ||
                !FIREBASE_CONFIG.appId) {
                console.error('Firebase config is incomplete or missing. Please set FIREBASE_* environment variables.');
                return false;
            }
            const swRegistration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
            // Force the browser to check for a new service worker (updates may not auto-install).
            await swRegistration.update();
            // Ensure the active (not just registered) SW is used before requesting the FCM token.
            if (swRegistration.installing) {
                await new Promise(resolve => swRegistration.installing.addEventListener('statechange', function wait(e) {
                    if (e.target.state === 'activated') {
                        e.target.removeEventListener('statechange', wait);
                        resolve();
                    }
                }));
            } else if (!swRegistration.active) {
                await navigator.serviceWorker.ready;
            }
            if (!firebase.apps.length) {
                firebase.initializeApp(FIREBASE_CONFIG);
            }
            if (!FIREBASE_VAPID_KEY) {
                console.error('FIREBASE_VAPID_KEY is missing. Set the FCM Web Push certificate key from Firebase Console > Cloud Messaging.');
                return false;
            }
            const messaging = firebase.messaging();

            // Foreground messages are not auto-displayed by the FCM SDK; show them manually.
            // On Android Chrome, showNotification is more reliable when triggered from the
            // service worker context. We post a message to the SW and let it display.
            messaging.onMessage((payload) => {
                console.log('FCM foreground message:', payload);
                const notification = payload.notification || {};
                const data = payload.data || {};
                const roomId = data.room_id ? parseInt(data.room_id, 10) : 0;
                // title = author, body = room name (server no longer sends message content)
                let title = notification.title || data.title || 'Chat Message';
                if (data.room_name && data.room_name !== title) {
                    title += ' — ' + data.room_name;
                }
                const options = {
                    body: notification.body || data.body || '',
                    icon: data.icon || '/favicon.ico',
                    badge: '/favicon.ico',
                    tag: `chat-${data.room_id || 'general'}`,
                    requireInteraction: true,
                    data: {
                        room_id: roomId,
                        click_action: data.click_action || '/chat',
                    },
                };
                const activeWorker = swRegistration.active || navigator.serviceWorker.controller;
                if (activeWorker) {
                    activeWorker.postMessage({
                        type: 'SHOW_NOTIFICATION',
                        title: title,
                        options: options,
                    });
                } else {
                    // Fallback: try directly from the page context.
                    swRegistration.showNotification(title, options);
                }
            });

            const token = await messaging.getToken({
                vapidKey: FIREBASE_VAPID_KEY,
                serviceWorkerRegistration: swRegistration,
            });
            // console.log('FCM token obtained:', token);
            if (!token) {
                console.warn('FCM token retrieval failed');
                return false;
            }
            // Send token to server
            await this.registerDevice(token);
            return true;
        } catch (error) {
            console.error('Error initializing FCM:', error);
            return false;
        }
    },

    /**
     * Register FCM device with server
     * @async
     * @private
     * @param {string} token - FCM registration token
     * @returns {Promise<Object|null>} - Server response on success, null on failure
     */
    async registerDevice(token) {
        try {
            const response = await fetch('/chat/api/push/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    platform: 'fcm',
                    registration_id: token,
                })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                console.log('Device registered successfully:', data);
                return data;
            } else {
                console.error('Device registration failed:', data);
                return null;
            }
        } catch (error) {
            console.error('Error registering device:', error);
            return null;
        }
    },

    /**
     * Unregister FCM device from server
     * @async
     * @param {string} registrationId - FCM registration token
     * @returns {Promise<Object|null>} - Server response on success, null on failure
     */
    async unregisterDevice(registrationId) {
        try {
            const response = await fetch('/chat/api/push/unregister/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    platform: 'fcm',
                    registration_id: registrationId
                })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                console.log('Device unregistered:', data);
                return data;
            } else {
                console.error('Device unregistration failed:', data);
                return null;
            }

        } catch (error) {
            console.error('Error unregistering device:', error);
            return null;
        }
    },

    // Utility: Get CSRF token from cookie
    getCSRFToken() {
        const name = 'csrftoken';
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [key, value] = cookie.trim().split('=');
            if (key === name) {
                return decodeURIComponent(value);
            }
        }
        return '';
    },

    // Toggle notifications for a room (muted_by logic still in DB)
    async toggleRoomNotifications(roomId, enabled) {
        try {
            const response = await fetch('/chat/api/toggle-notifications/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    room_id: roomId,
                    enabled: enabled
                })
            });
            return response.ok;
        } catch (error) {
            console.error('Error toggling notifications:', error);
            return false;
        }
    },

};
// Export for ES modules
export { PushNotificationManager };
