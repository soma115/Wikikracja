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
