#!/usr/bin/env python3
"""
Run the full verification pipeline: ruff, Django system checks,
collectstatic, pytest and jest.

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
from start_dev import BASE_DIR, copy_env, ensure_secret_key, load_env, run


def _dev_server_is_ready(url="http://127.0.0.1:8000/", timeout=1):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _start_dev_server():
    """Start the Django development server for Playwright tests."""
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen([sys.executable, "manage.py", "runserver", "0.0.0.0:8000"], cwd=BASE_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if _dev_server_is_ready():
            return proc
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
        print("Using existing Django development server at http://127.0.0.1:8000/")

    try:
        run([npx, "playwright", "test", "--reporter=line"])
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
        print(f"Tailwind build failed with exit code {e.returncode}")
        sys.exit(1)

    original = build_file.read_text(encoding='utf-8')
    rebuilt = temp_build.read_text(encoding='utf-8')
    temp_build.unlink(missing_ok=True)

    if original != rebuilt:
        print("tailwind.build.css is out of date. Run `npm run build:css` and commit the result.")
        sys.exit(1)
    print("Tailwind build: OK (tailwind.build.css is up to date).")


def main():
    parser = argparse.ArgumentParser(description="Run all project checks and tests.")
    parser.add_argument("--no-ruff", action="store_true", help="Skip ruff lint and format checks.")
    parser.add_argument("--no-django-check", action="store_true", help="Skip Django system checks.")
    parser.add_argument("--no-collectstatic", action="store_true", help="Skip collectstatic.")
    parser.add_argument("--no-pytest", action="store_true", help="Skip Python tests.")
    parser.add_argument("--no-jest", action="store_true", help="Skip JavaScript tests.")
    parser.add_argument("--no-regression-scan", action="store_true", help="Skip Bootstrap/deleted-CSS regression scan.")
    parser.add_argument("--no-tailwind-build-check", action="store_true", help="Skip tailwind.build.css freshness check.")
    parser.add_argument("--no-playwright", action="store_true", help="Skip Playwright end-to-end tests.")
    args = parser.parse_args()

    if sys.prefix == sys.base_prefix:
        print("Activate your virtualenv first.")
        sys.exit(1)

    copy_env()
    ensure_secret_key()
    load_env()

    print(f"Running in: {BASE_DIR}\n")

    if not args.no_ruff:
        run([sys.executable, "-m", "ruff", "check", "."])
        run([sys.executable, "-m", "ruff", "format", "--check", "."])

    if not args.no_regression_scan:
        if run_regression_scan() != 0:
            sys.exit(1)

    if not args.no_tailwind_build_check:
        tailwind_build_check()

    manage = [sys.executable, "manage.py"]

    if not args.no_django_check:
        run(manage + ["check"])

    if not args.no_collectstatic:
        run(manage + ["collectstatic", "--noinput", "--clear"])

    if not args.no_pytest:
        # Use every available CPU thread so the test suite runs as fast as possible.
        test_threads = os.cpu_count() or 2
        run([sys.executable, "-m", "pytest", "-q", "-n", str(test_threads)])

    if not args.no_jest:
        npx = shutil.which("npx")
        # On Windows the bare "npx" path may not be a Win32 executable; prefer npx.cmd.
        if sys.platform == "win32" and npx and not npx.lower().endswith((".exe", ".cmd", ".bat")):
            npx = shutil.which("npx.cmd") or npx
        if npx is None:
            print("npx not found in PATH. Install Node or use --no-jest.")
            sys.exit(1)
        run([npx, "jest"])

    if not args.no_playwright:
        playwright_check()

    print("\nAll checks and tests passed.")


if __name__ == "__main__":
    main()
