import os

from zzz.settings import *  # noqa: F401, F403

DEBUG = False
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != 'django_browser_reload']  # noqa: F405
MIDDLEWARE = [middleware for middleware in MIDDLEWARE if middleware != 'django_browser_reload.middleware.BrowserReloadMiddleware']  # noqa: F405

STATIC_ROOT = os.environ.get('WIKIKRACJA_TEST_STATIC_ROOT', STATIC_ROOT)  # noqa: F405
MEDIA_ROOT = os.environ.get('WIKIKRACJA_TEST_MEDIA_ROOT', MEDIA_ROOT)  # noqa: F405
DATABASES['default']['TEST'] = {'NAME': ':memory:'}  # noqa: F405

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

# Disable Channels / real channel layers — tests don't need WebSocket
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
