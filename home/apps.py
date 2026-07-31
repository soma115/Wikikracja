import os

from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.dispatch import receiver


class HomeConfig(AppConfig):
    name = 'home'

    def ready(self):
        @receiver(post_migrate)
        def update_site_domain(sender, **kwargs):
            """Update Django Site from the voted SiteParameters after migrations."""
            from site_settings.models import SiteParameters
            from site_settings.params import _sync_django_site

            try:
                sp = SiteParameters.get()
                _sync_django_site(
                    sp,
                    fallback_domain=os.getenv('SITE_DOMAIN'),
                    fallback_name=os.getenv('SITE_NAME'),
                )
            except Exception:
                pass

        import home.signals  # noqa
