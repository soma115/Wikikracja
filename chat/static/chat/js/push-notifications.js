import { FIREBASE_CONFIG, FIREBASE_VAPID_KEY } from '/dynamic-settings.js';
import { sendNotificationAck } from './utility.js';

document.addEventListener('DOMContentLoaded', async function() {
    const enabled = await PushNotificationManager.initialize();
    console.log('[NOTIFDBG] Push notifications enabled:', enabled);
});

const PushNotificationManager = {
    async initialize() {
        if ('Notification' in window && 'serviceWorker' in navigator) {
            return await this.initFCM();
        }
        console.warn('[NOTIFDBG] No supported push notification platform detected');
        return false;
    },

    // Guards against concurrent initFCM() calls (e.g. Android reloading/resuming a
    // backgrounded tab multiple times in quick succession). Without this, overlapping
    // calls can race on the service worker lifecycle and rotate/invalidate the push
    // subscription right after it was created, causing FCM to report the freshly
    // registered token as "Device unregistered" a few seconds later.
    _initPromise: null,

    async initFCM() {
        if (this._initPromise) {
            return this._initPromise;
        }
        this._initPromise = this._doInitFCM();
        try {
            return await this._initPromise;
        } finally {
            this._initPromise = null;
        }
    },

    async _doInitFCM() {
        try {
            if (Notification.permission !== 'granted') {
                console.log('[NOTIFDBG] Notification permission not granted yet; skipping FCM token retrieval.');
                return false;
            }
            if (!FIREBASE_CONFIG ||
                !FIREBASE_CONFIG.apiKey ||
                !FIREBASE_CONFIG.authDomain ||
                !FIREBASE_CONFIG.projectId ||
                !FIREBASE_CONFIG.storageBucket ||
                !FIREBASE_CONFIG.messagingSenderId ||
                !FIREBASE_CONFIG.appId) {
                console.error('[NOTIFDBG] Firebase config is incomplete or missing. Please set FIREBASE_* environment variables.');
                return false;
            }
            const swRegistration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
            // NOTE: do NOT call swRegistration.update() here. Forcing a SW update check on
            // every init raced with itself when this ran concurrently (e.g. Android
            // reloading a backgrounded tab), which appeared to rotate/invalidate the push
            // subscription right after registration. The browser already checks for SW
            // updates on its own (on navigation / periodically).
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
                console.error('[NOTIFDBG] FIREBASE_VAPID_KEY is missing. Set the FCM Web Push certificate key from Firebase Console > Cloud Messaging.');
                return false;
            }
            const messaging = firebase.messaging();

            // Foreground messages are not auto-displayed by the FCM SDK; show them manually.
            // On Android Chrome, showNotification is more reliable when triggered from the
            // service worker context. We post a message to the SW and let it display.
            messaging.onMessage((payload) => {
                console.log('[NOTIFDBG] FCM foreground message:', payload);
                const notification = payload.notification || {};
                const data = payload.data || {};
                const notificationId = data.notification_id || null;
                const roomId = data.room_id ? parseInt(data.room_id, 10) : 0;
                const eventId = data.event_id ? parseInt(data.event_id, 10) : 0;

                let tag;
                if (data.tag) {
                    tag = data.tag;
                } else if (eventId) {
                    tag = `event-${eventId}`;
                } else {
                    tag = `chat-${data.room_id || 'general'}`;
                }

                const clickAction = data.click_action || (eventId ? `/events/${eventId}/` : '/chat');
                const title = notification.title || data.title || (eventId ? 'Event' : 'Chat Message');
                const options = {
                    body: notification.body || data.body || '',
                    icon: data.icon || '/favicon.ico',
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
                const activeWorker = swRegistration.active || navigator.serviceWorker.controller;
                if (activeWorker) {
                    console.debug('[NOTIFDBG] FCM foreground: dispatching to SW for display', { notificationId, tag });
                    // The SW acks 'shown'/'error' once it has actually called showNotification()
                    // (see firebase-messaging-sw.js's 'message' listener) — postMessage itself
                    // doesn't guarantee display, so we don't ack here.
                    activeWorker.postMessage({
                        type: 'SHOW_NOTIFICATION',
                        title: title,
                        options: options,
                    });
                } else {
                    // Fallback: try directly from the page context.
                    console.debug('[NOTIFDBG] FCM foreground: no active SW, showing directly', { notificationId, tag });
                    swRegistration.showNotification(title, options)
                        .then(() => sendNotificationAck({ notification_id: notificationId, tag, status: 'shown', source: 'fcm-foreground-direct' }))
                        .catch((e) => {
                            console.error('[NOTIFDBG] FCM foreground direct showNotification failed:', e);
                            sendNotificationAck({ notification_id: notificationId, tag, status: 'error', source: 'fcm-foreground-direct', reason: String(e) });
                        });
                }
            });

            const token = await messaging.getToken({
                vapidKey: FIREBASE_VAPID_KEY,
                serviceWorkerRegistration: swRegistration,
            });
            console.debug('[NOTIFDBG] FCM token obtained (len=' + (token ? token.length : 0) + ')');
            if (!token) {
                console.warn('[NOTIFDBG] FCM token retrieval failed');
                return false;
            }
            // Send token to server
            await this.registerDevice(token);
            return true;
        } catch (error) {
            console.error('[NOTIFDBG] Error initializing FCM:', error);
            return false;
        }
    },

    /**
     * Detect a coarse device type for the registration payload.
     * @private
     * @returns {string} 'mobile', 'tablet', 'desktop' or ''
     */
    getDeviceType() {
        if (navigator.userAgentData && navigator.userAgentData.platform) {
            const p = navigator.userAgentData.platform.toLowerCase();
            if (p.includes('android') || p.includes('ios')) return 'mobile';
            if (p.includes('ipados')) return 'tablet';
            return 'desktop';
        }
        const ua = navigator.userAgent.toLowerCase();
        if (/ipad|android(?!.*mobile)|tablet/.test(ua)) return 'tablet';
        if (/android|webos|iphone|ipod|blackberry|iemobile|opera mini/.test(ua)) return 'mobile';
        return 'desktop';
    },

    /**
     * Detect whether the page is running as an installed PWA.
     * @private
     * @returns {string} 'standalone', 'minimal-ui', 'fullscreen' or 'browser'
     */
    getDisplayMode() {
        if (navigator.standalone) {
            return 'standalone'; // iOS Safari PWA
        }
        const modes = ['standalone', 'fullscreen', 'minimal-ui', 'browser'];
        for (const mode of modes) {
            if (window.matchMedia(`(display-mode: ${mode})`).matches) {
                return mode;
            }
        }
        return 'browser';
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
                    device_type: this.getDeviceType(),
                    display_mode: this.getDisplayMode(),
                })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                console.log('[NOTIFDBG] Device registered successfully:', data);
                return data;
            } else {
                console.error('[NOTIFDBG] Device registration failed:', data);
                return null;
            }
        } catch (error) {
            console.error('[NOTIFDBG] Error registering device:', error);
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
                console.log('[NOTIFDBG] Device unregistered:', data);
                return data;
            } else {
                console.error('[NOTIFDBG] Device unregistration failed:', data);
                return null;
            }

        } catch (error) {
            console.error('[NOTIFDBG] Error unregistering device:', error);
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


};
// Export for ES modules
export { PushNotificationManager };
