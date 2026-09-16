#!/usr/bin/env python3
"""
Run the full verification pipeline: ruff, UI guards, Django system checks,
translation compilation, collectstatic, pytest, jest and Playwright.

Reuses the environment helpers from `start_dev.py` so both scripts keep a
single source of truth for .env handling and command execution.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request

from regression_scan import run_regression_scan
from start_dev import BASE_DIR, copy_env, ensure_secret_key, load_env
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


def _dev_server_is_ready(url="http://127.0.0.1:8006/healthz/live/", timeout=1):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200 and resp.read().decode().strip() == "ok"
    except Exception:
        return False


def _start_dev_server():
    """Start the Django development server for Playwright tests."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen([sys.executable, "manage.py", "runserver", "0.0.0.0:8006"], cwd=BASE_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if _dev_server_is_ready():
            return proc
        if proc.poll() is not None:
            print("Could not start the Django development server; port 8006 may already be in use.")
            sys.exit(1)
        time.sleep(1)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Could not start the Django development server for Playwright tests.")
    sys.exit(1)


def _stop_dev_server(proc):
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def playwright_check():
    """Run Playwright end-to-end tests if a dev server is available or can be started."""
    npx = shutil.which("npx")
    if sys.platform == "win32" and npx and not npx.lower().endswith((".exe", ".cmd", ".bat")):
        npx = shutil.which("npx.cmd") or npx
    if npx is None:
        print("npx not found in PATH. Install Node or use --no-playwright.")
        sys.exit(1)

    server_proc = None
    if not _dev_server_is_ready():
        print("Starting Django development server for Playwright tests...")
        server_proc = _start_dev_server()
    else:
        print("Using existing Django development server at http://127.0.0.1:8006/")

    os.environ["PLAYWRIGHT_BASE_URL"] = "http://127.0.0.1:8006"
    try:
        _run_step([npx, "playwright", "test", "--reporter=line"], "Playwright end-to-end tests")
    finally:
        _stop_dev_server(server_proc)


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

    temp_build = build_file.with_suffix('.build.check.css')
    cmd = [npx, "tailwindcss", "-i", "./home/static/home/css/tailwind.css", "-o", str(temp_build)]
    print("$", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, cwd=BASE_DIR, env=os.environ.copy())
    except subprocess.CalledProcessError as e:
        temp_build.unlink(missing_ok=True)
        print("[full-pipeline] FAILED: Tailwind CSS build")
        print(f"[full-pipeline] Command: {' '.join(map(str, cmd))}")
        print(f"[full-pipeline] Exit code: {e.returncode}")
        sys.exit(e.returncode or 1)

    original = build_file.read_text(encoding='utf-8')
    rebuilt = temp_build.read_text(encoding='utf-8')
    temp_build.unlink(missing_ok=True)

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

    copy_env()
    ensure_secret_key()
    load_env()

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
        # Use every available CPU thread so the test suite runs as fast as possible.
        test_threads = os.cpu_count() or 2
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
