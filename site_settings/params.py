"""Central registry of database-backed, votable system parameters.

These values used to live in environment variables / ``django.conf.settings``.
They are now stored on the ``SiteParameters`` singleton so citizens can change
them through a referendum (see ``glosowania``). This module is the single
source of truth describing every votable parameter and drives:

- seeding of the singleton from ``settings`` defaults,
- the proposal form (``ParametersProposalForm``),
- the human readable change list shown in the referendum,
- applying approved changes back onto the singleton (and Django Sites).

Parameter kinds:
    ``int``  -> non-negative integer
    ``bool`` -> boolean
    ``str``  -> free text
"""
from django.utils.translation import gettext_lazy as _

# Category keys used to group parameters in the proposal form / display.
CATEGORY_VOTING = 'voting'
CATEGORY_CHAT = 'chat'
CATEGORY_CITIZENS = 'citizens'
CATEGORY_GROUP = 'group'
CATEGORY_SITE = 'site'

CATEGORY_LABELS = {
    CATEGORY_VOTING: _('Voting parameters'),
    CATEGORY_CHAT: _('Chat settings'),
    CATEGORY_CITIZENS: _('Citizens settings'),
    CATEGORY_GROUP: _('Group settings'),
    CATEGORY_SITE: _('Site identity'),
}

# Ordered category list controls display / form ordering.
CATEGORY_ORDER = [
    CATEGORY_VOTING,
    CATEGORY_CHAT,
    CATEGORY_CITIZENS,
    CATEGORY_GROUP,
    CATEGORY_SITE,
]


class ParamSpec:
    """Describes a single votable parameter."""

    def __init__(self, name, settings_name, kind, category, label, help_text='', unit='', warning='', min_value=None, max_value=None):
        self.name = name  # field name on SiteParameters
        self.settings_name = settings_name  # django.conf.settings attribute used as seed default
        self.kind = kind  # 'int' | 'bool' | 'str'
        self.category = category
        self.label = label
        self.help_text = help_text
        self.unit = unit  # e.g. _('days'); shown next to the value
        self.warning = warning  # optional caution shown in the form
        # Hardcoded inclusive bounds for 'int' parameters (None = unbounded).
        self.min_value = min_value
        self.max_value = max_value


PARAM_SPECS = [
    # --- Voting parameters ---
    ParamSpec('wymaganych_podpisow', 'WYMAGANYCH_PODPISOW', 'int', CATEGORY_VOTING,
              _('Required signatures'),
              _('Number of signatures a new proposal must gather to trigger a referendum.'),
              min_value=2, max_value=20),
    ParamSpec('czas_na_zebranie_podpisow', 'CZAS_NA_ZEBRANIE_PODPISOW', 'int', CATEGORY_VOTING,
              _('Time to gather signatures'),
              _('Maximum number of days to gather signatures before a proposal is rejected.'),
              unit=_('days'), min_value=1, max_value=3650),
    ParamSpec('dyskusja', 'DYSKUSJA', 'int', CATEGORY_VOTING,
              _('Discussion period'),
              _('Number of days a proposal stays in queue/discussion before the referendum starts.'),
              unit=_('days'), min_value=1, max_value=365),
    ParamSpec('czas_trwania_referendum', 'CZAS_TRWANIA_REFERENDUM', 'int', CATEGORY_VOTING,
              _('Referendum duration'),
              _('Number of days a referendum lasts.'),
              unit=_('days'), min_value=1, max_value=365),
    # --- Chat settings ---
    ParamSpec('archive_public_chat_room', 'ARCHIVE_PUBLIC_CHAT_ROOM', 'int', CATEGORY_CHAT,
              _('Archive public chat room after'),
              _('Public chat rooms are archived after this many days without activity.'),
              unit=_('days'), min_value=1, max_value=3650),
    ParamSpec('delete_public_chat_room', 'DELETE_PUBLIC_CHAT_ROOM', 'int', CATEGORY_CHAT,
              _('Delete public chat room after'),
              _('Public chat rooms are deleted after this many days without activity.'),
              unit=_('days'), min_value=1, max_value=3650),
    # --- Citizens settings ---
    ParamSpec('acceptance', 'ACCEPTANCE', 'int', CATEGORY_CITIZENS,
              _('Acceptance threshold'),
              _('Reputation threshold for accepting new members and protecting existing ones.'),
              min_value=1, max_value=100),
    ParamSpec('delete_inactive_user_after', 'DELETE_INACTIVE_USER_AFTER', 'int', CATEGORY_CITIZENS,
              _('Delete inactive user after'),
              _('Inactive/unconfirmed users are removed after this many days.'),
              unit=_('days'), min_value=1, max_value=3650),
    # --- Group settings ---
    ParamSpec('group_is_public', 'GROUP_IS_PUBLIC', 'bool', CATEGORY_GROUP,
              _('Group is public'),
              _('If enabled, anyone can register and the public inbox is available.')),
    # --- Site identity ---
    ParamSpec('site_name', 'SITE_NAME', 'str', CATEGORY_SITE,
              _('Site name'),
              _('Full name of the instance shown across the site.')),
]

SPECS_BY_NAME = {spec.name: spec for spec in PARAM_SPECS}


def specs_by_category():
    """Yield ``(category_key, category_label, [ParamSpec, ...])`` in display order."""
    for category in CATEGORY_ORDER:
        specs = [s for s in PARAM_SPECS if s.category == category]
        if specs:
            yield category, CATEGORY_LABELS[category], specs


def seed_defaults():
    """Return a dict of ``{name: default}`` seeded from ``django.conf.settings``."""
    from django.conf import settings
    defaults = {}
    for spec in PARAM_SPECS:
        defaults[spec.name] = getattr(settings, spec.settings_name, None)
    return defaults


def coerce(spec, raw):
    """Coerce a raw value to the python type expected by ``spec``."""
    if spec.kind == 'int':
        return int(raw)
    if spec.kind == 'bool':
        if isinstance(raw, str):
            return raw.strip().lower() in ('1', 'true', 't', 'yes', 'y', 'on')
        return bool(raw)
    return '' if raw is None else str(raw)


def clamp(spec, value):
    """Clamp an int value to the spec's hardcoded [min_value, max_value] bounds."""
    if spec.kind != 'int':
        return value
    if spec.min_value is not None and value < spec.min_value:
        return spec.min_value
    if spec.max_value is not None and value > spec.max_value:
        return spec.max_value
    return value


def display_value(spec, value):
    """Return a human readable representation of a parameter value."""
    if spec.kind == 'bool':
        return _('Yes') if value else _('No')
    text = '' if value is None else str(value)
    if spec.unit and text != '':
        return f'{text} {spec.unit}'
    return text


def describe_changes(proposed):
    """Return a list of ``(label, old_display, new_display)`` for the proposed changes.

    Compares the proposed values against the current singleton values.
    """
    from site_settings.models import SiteParameters

    current = SiteParameters.get()
    rows = []
    for spec in PARAM_SPECS:
        if spec.name not in proposed:
            continue
        old = getattr(current, spec.name)
        new = coerce(spec, proposed[spec.name])
        rows.append((spec.label, display_value(spec, old), display_value(spec, new)))
    return rows


def get_param(name):
    """Return the current value of a single parameter from the singleton."""
    from site_settings.models import SiteParameters
    return getattr(SiteParameters.get(), name)


def apply_parameters(proposed):
    """Apply a ``{name: value}`` mapping of approved changes to the singleton.

    Also syncs the Django Sites entry when ``site_name`` changes,
    since it is read from the ``django_site`` table at runtime.
    The domain is always taken from ``settings.SITE_DOMAIN``.
    """
    from site_settings.models import SiteParameters

    sp = SiteParameters.get()
    for name, value in proposed.items():
        spec = SPECS_BY_NAME.get(name)
        if spec is None:
            continue
        setattr(sp, name, clamp(spec, coerce(spec, value)))
    sp.save()

    if 'site_name' in proposed:
        _sync_django_site(sp)
    return sp


def apply_brand_mark(image_field_file):
    """Copy a proposed logo file onto the SiteSettings brand mark and save.

    Saving triggers SiteSettings.save(), which letterboxes the image and
    regenerates favicon / PWA derivatives.
    """
    import os

    from site_settings.models import SiteSettings

    if not image_field_file:
        return
    ss = SiteSettings.get()
    image_field_file.open('rb')
    ss.brand_mark.save(os.path.basename(image_field_file.name), image_field_file, save=True)


def _sync_django_site(sp, fallback_domain=None, fallback_name=None):
    from contextlib import suppress

    from django.contrib.sites.models import Site

    with suppress(Exception):
        from django.conf import settings

        domain = getattr(settings, 'SITE_DOMAIN', '') or fallback_domain
        name = sp.site_name or fallback_name or domain

        if not domain:
            return

        try:
            site = Site.objects.get(id=1)
        except Site.DoesNotExist:
            Site.objects.create(id=1, domain=domain, name=name or domain)
        else:
            changed = False
            if site.domain != domain:
                site.domain = domain
                changed = True
            if name and site.name != name:
                site.name = name
                changed = True
            if changed:
                site.save()

        # Drop the per-process Sites cache so request.site reflects the new
        # values without an application restart.
        Site.objects.clear_cache()
