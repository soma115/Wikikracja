"""Verify that generated Tailwind CSS matches its source stylesheet."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
GENERATED_CSS = BASE_DIR / "home/static/home/css/tailwind.build.css"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="wikikracja-tailwind-") as temporary_dir:
        generated_copy = Path(temporary_dir) / GENERATED_CSS.name
        npm = "npm.cmd" if os.name == "nt" else "npm"
        result = subprocess.run([npm, "run", "build:css", "--", "-o", str(generated_copy)], cwd=BASE_DIR, capture_output=True, text=True)
        if result.returncode:
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            return result.returncode

        if not GENERATED_CSS.exists() or GENERATED_CSS.read_bytes() != generated_copy.read_bytes():
            print("Generated Tailwind CSS is out of date. Run `npm run build:css` and include the updated file.")
            return 1

    print("Generated Tailwind CSS: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
