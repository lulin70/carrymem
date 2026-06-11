#!/usr/bin/env python3
"""CarryMem 模块依赖分析工具。

使用 AST 解析 src/carrymem/ 下所有 .py 文件的 import 语句，
输出模块间依赖矩阵、循环依赖检测报告和分层违规检查。

用法:
    python scripts/analyze_dependencies.py              # 完整分析
    python scripts/analyze_dependencies.py --matrix      # 仅依赖矩阵
    python scripts/analyze_dependencies.py --cycles      # 仅循环依赖
    python scripts/analyze_dependencies.py --layers      # 仅分层检查
    python scripts/analyze_dependencies.py --dot         # 输出 Graphviz DOT 格式
"""

from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ── 项目根目录（相对于本脚本位置）─────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / "src" / "carrymem"

# ── carrymem 内部模块前缀 ───────────────────────────────
INTERNAL_PREFIX = "carrymem."

# ── 层次定义（按设计意图） ────────────────────────────
LAYER_DEFINITION: Dict[str, int] = {
    # 第 1 层：基础设施
    "security": 1,
    "utils": 1,
    "patterns": 1,
    "coordinators": 1,
    # 第 2 层：适配器
    "adapters": 2,
    # 第 3 层：处理层
    "layers": 3,
    # 第 4 层：业务逻辑
    "core": 4,
    "rules": 4,
    "semantic": 4,
    "llm": 4,
    # 第 5 层：集成
    "integration": 5,
    # 第 6 层：用户接口
    "cli": 6,
}

# 根级模块默认为第 4 层（业务逻辑）
ROOT_DEFAULT_LAYER = 4


class DependencyAnalyzer:
    """AST 驱动的 Python 模块依赖分析器。"""

    def __init__(self, source_dir: Path):
        self.source_dir = source_dir.resolve()
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.module_files: Dict[str, Path] = {}
        self.all_modules: Set[str] = set()

    def scan(self) -> None:
        """递归扫描 source_dir 下所有 .py 文件，提取 import 关系。"""
        for py_file in sorted(self.source_dir.rglob("*.py")):
            if py_file.name.startswith(".") or py_file.suffix != ".py":
                continue
            rel_path = py_file.relative_to(self.source_dir)
            module_name = self._path_to_module(rel_path)
            self.module_files[module_name] = py_file
            self.all_modules.add(module_name)
            self._extract_imports(py_file, module_name)

    @staticmethod
    def _path_to_module(rel_path: Path) -> str:
        """将相对路径转为模块名。如: core/_lifecycle.py → core._lifecycle"""
        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][: -len(".py")]
        return ".".join(parts) if parts else ""

    def _extract_imports(self, file_path: Path, module_name: str) -> None:
        """从单个文件中 AST 解析 import 语句。"""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"  [WARN] 无法解析 {file_path}: {e}", file=sys.stderr)
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    dep = self._normalize_import(alias.name)
                    if dep and dep != module_name:
                        self.dependencies[module_name].add(dep)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    dep = self._normalize_import(node.module)
                    if dep and dep != module_name:
                        self.dependencies[module_name].add(dep)

    def _normalize_import(self, import_name: str) -> Optional[str]:
        """标准化导入名，仅保留 carrymem 内部依赖。

        Returns:
            标准化的内部模块名，非内部依赖返回 None。
        """
        name = import_name.split(".")[0]
        if not name.startswith("carrymem"):
            return None

        # 去掉 'carrymem.' 前缀得到相对模块名
        relative = import_name[len(INTERNAL_PREFIX):]

        # 处理相对导入（以点开头的情况已在 ImportFrom 中处理为绝对路径）
        # 这里只做标准化
        return f"carrymem.{relative}" if relative else None

    def get_layer(self, module: str) -> int:
        """根据模块名判断其所在层次。"""
        # 去掉 carrymem. 前缀
        inner = module[len(INTERNAL_PREFIX):] if module.startswith(INTERNAL_PREFIX) else module
        top_level = inner.split(".")[0] if inner else ""
        return LAYER_DEFINITION.get(top_level, ROOT_DEFAULT_LAYER)

    # ── 报告生成方法 ──────────────────────────────────────

    def report_matrix(self) -> str:
        """输出依赖矩阵。"""
        lines: List[str] = []
        lines.append("=" * 80)
        lines.append("CarryMem 模块依赖矩阵")
        lines.append("=" * 80)
        lines.append(f"扫描范围: {self.source_dir}")
        lines.append(f"总模块数: {len(self.all_modules)}")
        lines.append(f"总依赖关系数: {sum(len(v) for v in self.dependencies.values())}")
        lines.append("")

        # 按模块名排序
        for mod in sorted(self.dependencies.keys()):
            deps = sorted(self.dependencies[mod])
            internal_deps = [d for d in deps if d.startswith(INTERNAL_PREFIX)]
            external_deps = [d for d in deps if not d.startswith(INTERNAL_PREFIX)]

            layer = self.get_layer(mod)
            lines.append(f"[L{layer}] {mod}")
            if internal_deps:
                for d in internal_deps:
                    d_layer = self.get_layer(d)
                    arrow = "→" if d_layer >= layer else "↑" if d_layer < layer else "→"
                    lines.append(f"       {arrow} {d}  [L{d_layer}]")
            if external_deps:
                lines.append(f"       (外部: {', '.join(external_deps[:5])}{'...' if len(external_deps) > 5 else ''})")
            if not deps:
                lines.append("       (无内部依赖)")
            lines.append("")

        return "\n".join(lines)

    def detect_cycles(self) -> List[List[str]]:
        """检测循环依赖（DFS）。
        
        Returns:
            发现的所有环路列表，每条环路是一个有序的模块名列表。
        """
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        path: List[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.dependencies.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # 找到环路
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.remove(node)

        for mod in sorted(self.all_modules):
            if mod not in visited:
                dfs(mod)

        # 去重（同一环路可能从不同起点发现多次）
        unique_cycles: List[List[str]] = []
        seen_cycle_sets: Set[frozenset] = set()
        for cycle in cycles:
            cycle_key = frozenset(cycle[:-1])  # 不含重复的终点
            if cycle_key not in seen_cycle_sets:
                seen_cycle_sets.add(cycle_key)
                unique_cycles.append(cycle)

        return unique_cycles

    def report_cycles(self) -> str:
        """循环依赖报告。"""
        cycles = self.detect_cycles()
        lines: List[str] = []
        lines.append("=" * 80)
        lines.append("循环依赖检测报告")
        lines.append("=" * 80)

        if not cycles:
            lines.append("✅ 未发现循环依赖")
            return "\n".join(lines)

        lines.append(f"⚠️ 发现 {len(cycles)} 个潜在循环依赖:")
        lines.append("")

        for i, cycle in enumerate(cycles, 1):
            severity = "🔴" if len(cycle) <= 3 else "🟡"
            lines.append(f"{severity} 循环 #{i}: {' → '.join(cycle)}")
            lines.append(f"   环路长度: {len(cycle)-1}")
            # 分析涉及的层次
            layers_in_cycle = [f"{self.get_layer(m)}({m})" for m in cycle[:-1]]
            lines.append(f"   涉及层次: {', '.join(layers_in_cycle)}")
            lines.append("")

        return "\n".join(lines)

    def report_layer_violations(self) -> str:
        """分层违规报告。"""
        lines: List[str] = []
        violations: List[Tuple[str, str, int, int]] = []

        for mod, deps in self.dependencies.items():
            mod_layer = self.get_layer(mod)
            for dep in deps:
                if not dep.startswith(INTERNAL_PREFIX):
                    continue
                dep_layer = self.get_layer(dep)
                # 低层依赖高层是违规
                if dep_layer > mod_layer:
                    violations.append((mod, dep, mod_layer, dep_layer))

        lines.append("=" * 80)
        lines.append("分层违规检查报告")
        lines.append("=" * 80)

        if not violations:
            lines.append("✅ 未发现分层违规（低层模块依赖高层模块）")
            return "\n".join(lines)

        lines.append(f"⚠️ 发现 {len(violations)} 处分层违规:")
        lines.append("")
        lines.append(f"{'源模块':<40} {'目标模块':<35} {'源层':>4} {'目标层':>6}")
        lines.append("-" * 85)

        for src, dst, src_l, dst_l in sorted(violations):
            lines.append(f"{src:<40} {dst:<35} L{src_l:>2}   L{dst_l:>2}")

        lines.append("")
        lines.append(f"说明: 源层(L{src_l}) < 目标层(L{dst_l}) 表示低层模块依赖了高层模块，违反分层原则。")
        return "\n".join(lines)

    def report_summary(self) -> str:
        """汇总统计报告。"""
        lines: List[str] = []
        lines.append("=" * 80)
        lines.append("CarryMem 模块依赖分析 — 汇总报告")
        lines.append("=" * 80)
        lines.append("")

        # 基本统计
        total_modules = len(self.all_modules)
        total_deps = sum(len(v) for v in self.dependencies.values())
        internal_deps = sum(
            1 for deps in self.dependencies.values() for d in deps if d.startswith(INTERNAL_PREFIX)
        )
        cycles = self.detect_cycles()

        # 层次分布
        layer_dist: Dict[int, int] = defaultdict(int)
        for mod in self.all_modules:
            layer_dist[self.get_layer(mod)] += 1

        # 扇入扇出
        fan_out = {mod: len(deps) for mod, deps in self.dependencies.items()}
        fan_in: Dict[str, int] = defaultdict(int)
        for deps in self.dependencies.values():
            for d in deps:
                if d.startswith(INTERNAL_PREFIX):
                    fan_in[d] += 1

        top_fan_out = sorted(fan_out.items(), key=lambda x: -x[1])[:10]
        top_fan_in = sorted(fan_in.items(), key=lambda x: -x[1])[:10]

        lines.append(f"📊 基本统计:")
        lines.append(f"   总模块数:     {total_modules}")
        lines.append(f"   总依赖数:     {total_deps}")
        lines.append(f"   内部依赖数:   {internal_deps}")
        lines.append(f"   外部依赖数:   {total_deps - internal_deps}")
        lines.append(f"   循环依赖数:   {len(cycles)}")
        lines.append("")

        lines.append(f"📚 层次分布:")
        for layer_num in sorted(layer_dist.keys()):
            lines.append(f"   L{layer_num}: {layer_dist[layer_num]} 个模块")
        lines.append("")

        lines.append(f"🔥 高扇出 TOP10 (最多依赖他人的模块):")
        for mod, count in top_fan_out:
            lines.append(f"   {count:>3}  {mod}")
        lines.append("")

        lines.append(f"🎯 高扇入 TOP10 (被最多模块依赖):")
        for mod, count in top_fan_in:
            lines.append(f"   {count:>3}  {mod}")
        lines.append("")

        return "\n".join(lines)

    def export_dot(self) -> str:
        """导出 Graphviz DOT 格式的依赖图。"""
        lines: List[str] = []
        lines.append('digraph carrymem_dependencies {')
        lines.append('    rankdir=LR;')
        lines.append('    node [shape=box, fontname="Helvetica"];')
        lines.append('')

        # 按层次分组
        subgraphs: Dict[int, List[str]] = defaultdict(list)
        for mod in self.all_modules:
            subgraphs[self.get_layer(mod)].append(mod)

        for layer_num in sorted(subgraphs.keys()):
            mods = subgraphs[layer_num]
            cluster_name = f"cluster_L{layer_num}"
            lines.append(f'    subgraph {cluster_name} {{')
            lines.append(f'        label = "Layer {layer_num}";')
            lines.append(f'        style = filled;')
            colors = {1: "#e8f5e9", 2: "#e3f2fd", 3: "#fff3e0", 4: "#fce4ec", 5: "#f3e5f5", 6: "#efebe9"}
            lines.append(f'        color = "{colors.get(layer_num, "#ffffff")}";')
            for mod in mods:
                safe_name = mod.replace(".", "_").replace("carrymem_", "")
                lines.append(f'        "{safe_name}" [label="{mod}"];')
            lines.append("    }")
            lines.append("")

        # 边
        drawn_edges: Set[Tuple[str, str]] = set()
        for src, deps in self.dependencies.items():
            for dst in deps:
                if not dst.startswith(INTERNAL_PREFIX):
                    continue
                edge = (src, dst)
                if edge not in drawn_edges:
                    drawn_edges.add(edge)
                    s = src.replace(".", "_").replace("carrymem_", "")
                    d = dst.replace(".", "_").replace("carrymem_", "")
                    src_layer = self.get_layer(src)
                    dst_layer = self.get_layer(dst)
                    color = "red" if dst_layer > src_layer else "black"
                    style = "bold" if dst_layer > src_layer else "solid"
                    lines.append(f'    "{s}" -> "{d}" [color={color}, style={style}];')

        lines.append("}")
        return "\n".join(lines)


def main():
    """主入口函数。"""
    args = set(sys.argv[1:])
    
    if not SRC_DIR.exists():
        print(f"❌ 源码目录不存在: {SRC_DIR}", file=sys.stderr)
        sys.exit(1)

    analyzer = DependencyAnalyzer(SRC_DIR)
    print("🔍 正在扫描模块...", file=sys.stderr)
    analyzer.scan()
    print(f"✅ 扫描完成: {len(analyzer.all_modules)} 个模块\n", file=sys.stderr)

    if not args or "--matrix" in args:
        print(analyzer.report_matrix())

    if not args or "--cycles" in args:
        print(analyzer.report_cycles())

    if not args or "--layers" in args:
        print(analyzer.report_layer_violations())

    if "--summary" in args or not args:
        print(analyzer.report_summary())

    if "--dot" in args:
        dot_output = PROJECT_ROOT / "docs" / "dependency_graph.dot"
        dot_output.write_text(analyzer.export_dot(), encoding="utf-8")
        print(f"\n📝 DOT 文件已导出至: {dot_output}", file=sys.stderr)
        print("   可使用 `dot -Tpng docs/dependency_graph.png -o dependency_graph.png` 生成图片", file=sys.stderr)


if __name__ == "__main__":
    main()
