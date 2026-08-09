from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': (BASE_DIR / 'db' / 'db.sqlite3'), 'OPTIONS': {'timeout': 60}}}
