#!/usr/bin/env python3
"""
Regression scan for Bootstrap and deleted CSS references.

Fails if forbidden patterns are found outside documentation/build artifacts.
Intended to run both in CI and locally without a virtualenv.
"""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

IGNORED_SCAN_DIRS = {'.git', '.venv', 'venv', 'node_modules', 'static', '__pycache__', '.ruff_cache', '.pytest_cache', '.mypy_cache', 'docs', 'media', '.idea'}

IGNORED_SCAN_FILES = {'package-lock.json', 'tailwind.build.css', 'yarn.lock', 'regression_scan.py'}

FORBIDDEN_PATTERNS = [
    (r'\bdata-bs-[a-zA-Z0-9-]+\b', 'Bootstrap data attribute'),
    (r'\bdjango[_-]bootstrap5\b', 'django-bootstrap5 package'),
    (r'\bcrispy[_-]bootstrap5\b', 'crispy-bootstrap5 package'),
    (r'\bbootstrap_messages\b', 'Bootstrap messages template tag'),
    (r'--bs-[a-zA-Z0-9-]+', 'Bootstrap CSS variable'),
    (r'\bbootstrap(?:\.min)?\.(?:js|css)\b', 'Bootstrap static file'),
    (r'\bbootstrap\.bundle(?:\.min)?\.js\b', 'Bootstrap JS bundle'),
    (r'\bdjango_tables2/bootstrap5\.html\b', 'Bootstrap table template'),
    (r'\bchat/css/chat\.css\b', 'Deleted chat stylesheet'),
    (r'\bchat/static/chat/css/chat\.css\b', 'Deleted chat stylesheet'),
]

DELETED_CSS_PATHS = [
    'home/css/base.css',
    'home/css/navigation.css',
    'home/css/forms.css',
    'home/css/buttons.css',
    'home/css/feedback.css',
    'home/css/tables.css',
    'home/css/typography.css',
    'home/css/modules.css',
    'home/css/utilities.css',
    'home/css/layout.css',
    'home/css/light-mode.css',
    'home/css/darkly.css',
    'home/css/cards.css',
    'home/static/home/css/base.css',
    'home/static/home/css/navigation.css',
    'home/static/home/css/forms.css',
    'home/static/home/css/buttons.css',
    'home/static/home/css/feedback.css',
    'home/static/home/css/tables.css',
    'home/static/home/css/typography.css',
    'home/static/home/css/modules.css',
    'home/static/home/css/utilities.css',
    'home/static/home/css/layout.css',
    'home/static/home/css/light-mode.css',
    'home/static/home/css/darkly.css',
    'home/static/home/css/cards.css',
    'chat/static/chat/css/chat.css',
]


def _scan_should_ignore(dirs):
    """Remove ignored directories in-place for os.walk."""
    for d in list(dirs):
        if d in IGNORED_SCAN_DIRS:
            dirs.remove(d)


def run_regression_scan():
    """Search the repository for Bootstrap or deleted-CSS references."""
    issues = []
    compiled = [(re.compile(p, re.IGNORECASE), desc) for p, desc in FORBIDDEN_PATTERNS]

    for root, dirs, files in os.walk(BASE_DIR):
        _scan_should_ignore(dirs)
        for name in files:
            if name in IGNORED_SCAN_FILES:
                continue
            if name.endswith(('.pyc', '.pyo')):
                continue
            path = Path(root) / name
            try:
                text = path.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            rel = path.relative_to(BASE_DIR)
            for pattern, desc in compiled:
                for i, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        issues.append(f"{rel}:{i}: {desc}")
                        break
            for deleted in DELETED_CSS_PATHS:
                if deleted in text:
                    for i, line in enumerate(text.splitlines(), 1):
                        if deleted in line:
                            issues.append(f"{rel}:{i}: deleted stylesheet reference: {deleted}")
                            break

    if issues:
        print("\n".join(issues))
        print(f"\n{len(issues)} regression issue(s) found.")
        return 1
    print("Regression scan: OK (no Bootstrap/deleted-CSS references found).")
    return 0


def main():
    sys.exit(run_regression_scan())


if __name__ == "__main__":
    main()
