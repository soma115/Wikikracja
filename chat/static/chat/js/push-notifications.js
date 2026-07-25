import { VAPID_PUBLIC_KEY } from '/dynamic-settings.js';

function urlBase64ToUint8Array(base64String) {
    if (!base64String) return new Uint8Array(0);
    const clean = base64String.trim().replace(/^["']|["']$/g, '');
    const padding = '='.repeat((4 - clean.length % 4) % 4);
    const base64 = (clean + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

document.addEventListener('DOMContentLoaded', async function() {
    const enabled = await PushNotificationManager.initialize();
    console.log('Push notifications enabled:', enabled);
});

const PushNotificationManager = {
    async initialize() {
        if ('Notification' in window && 'serviceWorker' in navigator) {
            return await this.initWebPush();
        }
        console.warn('No supported push notification platform detected');
        return false;
    },

    async initWebPush() {
        try {
            // Register service worker FIRST (needed for PWA and push notifications)
            // This happens regardless of notification permission to enable PWA functionality
            if (!navigator.serviceWorker.controller) {
                const registration = await navigator.serviceWorker.register('/sw.js');
                await this.waitForServiceWorkerActive(registration, 3000);
            }
            const swRegistration = await navigator.serviceWorker.ready;

            if (Notification.permission !== 'granted') {
                console.log('Service Worker registered, but notification permission not granted');
                // console.log('Permission status:', Notification.permission);
                return false;
            }

            if (!VAPID_PUBLIC_KEY || VAPID_PUBLIC_KEY.trim() === '') {
                console.error('VAPID public key is empty or missing. Please set VAPID_PUBLIC_KEY in your .env file.');
                return false;
            }
            const subscription = await swRegistration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
            });
            await this.registerDevice('webpush', subscription);
            return true;
        } catch (error) {
            console.error('Error initializing WebPush:', error);
            return false;
        }
    },

    /**
     * Register device with server
     * @async
     * @private
     * @param {'webpush'} platform - Platform name
     * @param {PushSubscription} registration - Push subscription
     * @returns {Promise<Object|null>} - Server response on success, null on failure
     */
    async registerDevice(platform, registration) {
        try {
            const registrationJson = registration.toJSON ? registration.toJSON() : registration;
            const response = await fetch('/chat/api/push/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    platform: platform,
                    registration_id: registration.endpoint || registration,
                    p256dh: registrationJson.keys?.p256dh || '',
                    auth: registrationJson.keys?.auth || '',
                })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                console.log(`Device registered successfully: ${platform}`, data);
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
     * Unregister device from server
     * @async
     * @param {'webpush'} platform - Platform name
     * @param {string} registrationId - Device registration ID
     * @returns {Promise<Object|null>} - Server response on success, null on failure
     */
    async unregisterDevice(platform, registrationId) {
        try {
            const response = await fetch('/chat/api/push/unregister/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    platform: platform,
                    registration_id: registrationId
                })
            });
            const data = await response.json();
            if (response.ok && data.success) {
                console.log(`Device unregistered: ${platform}`, data);
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

    /**
     * Display a push notification
     * Shows notification using Web Push API or basic Notification constructor
     * @param {Object} notification - Notification data
     * @param {string} notification.title - Notification title
     * @param {string} notification.body - Notification body text
     * @param {string} [notification.icon] - URL to notification icon
     * @param {string} [notification.badge] - URL to notification badge
     * @param {Object} [notification.data] - Additional data (room_id, click_action, url)
     * @returns {Notification|null} - Notification object if shown, null otherwise
     */
    showNotification(notification) {
        if (Notification.permission !== 'granted')
            return;

        const notif = new Notification(notification.title || 'Chat Message', {
            body: notification.body || '',
            icon: notification.icon || '/favicon.ico',
            badge: notification.badge || '/favicon.ico',
            tag: `chat-${notification.room_id || 'general'}`,
            requireInteraction: true
        });

        if (notification.click_action) {
            notif.onclick = () => {
                window.location.href = notification.click_action;
                notif.close();
            };
        }
        return notif;
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

    async waitForServiceWorkerActive(registration, timeout = 3000) {
        return new Promise((resolve, reject) => {
            // If already has controller, it's active
            if (navigator.serviceWorker.controller) {
                console.log('Service Worker already active');
                resolve();
                return;
            }

            // Wait for controllerchange event (SW became active)
            const controllerChangeListener = () => {
                console.log('Service Worker became active (controllerchange)');
                navigator.serviceWorker.removeEventListener('controllerchange', controllerChangeListener);
                clearTimeout(timeoutId);
                resolve();
            };

            navigator.serviceWorker.addEventListener('controllerchange', controllerChangeListener);

            // Also check registration.state periodically
            const checkState = () => {
                if (registration.installing) {
                    console.log('SW state: installing');
                } else if (registration.waiting) {
                    console.log('SW state: waiting');
                } else if (registration.active) {
                    console.log('SW state: active');
                }
            };

            // Check state immediately and periodically
            checkState();
            const stateInterval = setInterval(checkState, 500);

            // Also check periodically if controller exists (additional safety)
            const checkController = setInterval(() => {
                if (navigator.serviceWorker.controller) {
                    console.log('Service Worker detected as active via controller');
                    clearInterval(stateInterval);
                    clearInterval(checkController);
                    navigator.serviceWorker.removeEventListener('controllerchange', controllerChangeListener);
                    resolve();
                }
            }, 100);

            // Timeout fallback - check if registration became active
            const timeoutId = setTimeout(() => {
                console.log(`Service Worker activation timeout after ${timeout}ms`);
                console.log(`Final SW state: ${registration.state}`);
                clearInterval(stateInterval);
                clearInterval(checkController);
                navigator.serviceWorker.removeEventListener('controllerchange', controllerChangeListener);

                // If still no controller but registration is active, try to use it anyway
                if (registration.active && !navigator.serviceWorker.controller) {
                    // console.log('Registration is active but no controller - forcing activation');
                    // Calling skipWaiting may help
                    if (registration.waiting) {
                        registration.waiting.postMessage({ type: 'SKIP_WAITING' });
                    }
                }
                resolve();
            }, timeout);
        });
    },
};
// Export for ES modules
export { PushNotificationManager };
