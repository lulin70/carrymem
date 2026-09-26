"""Tests for ``scripts/check_swallowed_assert.py``.

The script is a blocking CI gate.  A gate whose detector silently stops
detecting turns CI green for the exact failure mode it exists to prevent, so the
detector's behaviour is pinned here rather than left to a one-off manual check.

The positive cases below are the shapes that were found in real code during the
2026-09-24 review: while the detector was being written, its scope walker failed
to yield the node it was given, which made the nested-scope guard inert and
inverted the result — every fixture reported the opposite of the truth.
"""

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_swallowed_assert.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_swallowed_assert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


gate = _load_module()


# ── cases the gate must report ───────────────────────────────────────────────

MUST_FAIL = {
    "broad_pass": """
        try:
            assert 1 == 2
        except Exception:
            pass
    """,
    "bare_pass": """
        try:
            assert 1 == 2
        except:
            pass
    """,
    "broad_in_tuple": """
        try:
            assert 1 == 2
        except (ValueError, Exception):
            print("swallowed")
    """,
    "base_exception": """
        try:
            assert 1 == 2
        except BaseException:
            return None
    """,
    "binding_never_used": """
        try:
            assert 1 == 2
        except Exception as exc:
            pass
    """,
    "nested_try_inside_try": """
        try:
            try:
                assert 1 == 2
            finally:
                pass
        except Exception:
            pass
    """,
}

# ── cases the gate must stay silent about ────────────────────────────────────

MUST_PASS = {
    "re_raises_bare": """
        try:
            assert 1 == 2
        except Exception:
            raise
    """,
    "re_raises_wrapped": """
        try:
            assert 1 == 2
        except Exception as exc:
            raise RuntimeError("wrapped") from exc
    """,
    "narrow_handler": """
        try:
            assert 1 == 2
        except ValueError:
            pass
    """,
    "assert_outside_try": """
        assert 1 == 1
        try:
            print("work")
        except Exception:
            pass
    """,
    "assert_in_nested_scope": """
        try:
            def inner():
                assert 1 == 2

            inner()
        except Exception:
            pass
    """,
    "no_assert_at_all": """
        try:
            print("work")
        except Exception:
            pass
    """,
    "records_for_later_assertion": """
        errors = []
        try:
            assert 1 == 2
        except Exception as exc:
            errors.append(f"op failed: {exc}")
        assert not errors, errors
    """,
}


def _write(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "probe.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


@pytest.mark.parametrize("name", sorted(MUST_FAIL))
def test_reports_swallowed_assert(tmp_path: Path, name: str) -> None:
    findings = gate.scan_file(_write(tmp_path, MUST_FAIL[name]))
    assert findings, f"{name}: the gate must report this swallowed assert"
    assert findings[0][0] > 0, f"{name}: finding must carry the real line number"


@pytest.mark.parametrize("name", sorted(MUST_PASS))
def test_ignores_legitimate_pattern(tmp_path: Path, name: str) -> None:
    findings = gate.scan_file(_write(tmp_path, MUST_PASS[name]))
    assert findings == [], f"{name}: the gate must not report this pattern, got {findings}"


def test_main_exits_non_zero_on_a_violation(tmp_path: Path) -> None:
    assert gate.main([str(_write(tmp_path, MUST_FAIL["broad_pass"]))]) == 1


def test_main_exits_zero_on_clean_input(tmp_path: Path) -> None:
    assert gate.main([str(_write(tmp_path, MUST_PASS["records_for_later_assertion"]))]) == 0


def test_clean_path_argument_is_reported_not_crashed(tmp_path: Path) -> None:
    """A non-.py path selects nothing instead of raising."""
    assert gate.collect_python_files(tmp_path / "missing.py") == []
