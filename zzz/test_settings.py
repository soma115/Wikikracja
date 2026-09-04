from zzz.settings import *  # noqa: F401, F403

DATABASES['default']['TEST'] = {'NAME': ':memory:'}  # noqa: F405

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

# Disable Channels / real channel layers — tests don't need WebSocket
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
