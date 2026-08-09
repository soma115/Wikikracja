"""
Django management command to sync the django_site table with environment settings.

Purpose:
    Keeps django.contrib.sites.models.Site in sync with ``settings.SITE_DOMAIN``
    and the site name from ``SiteParameters`` / environment fallback.

Why this exists:
    The post_migrate signal in home/apps.py only fires when migrations actually run.
    On container restart, if there are no new migrations, the signal doesn't fire and
    the Site record can become stale or remain at default (example.com).

When it runs:
    Automatically on every container startup (see Dockerfile CMD).
    Can also be run manually: python manage.py update_site
"""

from types import SimpleNamespace

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Update django.contrib.sites.models.Site from settings and SiteParameters'

    def handle(self, *args, **options):
        from site_settings.models import SiteParameters
        from site_settings.params import _sync_django_site

        try:
            sp = SiteParameters.get()
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'Could not load SiteParameters: {e}. Using environment fallback.'))
            sp = SimpleNamespace(site_name='')

        _sync_django_site(sp, fallback_name=settings.SITE_NAME)

        from django.contrib.sites.models import Site

        site = Site.objects.get(id=1)
        self.stdout.write(self.style.SUCCESS(f'Site: {site.domain} - {site.name}'))
