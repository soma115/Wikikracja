import io
import os
import shutil
import tempfile

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import DateTimeField, ImageField
from django.test import TestCase, override_settings

from site_settings.models import SiteSettings
from site_settings.tests.utils import make_branding_png


class SiteSettingsBrandingFieldsTest(TestCase):
    """Test 1 (TDD red): pola brandingowe istnieją na modelu + singleton działa."""

    def test_brand_mark_is_optional_image_field(self):
        field = SiteSettings._meta.get_field('brand_mark')
        self.assertIsInstance(field, ImageField)
        self.assertTrue(field.blank)
        self.assertTrue(field.null)
        self.assertEqual(field.upload_to, 'site_branding/')

    def test_updated_at_is_auto_now_datetime(self):
        field = SiteSettings._meta.get_field('updated_at')
        self.assertIsInstance(field, DateTimeField)
        self.assertTrue(field.auto_now)

    def test_singleton_get_returns_settings_with_empty_branding_and_timestamp(self):
        ss = SiteSettings.get()
        # brand_mark jest opcjonalne, na świeżym singletonie jest puste
        self.assertFalse(bool(ss.brand_mark))
        # updated_at musi być ustawiony automatycznie przez auto_now przy create
        self.assertIsNotNone(ss.updated_at)


class SiteSettingsBrandingSizeValidatorTest(TestCase):
    """Test 2 (TDD red): walidator rozmiaru pliku — limit 1 MB dla pól brandingowych."""

    LIMIT_BYTES = 1024 * 1024  # 1 MB

    def test_validator_rejects_file_just_over_1mb(self):
        from site_settings.validators import validate_branding_image_size

        big_file = SimpleUploadedFile('big.png', b'x' * (self.LIMIT_BYTES + 1), content_type='image/png')
        with self.assertRaises(ValidationError):
            validate_branding_image_size(big_file)

    def test_validator_accepts_file_at_exactly_1mb(self):
        from site_settings.validators import validate_branding_image_size

        ok_file = SimpleUploadedFile('ok.png', b'x' * self.LIMIT_BYTES, content_type='image/png')
        # boundary inclusive — nie powinno rzucać
        validate_branding_image_size(ok_file)

    def test_brand_mark_field_has_size_validator_attached(self):
        from site_settings.validators import validate_branding_image_size

        field = SiteSettings._meta.get_field('brand_mark')
        self.assertIn(validate_branding_image_size, field.validators)


class SiteSettingsBrandingDimensionsValidatorTest(TestCase):
    """Test 3 (TDD red): walidator wymiarów — najdłuższy bok 512-1024 px (prostokąty OK, letterbox dorabia kwadrat przy zapisie)."""

    def test_validator_accepts_minimum_square_512x512(self):
        from site_settings.validators import validate_brand_mark_dimensions

        validate_brand_mark_dimensions(make_branding_png(512, 512))

    def test_validator_accepts_maximum_square_1024x1024(self):
        from site_settings.validators import validate_brand_mark_dimensions

        validate_brand_mark_dimensions(make_branding_png(1024, 1024))

    def test_validator_accepts_non_square_rectangle_within_range(self):
        from site_settings.validators import validate_brand_mark_dimensions

        # prostokąt 1024×500: longest=1024 (≤max), akceptowany — letterbox dorobi kwadrat przy save
        validate_brand_mark_dimensions(make_branding_png(1024, 500))

    def test_validator_rejects_too_small_square(self):
        from site_settings.validators import validate_brand_mark_dimensions

        with self.assertRaises(ValidationError) as ctx:
            validate_brand_mark_dimensions(make_branding_png(511, 511))
        self.assertEqual(ctx.exception.code, 'branding_too_small')

    def test_validator_rejects_too_large_square(self):
        from site_settings.validators import validate_brand_mark_dimensions

        with self.assertRaises(ValidationError) as ctx:
            validate_brand_mark_dimensions(make_branding_png(1025, 1025))
        self.assertEqual(ctx.exception.code, 'branding_too_large')

    def test_brand_mark_field_has_dimensions_validator_attached(self):
        from site_settings.validators import validate_brand_mark_dimensions

        field = SiteSettings._meta.get_field('brand_mark')
        self.assertIn(validate_brand_mark_dimensions, field.validators)


class SiteSettingsBrandMarkFormatValidatorTest(TestCase):
    """Test: walidator akceptuje wyłącznie PNG (cały pipeline derivatives produkuje PNG)."""

    @staticmethod
    def _make_image(format: str, mode: str = 'RGBA') -> SimpleUploadedFile:
        from PIL import Image

        img = Image.new(mode, (512, 512), (0, 128, 255, 255) if mode == 'RGBA' else (0, 128, 255))
        buf = io.BytesIO()
        img.save(buf, format=format)
        buf.seek(0)
        ext = format.lower()
        return SimpleUploadedFile(f'test.{ext}', buf.getvalue(), content_type=f'image/{ext}')

    def test_validator_accepts_png(self):
        from site_settings.validators import validate_brand_mark_format

        validate_brand_mark_format(self._make_image('PNG'))

    def test_validator_rejects_webp(self):
        # WebP zawiera alpha, ale cały pipeline derivatives produkuje PNG — akceptujemy tylko PNG dla spójności
        from site_settings.validators import validate_brand_mark_format

        with self.assertRaises(ValidationError) as ctx:
            validate_brand_mark_format(self._make_image('WEBP'))
        self.assertEqual(ctx.exception.code, 'branding_unsupported_format')

    def test_validator_rejects_jpeg(self):
        from site_settings.validators import validate_brand_mark_format

        with self.assertRaises(ValidationError) as ctx:
            validate_brand_mark_format(self._make_image('JPEG', mode='RGB'))
        self.assertEqual(ctx.exception.code, 'branding_unsupported_format')

    def test_brand_mark_field_has_format_validator_attached(self):
        from site_settings.validators import validate_brand_mark_format

        field = SiteSettings._meta.get_field('brand_mark')
        self.assertIn(validate_brand_mark_format, field.validators)


class SiteSettingsBrandingDerivativesTest(TestCase):
    """Test 4 (TDD red): po zapisie brand_mark Pillow generuje derivatives faviconu/PWA."""

    def setUp(self):
        self.tmp_media = tempfile.mkdtemp(prefix='wikikracja_test_media_')
        self.override = override_settings(MEDIA_ROOT=self.tmp_media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp_media, ignore_errors=True)

    def _save_brand_mark(self, size: int = 1024) -> SiteSettings:
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png(size, color=(255, 0, 0, 255))
        ss.save()
        return ss

    def test_save_creates_favicon_ico(self):
        self._save_brand_mark()
        path = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived', 'favicon.ico')
        self.assertTrue(os.path.exists(path), f'favicon.ico not generated at {path}')

    def test_save_creates_apple_touch_icon_180x180(self):
        from PIL import Image

        self._save_brand_mark()
        path = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived', 'apple-touch-icon.png')
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (180, 180))

    def test_save_creates_pwa_icon_192x192(self):
        from PIL import Image

        self._save_brand_mark()
        path = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived', 'icon-192.png')
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (192, 192))

    def test_save_creates_pwa_icon_512x512(self):
        from PIL import Image

        self._save_brand_mark()
        path = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived', 'icon-512.png')
        self.assertTrue(os.path.exists(path))
        with Image.open(path) as img:
            self.assertEqual(img.size, (512, 512))

    def test_save_without_brand_mark_does_not_create_derivatives(self):
        ss = SiteSettings.get()
        ss.save()
        derived_dir = os.path.join(settings.MEDIA_ROOT, 'site_branding', 'derived')
        has_files = os.path.exists(derived_dir) and bool(os.listdir(derived_dir))
        self.assertFalse(has_files, 'derived dir should be empty without brand_mark')


class SiteSettingsBrandingLetterboxTest(TestCase):
    """Test: po zapisie brand_mark jako prostokąt, plik na dysku jest letterbox'em do kwadratu."""

    def setUp(self):
        self.tmp_media = tempfile.mkdtemp(prefix='wikikracja_test_media_')
        self.override = override_settings(MEDIA_ROOT=self.tmp_media)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp_media, ignore_errors=True)

    def test_save_letterboxes_wide_brand_mark_to_square(self):
        from PIL import Image

        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png(1024, 500, color=(255, 0, 0, 255))
        ss.save()
        with Image.open(ss.brand_mark.path) as img:
            self.assertEqual(img.size, (1024, 1024))

    def test_save_letterboxes_tall_brand_mark_to_square(self):
        from PIL import Image

        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png(600, 1024, color=(255, 0, 0, 255))
        ss.save()
        with Image.open(ss.brand_mark.path) as img:
            self.assertEqual(img.size, (1024, 1024))
