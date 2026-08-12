import io
import os

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

DERIVED_SUBDIR = 'site_branding/derived'
TARGET_BRAND_MARK_SIZE = 1024

# wymiary PNG derivatives — używane przez przeglądarki/iOS/Android/PWA
PNG_DERIVATIVES = {
    'apple-touch-icon.png': 180,  # iOS Safari "Dodaj do ekranu głównego"
    'icon-192.png': 192,  # Android PWA install
    'icon-512.png': 512,  # PWA splash screen
}
FAVICON_SIZES = [(16, 16), (32, 32), (48, 48)]  # multi-size ICO


def _process_brand_mark_image(img: Image.Image) -> Image.Image:
    """Skaluj obraz do TARGET_BRAND_MARK_SIZE najdłuższego boku i letterboxuj do kwadratu."""
    img = img.convert('RGBA')
    width, height = img.size
    longest = max(width, height)
    scale = TARGET_BRAND_MARK_SIZE / longest
    new_size = (int(round(width * scale)), int(round(height * scale)))
    if new_size != (width, height):
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    if img.width != TARGET_BRAND_MARK_SIZE or img.height != TARGET_BRAND_MARK_SIZE:
        canvas = Image.new('RGBA', (TARGET_BRAND_MARK_SIZE, TARGET_BRAND_MARK_SIZE), (0, 0, 0, 0))
        canvas.paste(img, ((TARGET_BRAND_MARK_SIZE - img.width) // 2, (TARGET_BRAND_MARK_SIZE - img.height) // 2))
        img = canvas
    return img


def normalize_brand_mark(file, *, target_name='brand_mark.png'):
    """Znormalizuj wczytany obrazek do kwadratowego PNG 1024×1024 px.

    Obsługuje UploadedFile, FieldFile i ścieżki. Zwraca InMemoryUploadedFile.
    """
    try:
        if hasattr(file, 'seek'):
            file.seek(0)
        with Image.open(file) as img:
            normalized = _process_brand_mark_image(img)
            output = io.BytesIO()
            normalized.save(output, format='PNG')
    except (UnidentifiedImageError, OSError) as e:
        raise ValidationError(_('Could not process image file.'), code='branding_image_unreadable') from e

    output.seek(0)
    return InMemoryUploadedFile(output, field_name='brand_mark', name=target_name, content_type='image/png', size=len(output.getvalue()), charset=None)


def regenerate_brand_derivatives(site_settings):
    """Generuje favicon.ico + apple-touch-icon + PWA icons z brand_mark."""
    if not site_settings.brand_mark:
        return

    derived_dir = os.path.join(settings.MEDIA_ROOT, DERIVED_SUBDIR)
    os.makedirs(derived_dir, exist_ok=True)

    with Image.open(site_settings.brand_mark.path) as img:
        # konwersja na RGBA chroni przed plikami bez alpha (np. JPG) — derivatives zawsze z przezroczystością
        rgba = img.convert('RGBA')

        for filename, size in PNG_DERIVATIVES.items():
            resized = rgba.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(os.path.join(derived_dir, filename), format='PNG')

        # multi-size ICO — Pillow natywnie generuje wszystkie rozmiary z listy
        rgba.save(os.path.join(derived_dir, 'favicon.ico'), format='ICO', sizes=FAVICON_SIZES)


def cleanup_brand_derivatives(site_settings):
    """Usuwa wygenerowane derivatives faviconu/PWA z dysku — wołane gdy brand_mark zostaje wyczyszczony."""
    derived_dir = os.path.join(settings.MEDIA_ROOT, DERIVED_SUBDIR)
    if not os.path.isdir(derived_dir):
        return
    for filename in (*PNG_DERIVATIVES.keys(), 'favicon.ico'):
        path = os.path.join(derived_dir, filename)
        if os.path.isfile(path):
            os.remove(path)


def get_branding_version(site_settings):
    """Zwraca unix timestamp z updated_at jako string — query param dla cache-busting."""
    if site_settings.updated_at:
        return str(int(site_settings.updated_at.timestamp()))
    return '0'
