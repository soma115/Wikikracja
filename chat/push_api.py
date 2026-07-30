"""
Push Notification API endpoints for FCM device registration and management.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from push_notifications.models import GCMDevice

log = logging.getLogger(__name__)


@method_decorator(login_required, name='dispatch')
class PushDeviceRegisterView(View):
    """
    Register a device for push notifications.
    POST parameters:
    - platform: 'fcm'
    - registration_id: FCM device token
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

            if platform == 'fcm':
                debounce_key = f'push_reg_debounce:{registration_id}'
                # Android reloads/resumes tabs in quick succession, which can cause
                # multiple register calls for the same token within a few seconds.
                # Each call used to rotate the push subscription and invalidate the
                # token before the backend could use it.
                if cache.get(debounce_key):
                    log.info(f"User {user.id} debounced duplicate push registration: {platform}")
                    return JsonResponse({
                        'success': True,
                        'platform': platform,
                        'debounced': True,
                    })

                # A registration_id (FCM token) identifies one physical
                # browser/device install. It is NOT guaranteed unique per-user in the DB, so if
                # a different user previously registered this same token (e.g. someone else
                # logged in on this browser before), we must reassign it to the current user -
                # otherwise both users would end up with an active device row for the same
                # physical endpoint, and pushes meant for "the other user" would show up on
                # this device too (looks like "I get notified when I send a message myself").
                GCMDevice.objects.filter(registration_id=registration_id).exclude(user=user).delete()
                device, created = GCMDevice.objects.get_or_create(user=user, registration_id=registration_id, defaults={
                    'active': True,
                    'device_id': "",
                    'cloud_message_type': 'FCM',
                })
                if not created:
                    device.active = True
                    device.device_id = ""
                    device.cloud_message_type = 'FCM'
                    device.save()
                # Deactivate any other active FCM tokens for this user so only the
                # most recent installation (browser or PWA) receives push.
                GCMDevice.objects.filter(user=user, active=True).exclude(pk=device.pk).update(active=False)
                # Mark this token as recently registered so rapid repeats are ignored.
                cache.set(debounce_key, True, timeout=30)
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
    - platform: 'fcm'
    - registration_id: FCM device token
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
            if platform == 'fcm':
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
