#!/usr/bin/env python3
"""CarryMem API Reference Documentation Generator.

Scans src/carrymem/core/ for all _*.py modules, extracts class docstrings
and public method signatures, and generates a comprehensive API_REFERENCE.md.

Usage:
    python docs/generate_docs.py

Output:
    docs/API_REFERENCE.md  (overwritten)
"""

import ast
import inspect
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Configuration ────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORE_DIR = PROJECT_ROOT / "src" / "carrymem" / "core"
OUTPUT_FILE = PROJECT_ROOT / "docs" / "API_REFERENCE.md"

# Additional modules to document (beyond core/_*.py)
EXTRA_MODULES = [
    ("src/carrymem/monitoring/__init__.py", "monitoring"),
    ("src/carrymem/plugins/__init__.py", "plugins"),
    ("src/carrymem/security/permissions.py", "security.permissions"),
    ("src/carrymem/adapters/base.py", "adapters.base"),
    ("src/carrymem/adapters/json_adapter.py", "adapters.json_adapter"),
    ("src/carrymem/coordinators/classification_pipeline.py", "coordinators.classification_pipeline"),
]


# ── AST Helpers ──────────────────────────────────────────────────────────


def _get_docstring(node: ast.AST) -> Optional[str]:
    """Extract docstring from an AST node."""
    return ast.get_docstring(node)


def _get_public_methods(class_node: ast.ClassDef) -> List[Tuple[ast.FunctionDef, str]]:
    """Get all public methods (not starting with _) from a class definition.

    Returns:
        List of (method_node, signature_string) tuples.
    """
    methods = []
    for item in class_node.body:
        if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
            # Build signature string
            args = item.args
            parts = []

            # Regular arguments
            for i, arg in enumerate(args.args):
                if arg.arg in ("self", "cls"):
                    continue
                part = arg.arg
                if args.defaults and i >= len(args.args) - len(args.defaults):
                    default_idx = i - (len(args.args) - len(args.defaults))
                    default = args.defaults[default_idx]
                    part += f"={_ast_node_to_str(default)}"
                # Add annotation if present
                if arg.annotation:
                    ann = _ast_node_to_str(arg.annotation)
                    part = f"{arg.arg}: {ann}"
                else:
                    part = arg.arg
                parts.append(part)

            # *args
            if args.vararg:
                v = args.vararg.arg
                if args.vararg.annotation:
                    ann = _ast_node_to_str(args.vararg.annotation)
                    v = f"*{v}: {ann}"
                else:
                    v = f"*{v}"
                parts.append(v)

            # **kwargs
            if args.kwarg:
                k = args.kwarg.arg
                if args.kwarg.annotation:
                    ann = _ast_node_to_str(args.kwarg.annotation)
                    k = f"**{k}: {ann}"
                else:
                    k = f"**{k}"
                parts.append(k)

            sig = f"{item.name}({', '.join(parts)})"
            methods.append((item, sig))

    return methods


def _ast_node_to_str(node: ast.AST) -> str:
    """Convert an AST node to a source-like string."""
    if isinstance(node, ast.Constant):
        return repr(node.value)
    elif isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        return f"{_ast_node_to_str(node.value)}.{node.attr}"
    elif isinstance(node, ast.Subscript):
        value = _ast_node_to_str(node.value)
        slice_val = _ast_node_to_str(node.slice) if hasattr(node.slice, 'id') or isinstance(node.slice, (ast.Name, ast.Constant)) else "..."
        return f"{value}[{slice_val}]"
    elif isinstance(node, ast.Tuple):
        elts = ", ".join(_ast_node_to_str(e) for e in node.elts)
        return f"({elts})"
    elif isinstance(node, ast.List):
        elts = ", ".join(_ast_node_to_str(e) for e in node.elts)
        return f"[{elts}]"
    elif isinstance(node, ast.Dict):
        items = []
        for k, v in zip(node.keys, node.values):
            ks = _ast_node_to_str(k) if k else "..."
            vs = _ast_node_to_str(v)
            items.append(f"{ks}: {vs}")
        return "{" + ", ".join(items) + "}"
    elif isinstance(node, ast.BinOp):
        left = _ast_node_to_str(node.left)
        right = _ast_node_to_str(node.right)
        op_map = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.Mod: "%"}
        op = op_map.get(type(node.op), "?")
        return f"{left} {op} {right}"
    elif isinstance(node, ast.Call):
        func = _ast_node_to_str(node.func)
        args = ", ".join(_ast_node_to_str(a) for a in node.args)
        return f"{func}({args})"
    elif isinstance(node, ast.UnaryOp):
        operand = _ast_node_to_str(node.operand)
        if isinstance(node.op, ast.USub):
            return f"-{operand}"
        return operand
    else:
        return "..."


def _parse_args_from_docstring(docstring: Optional[str]) -> List[Dict[str, str]]:
    """Parse Args/Returns from a Google-style docstring.

    Returns:
        List of {"name": ..., "type": ..., "desc": ...} dicts.
    """
    if not docstring:
        return []

    result = []
    lines = docstring.split("\n")

    in_args = False
    in_returns = False
    current_section = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("Args:") or stripped.startswith("Arguments:"):
            in_args = True
            in_returns = False
            continue
        elif stripped.startswith("Returns:"):
            in_returns = True
            in_args = False
            result.append({"name": "_returns", "type": "", "desc": stripped.replace("Returns:", "").strip()})
            continue
        elif stripped and not stripped.startswith(" ") and in_args:
            # New section started
            in_args = False
        elif stripped and not stripped.startswith(" ") and in_returns:
            in_returns = False

        if in_args and stripped:
            # Parse "param_name (type): description" or "param_name: description"
            m = re.match(r"^(\w+)\s*(?:\(([^)]*)\))?:\s*(.*)$", stripped)
            if m:
                result.append({
                    "name": m.group(1),
                    "type": m.group(2) or "",
                    "desc": m.group(3),
                })

    return result


# ── Module Scanner ────────────────────────────────────────────────────────


def scan_module(filepath: Path) -> Dict[str, Any]:
    """Parse a Python module and extract API documentation info.

    Args:
        filepath: Path to the .py file.

    Returns:
        Dict with module_docstring, classes list.
    """
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError as e:
        print(f"  [WARN] Syntax error in {filepath}: {e}", file=sys.stderr)
        return {"module_docstring": "", "classes": [], "errors": [str(e)]}

    module_docstring = _get_docstring(tree) or ""
    classes = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            class_docstring = _get_docstring(node) or ""
            public_methods = _get_public_methods(node)

            # Get properties
            properties = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in item.decorator_list:
                        if isinstance(dec, ast.Name) and dec.id == "property":
                            prop_sig = f"{item.name}: property"
                            prop_doc = _get_docstring(item) or ""
                            properties.append({
                                "name": item.name,
                                "signature": prop_sig,
                                "docstring": prop_doc,
                            })
                            break

            classes.append({
                "name": node.name,
                "docstring": class_docstring,
                "methods": [
                    {
                        "name": m.name,
                        "signature": sig,
                        "docstring": _get_docstring(m) or "",
                    }
                    for m, sig in public_methods
                ],
                "properties": properties,
            })

    return {
        "module_path": str(filepath.relative_to(PROJECT_ROOT)),
        "module_name": filepath.stem,
        "module_docstring": module_docstring,
        "classes": classes,
        "errors": [],
    }


# ── Markdown Generator ───────────────────────────────────────────────────


def generate_markdown(modules: List[Dict[str, Any]]) -> str:
    """Generate the full API reference Markdown from parsed module data.

    Args:
        modules: List of parsed module info dicts.

    Returns:
        Complete Markdown string.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    lines.append("# CarryMem API Reference\n")
    lines.append(f"**Generated**: {now}  ")
    lines.append(f"**Source**: `docs/generate_docs.py`  ")
    lines.append(f"**Total Modules Documented**: {len(modules)}\n")
    lines.append("---\n")

    # Table of Contents
    lines.append("## Table of Contents\n")
    for mod in modules:
        mod_id = mod["module_name"].lstrip("_").replace(".", "-").replace("_", "-")
        display_name = mod["module_name"]
        lines.append(f"- [{display_name}](#{mod_id})")
    lines.append("")
    lines.append("---\n")

    # Per-module documentation
    for mod in modules:
        mod_id = mod["module_name"].lstrip("_").replace(".", "-").replace("_", "-")
        display_name = mod["module_name"]

        lines.append(f"## {display_name}\n")
        lines.append(f'**Module**: `{mod["module_path"]}`\n')

        if mod["module_docstring"]:
            # First paragraph only for summary
            first_para = mod["module_docstring"].split("\n\n")[0].strip()
            lines.append(f"> {first_para}\n")

        if not mod["classes"]:
            lines.append("*No public classes found.*\n")
            continue

        # Class list table
        lines.append("### Classes\n")
        lines.append("| Class | Description |")
        lines.append("|-------|-------------|")
        for cls in mod["classes"]:
            desc = cls["docstring"].split("\n")[0].strip() if cls["docstring"] else "*No docstring*"
            # Truncate long descriptions
            if len(desc) > 80:
                desc = desc[:77] + "..."
            lines.append(f"| `{cls['name']}` | {desc} |")
        lines.append("")

        # Detailed per-class API
        for cls in mod["classes"]:
            cls_anchor = cls["name"].lower()
            lines.append(f"#### Class: `{cls['name']}`\n")

            if cls["docstring"]:
                lines.append(f"**Docstring**:\n")
                lines.append(f"> {cls['docstring'].split(chr(10))[0]}")
                lines.append("")

            # Properties
            if cls["properties"]:
                lines.append("**Properties**:\n")
                lines.append("| Property | Type | Description |")
                lines.append("|----------|------|-------------|")
                for prop in cls["properties"]:
                    desc = prop["docstring"].split("\n")[0].strip() if prop["docstring"] else ""
                    lines.append(f"| `{prop['name']}` | `property` | {desc} |")
                lines.append("")

            # Methods
            if cls["methods"]:
                lines.append("**Methods**:\n")
                for method in cls["methods"]:
                    lines.append(f"<details>")
                    lines.append(f"<summary><code>{method['signature']}</code></summary>\n")

                    if method["docstring"]:
                        # Format docstring nicely
                        ds_lines = method["docstring"].split("\n")
                        for dl in ds_lines[:15]:  # Limit to avoid huge output
                            lines.append(f"  {dl}")
                        if len(ds_lines) > 15:
                            lines.append(f"  ... ({len(ds_lines) - 15} more lines)")
                    else:
                        lines.append("  *No docstring.*")

                    lines.append("\n</details>\n")

            lines.append("---\n")

    # Summary statistics
    total_classes = sum(len(m["classes"]) for m in modules)
    total_methods = sum(
        len(cls["methods"]) + len(cls["properties"])
        for m in modules
        for cls in m["classes"]
    )
    total_with_doc = sum(
        1
        for m in modules
        for cls in m["classes"]
        if cls["docstring"]
    )
    methods_with_doc = sum(
        sum(1 for meth in cls["methods"] if meth["docstring"])
        + sum(1 for prop in cls["properties"] if prop["docstring"])
        for m in modules
        for cls in m["classes"]
    )

    lines.append("## Summary Statistics\n")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Modules | {len(modules)} |")
    lines.append(f"| Total Classes | {total_classes} |")
    lines.append(f"| Total Methods/Properties | {total_methods} |")
    lines.append(f"| Classes with Docstrings | {total_with_doc}/{total_classes} |")
    lines.append(f"| Methods with Docstrings | {methods_with_doc}/{total_methods} |")
    lines.append("")
    lines.append("---\n")
    lines.append("*Auto-generated by `docs/generate_docs.py`. Do not edit manually.*\n")

    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    """Main entry point: scan modules and generate documentation."""
    print("=" * 60)
    print("CarryMem API Reference Generator")
    print("=" * 60)

    modules: List[Dict[str, Any]] = []

    # 1. Scan core/_*.py files
    print(f"\n[1/2] Scanning core modules: {CORE_DIR}")
    if CORE_DIR.exists():
        core_files = sorted(CORE_DIR.glob("_*.py"))
        print(f"      Found {len(core_files)} core module(s)")
        for fpath in core_files:
            print(f"      - {fpath.name}")
            info = scan_module(fpath)
            modules.append(info)
            if info["errors"]:
                for err in info["errors"]:
                    print(f"        ERROR: {err}")
    else:
        print(f"      ERROR: Core directory not found: {CORE_DIR}")

    # 2. Scan extra modules
    print(f"\n[2/2] Scanning extra modules:")
    for rel_path, name in EXTRA_MODULES:
        fpath = PROJECT_ROOT / rel_path
        if fpath.exists():
            print(f"      - {name}")
            info = scan_module(fpath)
            info["module_name"] = name
            modules.append(info)
        else:
            print(f"      - {name} (SKIPPED: file not found)")

    # Generate markdown
    print(f"\nGenerating API_REFERENCE.md ({len(modules)} modules)...")
    markdown = generate_markdown(modules)

    # Write output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(markdown, encoding="utf-8")
    print(f"\nDone! Output written to: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size:,} bytes")

    # Print summary
    total_classes = sum(len(m["classes"]) for m in modules)
    total_methods = sum(sum(len(c["methods"]) + len(c["properties"]) for c in m["classes"]) for m in modules)
    print(f"\nSummary: {len(modules)} modules, {total_classes} classes, {total_methods} methods/properties")


if __name__ == "__main__":
    main()
