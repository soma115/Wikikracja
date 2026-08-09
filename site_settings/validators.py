from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_BRANDING_FILE_SIZE = 1024 * 1024  # 1 MB
MIN_BRAND_MARK_DIMENSION = 512  # min najdłuższego boku — równy największemu derivative (PWA icon-512)
MAX_BRAND_MARK_DIMENSION = 1024  # max najdłuższego boku — 2× icon-512, dla Retina
ALLOWED_BRAND_FORMATS = {'PNG'}  # wyłącznie PNG — cały pipeline derivatives produkuje PNG, spójne dla admina i magazynowania


def validate_branding_image_size(file):
    """Odrzuca pliki brandingowe przekraczające 1 MB."""
    if file.size > MAX_BRANDING_FILE_SIZE:
        raise ValidationError(_('Branding image file is too large (max 1 MB).'), code='branding_file_too_large')


def validate_brand_mark_dimensions(file):
    """Sprawdza, że najdłuższy bok brand mark jest w zakresie 512-1024 px (prostokąty akceptowane, letterbox przy zapisie)."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(file) as img:
            width, height = img.size
    except (UnidentifiedImageError, OSError) as e:
        raise ValidationError(_('Could not read image file.'), code='branding_image_unreadable') from e
    finally:
        # rewind, żeby Django mogło ponownie odczytać plik do zapisu na dysk
        if hasattr(file, 'seek'):
            file.seek(0)

    # prostokąty są akceptowane — przy zapisie dorabiamy letterbox do kwadratu
    longest = max(width, height)

    if longest < MIN_BRAND_MARK_DIMENSION:
        raise ValidationError(_('Brand mark longest side must be at least %(min)d pixels.'), code='branding_too_small', params={'min': MIN_BRAND_MARK_DIMENSION})

    if longest > MAX_BRAND_MARK_DIMENSION:
        raise ValidationError(_('Brand mark longest side must be at most %(max)d pixels.'), code='branding_too_large', params={'max': MAX_BRAND_MARK_DIMENSION})


def validate_brand_mark_format(file):
    """Akceptuje wyłącznie PNG — cały pipeline derivatives produkuje PNG, WebP odpada dla spójności."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(file) as img:
            fmt = img.format
    except (UnidentifiedImageError, OSError) as e:
        raise ValidationError(_('Could not read image file.'), code='branding_image_unreadable') from e
    finally:
        if hasattr(file, 'seek'):
            file.seek(0)

    if fmt not in ALLOWED_BRAND_FORMATS:
        raise ValidationError(_('Brand mark must be a PNG file (format supporting transparency). Got %(fmt)s.'), code='branding_unsupported_format', params={'fmt': fmt or 'unknown'})
