"""
Push Notification API endpoints for device registration and management.
Supports WebPush, FCM (Android)
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from push_notifications.models import GCMDevice, WebPushDevice

log = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class PushDeviceRegisterView(View):
    """
    Register a device for push notifications.
    POST parameters:
    - platform: 'webpush', 'fcm'
    - registration_id: device token / endpoint URL
    - p256dh: (WebPush only) p256dh public key
    - auth: (WebPush only) authentication secret
    """
    def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            platform = data.get('platform', '').lower()
            registration_id = data.get('registration_id', '')
            p256dh = data.get('p256dh', '')
            auth = data.get('auth', '')

            if not platform or not registration_id:
                return JsonResponse({
                    'error': 'Missing required parameters'
                }, status=400)

            user = request.user

            # Check if device already exists for this user and registration_id
            if platform == 'webpush':
                device, created = WebPushDevice.objects.get_or_create(user=user, registration_id=registration_id, defaults={
                    'p256dh': p256dh,
                    'auth': auth,
                    'active': True,
                })
                if not created:
                    # Update existing device
                    device.p256dh = p256dh
                    device.auth = auth
                    device.active = True
                    device.save()
            elif platform == 'fcm':
                device, created = GCMDevice.objects.get_or_create(user=user, registration_id=registration_id, defaults={
                    'active': True,
                    'device_id': "",
                })
                if not created:
                    device.active = True
                    device.device_id = ""
                    device.save()
                # Deactivate any other active FCM tokens for this user so only the
                # most recent installation (browser or PWA) receives push.
                GCMDevice.objects.filter(user=user, active=True).exclude(pk=device.pk).update(active=False)
            else:
                return JsonResponse({
                    'error': f'Unsupported platform: {platform}'
                }, status=400)

            log.info(f"User {user.id} registered push device: {platform}")

            return JsonResponse({
                'success': True,
                'device_id': device.id,
                'platform': platform,
                'created': created,
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            log.error(f"Error registering push device: {e}")
            return JsonResponse({
                'error': str(e)
            }, status=500)


@method_decorator(login_required, name='dispatch')
class PushDeviceUnregisterView(View):
    """
    Unregister a device (deactivate it).
    POST parameters:
    - platform: 'webpush', 'fcm'
    - registration_id: device token / endpoint URL
    """
    def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            platform = data.get('platform', '').lower()
            registration_id = data.get('registration_id', '')

            if not platform or not registration_id:
                return JsonResponse({
                    'error': 'Missing required parameters'
                }, status=400)

            user = request.user

            # Find and deactivate the device
            if platform == 'webpush':
                devices = WebPushDevice.objects.filter(user=user, registration_id=registration_id)
            elif platform == 'fcm':
                devices = GCMDevice.objects.filter(user=user, registration_id=registration_id)
            else:
                return JsonResponse({
                    'error': f'Unsupported platform: {platform}'
                }, status=400)

            count = 0
            for device in devices:
                device.active = False
                device.save()
                count += 1

            log.info(f"User {user.id} unregistered {count} {platform} device(s)")

            return JsonResponse({
                'success': True,
                'deactivated': count,
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            log.error(f"Error unregistering push device: {e}")
            return JsonResponse({
                'error': str(e)
            }, status=500)
