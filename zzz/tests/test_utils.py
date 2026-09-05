import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import OperationalError
from django.test import SimpleTestCase

from zzz.utils import get_site_domain


class SiteDomainTest(SimpleTestCase):
    def test_returns_current_site_domain(self):
        with patch.object(Site.objects, 'get_current', return_value=SimpleNamespace(domain='testserver')):
            self.assertEqual(get_site_domain(), 'testserver')

    def test_missing_site_uses_fallback(self):
        with patch.object(Site.objects, 'get_current', side_effect=Site.DoesNotExist):
            self.assertEqual(get_site_domain(), 'localhost')

    def test_database_errors_are_not_silently_replaced_with_localhost(self):
        with patch.object(Site.objects, 'get_current', side_effect=OperationalError('database unavailable')):
            with self.assertRaises(OperationalError):
                get_site_domain()

    def test_system_check_works_before_database_migrations(self):
        script = '''
from django.conf import settings
settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
import django
django.setup()
from django.core.management import call_command
call_command('check')
'''
        env = {**os.environ, 'DJANGO_SETTINGS_MODULE': 'zzz.test_settings', 'RUN_MAIN': 'false', 'SCHEDULER_ENABLED': 'false'}
        result = subprocess.run([sys.executable, '-c', script], cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
