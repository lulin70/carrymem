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
from typing import Optional

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


def run(
    command: list[str],
    *,
    env: Optional[dict[str, str]] = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run one gate command from the repository root."""
    print("\n$ " + " ".join(command))
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=capture, check=False)


def install_environment(python: Path, *, env: dict[str, str]) -> None:
    """Install the exact lint toolchain, the test dependencies, and the package."""
    requirements = [f"{name}=={version}" for name, version in TOOLS.items()]
    run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip>=26.1.2"],
        env=env,
    )
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
        ],
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit("Unable to install the pinned local CI toolchain.")

    # Editable install so the `carrymem` console script exists, exactly as the CI
    # jobs have it. Tests that shell out to the CLI would otherwise behave
    # differently here than in CI.
    editable = run(
        [str(python), "-m", "pip", "install", "--disable-pip-version-check", "-e", "."],
        env=env,
    )
    if editable.returncode != 0:
        raise SystemExit("Unable to install the project in editable mode.")


def check_versions(python: Path, *, env: dict[str, str]) -> bool:
    """Fail if the disposable environment did not receive the requested versions."""
    expected = repr(TOOLS)
    version_check = (
        "import importlib.metadata as m, sys; "
        "expected = %s; "
        "actual = {n: m.version(n) for n in expected}; "
        "print(actual); sys.exit(actual != expected)"
    )
    result = run([str(python), "-c", version_check % expected], env=env)
    return result.returncode == 0


def resolve_pip_index_url() -> Optional[str]:
    """Resolve the host pip index so the isolated runtime keeps using it.

    The runtime isolation overrides ``HOME``, which hides the user-level
    ``pip.conf`` (e.g. a regional mirror such as Tsinghua TUNA) from pip.
    Without this, the disposable venv install silently falls back to the
    default index, which may be unreachable from some networks. An explicit
    ``PIP_INDEX_URL`` in the host environment always wins.
    """
    url = os.environ.get("PIP_INDEX_URL")
    if url:
        return url
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "config", "get", "global.index-url"],
            text=True,
            capture_output=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode == 0:
        value = result.stdout.strip()
        if value:
            return value
    return None


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

        # resolve(): on macOS the system temp dir sits behind the /var ->
        # /private/var symlink. HOME must be the resolved real path, otherwise
        # os.path.expanduser("~") disagrees with Path.resolve() on the same
        # location and any home-relative path check splits into two spellings
        # of one directory (observed as 3 path-validation test failures).
        # GitHub runner.temp is already a real path, so this is a no-op there.
        runtime_root = Path(temp_dir).resolve() / "runtime"
        runtime_dirs = {
            "home": runtime_root / "home",
            "config": runtime_root / "config",
            "data": runtime_root / "data",
            "cache": runtime_root / "cache",
            "logs": runtime_root / "logs",
            "backups": runtime_root / "backups",
        }
        for directory in runtime_dirs.values():
            directory.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(
            {
                "HOME": str(runtime_dirs["home"]),
                "CARRYMEM_CONFIG_DIR": str(runtime_dirs["config"]),
                "CARRYMEM_CONFIG_FILE": str(runtime_dirs["config"] / "config.yaml"),
                "CARRYMEM_DB_PATH": str(runtime_dirs["data"] / "memories.db"),
                "CARRYMEM_DATA_PATH": str(runtime_dirs["data"]),
                "CARRYMEM_CACHE_DIR": str(runtime_dirs["cache"]),
                "CARRYMEM_LOG_DIR": str(runtime_dirs["logs"]),
                "CARRYMEM_BACKUP_DIR": str(runtime_dirs["backups"]),
                "CARRYMEM_LOCK_FILE": str(runtime_dirs["config"] / "carrymem.lock"),
            }
        )
        print("Runtime isolation:")
        for name, directory in runtime_dirs.items():
            print(f"  {name}: {directory}")

        pip_index_url = resolve_pip_index_url()
        if pip_index_url:
            env["PIP_INDEX_URL"] = pip_index_url
            print(f"  pip index (inherited from host): {pip_index_url}")

        install_environment(python, env=env)
        if not check_versions(python, env=env):
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
            ("version-consistency", [str(python), str(ROOT / "scripts" / "check_version_consistency.py")]),
            (
                "swallowed-assert",
                [str(python), str(ROOT / "scripts" / "check_swallowed_assert.py")],
            ),
        ]

        failures: list[str] = []
        for name, command in gates:
            result = run(command, env=env)
            if result.returncode != 0:
                failures.append(name)

        radon = run([str(python), "-m", "radon", "cc", "-s", "-n", "D", "src/"], env=env, capture=True)
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
        print(
            "\nAll eight blocking local CI gates passed "
            "(flake8, black, isort, mypy, pytest, radon, version-consistency, swallowed-assert)."
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
