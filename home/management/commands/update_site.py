"""
Django management command to sync the django_site table with SiteParameters.

Purpose:
    Keeps django.contrib.sites.models.Site in sync with the voted SiteParameters
    singleton. SiteParameters values take precedence; environment variables
    (SITE_DOMAIN / SITE_NAME) are used as a fallback only when the parameters
    table is unavailable or the voted values are empty.

Why this exists:
    The post_migrate signal in home/apps.py only fires when migrations actually run.
    On container restart, if there are no new migrations, the signal doesn't fire and
    the Site record can become stale or remain at default (example.com).

When it runs:
    Automatically on every container startup (see Dockerfile CMD).
    Can also be run manually: python manage.py update_site
"""
import os
from types import SimpleNamespace

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Update django.contrib.sites.models.Site from SiteParameters (env fallback)'

    def handle(self, *args, **options):
        from site_settings.models import SiteParameters
        from site_settings.params import _sync_django_site

        try:
            sp = SiteParameters.get()
        except Exception as e:
            self.stderr.write(self.style.WARNING(f'Could not load SiteParameters: {e}. Using environment fallback.'))
            sp = SimpleNamespace(site_domain='', site_name='')

        if not (sp.site_domain or os.getenv('SITE_DOMAIN')):
            self.stdout.write(self.style.WARNING('No site domain configured in SiteParameters or environment'))
            return

        _sync_django_site(
            sp,
            fallback_domain=os.getenv('SITE_DOMAIN'),
            fallback_name=os.getenv('SITE_NAME'),
        )

        from django.contrib.sites.models import Site
        site = Site.objects.get(id=1)
        self.stdout.write(self.style.SUCCESS(f'Site: {site.domain} - {site.name}'))
