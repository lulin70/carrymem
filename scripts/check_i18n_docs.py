#!/usr/bin/env python3
"""Check that the translated README files stay consistent with the English one.

Errors (exit 1):
  - A translation file is missing, empty, or too short.
  - A translation does not link back to the English README.
  - A translation does not mention the canonical version from VERSION.
  - A translation file exists but the English README does not link to it.

Warnings (exit 0):
  - The heading count of a translation drifts far from the English README.
  - A translation is much shorter than the English README.

Run: python3 scripts/check_i18n_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "README.md"
I18N_DIR = ROOT / "docs" / "i18n"
MIN_LINES = 50
MAX_HEADING_DRIFT = 5
MIN_LENGTH_RATIO = 0.40

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def read_version() -> str:
    """Return the canonical version from VERSION."""
    version_file = ROOT / "VERSION"
    if not version_file.is_file():
        raise SystemExit("ERROR: VERSION file is missing")
    return version_file.read_text(encoding="utf-8").strip()


def h2_count(text: str) -> int:
    """Count level-2 Markdown headings."""
    return sum(1 for line in text.splitlines() if line.startswith("## "))


def links(text: str) -> set[str]:
    """Return the set of link targets in a Markdown text."""
    return {m.group(1).strip() for m in LINK_RE.finditer(text)}


def main() -> int:
    version = read_version()
    errors: list[str] = []
    warnings: list[str] = []

    if not BASE.is_file():
        print("ERROR: README.md is missing")
        return 1
    base_text = BASE.read_text(encoding="utf-8")
    base_links = links(base_text)
    base_h2 = h2_count(base_text)

    translations = sorted(I18N_DIR.glob("README-*.md"))
    if not translations:
        print("ERROR: no translation files found in docs/i18n/")
        return 1

    print(f"Canonical version: {version}")
    print(f"English README: {len(base_text.splitlines())} lines, {base_h2} H2 headings")
    print(f"Translations: {len(translations)}")

    for path in translations:
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        if len(lines) < MIN_LINES:
            errors.append(f"{rel}: too short ({len(lines)} lines, minimum {MIN_LINES})")
            continue

        if "../../README.md" not in links(text):
            errors.append(f"{rel}: no link back to ../../README.md")

        if version not in text:
            errors.append(f"{rel}: canonical version {version} is missing")

        if not any(link.endswith(path.name) for link in base_links):
            errors.append(f"README.md: no link to {rel}")

        drift = abs(h2_count(text) - base_h2)
        if drift > MAX_HEADING_DRIFT:
            warnings.append(f"{rel}: H2 heading drift {drift} (English {base_h2}, file {h2_count(text)})")

        ratio = len(lines) / max(len(base_text.splitlines()), 1)
        if ratio < MIN_LENGTH_RATIO:
            warnings.append(f"{rel}: length ratio {ratio:.2f} (minimum {MIN_LENGTH_RATIO})")

    for warning in warnings:
        print(f"WARNING: {warning}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1

    print(f"OK: {len(translations)} translations are consistent ({len(warnings)} warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
