#!/usr/bin/env python3
"""
UI unification guard.

Checks changed (or all) frontend files against the shared Tailwind pipeline
and documented UI standards. Intended to run in pre-commit hooks and CI.

Usage:
    python scripts/ui_guard.py              # checks git-tracked changed files
    python scripts/ui_guard.py --all        # checks the whole repository
    python scripts/ui_guard.py --strict     # exit with non-zero on warnings
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

UI_STANDARDS_FILE = BASE_DIR / 'docs' / 'UI_STANDARDS.html'
CSS_SOURCE = BASE_DIR / 'home' / 'static' / 'home' / 'css' / 'tailwind.css'
TOKENS_FILE = BASE_DIR / 'home' / 'static' / 'home' / 'css' / 'tokens.css'

# 'static' is intentionally NOT ignored here: only the repo-root static/
# directory (collectstatic output) is skipped — see _should_ignore/all_files.
# Module sources under <app>/static/ are always checked.
IGNORED_DIRS = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.ruff_cache', '.pytest_cache', '.mypy_cache', 'media', '.idea', 'lib', 'tinymce'}

# Repo-root directory produced by collectstatic — generated, never scanned.
GENERATED_DIRS = {'static'}

# Paths intentionally exempt from full UI guard (self-styled docs page).
EXEMPT_FILES = {'docs/UI_STANDARDS.html'}

# Allow-list for non-tw-* semantic hooks. Each entry is a regex.
FONTAWESOME_PREFIXES = {'fas', 'far', 'fab', 'fal', 'fa-fw'}

ALLOWED_NON_TW_CLASSES = [
    # Django/crispy-forms validation state contract (home/templates/tw/*,
    # core/widgets.py, form JS) — semantic hook, not a component class.
    r'^is-invalid$',
    r'^is-valid$',
    # HTML state attributes emitted as class hooks.
    r'^hidden$',
    r'^readonly$',
    r'^disabled$',
    r'^required$',
    # crispy-forms layout contract (home/templates/tw/layout/buttonholder.html).
    r'^buttonHolder$',
    # django-allauth stock template classes kept for upstream compatibility.
    r'^ctrlHolder$',
    r'^blockLabels$',
    r'^primaryAction$',
    r'^secondaryAction$',
    r'^verified$',
    r'^unverified$',
    r'^login$',
    r'^title$',
    # django-simple-captcha markup.
    r'^captcha$',
    # TinyMCE vendor classes.
    r'^tox-.*',
    # Transactional e-mail templates keep scoped classes — external mail
    # clients cannot consume the Tailwind pipeline (home/templates/emails/).
    r'^email-.*',
]

# Inline style assignments that should be classes instead. `style.display` and
# `style.setProperty('--var')` is excluded — dynamic CSS-variable updates are the
# sanctioned mechanism. `style.display` is also flagged: show/hide state must go
# through `classList` + `tw-d-none`, never through inline style.
JS_INLINE_STYLE_RE = re.compile(
    r'\.style\.(?:cssText|display|opacity|visibility|color|background(?:Color)?|width|height'
    r'|minWidth|minHeight|maxWidth|maxHeight|fontSize|padding\w*|margin\w*|border\w*)\s*='
)


class UIGuard:
    def __init__(self, strict=False):
        self.issues = []
        self.warnings = []
        self.strict = strict
        self.allowed_icon_classes = self._load_icon_dictionary()
        self.known_css_classes = self._load_known_css_classes()

    def _load_known_css_classes(self):
        """Load class names from the generated and source Tailwind CSS."""
        known = set()
        css_pattern = re.compile(r'\.([a-zA-Z][a-zA-Z0-9_-]*)')
        for path in (CSS_SOURCE, BASE_DIR / 'home' / 'static' / 'home' / 'css' / 'tailwind.build.css'):
            if path.exists():
                text = path.read_text(encoding='utf-8', errors='ignore')
                for match in css_pattern.finditer(text):
                    known.add(match.group(1))
        return known

    def _load_icon_dictionary(self):
        """Parse the icon dictionary from docs/UI_STANDARDS.html."""
        icons = set()
        if UI_STANDARDS_FILE.exists():
            text = UI_STANDARDS_FILE.read_text(encoding='utf-8', errors='ignore')
            for match in re.finditer(r'<code>(fa-[a-z0-9-]+)</code>', text):
                icons.add(match.group(1))
        return icons

    def _should_ignore(self, path):
        rel = '/'.join(path.relative_to(BASE_DIR).parts)
        parts = path.relative_to(BASE_DIR).parts
        # Skip generated collectstatic output (repo-root static/) while still
        # checking module sources under <app>/static/.
        if parts and parts[0] in GENERATED_DIRS:
            return True
        # Vendored/minified bundles are not project classes.
        if path.name.endswith(('.min.js', '.min.css')):
            return True
        if any(part in IGNORED_DIRS for part in parts):
            return True
        if rel in EXEMPT_FILES:
            return True
        return False

    def _is_allowed_non_tw(self, cls):
        for pattern in ALLOWED_NON_TW_CLASSES:
            if re.match(pattern, cls):
                return True
        return False

    def _class_token_issues(self, html, line_no, path):
        for match in re.finditer(r'class=["\']([^"\']+)["\']', html):
            # Strip Django/Jinja template tags before splitting classes to avoid
            # false positives from expressions like {% if x == -1 %}.
            class_str = re.sub(r'\{%.*?%}', ' ', match.group(1))
            class_str = re.sub(r'\{\{.*?}}', ' ', class_str)
            classes = class_str.split()
            for cls in classes:
                if cls.startswith('tw-'):
                    continue
                if cls in FONTAWESOME_PREFIXES or cls.startswith('fa-'):
                    continue
                if ':' in cls or '{' in cls or '%' in cls or '/' in cls or '(' in cls:
                    # Jinja/Django template expressions and noise
                    continue
                if self._is_allowed_non_tw(cls):
                    continue
                if cls in self.known_css_classes:
                    # Being defined in the shared stylesheet does NOT make an
                    # unprefixed class legal — surface it so it gets migrated
                    # or explicitly allowlisted.
                    self.warnings.append(f"{path}:{line_no}: non-tw class '{cls}' is defined in the shared stylesheet; migrate to tw-* or allowlist")
                    continue
                # Only flag classes that look like custom component classes.
                if '-' not in cls:
                    continue
                self.issues.append(f"{path}:{line_no}: class '{cls}' is not a known tw-* / shared component class")

    def _icon_issues(self, html, line_no, path):
        for match in re.finditer(r'class="[^"]*fas (fa-[a-z0-9-]+)', html):
            icon = match.group(1)
            if icon.endswith(('-', '_', '%')) or '{' in icon:
                continue
            if icon not in self.allowed_icon_classes:
                self.warnings.append(f"{path}:{line_no}: icon '{icon}' is not in docs/UI_STANDARDS.html")

    def _inline_style_issues(self, html, line_no, path):
        for match in re.finditer(r'\bstyle=(["\'])(.*?)\1', html):
            content = match.group(2).strip()
            if re.match(r'^\s*--[a-zA-Z-]+\s*:', content):
                continue
            self.issues.append(f"{path}:{line_no}: inline style '{content[:40]}...' not allowed (use a class or CSS variable)")

    def _link_stylesheet_issues(self, html, line_no, path):
        for match in re.finditer(r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', html):
            snippet = match.group(0)
            if any(allowed in snippet for allowed in {'tailwind.build.css', 'tokens.css', 'all.min.css', 'ui-standards.css'}):
                continue
            self.issues.append(f"{path}:{line_no}: module-specific stylesheet link not allowed")

    def _style_block_issues(self, html, line_no, path):
        # Transactional e-mail templates need self-contained styles — external
        # mail clients cannot consume the Tailwind pipeline.
        rel = '/'.join(path.relative_to(BASE_DIR).parts)
        if '/emails/' in rel:
            return
        if re.search(r'<style\b', html):
            self.issues.append(f"{path}:{line_no}: inline <style> block not allowed (move rules to tailwind.css)")

    def _js_inline_style_issues(self, code, line_no, path):
        for match in JS_INLINE_STYLE_RE.finditer(code):
            self.warnings.append(f"{path}:{line_no}: JS inline style '{match.group(0).strip()}' — prefer a tw-* class (display/CSS variables are allowed)")

    def _should_expect_toolbar(self, path):
        """Shared toolbar is only mandatory on main module list views."""
        name = path.name
        rel = '/'.join(path.relative_to(BASE_DIR).parts)
        if name.startswith('_') or name.startswith('base'):
            return False
        if not (name.endswith('list.html') or name.endswith('board.html')):
            return False
        if any(x in rel for x in ('/emails/', '/tw/', '/includes/', '/admin/', '/allauth/')):
            return False
        return True

    def _check_html(self, path):
        text = path.read_text(encoding='utf-8', errors='ignore')
        for i, line in enumerate(text.splitlines(), 1):
            self._class_token_issues(line, i, path)
            self._icon_issues(line, i, path)
            self._inline_style_issues(line, i, path)
            self._link_stylesheet_issues(line, i, path)
            self._style_block_issues(line, i, path)
            self._js_inline_style_issues(line, i, path)

        # Structural guidance
        if self._should_expect_toolbar(path):
            if 'tw-toolbar' not in text and 'home/includes/toolbar.html' not in text:
                self.warnings.append(f"{path}: no shared toolbar detected; consider using home/includes/toolbar.html")
        if ('data-view-container' in text or 'data-view-only' in text) and 'tw-proposals-list' not in text:
            self.warnings.append(f"{path}: list/grid view should use tw-proposals-list")

    def _check_css(self, path):
        text = path.read_text(encoding='utf-8', errors='ignore')
        module_prefixed = re.findall(r'^\s*\.([a-z]+-[a-zA-Z0-9_-]+)\s*\{', text, re.MULTILINE)
        for cls in module_prefixed:
            if not cls.startswith('tw-') and not self._is_allowed_non_tw(cls):
                self.warnings.append(f"{path}: CSS rule '.{cls}' looks module-specific; prefer 'tw-' or shared component")

    def _check_js(self, path):
        text = path.read_text(encoding='utf-8', errors='ignore')
        if path.name != 'breakpoints.js':
            for match in re.finditer(r"matchMedia\('\(max-width:\s*(\d+)", text):
                self.warnings.append(f"{path}: hardcoded matchMedia breakpoint {match.group(1)}px; use shared breakpoints.js")
        for i, line in enumerate(text.splitlines(), 1):
            self._js_inline_style_issues(line, i, path)

    def _check_html_lines(self, lines, path, is_new_file=False):
        for i, line in lines:
            self._class_token_issues(line, i, path)
            self._icon_issues(line, i, path)
            self._inline_style_issues(line, i, path)
            self._link_stylesheet_issues(line, i, path)
            self._style_block_issues(line, i, path)
            self._js_inline_style_issues(line, i, path)
        if is_new_file and self._should_expect_toolbar(path):
            text = '\n'.join(line for _, line in lines)
            if 'tw-toolbar' not in text and 'home/includes/toolbar.html' not in text:
                self.warnings.append(f"{path}: no shared toolbar detected; consider using home/includes/toolbar.html")
            if ('data-view-container' in text or 'data-view-only' in text) and 'tw-proposals-list' not in text:
                self.warnings.append(f"{path}: list/grid view should use tw-proposals-list")

    def _check_css_lines(self, lines, path):
        for i, line in lines:
            module_prefixed = re.findall(r'^\s*\.([a-z]+-[a-zA-Z0-9_-]+)\s*\{', line)
            for cls in module_prefixed:
                if not cls.startswith('tw-') and not self._is_allowed_non_tw(cls):
                    self.warnings.append(f"{path}:{i}: CSS rule '.{cls}' looks module-specific; prefer 'tw-' or shared component")

    def _check_js_lines(self, lines, path):
        for i, line in lines:
            if path.name != 'breakpoints.js':
                for match in re.finditer(r"matchMedia\('\(max-width:\s*(\d+)", line):
                    self.warnings.append(f"{path}:{i}: hardcoded matchMedia breakpoint {match.group(1)}px; use shared breakpoints.js")
            self._js_inline_style_issues(line, i, path)

    def check_file(self, path, lines=None, is_new_file=False):
        if self._should_ignore(path):
            return
        name = path.name
        if name.endswith('.html'):
            if lines is not None:
                self._check_html_lines(lines, path, is_new_file)
            else:
                self._check_html(path)
        elif name == 'tailwind.css':
            if lines is not None:
                self._check_css_lines(lines, path)
            else:
                self._check_css(path)
        elif name.endswith('.js'):
            if lines is not None:
                self._check_js_lines(lines, path)
            else:
                self._check_js(path)

    def check_files(self, files, full=False, base='HEAD'):
        for f in files:
            p = Path(f).resolve()
            if p.is_dir():
                continue
            if full:
                self.check_file(p)
                continue
            # Diff mode: only new/added lines.
            lines = changed_lines(p, base=base)
            is_new_file = is_added_file(p)
            if lines:
                self.check_file(p, lines, is_new_file)

    def report(self):
        if self.warnings:
            print("UI guard warnings:")
            for w in self.warnings:
                print(f"  {w}")
            print(f"\n{len(self.warnings)} warning(s).")
        if self.issues:
            print("\nUI guard issues:")
            for issue in self.issues:
                print(f"  {issue}")
            print(f"\n{len(self.issues)} issue(s) found.")
            return 1
        if not self.issues and not self.warnings:
            print("UI guard: OK.")
            return 0
        if self.strict:
            print("UI guard: warnings treated as errors in strict mode.")
            return 1
        print("UI guard: OK (warnings only).")
        return 0


def changed_files(base='HEAD'):
    try:
        out = subprocess.check_output(['git', 'diff', '--name-only', base], cwd=BASE_DIR, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ''
    staged = ''
    try:
        staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', base], cwd=BASE_DIR, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    status = ''
    try:
        status = subprocess.check_output(['git', 'status', '--short'], cwd=BASE_DIR, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    files = set((out + '\n' + staged).splitlines())
    for line in status.splitlines():
        if line.startswith('??') or line.startswith('A '):
            files.add(line[3:].strip())
    return sorted(f for f in files if f)


def is_added_file(path):
    rel = '/'.join(path.relative_to(BASE_DIR).parts)
    try:
        status = subprocess.check_output(['git', 'status', '--short', '--', rel], cwd=BASE_DIR, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return bool(status) and (status.startswith('A ') or status.startswith('??'))


def changed_lines(path, base='HEAD'):
    """Return list of (line_number, text) for new/added lines in git diff."""
    rel = '/'.join(path.relative_to(BASE_DIR).parts)
    try:
        out = subprocess.check_output(['git', 'diff', '-U0', base, '--', rel], cwd=BASE_DIR, text=True, errors='ignore')
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ''
    try:
        staged = subprocess.check_output(['git', 'diff', '--cached', '-U0', base, '--', rel], cwd=BASE_DIR, text=True, errors='ignore')
    except (subprocess.CalledProcessError, FileNotFoundError):
        staged = ''
    if path.exists():
        content = path.read_text(encoding='utf-8', errors='ignore')
    else:
        content = ''
    # Untracked / added files: treat all lines as new.
    if is_added_file(path):
        return [(i, line) for i, line in enumerate(content.splitlines(), 1)]
    lines = []
    for diff in (out, staged):
        current_old = 0
        for raw in diff.splitlines():
            if raw.startswith('@@'):
                m = re.search(r'\+(\d+)(?:,\d+)?', raw)
                if m:
                    current_old = int(m.group(1))
                continue
            if raw.startswith('+') and not raw.startswith('+++'):
                lines.append((current_old, raw[1:]))
                current_old += 1
            elif raw.startswith(' '):
                current_old += 1
    return lines


def all_files():
    files = []
    for root, dirs, filenames in os.walk(BASE_DIR):
        for d in list(dirs):
            # Repo-root 'static/' is collectstatic output — generated, skipped.
            # 'static' is deliberately absent from IGNORED_DIRS so module
            # sources under <app>/static/ remain checked.
            if d in IGNORED_DIRS or (Path(root) == BASE_DIR and d in GENERATED_DIRS):
                dirs.remove(d)
        for name in filenames:
            if name.endswith(('.min.js', '.min.css')):
                continue
            if name.endswith(('.html', '.css', '.js')):
                files.append(str(Path(root) / name))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description='UI unification guard')
    parser.add_argument('--all', action='store_true', help='check all files instead of changed ones')
    parser.add_argument('--strict', action='store_true', help='exit with non-zero on warnings')
    parser.add_argument('--base', default='HEAD', help='git ref to diff against (default: HEAD)')
    args = parser.parse_args()

    files = all_files() if args.all else changed_files(base=args.base)
    guard = UIGuard(strict=args.strict)
    guard.check_files(files, full=args.all, base=args.base)
    sys.exit(guard.report())


if __name__ == '__main__':
    main()
