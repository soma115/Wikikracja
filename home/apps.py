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
                _sync_django_site(sp, fallback_name=settings.SITE_NAME)
            except Exception:
                pass

        # Ensure the global activity feed cache is rebuilt on every process
        # start (e.g. after deploying or restarting the dev server) so the
        # feed does not serve stale data left over from an older cache entry.
        from core.services.feed import invalidate_feed_cache

        invalidate_feed_cache()

        # Cache-invalidation signals for the feed now live in the apps that
        # own the feed-related models (board, chat, events, glosowania,
        # obywatele, tasks).  home.signals is no longer needed.
