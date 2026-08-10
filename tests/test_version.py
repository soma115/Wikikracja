"""Wersjonowanie: short git SHA jako build ref."""

import re

import pytest

import zzz


def test_version_is_short_sha_or_fallback():
    """zzz.__version__ to krótki SHA (7+ znaków hex) lub fallback 'unknown'."""
    assert zzz.__version__ and len(zzz.__version__) >= 7
    assert re.fullmatch(r"[0-9a-f]{7,}|unknown", zzz.__version__)


@pytest.mark.django_db
def test_context_processor_exposes_app_version(rf):
    """site_name() wystawia app_version równy zzz.__version__."""
    from zzz.context_processors import site_name

    ctx = site_name(rf.get("/"))
    assert ctx["app_version"] == zzz.__version__


def test_sidebar_renders_dynamic_version(authenticated_client, monkeypatch):
    """Sidebar renderuje wartość z context processora, nie zahardkodowany string."""
    monkeypatch.setattr("zzz.__version__", "abc1234-test")
    client, _ = authenticated_client
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"v.abc1234-test" in resp.content
