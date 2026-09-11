"""Registry for per-application dashboard widget providers.

Each application that contributes to the logged-in dashboard, public landing page,
or group settings page:
1. implements one or more context builders in `<app>/dashboard.py`;
2. registers them in `<app>/apps.py::ready()`.

`home` no longer needs to import models from other apps to build the dashboard.
"""

from dataclasses import dataclass
from typing import Callable, Optional

DashboardContextProvider = Callable[[object, str], dict]
PublicContextProvider = Callable[[], dict]
GroupSettingsContextProvider = Callable[[object], dict]


@dataclass
class DashboardEntry:
    name: str
    get_context: Optional[DashboardContextProvider] = None
    get_public_context: Optional[PublicContextProvider] = None
    get_group_settings_context: Optional[GroupSettingsContextProvider] = None


_providers: list[DashboardEntry] = []


def register_dashboard_provider(
    name: str, *, get_context: Optional[DashboardContextProvider] = None, get_public_context: Optional[PublicContextProvider] = None, get_group_settings_context: Optional[GroupSettingsContextProvider] = None
) -> None:
    _providers.append(DashboardEntry(name=name, get_context=get_context, get_public_context=get_public_context, get_group_settings_context=get_group_settings_context))


def collect_dashboard_context(user, month_param: str = '') -> dict:
    ctx = {}
    for entry in _providers:
        if entry.get_context:
            ctx.update(entry.get_context(user, month_param))
    return ctx


def collect_public_context() -> dict:
    ctx = {}
    for entry in _providers:
        if entry.get_public_context:
            ctx.update(entry.get_public_context())
    return ctx


def collect_group_settings_context(user) -> dict:
    ctx = {}
    for entry in _providers:
        if entry.get_group_settings_context:
            ctx.update(entry.get_group_settings_context(user))
    return ctx
