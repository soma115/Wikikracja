import os

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from site_settings.validators import validate_brand_mark_dimensions, validate_brand_mark_format, validate_branding_image_size


class SiteSettings(models.Model):
    brand_mark = models.ImageField(
        upload_to='site_branding/',
        blank=True,
        null=True,
        validators=[validate_branding_image_size, validate_brand_mark_dimensions, validate_brand_mark_format],
        verbose_name=_('Brand mark'),
        help_text=_('Graphic mark (PNG/JPEG/WebP/GIF, max 5 MB, source 64-4096 px). Resized to 1024×1024 px PNG with letterbox and converted to favicon/PWA icons on save.'),
    )
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = _('Site settings')

    def __str__(self):
        return 'Site Settings'

    def save(self, *args, **kwargs):
        # late import — services.py importuje PIL, niepotrzebnie ładować przy każdym ładowaniu modelu
        from site_settings.services import cleanup_brand_derivatives, normalize_brand_mark, regenerate_brand_derivatives

        # Normalizujemy do 1024×1024 px PNG PRZED super().save(), żeby na dysk trafił
        # tylko gotowy plik (unikamy kolizji nazw i podwójnego zapisu).
        if self.brand_mark:
            old_name = self.brand_mark.name
            new_name = os.path.splitext(os.path.basename(old_name))[0] + '.png' if old_name else 'brand_mark.png'
            self.brand_mark = normalize_brand_mark(self.brand_mark, target_name=new_name)

        super().save(*args, **kwargs)

        if self.brand_mark:
            regenerate_brand_derivatives(self)
        else:
            cleanup_brand_derivatives(self)

    def has_brand_mark_file(self):
        """Check that brand_mark points to a file which actually exists on disk.

        Guards against a stale DB reference (e.g. media not restored/synced)
        rendering a broken <img> in templates instead of the icon fallback.
        """
        if not self.brand_mark:
            return False
        try:
            return os.path.isfile(self.brand_mark.path)
        except (ValueError, OSError) as _:
            return False

    def has_brand_derivatives(self):
        """Check if derived branding files (favicon, apple-touch-icon, etc.) exist on disk.

        Regenerates missing derivatives automatically to prevent fallback to default favicon.
        """
        if not self.brand_mark:
            return False
        derived_dir = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived')
        favicon_path = os.path.join(derived_dir, 'favicon.ico')

        # If file exists, return True
        if os.path.isfile(favicon_path):
            return True

        # If file is missing but brand_mark exists, regenerate it
        from site_settings.services import regenerate_brand_derivatives

        try:
            regenerate_brand_derivatives(self)
            return os.path.isfile(favicon_path)
        except Exception:
            # If regeneration fails, fall back to False (use default favicon)
            return False

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
    site_name = models.CharField(max_length=255, blank=True, default='', verbose_name=_('Site name'))

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
    order = models.PositiveIntegerField(default=0, verbose_name=_('Order'))

    class Meta:
        ordering = ['order']
        verbose_name = _('Quick link')
        verbose_name_plural = _('Quick links')

    def __str__(self):
        return self.title
