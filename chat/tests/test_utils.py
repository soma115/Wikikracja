from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import SimpleTestCase

from chat.utils import get_upload_path


class UploadPathTest(SimpleTestCase):
    def test_accepts_plain_attachment_names(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            for filename in ('image.webp', 'a-b_c.123.png'):
                with self.subTest(filename=filename):
                    self.assertEqual(get_upload_path(filename), Path(media_root).resolve() / 'uploads' / filename)

    def test_rejects_paths_and_unsafe_names_without_normalizing(self):
        filenames = (
            '../image.webp',
            '../../image.webp',
            'nested/image.webp',
            r'nested\image.webp',
            '/image.webp',
            r'C:\image.webp',
            '.hidden.webp',
            'a..webp',
            "folder' data-review='marker/image.webp",
            "image'.webp",
            'image".webp',
            'image.webp?x=1',
            'image.webp#x',
            '%2e%2e.webp',
            'image\x00.webp',
            '',
            None,
            123,
        )
        for filename in filenames:
            with self.subTest(filename=filename):
                self.assertIsNone(get_upload_path(filename))

    def test_rejects_resolved_path_outside_upload_directory(self):
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            root = Path(media_root).resolve()
            with patch.object(Path, 'resolve', side_effect=[root / 'uploads', root / 'outside.webp']):
                self.assertIsNone(get_upload_path('image.webp'))
