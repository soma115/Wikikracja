"""Wersjonowanie: jedno źródło prawdy.

Kontrakt (Wariant A):
- `zzz.__version__` jest kanonicznym numerem wersji w runtime.
- Musi być spójny z `pyproject.toml:project.version` (semantic-release bumpuje
  oba w jednym kroku przez `version_variables`) — guard przeciw rozjazdowi.
- Context processor wystawia go do szablonów jako `app_version`.
- Sidebar renderuje wartość dynamicznie, NIE sztywny string.
"""
import tomllib
from pathlib import Path

import pytest

import zzz


def _pyproject_version():
    path = Path(zzz.__file__).resolve().parent.parent / "pyproject.toml"
    with open(path, "rb") as f:
        return tomllib.load(f)["project"]["version"]


def test_version_module_matches_pyproject():
    """zzz.__version__ == pyproject.toml — jedno źródło prawdy, koniec rozjazdu."""
    assert zzz.__version__ == _pyproject_version()


@pytest.mark.django_db
def test_context_processor_exposes_app_version(rf):
    """site_name() wystawia app_version równy zzz.__version__."""
    from zzz.context_processors import site_name

    ctx = site_name(rf.get("/"))
    assert ctx["app_version"] == zzz.__version__


def test_sidebar_renders_dynamic_version(authenticated_client, monkeypatch):
    """Sidebar renderuje wersję z context processora, nie zahardkodowany numer."""
    monkeypatch.setattr("zzz.__version__", "9.9.9-test")
    client, _ = authenticated_client
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"v.9.9.9-test" in resp.content
