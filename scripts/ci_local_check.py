#!/usr/bin/env python3
"""Run the repository's blocking quality gates in a disposable CI-like venv.

The commands and tool versions intentionally mirror the blocking gates in
``.github/workflows/ci.yml`` and the ``pre-release-test`` job in
``.github/workflows/release.yml``.  The temporary environment is removed when the
script exits, so the result does not depend on packages installed globally.

The test gate runs the suite exactly the way the release gate does
(``--cov=carrymem``, ``--timeout=120``, ``-m "not slow"``).  That equivalence
matters: running the suite without ``--cov`` is not the same measurement, because
coverage instrumentation alone slowed the first core operation from 7.5ms to
106ms locally — enough to hide a release-blocking failure.  The 80% floor is
enforced by ``[tool.coverage.report] fail_under`` in ``pyproject.toml``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "flake8": "7.3.0",
    "black": "26.5.1",
    "isort": "6.1.0",
    "mypy": "2.3.0",
    "radon": "6.0.1",
}
RUNTIME_REQUIREMENTS = [
    "rich>=13.0",
    "textual>=0.40",
    "aiosqlite>=0.19",
    "cryptography>=50.0.0",
    "PyYAML>=5.0",
]
TEST_REQUIREMENTS = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "pytest-mock>=3.10",
    "pytest-timeout>=2.0",
    "coverage[toml]>=7.0",
    "pycld2>=0.41",
    "langdetect>=1.0.9",
]


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    """Run one gate command from the repository root."""
    print("\n$ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=capture, check=False)


def install_environment(python: Path) -> None:
    """Install the exact lint toolchain, the test dependencies, and the package."""
    requirements = [f"{name}=={version}" for name, version in TOOLS.items()]
    run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip>=26.1.2"])
    result = run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            *requirements,
            *RUNTIME_REQUIREMENTS,
            *TEST_REQUIREMENTS,
        ]
    )
    if result.returncode != 0:
        raise SystemExit("Unable to install the pinned local CI toolchain.")

    # Editable install so the `carrymem` console script exists, exactly as the CI
    # jobs have it. Tests that shell out to the CLI would otherwise behave
    # differently here than in CI.
    editable = run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-e", "."])
    if editable.returncode != 0:
        raise SystemExit("Unable to install the project in editable mode.")


def check_versions(python: Path) -> bool:
    """Fail if the disposable environment did not receive the requested versions."""
    expected = repr(TOOLS)
    result = run(
        [
            str(python),
            "-c",
            "import importlib.metadata as m, sys; expected = %s; actual = {n: m.version(n) for n in expected}; print(actual); sys.exit(actual != expected)"
            % expected,
        ]
    )
    return result.returncode == 0


def main() -> int:
    if sys.version_info < (3, 12):
        print("Python 3.12 or newer is required.", file=sys.stderr)
        return 1

    print("CarryMem local CI quality gates")
    print(f"Repository: {ROOT}")
    print("The temporary venv will be deleted after this run.")

    with tempfile.TemporaryDirectory(prefix="carrymem-ci-") as temp_dir:
        venv_dir = Path(temp_dir) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = venv_dir / "bin" / "python"
        if os.name == "nt":
            python = venv_dir / "Scripts" / "python.exe"

        install_environment(python)
        if not check_versions(python):
            return 1

        gates: list[tuple[str, list[str]]] = [
            (
                "flake8",
                [str(python), "-m", "flake8", "src/", "tests/", "--count", "--max-line-length=120", "--statistics"],
            ),
            (
                "black",
                [str(python), "-m", "black", "--check", "--diff", "--color", "--line-length=120", "src/", "tests/"],
            ),
            (
                "isort",
                [str(python), "-m", "isort", "--check-only", "--diff", "src/", "tests/"],
            ),
            ("mypy", [str(python), "-m", "mypy", "src/"]),
            (
                "pytest",
                [
                    str(python),
                    "-m",
                    "pytest",
                    "tests/",
                    "--cov=carrymem",
                    "--cov-report=term-missing",
                    "--timeout=120",
                    "-m",
                    "not slow",
                    "-q",
                ],
            ),
        ]

        failures: list[str] = []
        for name, command in gates:
            result = run(command)
            if result.returncode != 0:
                failures.append(name)

        radon = run([str(python), "-m", "radon", "cc", "-s", "-n", "D", "src/"], capture=True)
        if radon.stdout:
            print(radon.stdout, end="")
        if radon.stderr:
            print(radon.stderr, end="", file=sys.stderr)
        if radon.returncode != 0 or radon.stdout.strip():
            failures.append("radon")
        else:
            print("radon: no functions with complexity >= 21")

        if failures:
            print("\nFAILED gates: " + ", ".join(failures))
            return 1
        print("\nAll six blocking local CI gates passed (flake8, black, isort, mypy, pytest, radon).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
