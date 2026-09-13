from site_settings.models import SiteParameters
from site_settings.services import get_branding_version


def branding(request):
    """Wstrzykuje SiteParameters (logo, brand mark) + version (cache-bust) do każdego template'u."""
    ss = SiteParameters.get()
    return {'branding': ss, 'branding_version': get_branding_version(ss)}
