"""Run a fast, change-aware subset of the Django test suite before pushing."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
SMOKE_TESTS = ("tests/test_smoke.py", "tests/test_workflow_chat.py", "tests/test_workflow_glosowania.py")
APP_TEST_DIRS = {
    "ankiety": "ankiety/tests",
    "board": "tests/test_board.py tests/test_board_categories.py",
    "bookkeeping": "bookkeeping/tests",
    "chat": "chat/tests",
    "core": "core",
    "events": "events/tests",
    "glosowania": "glosowania/tests",
    "home": "home",
    "obywatele": "obywatele/tests",
    "site_settings": "site_settings/tests",
    "tasks": "tasks/tests",
    "zzz": "zzz/tests",
}
FILE_TEST_TARGETS = {
    "chat/management/commands/": "chat/tests/test_commands.py",
    "chat/services.py": "chat/tests/test_services.py",
    "chat/models.py": "chat/tests/test_models.py",
    "chat/views.py": "chat/tests/test_views.py",
    "glosowania/management/commands/": "glosowania/tests/test_vote_command.py",
    "glosowania/services.py": "glosowania/tests/test_models.py glosowania/tests/test_vote_buffer.py",
    "tasks/models.py": "tasks/tests/test_models.py",
}
ZERO_SHA = "0" * 40


def _git_changed_files() -> list[str]:
    lines = [line.split() for line in sys.stdin.read().splitlines() if line.split()]
    changed: set[str] = set()
    for fields in lines:
        if len(fields) < 4:
            continue
        local_sha, remote_sha = fields[1], fields[3]
        if remote_sha == ZERO_SHA:
            command = ["git", "diff", "--name-only", local_sha, "--"]
        else:
            command = ["git", "diff", "--name-only", f"{remote_sha}...{local_sha}", "--"]
        result = subprocess.run(command, cwd=BASE_DIR, check=True, capture_output=True, text=True)
        changed.update(line for line in result.stdout.splitlines() if line)
    if changed:
        return sorted(changed)

    result = subprocess.run(["git", "diff", "--name-only", "HEAD", "--"], cwd=BASE_DIR, check=True, capture_output=True, text=True)
    return sorted(line for line in result.stdout.splitlines() if line)


def _tests_for_files(files: list[str]) -> list[str]:
    tests = set(SMOKE_TESTS)
    for filename in files:
        path = Path(filename)
        normalized = path.as_posix()
        if path.name.startswith("test_") and path.suffix == ".py" and len(path.parts) >= 2 and "tests" in path.parts:
            tests.add(normalized)
            continue
        targeted = next((target for prefix, target in FILE_TEST_TARGETS.items() if normalized.startswith(prefix)), None)
        if targeted:
            tests.update(targeted.split())
            continue
        if path.parts and path.parts[0] in APP_TEST_DIRS:
            tests.update(APP_TEST_DIRS[path.parts[0]].split())
    return sorted(tests)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print selected tests without running them.")
    parser.add_argument("--files", nargs="*", help="Override changed files for local verification.")
    args = parser.parse_args()

    files = args.files if args.files is not None and args.files else _git_changed_files()
    tests = _tests_for_files(files)
    command = [sys.executable, "-m", "pytest", "-q", "-n", "0", *tests]

    print("Changed files:", ", ".join(files) if files else "none")
    print("Selected tests:", " ".join(tests))
    if args.dry_run:
        return 0
    return subprocess.run(command, cwd=BASE_DIR).returncode


if __name__ == "__main__":
    raise SystemExit(main())
