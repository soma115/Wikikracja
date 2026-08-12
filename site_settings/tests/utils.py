import io

from django.core.files.uploadedfile import SimpleUploadedFile


def make_branding_png(width: int = 1024, height: int | None = None, color=(0, 128, 255, 255)) -> SimpleUploadedFile:
    """Generuje PNG do testów brandingu. Domyślnie kwadrat 1024×1024 niebieski z pełnym alpha."""
    from PIL import Image

    if height is None:
        height = width
    img = Image.new('RGBA', (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return SimpleUploadedFile(f'{width}x{height}.png', buf.getvalue(), content_type='image/png')


def make_branding_image(format: str, width: int = 1024, height: int | None = None, color=(0, 128, 255, 255)) -> SimpleUploadedFile:
    """Generuje obrazek w podanym formacie (PNG/JPEG/WebP/GIF) do testów brandingu."""
    from PIL import Image

    if height is None:
        height = width
    mode = 'RGBA' if format in {'PNG', 'WEBP', 'GIF'} else 'RGB'
    if mode == 'RGB' and len(color) == 4:
        color = color[:3]
    img = Image.new(mode, (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    ext = format.lower()
    return SimpleUploadedFile(f'{width}x{height}.{ext}', buf.getvalue(), content_type=f'image/{ext}')
