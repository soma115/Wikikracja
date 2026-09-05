import base64
import json
import logging
import mimetypes
from os import getenv, path

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import credentials

from zzz.settings_base import BASE_DIR, DATABASES  # noqa: F401

# Register additional MIME types not recognized by default
mimetypes.add_type('image/webp', '.webp')


def env_bool(name, default=False):
    value = getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "t", "yes", "y", "on")


def env_int(name, default):
    value = getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def env_list(name, default=None, sep=","):
    value = getenv(name)
    if value is None:
        return default if default is not None else []
    parts = [p.strip() for p in value.split(sep)]
    return [p for p in parts if p]


STATIC_ROOT = path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = path.join(BASE_DIR, 'media')

load_dotenv(path.join(BASE_DIR, '.env'))

DEBUG = env_bool("DEBUG", False)
DEBUG_TOOLBAR = env_bool("DEBUG_TOOLBAR", False)
SITE_PROTOCOL = "http" if DEBUG else "https"

SECRET_KEY = getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        # Generate a random key for development
        import secrets

        SECRET_KEY = secrets.token_urlsafe(50)
    else:
        raise RuntimeError("SECRET_KEY is required when DEBUG is False")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Canonical domain redirect: any host in DOMAIN_ALIASES is permanently
# redirected to SITE_DOMAIN. Strict list, no regex matching.
SITE_DOMAIN = getenv("SITE_DOMAIN", "")
SITE_NAME = getenv("SITE_NAME") or SITE_DOMAIN
DOMAIN_ALIASES = env_list("DOMAIN_ALIASES", default=[])
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", default=["http://localhost", "http://127.0.0.1"])
INTERNAL_IPS = ['127.0.0.1', '192.168.1.3', '192.168.178.79', '10.1.77.31', '10.0.0.0/8']

CSRF_COOKIE_SECURE = False if DEBUG else True
CSRF_COOKIE_SAMESITE = getenv("CSRF_COOKIE_SAMESITE", "Lax")

# Session cookie settings - must match CSRF settings for WebSocket to work
SESSION_COOKIE_SECURE = False if DEBUG else True
SESSION_COOKIE_SAMESITE = getenv("SESSION_COOKIE_SAMESITE", "Lax")
# SESSION_COOKIE_HTTPONLY = True

# Reverse proxy configuration (required when behind Traefik/nginx)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

TIME_ZONE = getenv("TIME_ZONE", "Europe/Warsaw")
LANGUAGE_CODE = getenv("LANGUAGE_CODE", "pl")

SITE_ID = 1
USE_I18N = True
USE_L10N = True
USE_TZ = True
LOCALE_PATHS = (path.join(BASE_DIR, 'locale'),)
DATE_FORMAT = "Y-m-d"

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = 'bootstrap5'
ASGI_APPLICATION = 'zzz.routing.application'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
ROOT_URLCONF = 'zzz.urls'

if DEBUG:
    ASGI_THREADS = 1


def gettext_lazy(s):
    return s


LANGUAGES = (('en', gettext_lazy('English')), ('pl', gettext_lazy('Polish')))

SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)
SESSION_COOKIE_AGE = env_int("SESSION_COOKIE_AGE", 60 * 60 * 24 * 90)  # default 90 days
REMEMBER_ME_DAYS = env_int("REMEMBER_ME_DAYS", 90)
REMEMBER_ME_COOKIE_AGE = env_int("REMEMBER_ME_COOKIE_AGE", 60 * 60 * 24 * REMEMBER_ME_DAYS)

REDIS_HOST = getenv("REDIS_HOST", "redis://redis:6379/1")
CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer', 'CONFIG': {'hosts': [REDIS_HOST]}}}

CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_HOST}}

UPLOAD_IMAGE_MAX_SIZE_MB = env_int("UPLOAD_IMAGE_MAX_SIZE_MB", 5)
UPLOAD_ATTACHMENT_MAX_SIZE_MB = env_int("UPLOAD_ATTACHMENT_MAX_SIZE_MB", 5)

# ZMIANA 5: maksymalna długość wiadomości czatu (konfigurowalna)
MESSAGE_MAX_LENGTH = env_int("MESSAGE_MAX_LENGTH", 1500)
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DATA_UPLOAD_MAX_MEMORY_SIZE", 10485760)

# X_FRAME_OPTIONS = 'SAMEORIGIN'
# X_FRAME_OPTIONS = 'ALLOW'
# TODO: Na produkcji jest:
X_FRAME_OPTIONS = 'DENY'
# Dlaczego?

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'obywatele.middleware.CanonicalDomainMiddleware',  # redirect aliases -> SITE_DOMAIN
    'whitenoise.middleware.WhiteNoiseMiddleware',  # above all other middleware apart from Django’s SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'obywatele.middleware.UserLanguageMiddleware',
    'obywatele.middleware.UpdateLastSeenMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sites.middleware.CurrentSiteMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',  # disabled; configure X-Frame-Options in reverse proxy
    # Na produkcji w nginx dodać:
    # add_header X-Frame-Options SAMEORIGIN;
    # albo w settings.py:
    # X_FRAME_OPTIONS = 'SAMEORIGIN'
    # X_FRAME_OPTIONS = 'ALLOW'
    # XS_SHARING_ALLOWED_METHODS = ['POST','GET','OPTIONS', 'PUT', 'DELETE']
    'allauth.account.middleware.AccountMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [path.join(BASE_DIR, 'templates'), path.join(BASE_DIR, 'templates', 'allauth')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'zzz.context_processors.footer',
                'zzz.context_processors.site_name',
                'site_settings.context_processors.branding',
                'zzz.context_processors.group_is_public',
                'zzz.context_processors.unread_count',
                'zzz.context_processors.upload_limits',
            ],
            'debug': False,
        },
    }
]

AUTHENTICATION_BACKENDS = ['obywatele.auth_backends.CaseInsensitiveEmailBackend', 'django.contrib.auth.backends.ModelBackend', 'allauth.account.auth_backends.AuthenticationBackend']

INSTALLED_APPS = [
    'zzz.apps.SchedulerConfig',
    'daphne',
    'channels',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'allauth',
    'allauth.account',
    # 'allauth.socialaccount',
    'django.contrib.staticfiles',
    'django_bootstrap5',
    'crispy_forms',
    'crispy_bootstrap5',
    'tinymce',
    'django_tables2',
    'django_filters',
    'corsheaders',  # https://stackoverflow.com/questions/22355540/access-control-allow-origin-in-django-app
    'obywatele',
    'glosowania',
    'bookkeeping',
    'chat',
    'home',
    'categories',
    'board',
    'events',
    'tasks',
    'ankiety',
    'captcha',
    'push_notifications',
    'site_settings',
]

if DEBUG:
    INSTALLED_APPS = [*INSTALLED_APPS, 'django_extensions', 'django_browser_reload', "django_watchfiles"]
    MIDDLEWARE = [*MIDDLEWARE, 'django_browser_reload.middleware.BrowserReloadMiddleware']

    if DEBUG_TOOLBAR:
        INSTALLED_APPS = [*INSTALLED_APPS, 'debug_toolbar']
        MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware', *MIDDLEWARE]

# LOGGING_DESTINATION: 'console' (default) or 'file'
# When 'file', logs are written to LOG_FILE (default: /var/log/wiki.log)
LOGGING_DESTINATION = getenv("LOGGING_DESTINATION", "console")
LOG_FILE = getenv("LOG_FILE", "/var/log/wiki.log")
LOG_LEVEL = getenv("LOG_LEVEL", "DEBUG" if DEBUG else "INFO").strip().upper()
if LOG_LEVEL not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
    raise RuntimeError("LOG_LEVEL must be one of: CRITICAL, ERROR, WARNING, INFO, DEBUG, NOTSET")
_log_to_file = LOGGING_DESTINATION == "file"
_active_handler = "file" if _log_to_file else "console"

# Just for suppressing "Using selector: EpollSelector"
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)


class CancelledErrorFilter(logging.Filter):
    """Filter to suppress asyncio CancelledError logs from normal client disconnects."""

    def filter(self, record):
        # Suppress only the specific CancelledError message from asyncio
        if record.name == 'asyncio' and 'CancelledError' in record.getMessage():
            return False
        return True


LOGGING_HANDLERS = {'console': {'level': LOG_LEVEL, 'class': 'logging.StreamHandler', 'formatter': 'verbose', 'stream': 'ext://sys.stdout', 'filters': ['cancelled_error_filter']}}
if _log_to_file:
    LOGGING_HANDLERS['file'] = {'level': LOG_LEVEL, 'class': 'logging.FileHandler', 'filename': LOG_FILE, 'formatter': 'verbose', 'filters': ['cancelled_error_filter']}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'verbose': {'format': '%(asctime)s %(levelname)s %(name)s %(message)s', 'datefmt': '%D %H:%M:%S'}},
    'filters': {'cancelled_error_filter': {'()': CancelledErrorFilter}},
    'handlers': LOGGING_HANDLERS,
    'loggers': {
        '': {'handlers': [_active_handler], 'level': LOG_LEVEL},
        # Urls:
        'django.channels.server': {'handlers': [_active_handler], 'level': 'ERROR'},
    },
}

# Allow complete LOGGING override via JSON environment variable
LOGGING_JSON = getenv("LOGGING_JSON")
if LOGGING_JSON:
    try:
        LOGGING = json.loads(LOGGING_JSON)
    except json.JSONDecodeError as e:
        err = "LOGGING_JSON contains invalid JSON: " + LOGGING_JSON + " Stack: " + e.args[0]
        print(err)
        raise RuntimeError(err) from None

EMAIL_BACKEND = getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = getenv("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
EMAIL_HOST_USER = getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = getenv("EMAIL_HOST_PASSWORD", "")
SERVER_EMAIL = getenv("SERVER_EMAIL", "")
DEFAULT_FROM_EMAIL = getenv("DEFAULT_FROM_EMAIL", SERVER_EMAIL)
EMAIL_SEND_DELAY_SECONDS = env_int("EMAIL_SEND_DELAY_SECONDS", 2)

if not DEBUG and EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    missing = []
    if not EMAIL_HOST:
        missing.append("EMAIL_HOST")
    if not EMAIL_HOST_USER:
        missing.append("EMAIL_HOST_USER")
    if not EMAIL_HOST_PASSWORD:
        missing.append("EMAIL_HOST_PASSWORD")
    if missing:
        raise RuntimeError("SMTP email is enabled but required settings are missing: " + ", ".join(missing))

#########################
# AllAuth Configuration #
#########################
# CRITICAL: Custom signup form and adapter for Wikikracja onboarding flow
ACCOUNT_FORMS = {
    'signup': 'obywatele.forms.CustomSignupForm'  # Custom form: email + captcha only
}
ACCOUNT_ADAPTER = 'obywatele.adapter.CustomAccountAdapter'  # Handles session and redirects
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# CRITICAL: Redirect to onboarding form immediately after signup
# Without this, users get stuck or redirected to wrong pages
ACCOUNT_SIGNUP_REDIRECT_URL = '/obywatele/onboarding/'
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/m',
    'confirm_email': '0/m',  # Disable cooldown (0 per minute = no cooldown)
}
ACCOUNT_INACTIVE_REDIRECT_URL = '/obywatele/onboarding/'
ACCOUNT_LOGIN_METHODS = set(env_list("ACCOUNT_LOGIN_METHODS", default=["email"]))
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*']  # , 'password2*'*/]
ACCOUNT_UNIQUE_EMAIL = True
# CRITICAL: Email verification settings for onboarding flow
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # Must verify email to continue
ACCOUNT_CONFIRM_EMAIL_ON_GET = True  # Allow GET requests for email confirmation
ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = '/obywatele/onboarding/'  # After email confirmation
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = '/obywatele/onboarding/'  # Same for logged in
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 7  # IMPORTANT: Links valid for 7 days (prevents "expired" errors)
ACCOUNT_PASSWORD_MIN_LENGTH = 8
# ACCOUNT_RATE_LIMITS = True  # doesn't work despite documentation
RATE_LIMITS = 5  # at least doesn't break signup
ACCOUNT_SESSION_REMEMBER = True  # Controls the life time of the session. Set to None to ask the user ("Remember me?"), False to not remember, and True to always remember.
ACCOUNT_SIGNUP_PASSWORD_VERIFICATION = False
ACCOUNT_SIGNUP_PASSWORD_GENERATION = True  # Auto-generate passwords for signup

# Captcha https://django-simple-captcha.readthedocs.io/en/latest/advanced.html
CAPTCHA_FONT_SIZE = 40
CAPTCHA_IMAGE_SIZE = (170, 50)
CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.random_char_challenge'
# CAPTCHA_CHALLENGE_FUNCT = 'captcha.helpers.math_challenge'
CAPTCHA_LENGTH = 3
CAPTCHA_TIMEOUT = 2
CAPTCHA_ANIMATED = True

#########################
# WhiteNoise Configuration
#########################
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # In development: serve source files directly via finders (no hashing, no collectstatic needed)
        # In production: compress + hash for optimal caching
        "BACKEND": ("django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG else "whitenoise.storage.CompressedStaticFilesStorage")
    },
}
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_MAX_AGE = 28800  # 8 hours
# Don't let WhiteNoise handle /media/ URLs - Django will serve them
WHITENOISE_STATIC_PREFIX = '/static/'
WHITENOISE_KEEP_ONLY_HASHED_FILES = False
WHITENOISE_MANIFEST_STRICT = False  # Allow missing manifest in dev mode

DEBUG_SKIP_AUTH = env_bool("DEBUG_SKIP_AUTH", False)

(BASE_DIR / "media" / "uploads").mkdir(parents=True, exist_ok=True)

#########################
# Push Notifications Configuration
#########################


def _clean_env_value(value: str) -> str:
    if not value:
        return value
    return value.strip().strip('"').strip("'")


def _normalize_service_account_key(data: dict) -> dict:
    """Ensure private_key has real newlines, not escaped \\n strings."""
    if "private_key" in data and isinstance(data["private_key"], str):
        # First convert literal \\n (two chars) to real newlines, then normalize line endings.
        key = data["private_key"].replace("\\n", "\n").replace("\r\n", "\n")
        data["private_key"] = key
    return data


def _load_firebase_credentials():
    """Load Firebase service account credentials from various formats:
    - FIREBASE_CERT_PATH / GOOGLE_APPLICATION_CREDENTIALS: path to JSON file
    - FIREBASE_CERT_JSON: raw JSON string (e.g. pasted into .env or secret)
    - FIREBASE_CERT_BASE64: base64-encoded JSON string
    """
    cert_path = getenv('FIREBASE_CERT_PATH', '')
    google_app_creds = getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    cert_json = getenv('FIREBASE_CERT_JSON', '')
    cert_b64 = getenv('FIREBASE_CERT_BASE64', '')

    # 1) base64-encoded JSON
    if cert_b64:
        try:
            raw = base64.b64decode(cert_b64).decode('utf-8')
            data = json.loads(raw)
            logging.info("Firebase credentials loaded from FIREBASE_CERT_BASE64")
            return credentials.Certificate(_normalize_service_account_key(data))
        except Exception as e:
            logging.warning(f"FIREBASE_CERT_BASE64 decoding failed: {e}")

    # 2) raw JSON string
    if cert_json:
        try:
            data = json.loads(cert_json)
            logging.info("Firebase credentials loaded from FIREBASE_CERT_JSON")
            return credentials.Certificate(_normalize_service_account_key(data))
        except Exception as e:
            logging.warning(f"FIREBASE_CERT_JSON parsing failed: {e}")

    # 3) paths - may also be JSON strings if someone pasted the JSON into the env var
    for name, value in (('FIREBASE_CERT_PATH', cert_path), ('GOOGLE_APPLICATION_CREDENTIALS', google_app_creds)):
        if not value:
            continue

        # It looks like a JSON string (someone pasted the whole file content)
        if value.strip().startswith('{'):
            try:
                data = json.loads(value)
                logging.info(f"Firebase credentials loaded from {name} as JSON string")
                return credentials.Certificate(_normalize_service_account_key(data))
            except Exception as e:
                logging.warning(f"{name} looked like JSON but failed to parse: {e}")

        # Treat as file path
        if path.exists(value):
            try:
                with open(value, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                logging.info(f"Firebase credentials loaded from {name} file: {value}")
                return credentials.Certificate(_normalize_service_account_key(data))
            except Exception as e:
                logging.warning(f"Failed to load Firebase credentials from {name}={value}: {e}")

    return None


# Check if already initialized
try:
    firebase_admin.get_app()
except ValueError:
    # Not initialized yet
    firebase_creds = _load_firebase_credentials()
    if firebase_creds:
        firebase_admin.initialize_app(credential=firebase_creds)
        logging.info("Firebase Admin SDK initialized for FCM")
    else:
        logging.warning("Firebase not initialized: No valid credentials found. Set FIREBASE_CERT_PATH (file path or JSON), GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_CERT_JSON or FIREBASE_CERT_BASE64.")

PUSH_NOTIFICATIONS_SETTINGS = {"FIREBASE_APP": firebase_admin.get_app() if firebase_admin._apps else None, "FCM_MAX_RECIPIENTS": 1000}

# Firebase Client Configuration (for Web/Android FCM)
FIREBASE_CONFIG = {
    'apiKey': _clean_env_value(getenv('FIREBASE_API_KEY', '')),
    'authDomain': _clean_env_value(getenv('FIREBASE_AUTH_DOMAIN', '')),
    'projectId': _clean_env_value(getenv('FIREBASE_PROJECT_ID', '')),
    'storageBucket': _clean_env_value(getenv('FIREBASE_STORAGE_BUCKET', '')),
    'messagingSenderId': _clean_env_value(getenv('FIREBASE_MESSAGING_SENDER_ID', '')),
    'appId': _clean_env_value(getenv('FIREBASE_APP_ID', '')),
}

# FCM Web Push certificate (key pair) from Firebase Console > Cloud Messaging.
# Required by messaging.getToken({ vapidKey }) for browsers (incl. Android Chrome).
FIREBASE_VAPID_KEY = _clean_env_value(getenv('FIREBASE_VAPID_KEY', ''))

# Onboarding: pk of the Board post 'Zasady wspólnoty'
ONBOARDING_RULES_POST_ID = None  # set to the pk after creating the post
