import os

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from site_settings.validators import validate_brand_mark_dimensions, validate_brand_mark_format, validate_branding_image_size


class SiteSettings(models.Model):
    branding_text = models.CharField(
        max_length=50,
        blank=True,
        default='',
        verbose_name=_('Branding text'),
        help_text=_('Optional name displayed in the header next to the brand mark. Defaults to the site name from Django Sites if empty.'),
    )
    brand_mark = models.ImageField(
        upload_to='site_branding/',
        blank=True,
        null=True,
        validators=[validate_branding_image_size, validate_brand_mark_dimensions, validate_brand_mark_format],
        verbose_name=_('Brand mark'),
        help_text=_('Graphic mark (longest side 512-1024 px, max 1 MB). Non-square images are letterboxed to a square on save. Source for favicon and PWA icons.'),
    )
    brand_mark_dark = models.ImageField(
        upload_to='site_branding/',
        blank=True,
        null=True,
        validators=[validate_branding_image_size, validate_brand_mark_dimensions, validate_brand_mark_format],
        verbose_name=_('Brand mark (dark themes)'),
        help_text=_('Optional variant for dark themes. Falls back to the main brand mark if empty.'),
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = _('Site settings')

    def __str__(self):
        return 'Site Settings'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # late import — services.py importuje PIL, niepotrzebnie ładować przy każdym ładowaniu modelu
        from site_settings.services import cleanup_brand_derivatives, letterbox_to_square, regenerate_brand_derivatives
        # I/O na dysku po super().save() — przy rollbacku transakcji pliki pozostają orphan w MEDIA_ROOT.
        # Akceptujemy tę cenę: SiteSettings to singleton edytowany rzadko (admin manual), prawdziwy rollback prawie nie występuje.
        # letterbox prostokątów do kwadratu PRZED regen derivatives (żeby favicon/PWA wynikały z kwadratu)
        if self.brand_mark:
            letterbox_to_square(self.brand_mark.path)
            regenerate_brand_derivatives(self)
        else:
            cleanup_brand_derivatives(self)
        # brand_mark_dark dostaje tylko letterbox — derivatives (favicon/PWA) zawsze z brand_mark (jasna wersja),
        # bo favicon w karcie przeglądarki i ikony PWA są theme-independent (rządzi system OS, nie app theme)
        if self.brand_mark_dark:
            letterbox_to_square(self.brand_mark_dark.path)

    def has_brand_derivatives(self):
        """Check if derived branding files (favicon, apple-touch-icon, etc.) exist on disk."""
        if not self.brand_mark:
            return False
        derived_dir = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived')
        favicon_path = os.path.join(derived_dir, 'favicon.ico')
        return os.path.isfile(favicon_path)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SiteParameters(models.Model):
    """Singleton holding database-backed system parameters votable via referendum.

    Seeded from ``django.conf.settings`` (env defaults) on first access. See
    ``site_settings/params.py`` for the parameter registry and apply logic.
    """
    # Voting parameters
    wymaganych_podpisow = models.PositiveIntegerField(default=2, verbose_name=_('Required signatures'))
    czas_na_zebranie_podpisow = models.PositiveIntegerField(default=365, verbose_name=_('Time to gather signatures (days)'))
    dyskusja = models.PositiveIntegerField(default=3, verbose_name=_('Discussion period (days)'))
    czas_trwania_referendum = models.PositiveIntegerField(default=3, verbose_name=_('Referendum duration (days)'))
    # Chat settings
    archive_public_chat_room = models.PositiveIntegerField(default=9, verbose_name=_('Archive public chat room after (days)'))
    delete_public_chat_room = models.PositiveIntegerField(default=360, verbose_name=_('Delete public chat room after (days)'))
    # Citizens settings
    acceptance = models.PositiveIntegerField(default=3, verbose_name=_('Acceptance threshold'))
    delete_inactive_user_after = models.PositiveIntegerField(default=30, verbose_name=_('Delete inactive user after (days)'))
    # Group settings
    group_is_public = models.BooleanField(default=True, verbose_name=_('Group is public'))
    # Site identity
    site_domain = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Site domain'))
    site_name = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Site name'))
    site_name_max_12_chars = models.CharField(max_length=12, blank=True, default='', verbose_name=_('Short site name (PWA)'))
    site_description = models.CharField(max_length=500, blank=True, default='', verbose_name=_('Site description'))

    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = _('Site parameters')
        verbose_name_plural = _('Site parameters')

    def __str__(self):
        return 'Site Parameters'

    @classmethod
    def get(cls):
        """Return the singleton, creating and seeding it from settings if missing."""
        from site_settings.params import seed_defaults

        obj = cls.objects.filter(pk=1).first()
        if obj is None:
            defaults = {k: v for k, v in seed_defaults().items() if v is not None}
            obj, _created = cls.objects.get_or_create(pk=1, defaults=defaults)
        return obj


class QuickLink(models.Model):
    title = models.CharField(max_length=100, verbose_name=_('Title'))
    url = models.CharField(max_length=500, verbose_name=_('URL'))
    icon = models.CharField(max_length=50, blank=True, default='', verbose_name=_('Icon (FontAwesome class)'))
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Quick link')
        verbose_name_plural = _('Quick links')

    def __str__(self):
        return self.title
