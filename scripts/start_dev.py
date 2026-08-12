#!/usr/bin/env python3
"""
Dev starter for Windows/Linux.
Default: prepare .env, ensure SECRET_KEY, load env, create media/uploads,
run migrations and start Daphne.
With --full: additionally pip install -r requirements.txt, makemigrations for
listed apps, makemessages/compilemessages and collectstatic.
"""

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE = BASE_DIR / ".env.example"
DB_DEFAULT = BASE_DIR / "db" / "db.sqlite3"


def copy_env():
    if ENV_FILE.exists():
        return
    if ENV_EXAMPLE.exists():
        ENV_FILE.write_text(ENV_EXAMPLE.read_text())
        print("Copied .env.example -> .env")
    else:
        print("Missing .env and .env.example. Please create .env first.")
        sys.exit(1)


def ensure_secret_key():
    lines = ENV_FILE.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("SECRET_KEY=") and line.strip().endswith("change-me"):
            new_key = "".join(secrets.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(50))
            lines[i] = f"SECRET_KEY={new_key}"
            ENV_FILE.write_text("\n".join(lines) + "\n")
            print("Updated SECRET_KEY in .env")
            break


def load_env():
    for raw in ENV_FILE.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, val = raw.split("=", 1)
        os.environ.setdefault(key, val)


def db_path():
    try:
        sys.path.insert(0, str(BASE_DIR))
        from zzz.settings_base import DATABASES

        return str(DATABASES["default"]["NAME"])
    except (Exception):
        return str(DB_DEFAULT)


def run(cmd, allow_failure=False):
    print("$", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, cwd=BASE_DIR, env=os.environ.copy())
    except subprocess.CalledProcessError as e:
        if allow_failure:
            print(f"Warning: Command failed with exit code {e.returncode}")
        else:
            raise


def main():
    parser = argparse.ArgumentParser(description="Start dev environment quickly; use --full for slow/setup tasks.")
    parser.add_argument("--full", action="store_true", help="Run full setup (pip install, makemigrations, i18n messages, collectstatic) before start.")
    args = parser.parse_args()

    if sys.prefix == sys.base_prefix:
        print("Activate your virtualenv first.")
        sys.exit(1)

    copy_env()
    ensure_secret_key()
    load_env()

    print(f"- DB path: {db_path()}")
    print("- Virtualenv must stay activated while running\n")

    # (BASE_DIR / "media" / "uploads").mkdir(parents=True, exist_ok=True)

    if args.full:
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    manage = [sys.executable, "manage.py"]
    apps = ["obywatele", "glosowania", "chat", "home", "bookkeeping", "board", "events", "tasks"]
    if args.full:
        for app in apps:
            run(manage + ["makemigrations", app])

    run(manage + ["migrate"])
    if args.full:
        run(manage + ["makemessages", "-v", "0", "--no-wrap", "--no-obsolete", "-l", "pl", "--ignore=.git/*", "--ignore=static/*", "--ignore=.mypy_cache/*"])
        run(manage + ["compilemessages", "-v", "0"], allow_failure=True)
        run(manage + ["collectstatic", "-v", "0", "--no-input", "-c"])

    print("\nDevelopment instance started\n")
    # run(["daphne", "zzz.asgi:application"])
    run(manage + ["runserver", "0.0.0.0:8000"])
    # run(manage + ["runserver_plus", "--cert", "cert", "0.0.0.0:8000"]) # ssl


if __name__ == "__main__":
    main()
