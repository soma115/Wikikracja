"""Base classes for project management commands."""

from django.conf import settings as s
from django.core.management.base import BaseCommand

from zzz.utils import get_site_domain


class TranslatedCommand(BaseCommand):
    """Management command base that activates the project locale and sets self.host."""

    help = ''

    def handle(self, *args, **options):
        from django.utils import translation

        translation.activate(s.LANGUAGE_CODE)
        self.host = get_site_domain()
        return self.run(*args, **options)

    def run(self, *args, **options):
        raise NotImplementedError("Subclasses must implement run()")
