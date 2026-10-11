#!/usr/bin/env python3
"""
Run the full verification pipeline: ruff, UI guards, Django system checks,
translation compilation, collectstatic, pytest, jest and Playwright.

Runs Django checks against temporary database, media and static paths.
The shared command runner is reused without loading or changing the local .env.
"""

import argparse
import atexit
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from regression_scan import run_regression_scan
from start_dev import BASE_DIR
from start_dev import run as run_command


def _run_step(command, name):
    print(f"\n[full-pipeline] {name}")
    try:
        run_command(command)
    except subprocess.CalledProcessError as exc:
        print(f"[full-pipeline] FAILED: {name}")
        print(f"[full-pipeline] Command: {' '.join(map(str, command))}")
        print(f"[full-pipeline] Exit code: {exc.returncode}")
        if name == "Playwright end-to-end tests":
            print(f"[full-pipeline] Playwright artifacts: {BASE_DIR / 'test-results'}")
            print(f"[full-pipeline] Playwright report: {BASE_DIR / 'playwright-report'}")
        raise SystemExit(exc.returncode or 1) from None
    except OSError as exc:
        print(f"[full-pipeline] FAILED: {name}")
        print(f"[full-pipeline] Command: {' '.join(map(str, command))}")
        print(f"[full-pipeline] OS error: {exc}")
        raise SystemExit(1) from None


def _configure_isolated_verification_environment():
    temporary_directory = tempfile.TemporaryDirectory(prefix="wikikracja-tests-")
    root = Path(temporary_directory.name)
    values = {
        "PYTHON_DOTENV_DISABLED": "1",
        "DJANGO_SETTINGS_MODULE": "zzz.test_settings",
        "SECRET_KEY": secrets.token_urlsafe(50),
        "DEBUG": "false",
        "SQLITE_DATABASE_PATH": str(root / "db.sqlite3"),
        "WIKIKRACJA_TEST_MEDIA_ROOT": str(root / "media"),
        "WIKIKRACJA_TEST_STATIC_ROOT": str(root / "static"),
        "SCHEDULER_ENABLED": "false",
        "RUN_MAIN": "false",
        "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        "EMAIL_HOST": "",
        "EMAIL_HOST_USER": "",
        "EMAIL_HOST_PASSWORD": "",
        "FIREBASE_CERT_PATH": "",
        "FIREBASE_CERT_JSON": "",
        "FIREBASE_CERT_BASE64": "",
        "GOOGLE_APPLICATION_CREDENTIALS": "",
    }
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)

    def restore_environment():
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        temporary_directory.cleanup()

    atexit.register(restore_environment)


def _e2e_base_url():
    local_config = dotenv_values(BASE_DIR / ".env.local")
    if not local_config.get("E2E_EMAIL") or not local_config.get("E2E_PASSWORD"):
        raise SystemExit("Playwright requires the dedicated E2E_EMAIL and E2E_PASSWORD in .env.local.")

    base_url = os.environ.get("E2E_BASE_URL") or local_config.get("E2E_BASE_URL")
    if not base_url:
        raise SystemExit("Set E2E_BASE_URL to the dedicated local E2E server in .env.local or the environment.")

    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        raise SystemExit("E2E_BASE_URL must be a valid HTTP(S) URL for a local E2E server.") from None

    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or port == 0
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise SystemExit("E2E_BASE_URL must be an HTTP(S) URL for a local E2E server, without credentials or a path.")

    os.environ["E2E_EMAIL"] = local_config["E2E_EMAIL"]
    os.environ["E2E_PASSWORD"] = local_config["E2E_PASSWORD"]
    os.environ["E2E_BASE_URL"] = base_url.rstrip("/")
    return os.environ["E2E_BASE_URL"]


def _dev_server_is_ready(base_url, timeout=1):
    try:
        with urllib.request.urlopen(f"{base_url}/healthz/live/", timeout=timeout) as resp:
            return resp.status == 200 and resp.read().decode().strip() == "ok"
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def playwright_check():
    npx = shutil.which("npx")
    if sys.platform == "win32" and npx and not npx.lower().endswith((".exe", ".cmd", ".bat")):
        npx = shutil.which("npx.cmd") or npx
    if npx is None:
        print("npx not found in PATH. Install Node or use --no-playwright.")
        sys.exit(1)

    base_url = _e2e_base_url()
    if not _dev_server_is_ready(base_url):
        raise SystemExit(f"The dedicated E2E server is not ready at {base_url}.")

    os.environ["PLAYWRIGHT_BASE_URL"] = base_url
    _run_step([npx, "playwright", "test", "--reporter=line"], "Playwright end-to-end tests")


def tailwind_build_check():
    """Ensure tailwind.build.css is up to date with tailwind.css and config."""
    build_file = BASE_DIR / 'home' / 'static' / 'home' / 'css' / 'tailwind.build.css'
    if not build_file.exists():
        print("tailwind.build.css not found; run `npm run build:css`.")
        sys.exit(1)

    npx = shutil.which("npx")
    if sys.platform == "win32" and npx and not npx.lower().endswith((".exe", ".cmd", ".bat")):
        npx = shutil.which("npx.cmd") or npx
    if npx is None:
        print("npx not found. Cannot check Tailwind build freshness.")
        sys.exit(1)

    with tempfile.TemporaryDirectory(prefix="wikikracja-tailwind-") as temp_directory:
        temp_build = Path(temp_directory) / "tailwind.build.css"
        cmd = [npx, "tailwindcss", "-i", "./home/static/home/css/tailwind.css", "-o", str(temp_build)]
        print("$", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True, cwd=BASE_DIR, env=os.environ.copy())
        except subprocess.CalledProcessError as e:
            print("[full-pipeline] FAILED: Tailwind CSS build")
            print(f"[full-pipeline] Command: {' '.join(map(str, cmd))}")
            print(f"[full-pipeline] Exit code: {e.returncode}")
            sys.exit(e.returncode or 1)

        original = build_file.read_text(encoding='utf-8')
        rebuilt = temp_build.read_text(encoding='utf-8')

    if original != rebuilt:
        print("tailwind.build.css is out of date. Run `npm run build:css` and commit the result.")
        sys.exit(1)
    print("Tailwind build: OK (tailwind.build.css is up to date).")


def _ui_guard_base():
    configured = os.environ.get("UI_GUARD_BASE")
    if configured:
        return configured
    try:
        subprocess.run(["git", "rev-parse", "--verify", "origin/main"], cwd=BASE_DIR, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "HEAD"
    return "origin/main"


def verify_runtime():
    """Fail early when verification is run with an incomplete environment."""
    if sys.version_info < (3, 14):
        print(f"Python 3.14+ is required; found {sys.version.split()[0]}.")
        sys.exit(1)

    try:
        import django
    except ImportError:
        print("Django is not installed in the active environment.")
        sys.exit(1)
    if django.VERSION < (6, 0):
        print(f"Django 6.0+ is required; found {django.get_version()}.")
        sys.exit(1)

    try:
        import pytest_asyncio  # noqa: F401
    except ImportError:
        print("pytest-asyncio is required for the asynchronous WebSocket tests.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Run all project checks and tests.")
    parser.add_argument("--no-ruff", action="store_true", help="Skip ruff lint and format checks.")
    parser.add_argument("--no-django-check", action="store_true", help="Skip Django system checks.")
    parser.add_argument("--no-collectstatic", action="store_true", help="Skip collectstatic.")
    parser.add_argument("--no-pytest", action="store_true", help="Skip Python tests.")
    parser.add_argument("--no-jest", action="store_true", help="Skip JavaScript tests.")
    parser.add_argument("--no-regression-scan", action="store_true", help="Skip Bootstrap/deleted-CSS regression scan.")
    parser.add_argument("--no-ui-guard", action="store_true", help="Skip the changed-file UI unification guard.")
    parser.add_argument("--no-tailwind-build-check", action="store_true", help="Skip tailwind.build.css freshness check.")
    parser.add_argument("--no-compilemessages", action="store_true", help="Skip translation compilation.")
    parser.add_argument("--no-playwright", action="store_true", help="Skip Playwright end-to-end tests.")
    args = parser.parse_args()

    verify_runtime()
    if sys.prefix == sys.base_prefix:
        print("Activate your virtualenv first.")
        sys.exit(1)

    _configure_isolated_verification_environment()
    print(f"Running in: {BASE_DIR}\n")

    if not args.no_ruff:
        _run_step([sys.executable, "-m", "ruff", "check", "."], "Ruff lint")
        _run_step([sys.executable, "-m", "ruff", "format", "--check", "."], "Ruff format")

    if not args.no_regression_scan:
        if run_regression_scan() != 0:
            print("[full-pipeline] FAILED: Regression scan")
            print("[full-pipeline] Command: scripts/regression_scan.py")
            print("[full-pipeline] Exit code: 1")
            sys.exit(1)

    if not args.no_ui_guard:
        _run_step([sys.executable, "scripts/ui_guard.py", "--base", _ui_guard_base()], "UI unification guard")

    if not args.no_tailwind_build_check:
        tailwind_build_check()

    manage = [sys.executable, "manage.py"]

    if not args.no_django_check:
        _run_step(manage + ["check"], "Django system check")

    if not args.no_compilemessages:
        _run_step(manage + ["compilemessages", "-v", "0"], "Translation compilation")

    if not args.no_collectstatic:
        _run_step(manage + ["collectstatic", "--noinput", "--clear"], "Django collectstatic")

    if not args.no_pytest:
        # Use half of the available CPU threads for the test suite.
        test_threads = max(1, (os.cpu_count() or 1) // 2)
        _run_step([sys.executable, "-m", "pytest", "-q", "-n", str(test_threads)], "pytest")

    if not args.no_jest:
        npx = shutil.which("npx")
        # On Windows the bare "npx" path may not be a Win32 executable; prefer npx.cmd.
        if sys.platform == "win32" and npx and not npx.lower().endswith((".exe", ".cmd", ".bat")):
            npx = shutil.which("npx.cmd") or npx
        if npx is None:
            print("npx not found in PATH. Install Node or use --no-jest.")
            sys.exit(1)
        _run_step([npx, "jest"], "Jest")

    if not args.no_playwright:
        playwright_check()

    print("\nAll checks and tests passed.")


if __name__ == "__main__":
    main()
