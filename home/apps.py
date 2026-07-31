from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate
from django.dispatch import receiver


class HomeConfig(AppConfig):
    name = 'home'

    def ready(self):
        @receiver(post_migrate)
        def update_site(sender, **kwargs):
            """Update django.contrib.sites.models.Site from settings and SiteParameters after migrations."""
            from site_settings.models import SiteParameters
            from site_settings.params import _sync_django_site

            try:
                sp = SiteParameters.get()
                _sync_django_site(
                    sp,
                    fallback_name=settings.SITE_NAME,
                )
            except Exception:
                pass

        import home.signals  # noqa
