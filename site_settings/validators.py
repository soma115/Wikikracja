from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MAX_BRANDING_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
MIN_BRAND_MARK_DIMENSION = 64  # minimalny najdłuższy bok źródła — mniejsze obrazki nie nadają się do upscalowania
MAX_BRAND_MARK_DIMENSION = 4096  # maksymalny najdłuższy bok źródła — większe ładowałyby się zbyt długo
ALLOWED_BRAND_FORMATS = {'PNG', 'JPEG', 'WEBP', 'GIF'}  # konwertowane do PNG przez pipeline


def validate_branding_image_size(file):
    """Odrzuca pliki brandingowe przekraczające 5 MB."""
    if file.size > MAX_BRANDING_FILE_SIZE:
        raise ValidationError(_('Branding image file is too large (max %(max_size)s).'), code='branding_file_too_large', params={'max_size': '5 MB'})


def validate_brand_mark_dimensions(file):
    """Sprawdza, że najdłuższy bok źródła mieści się w rozsądnym zakresie (64-4096 px).

    Właściwe dopasowanie do kwadratu 1024×1024 px dzieje się później przy normalizacji.
    """
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

    longest = max(width, height)

    if longest < MIN_BRAND_MARK_DIMENSION:
        raise ValidationError(_('Brand mark longest side must be at least %(min)d pixels.'), code='branding_too_small', params={'min': MIN_BRAND_MARK_DIMENSION})

    if longest > MAX_BRAND_MARK_DIMENSION:
        raise ValidationError(_('Brand mark longest side must be at most %(max)d pixels.'), code='branding_too_large', params={'max': MAX_BRAND_MARK_DIMENSION})


def validate_brand_mark_format(file):
    """Akceptuje PNG/JPEG/WebP/GIF — pipeline normalizuje obraz do PNG z kanałem alpha."""
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
        raise ValidationError(_('Brand mark must be a PNG, JPEG, WebP or GIF file. Got %(fmt)s.'), code='branding_unsupported_format', params={'fmt': fmt or 'unknown'})
