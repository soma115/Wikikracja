from site_settings.models import SiteSettings
from site_settings.services import get_branding_version


def branding(request):
    """Wstrzykuje SiteSettings (logo, brand mark) + version (cache-bust) do każdego template'u."""
    ss = SiteSettings.get()
    return {'branding': ss, 'branding_version': get_branding_version(ss)}
