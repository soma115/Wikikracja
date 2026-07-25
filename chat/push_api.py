"""
Push Notification API endpoints for device registration and management.
Supports Web Push.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from push_notifications.models import WebPushDevice

log = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class PushDeviceRegisterView(View):
    """
    Register a device for push notifications.
    POST parameters:
    - platform: 'webpush'
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
            user = request.user
            log.info(f"[Push] register request from user {user.id}: platform={platform} endpoint_len={len(registration_id)} p256dh_len={len(p256dh)} auth_len={len(auth)}")

            if not platform or not registration_id:
                log.warning(f"[Push] register missing params for user {user.id}: platform={platform} endpoint_len={len(registration_id)}")
                return JsonResponse({
                    'error': 'Missing required parameters'
                }, status=400)

            user = request.user

            # A registration_id (WebPush endpoint) identifies one physical
            # browser/device install. It is NOT guaranteed unique per-user in the DB, so if
            # a different user previously registered this same token (e.g. someone else
            # logged in on this browser before), we must reassign it to the current user -
            # otherwise both users would end up with an active device row for the same
            # physical endpoint, and pushes meant for "the other user" would show up on
            # this device too (looks like "I get notified when I send a message myself").
            if platform == 'webpush':
                WebPushDevice.objects.filter(registration_id=registration_id).exclude(user=user).delete()
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
            else:
                log.warning(f"[Push] unsupported platform from user {user.id}: {platform}")
                return JsonResponse({
                    'error': f'Unsupported platform: {platform}'
                }, status=400)

            log.info(f"[Push] user {user.id} registered {platform} device id={device.id} created={created}")

            return JsonResponse({
                'success': True,
                'device_id': device.id,
                'platform': platform,
                'created': created,
            })

        except json.JSONDecodeError:
            log.warning(f"[Push] invalid JSON in register request from user {user.id}")
            return JsonResponse({
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            log.error(f"[Push] Error registering push device for user {user.id}: {type(e).__name__}: {e}")
            return JsonResponse({
                'error': str(e)
            }, status=500)


@method_decorator(login_required, name='dispatch')
class PushDeviceUnregisterView(View):
    """
    Unregister a device (deactivate it).
    POST parameters:
    - platform: 'webpush'
    - registration_id: device token / endpoint URL
    """
    def post(self, request: HttpRequest):
        try:
            data = json.loads(request.body.decode('utf-8'))
            platform = data.get('platform', '').lower()
            registration_id = data.get('registration_id', '')
            user = request.user
            log.info(f"[Push] unregister request from user {user.id}: platform={platform} endpoint_len={len(registration_id)}")

            if not platform or not registration_id:
                log.warning(f"[Push] unregister missing params for user {user.id}")
                return JsonResponse({
                    'error': 'Missing required parameters'
                }, status=400)

            user = request.user

            # Find and deactivate the device
            if platform == 'webpush':
                devices = WebPushDevice.objects.filter(user=user, registration_id=registration_id)
            else:
                log.warning(f"[Push] unregister unsupported platform from user {user.id}: {platform}")
                return JsonResponse({
                    'error': f'Unsupported platform: {platform}'
                }, status=400)

            count = 0
            for device in devices:
                device.active = False
                device.save()
                count += 1

            log.info(f"[Push] user {user.id} unregistered {count} {platform} device(s)")

            return JsonResponse({
                'success': True,
                'deactivated': count,
            })

        except json.JSONDecodeError:
            log.warning(f"[Push] invalid JSON in unregister request from user {user.id}")
            return JsonResponse({
                'error': 'Invalid JSON'
            }, status=400)
        except Exception as e:
            log.error(f"[Push] Error unregistering push device for user {user.id}: {type(e).__name__}: {e}")
            return JsonResponse({
                'error': str(e)
            }, status=500)
