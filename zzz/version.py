"""Runtime build reference (short git SHA) for the application UI."""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_BUILD_SHA_FILENAMES = ["BUILD_SHA", ".build_sha"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _build_sha_from_file() -> str | None:
    for name in _BUILD_SHA_FILENAMES:
        path = _repo_root() / name
        if path.exists():
            return path.read_text(encoding="utf-8").strip() or None
    return None


def get_short_sha(fallback: str = "unknown") -> str:
    """Return the short git SHA from a build-time file or the local repo."""
    sha = _build_sha_from_file()
    if sha:
        return sha

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_repo_root(),
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        log.debug("Unable to determine short SHA: %s", exc)
        return fallback


__version__ = get_short_sha()
