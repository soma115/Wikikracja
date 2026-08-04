import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from site_settings.models import SiteSettings
from site_settings.tests.utils import make_branding_png


class SidebarBrandMarkRenderingTest(TestCase):
    """Test 7 (TDD red): sidebar i topbar renderują <img brand-mark> gdy brand_mark istnieje."""

    def setUp(self):
        self.tmp_media = tempfile.mkdtemp(prefix='wikikracja_test_media_')
        self.override = override_settings(MEDIA_ROOT=self.tmp_media)
        self.override.enable()

        User = get_user_model()
        self.user = User.objects.create_user(username='admin', password='testpass123')
        self.client.force_login(self.user)
        self.url = reverse('home')

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp_media, ignore_errors=True)

    def test_renders_fallback_fa_icon_when_no_brand_mark(self):
        response = self.client.get(self.url)
        content = response.content.decode('utf-8')
        self.assertIn('fa-building-columns', content)
        self.assertNotIn('class="brand-mark"', content)

    def test_renders_img_brand_mark_when_brand_mark_exists(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(self.url)
        content = response.content.decode('utf-8')
        # <img brand-mark> obecne (sidebar + topbar; konkretna liczba zależy od theme switching — test 8)
        self.assertIn('class="brand-mark', content)
        # fallback FA ikona już nie renderowana
        self.assertNotIn('fa-building-columns', content)
        # URL z MEDIA_URL
        self.assertIn('/media/site_branding/', content)

class ManifestAndAppleTouchIconBrandTest(TestCase):
    """Test 9 (TDD red): manifest icons + apple-touch-icon link używają derivatives gdy brand_mark istnieje."""

    def setUp(self):
        self.tmp_media = tempfile.mkdtemp(prefix='wikikracja_test_media_')
        self.override = override_settings(MEDIA_ROOT=self.tmp_media)
        self.override.enable()

        User = get_user_model()
        self.user = User.objects.create_user(username='admin', password='testpass123')
        self.client.force_login(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp_media, ignore_errors=True)

    def test_manifest_uses_static_fallback_without_brand_mark(self):
        response = self.client.get(reverse('manifest'))
        srcs = [icon['src'] for icon in response.json()['icons']]
        self.assertTrue(all('/static/home/images/' in src for src in srcs))

    def test_manifest_uses_media_derivatives_with_brand_mark(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(reverse('manifest'))
        srcs = [icon['src'] for icon in response.json()['icons']]
        self.assertEqual(sum('/media/site_branding/derived/' in s for s in srcs), 3)
        self.assertFalse(any('/static/home/images/' in s for s in srcs))

    def test_apple_touch_icon_link_uses_static_fallback_without_brand_mark(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('rel="apple-touch-icon"', content)
        self.assertIn('/static/home/images/favicon.ico', content)

    def test_apple_touch_icon_link_uses_media_with_brand_mark(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('rel="apple-touch-icon"', content)
        self.assertIn('/media/site_branding/derived/apple-touch-icon.png', content)

    def test_favicon_link_uses_static_fallback_without_brand_mark(self):
        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('rel="icon"', content)
        self.assertIn('/static/home/images/favicon.ico', content)

    def test_favicon_link_uses_media_with_brand_mark(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        self.assertIn('rel="icon"', content)
        self.assertIn('/media/site_branding/derived/favicon.ico', content)


class CacheBustVersioningTest(TestCase):
    """Test 10 (TDD red): URL-e brandowych assetów mają ?v=<timestamp> dla cache-bust."""

    def setUp(self):
        self.tmp_media = tempfile.mkdtemp(prefix='wikikracja_test_media_')
        self.override = override_settings(MEDIA_ROOT=self.tmp_media)
        self.override.enable()

        User = get_user_model()
        self.user = User.objects.create_user(username='admin', password='testpass123')
        self.client.force_login(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp_media, ignore_errors=True)

    def test_brand_mark_url_in_template_has_version_param(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        expected_ts = str(int(ss.updated_at.timestamp()))
        self.assertIn(f'{ss.brand_mark.url}?v={expected_ts}', content)

    def test_manifest_media_icons_have_version_param(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(reverse('manifest'))
        srcs = [icon['src'] for icon in response.json()['icons']]
        expected_ts = str(int(ss.updated_at.timestamp()))
        self.assertTrue(all(f'?v={expected_ts}' in src for src in srcs))

    def test_manifest_static_fallback_has_no_version_param(self):
        response = self.client.get(reverse('manifest'))
        srcs = [icon['src'] for icon in response.json()['icons']]
        self.assertFalse(any('?v=' in src for src in srcs))

    def test_apple_touch_icon_link_has_version_param_with_brand_mark(self):
        ss = SiteSettings.get()
        ss.brand_mark = make_branding_png()
        ss.save()

        response = self.client.get(reverse('home'))
        content = response.content.decode('utf-8')
        expected_ts = str(int(ss.updated_at.timestamp()))
        self.assertIn(f'apple-touch-icon.png?v={expected_ts}', content)


