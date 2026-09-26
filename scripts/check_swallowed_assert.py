#!/usr/bin/env python3
"""Blocking gate: no ``assert`` may be swallowed by a broad ``except`` handler.

Why this exists
---------------
An ``assert`` inside a ``try`` body whose handler catches ``Exception`` /
``BaseException`` / bare ``except:`` **without re-raising** turns an
AssertionError into a silent pass.  The test then reports green no matter what
the code under test does — the "false green" failure mode recorded in
``docs/design/V0.11.0_PROJECT_REVIEW.md`` §8 #18.  Static review does not catch
this reliably, so it is enforced mechanically here.

Scope
-----
``tests/`` and ``src/`` by default; pass one or more paths as arguments to scan
something else (used by the gate's own negative test).

Detection rules (deliberately conservative)
-------------------------------------------
1. The ``try`` body contains an ``assert`` (nested scopes excluded — an assert
   inside a nested ``def`` is not covered by this handler).
2. A handler is *broad* when it is bare, or names ``Exception``,
   ``BaseException``, ``ExceptionGroup`` or ``BaseExceptionGroup`` (directly or
   inside a tuple).
3. The handler is exempt when its body contains some ``raise`` (outside nested
   scopes) — any raise propagates, so the assert failure cannot be lost.
4. The handler is also exempt when it binds the exception (``except E as exc``)
   and the body references that binding.  The canonical legitimate form is
   collecting failures for a later aggregate assertion::

       errors = []
       ...
       except Exception as exc:
           errors.append(f"op failed: {exc}")
       ...
       assert not errors, errors      # the assert failure still fails the test

Non-goals
---------
This gate is not a proof that a test cannot pass falsely — it catches silent
swallows (``pass`` / ``print`` / ``continue`` / ``return`` with the exception
unobserved).  A handler that merely logs the exception is treated as observing
it, and only the full regression suite catches that class of false green
(``docs/design/V0.11.0_PROJECT_REVIEW.md`` §8 #18, second bullet).

Exit status: 1 when at least one site is found, 0 otherwise.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = ("tests", "src")
BROAD_EXCEPTIONS = {"Exception", "BaseException", "ExceptionGroup", "BaseExceptionGroup"}
NESTED_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def _iter_own_scope(node: ast.AST):
    """Yield ``node`` and its descendants, without descending into nested scopes.

    ``node`` itself is yielded first so the nested-scope guard applies to it
    too — otherwise a ``FunctionDef`` handed in directly would be traversed.
    """
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, NESTED_SCOPES):
            continue
        stack.extend(ast.iter_child_nodes(current))


def _is_broad(handler: ast.ExceptHandler) -> bool:
    """True when the handler catches Exception/BaseException (or is bare)."""
    node = handler.type
    if node is None:
        return True
    if isinstance(node, ast.Name):
        return node.id in BROAD_EXCEPTIONS
    if isinstance(node, ast.Tuple):
        return any(isinstance(elt, ast.Name) and elt.id in BROAD_EXCEPTIONS for elt in node.elts)
    return False


def _describe(handler: ast.ExceptHandler) -> str:
    return f"except {ast.unparse(handler.type)}" if handler.type else "bare except:"


def _observes_exception(handler: ast.ExceptHandler) -> bool:
    """True when the handler binds the exception and its body references it.

    ``except Exception as exc: errors.append(str(exc))`` observes the failure,
    so a later aggregate assertion can still fail the test.
    """
    if not handler.name:
        return False
    return any(isinstance(node, ast.Name) and node.id == handler.name for node in _iter_own_scope(handler))


def _swallowed_asserts(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(line, handler description)`` for every swallowing handler."""
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        if not any(any(isinstance(n, ast.Assert) for n in _iter_own_scope(stmt)) for stmt in node.body):
            continue
        for handler in node.handlers:
            if not _is_broad(handler):
                continue
            if any(isinstance(n, ast.Raise) for n in _iter_own_scope(handler)):
                continue
            if _observes_exception(handler):
                continue
            findings.append((node.lineno, _describe(handler)))
    return findings


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return findings for one file; unparsable files are reported as an error."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"  !! cannot parse {path}: {exc}", file=sys.stderr)
        return [(-1, "syntax error")]
    return _swallowed_asserts(tree)


def collect_python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix == ".py" else []
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    roots = [Path(a) for a in args] if args else [ROOT / name for name in DEFAULT_ROOTS]

    print("Swallowed-assert check (assert inside try whose broad except cannot propagate)")
    print("Scanning: " + ", ".join(str(r) for r in roots))

    total = 0
    for root in roots:
        for path in collect_python_files(root):
            for line, handler in scan_file(path):
                total += 1
                try:
                    shown = path.relative_to(ROOT)
                except ValueError:
                    shown = path
                print(f"  FAIL {shown}:{line}  assert swallowed by {handler}")

    if total:
        print(f"\nFAIL: {total} assert(s) can be swallowed by a broad except handler.")
        print("Fix: assert outside the try, narrow the handler, or re-raise.")
        return 1
    print("\nOK: no assert is swallowed by a broad except handler.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
