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
