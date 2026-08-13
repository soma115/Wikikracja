#!/usr/bin/env python3
"""
Run the full verification pipeline: ruff, Django system checks,
collectstatic, pytest and jest.

Reuses the environment helpers from `start_dev.py` so both scripts keep a
single source of truth for .env handling and command execution.
"""

import argparse
import shutil
import sys

from start_dev import BASE_DIR, copy_env, ensure_secret_key, load_env, run


def main():
    parser = argparse.ArgumentParser(description="Run all project checks and tests.")
    parser.add_argument("--no-ruff", action="store_true", help="Skip ruff lint and format checks.")
    parser.add_argument("--no-django-check", action="store_true", help="Skip Django system checks.")
    parser.add_argument("--no-collectstatic", action="store_true", help="Skip collectstatic.")
    parser.add_argument("--no-pytest", action="store_true", help="Skip Python tests.")
    parser.add_argument("--no-jest", action="store_true", help="Skip JavaScript tests.")
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

    manage = [sys.executable, "manage.py"]

    if not args.no_django_check:
        run(manage + ["check"])

    if not args.no_collectstatic:
        run(manage + ["collectstatic", "--noinput", "--clear"])

    if not args.no_pytest:
        run([sys.executable, "-m", "pytest", "-q"])

    if not args.no_jest:
        npx = shutil.which("npx")
        if npx is None:
            print("npx not found in PATH. Install Node or use --no-jest.")
            sys.exit(1)
        run([npx, "jest"])

    print("\nAll checks and tests passed.")


if __name__ == "__main__":
    main()
