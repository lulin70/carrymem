#!/usr/bin/env python3
"""Verify that every machine-readable version stamp agrees with ``VERSION``.

The release version is declared in five places read by different consumers
(PyPI metadata, the Python package, the MCP registry, the container image, and
the Smithery directory).  A release that updates only some of them ships a
mislabelled artifact: the v0.11.2 review found ``Dockerfile`` still stamped
``0.9.8`` and ``smithery.yaml`` still ``0.10.1`` while ``VERSION`` was already
``0.11.2``.  This gate fails loudly, printing the offending file and value,
instead of letting a stale stamp reach a registry.

The check has no third-party dependencies so it can run in any job, including
the lint job that does not install the project.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read_text(relative_path: str) -> str:
    """Read a repository file, failing clearly when it is missing."""
    path = ROOT / relative_path
    if not path.is_file():
        raise SystemExit(f"Missing version source: {relative_path}")
    return path.read_text(encoding="utf-8")


def _line_of(text: str, needle: str) -> int:
    """Return the 1-based line number of the first line containing ``needle``."""
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return index
    return 1


def collect_versions() -> list[tuple[str, int, str]]:
    """Return ``(file, line, value)`` for every machine-readable version stamp."""
    sources: list[tuple[str, int, str]] = []

    version_text = _read_text("VERSION")
    sources.append(("VERSION", 1, version_text.strip()))

    module_text = _read_text("src/carrymem/__version__.py")
    module_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', module_text)
    if module_match is None:
        raise SystemExit("Could not find __version__ in src/carrymem/__version__.py")
    module_line = _line_of(module_text, "__version__")
    sources.append(("src/carrymem/__version__.py", module_line, module_match.group(1)))

    server_text = _read_text("server.json")
    server_version = json.loads(server_text).get("version")
    if not isinstance(server_version, str):
        raise SystemExit('Could not find a string "version" in server.json')
    sources.append(("server.json", _line_of(server_text, '"version"'), server_version))

    dockerfile_text = _read_text("Dockerfile")
    dockerfile_match = re.search(r"^ARG VERSION=(\S+)\s*$", dockerfile_text, re.MULTILINE)
    if dockerfile_match is None:
        raise SystemExit("Could not find 'ARG VERSION=' in Dockerfile")
    dockerfile_line = _line_of(dockerfile_text, "ARG VERSION=")
    sources.append(("Dockerfile", dockerfile_line, dockerfile_match.group(1)))

    smithery_text = _read_text("smithery.yaml")
    smithery_match = re.search(r"^version:\s*(\S+)\s*$", smithery_text, re.MULTILINE)
    if smithery_match is None:
        raise SystemExit("Could not find a top-level 'version:' in smithery.yaml")
    sources.append(("smithery.yaml", _line_of(smithery_text, "version:"), smithery_match.group(1)))

    return sources


def main() -> int:
    sources = collect_versions()
    canonical = sources[0][2]

    if any(value != canonical for _, _, value in sources):
        print("Version consistency check FAILED: every source must equal VERSION.", file=sys.stderr)
        print(f"  VERSION declares: {canonical}", file=sys.stderr)
        for file_name, line_number, value in sources:
            marker = "  <-- MISMATCH" if value != canonical else ""
            print(f"  {file_name}:{line_number} = {value}{marker}", file=sys.stderr)
        return 1

    locations = ", ".join(f"{file_name}:{line_number}" for file_name, line_number, _ in sources)
    print(f"Version consistency OK: all {len(sources)} sources report {canonical} ({locations}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
