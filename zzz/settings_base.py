import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
SQLITE_DATABASE_PATH = os.getenv('SQLITE_DATABASE_PATH', str(BASE_DIR / 'db' / 'db.sqlite3'))
SQLITE_TIMEOUT = min(max(float(os.getenv('SQLITE_TIMEOUT', '60')), 0.1), 60.0)

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': SQLITE_DATABASE_PATH, 'OPTIONS': {'timeout': SQLITE_TIMEOUT}}}
