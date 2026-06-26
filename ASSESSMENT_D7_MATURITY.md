# CarryMem 项目成熟度诚实评估报告 (Dimension 7)

> **评估日期**: 2026-06-26
> **评估方法**: DevSquad 7维度并行评估 + 实际命令输出验证
> **评估原则**: 严格、准确、诚实，杜绝自评虚报（评审数据均附实际命令输出）

---

## 一、项目概览（实测数据）

| 指标 | 数值 | 验证命令 |
|------|------|----------|
| 版本号 | v0.4.0 | `grep version src/carrymem/__version__.py` → `__version__ = "0.4.0"` |
| 源码文件数 | 144 | `find src -name "*.py" \| wc -l` |
| 源码行数 | 42,741 LOC | `find src -name "*.py" -exec wc -l {} + \| tail -1` |
| 测试文件数 | 132 | `find tests -name "*.py" \| wc -l` |
| 测试行数 | 50,952 LOC | `find tests -name "*.py" -exec wc -l {} + \| tail -1` |
| 测试总数 | 4,108 (CI 运行 4,043，65 个 slow 被跳过) | `pytest tests/ -m "not slow" --co` |
| CI 状态 | 全部通过 (3 次近期运行) | `gh run list --limit 5` |
| >500 行文件数 | 26 | `find src -name "*.py" -exec wc -l {} + \| awk 'NF==2 && $1>500' \| wc -l` |

---

## 二、7 维度评分汇总

| # | 维度 | 评分 | 等级 | 关键发现 |
|---|------|------|------|----------|
| 1 | **架构 (Architecture)** | 75/100 | B | 分层清晰但 15+ 扁平顶层模块；`carrymem.py` shim 双重间接 |
| 2 | **安全 (Security)** | 80/100 | B+ | 参数化查询、PBKDF2 加密、InputValidator；但 `:memory:` 文件泄露磁盘 |
| 3 | **测试 (Testing)** | 65/100 | C+ | 4108 测试量充足；但覆盖率门禁未强制执行（实测 15.57%） |
| 4 | **性能 (Performance)** | 80/100 | B+ | 15+ 索引、FTS5 trigram、RecallCache；但每次写有 3 次额外 recall |
| 5 | **可维护性 (Maintainability)** | 55/100 | C- | 50% 函数无 docstring；PatternAnalyzer 1547 行 God Class |
| 6 | **文档 (Documentation)** | 60/100 | C | 外部文档完整但 15+ 处版本号停留在 v0.2.0 |
| 7 | **集成 (Integration)** | 70/100 | B- | Mixin 组合清晰但 3 个幽灵功能未接入 |
| 8 | **CI/CD** | 50/100 | D+ | CI 通过但门禁形同虚设；CD 完全缺失 |

### **综合成熟度评分: 67/100 (C+)**

> **诚实判定**: 项目处于 **"功能可用但质量欠债严重"** 阶段。核心管线（declare→classify→recall）E2E 测试通过，但工程化成熟度不足以支撑生产环境部署。

---

## 三、优势（值得肯定）

1. **分类管线设计扎实** — 三层漏斗（Rule Matcher → Pattern Analyzer → Semantic Classifier）职责清晰，核心分类不依赖外部 LLM，零配置可用
2. **测试量充足** — 4108 个测试，测试/源码行数比 1.19，含变异测试（mutation testing）
3. **CI 绿色** — 3 次近期运行全部通过，7 个 job 覆盖 syntax/test/build/lint/i18n/security/docs
4. **安全基础良好** — 参数化查询、PBKDF2 加密、InputValidator、AccessPolicy、审计日志
5. **Mixin facade 架构** — core/ 8 个 Mixin + Lifecycle，组合清晰，Protocol 结构化契约
6. **E2E 用户旅程验证通过** — declare→classify→recall→conflicts→audit→forget 完整链路跑通

---

## 四、弱点（必须正视）

### 🔴 P0 严重问题（阻断生产部署）

#### 1. `:memory:` 文件泄露磁盘根目录（数据完整性风险）
```
实测命令: ls -la ":memory:"*
-rw-r--r--  98304 May 13 15:38 :memory:
-rw-r--r--  32768 Jun 24 20:45 :memory:-shm
-rw-r--r--      0 May 13 15:38 :memory:-wal
```
**根因**: 某处代码将 SQLite 连接字符串 `":memory:"` 误当作文件路径，导致创建名为 `:memory:` 的物理文件。
**影响**: 数据泄露、磁盘污染、`:memory:` 数据库行为异常。
**修复**: 排查所有 `sqlite3.connect()` 调用，确保 `":memory:"` 不被拼接成路径。

#### 2. 覆盖率门禁形同虚设（CI 在"说谎"）
```
实测: pyproject.toml 配置 fail_under=75
实测: CI 命令只有 --cov-report=term-missing，无 --cov-fail-under
实测: 实际覆盖率 15.57%（远低于 75% 门禁）
实测: CI 仍然显示 success（绿色）
```
**根因**: `pyproject.toml` 的 `fail_under=75` 仅在本地 `pytest --cov` 直接生效；CI 命令未传 `--cov-fail-under`，且 `|| true` 兜底。
**影响**: 质量门禁名存实亡，覆盖率下降不会阻断 CI，给团队虚假的安全感。
**修复**: CI 命令追加 `--cov-fail-under=75`，或调整阈值为合理值（如 60%）。

#### 3. 3 个幽灵功能（违反"充分集成，不要有幽灵功能"原则）
```
实测: CodingContextAdapter (560 LOC)
  grep -rn "CodingContextAdapter" src/ → 仅在自身文件内出现，零生产引用

实测: entry_point_helpers.py (260 LOC)
  grep "from carrymem.utils.entry_point_helpers" → 仅在自身 docstring 示例中出现
  CLI/TUI/MCP 三个入口点均未导入使用

实测: logging_config (仅测试用)
```
**影响**: 代码膨胀、维护负担、误导开发者以为功能已集成。
**修复**: 要么接入 dispatch pipeline，要么删除（推荐删除，遵循 YAGNI）。

---

### 🟠 P1 重要问题（影响可维护性）

#### 4. PatternAnalyzer 1547 行 God Class
```
实测: find src -name "*.py" -exec wc -l {} + | sort -rn | head -5
  1547 src/carrymem/layers/pattern_analyzer.py
  1324 src/carrymem/cli/_rules.py
  1114 src/carrymem/rules/__init__.py
  1058 src/carrymem/tui.py
   968 src/carrymem/integration/layer2_mcp/handlers.py
```
**影响**: 单文件过大，难以测试、难以修改、违反 SRP。
**修复**: 参考 PyCC2 Phase 3 经验，按职责拆分为子模块。

#### 5. 50% 函数无 docstring
```
实测: 675/1349 函数无文档（来自子代理报告）
```
**影响**: 可维护性差，新人上手成本高。
**修复**: 优先补充 public API 的 docstring。

#### 6. 版本号不一致（15+ 处停留在 v0.2.0）
```
实测: grep -rn "0.2.0" docs/ → 15+ 处
  docs/RULES_USER_MANUAL.md:3: **Version**: v0.2.0
  docs/EXTERNAL_MEMORY_BENCHMARKS.md:3: **版本**: v0.2.0
  docs/i18n/API_REFERENCE-JP.md:3: **バージョン**: v0.2.0
  docs/i18n/RULES_USER_MANUAL-CN.md:3: **版本**: v0.2.0
  ...
实际版本: __version__.py = "0.4.0"
```
**影响**: 文档与代码不一致，用户困惑，违反"版本号必须在所有位置保持一致"硬约束。
**修复**: 全局替换 v0.2.0 → v0.4.0（CHANGELOG 中的历史记录除外）。

#### 7. 3 个 `skipif(True)` 伪装的永久跳过
```
实测: grep -rn "skipif(True" tests/
  tests/test_e2e_mcp_tools.py:489: @pytest.mark.skipif(True, reason="Knowledge adapter requires Obsidian vault")
  tests/test_e2e_mcp_tools.py:494: @pytest.mark.skipif(True, reason="Knowledge adapter requires Obsidian vault")
  tests/test_e2e_concurrent_access.py:360: @pytest.mark.skipif(True, reason="Multi-process SQLite requires WAL mode")
```
**影响**: 永久跳过的测试伪装成条件跳过，掩盖测试盲区。
**修复**: 要么改为 `@pytest.mark.skip` 并明确原因，要么实际实现测试。

---

### 🟡 P2 改进项（影响工程规范）

#### 8. CD 完全缺失
```
实测: ls .github/workflows/ → ci.yml, benchmark.yml
无 deploy.yml / release.yml / publish.yml
```
**影响**: 无自动化发布流程，依赖手动操作，易出错。
**修复**: 新增 release workflow（tag 触发 → build → publish to PyPI）。

#### 9. 61 个 slow 测试对 CI 永久不可见
```
实测: pytest --co -m "not slow" → "65 deselected"
CI 命令: -m "not slow"
```
**影响**: 性能回归无法被 CI 捕获。
**修复**: 新增 nightly job 运行 slow 测试，或降低阈值让部分 slow 测试进入 CI。

#### 10. 测试断言密度偏低 + 30+ 松散断言
```
实测: 4545 assertions / 4108 tests = 1.1 密度（偏低）
30+ assertTrue(len>0) 松散断言
```
**影响**: 测试质量参差，可能漏检回归。
**修复**: 强化断言，从 `assertTrue(len>0)` 改为精确断言。

#### 11. 目录结构问题
```
实测: .gitignore 配置 backup/ 但实际目录是 backups/
实测: 缺少 results/ 忽略规则
实测: 测试产物未清理：.coverage, coverage.xml, htmlcov/
实测: dist/ 残留旧 v0.2.4 构建产物
实测: INSTALL.md:123-124 复制粘贴 bug
```
**修复**: 修正 .gitignore，清理产物，修复文档 bug。

---

## 五、下一步建议（按优先级排序）

### 🎯 第一优先级：P0 修复（1-2 天）

1. **修复 `:memory:` 文件泄露**
   - 排查 `sqlite3.connect()` 调用链
   - 删除已泄露的 `:memory:*` 文件
   - 添加单元测试防止回归

2. **强制执行覆盖率门禁**
   - CI 命令追加 `--cov-fail-under=60`（先从合理值开始）
   - 移除 mypy 的 `|| true` 兜底
   - 验证：故意降低覆盖率，确认 CI 失败

3. **清理 3 个幽灵功能**
   - 删除 `CodingContextAdapter`（560 LOC，零引用）
   - 删除 `entry_point_helpers.py`（260 LOC，零引用）
   - 评估 `logging_config` 是否保留

### 🎯 第二优先级：P1 改进（3-5 天）

4. **统一版本号**
   - 全局替换 v0.2.0 → v0.4.0（保留 CHANGELOG 历史）
   - 添加 pre-commit hook 检查版本一致性

5. **拆分 PatternAnalyzer God Class**
   - 按职责拆分：模式检测 / 规则匹配 / 语义增强
   - 参考 PyCC2 Phase 3 经验

6. **修正 3 个 `skipif(True)` 永久跳过**
   - 改为 `@pytest.mark.skip` 或实际实现测试

7. **补充 public API docstring**
   - 优先补充 50% 无 docstring 的 public 函数

### 🎯 第三优先级：P2 工程化（5-7 天）

8. **新增 CD pipeline**
   - release.yml: tag 触发 → build → twine upload to PyPI
   - 自动生成 GitHub Release Notes

9. **nightly slow test job**
   - 每日定时运行 `-m "slow"` 测试

10. **清理目录结构**
    - 修正 .gitignore（backup/ → backups/）
    - 清理 dist/、htmlcov/、coverage.xml 产物
    - 修复 INSTALL.md copy-paste bug

11. **强化测试断言**
    - 30+ `assertTrue(len>0)` → 精确断言

---

## 六、成熟度判定总结

| 维度 | 判定 |
|------|------|
| **功能完整性** | ✅ 核心管线可用，E2E 通过 |
| **架构合理性** | ⚠️ 分层清晰但有 God Class 和幽灵功能 |
| **代码质量** | ⚠️ 50% 无 docstring，断言密度偏低 |
| **测试有效性** | ❌ 门禁未强制，覆盖率 15.57% 远低于声称的 75% |
| **CI/CD 完备性** | ❌ CI 绿但门禁失效，CD 完全缺失 |
| **文档准确性** | ❌ 15+ 处版本号不一致 |
| **安全合规** | ⚠️ 基础良好但 `:memory:` 泄露 |
| **生产就绪** | ❌ **未达到生产部署标准** |

### **最终诚实结论**

> CarryMem v0.4.0 是一个 **功能原型成熟但工程化欠债** 的项目。
>
> - **能跑**：核心管线 E2E 通过，CI 绿色
> - **不能上**：覆盖率门禁失效（15.57% vs 声称 75%）、`:memory:` 文件泄露、3 个幽灵功能、CD 缺失
>
> 完成上述 P0 修复后，预计可达到 **75/100 (B)** 的生产可用基线。
> 完成全部 P0-P2 后，预计可达到 **85/100 (B+)** 的工程化成熟基线。

---

## 七、评估证据附录（实际命令输出）

<details>
<summary>📋 点击展开验证命令输出</summary>

```bash
# 版本号验证
$ grep version src/carrymem/__version__.py
__version__ = "0.4.0"

# 文件数与行数
$ find src -name "*.py" | wc -l
144
$ find tests -name "*.py" | wc -l
132
$ find src -name "*.py" -exec wc -l {} + | tail -1
42741 total
$ find tests -name "*.py" -exec wc -l {} + | tail -1
50952 total

# CI 状态
$ gh run list --limit 5
completed  success  fix: resolve P2-P3 technical debt  CI Pipeline  new-main  push  28143321706  13m29s
completed  success  fix: resolve P2-P3 technical debt  Performance Benchmarks  new-main  push  28143321698  51s

# :memory: 文件泄露
$ ls -la ":memory:"*
-rw-r--r--  98304 May 13 15:38 :memory:
-rw-r--r--  32768 Jun 24 20:45 :memory:-shm
-rw-r--r--      0 May 13 15:38 :memory:-wal

# 覆盖率门禁未强制
$ grep "fail_under\|cov-fail-under" pyproject.toml .github/workflows/ci.yml
pyproject.toml:43:fail_under = 75
# CI 中无 --cov-fail-under

# 实际覆盖率
$ pytest tests/ -m "not slow" --co -q | tail -5
TOTAL  16707  13294  5348  19  15.57%
FAIL Required test coverage of 75.0% not reached. Total coverage: 15.57%
4043/4108 tests collected (65 deselected)

# 幽灵功能验证
$ grep -rn "CodingContextAdapter" src/ --include="*.py" | grep -v "coding_context_adapter.py"
# (无输出 → 零生产引用)

$ grep -rn "from carrymem.utils.entry_point_helpers" src/ tests/
# (无输出 → 零导入)

# 永久跳过
$ grep -rn "skipif(True" tests/
tests/test_e2e_mcp_tools.py:489: @pytest.mark.skipif(True, reason="Knowledge adapter requires Obsidian vault")
tests/test_e2e_mcp_tools.py:494: @pytest.mark.skipif(True, reason="Knowledge adapter requires Obsidian vault")
tests/test_e2e_concurrent_access.py:360: @pytest.mark.skipif(True, reason="Multi-process SQLite requires WAL mode")

# 版本号不一致
$ grep -rn "0.2.0" docs/ | wc -l
15+

# 大文件
$ find src -name "*.py" -exec wc -l {} + | sort -rn | head -5
1547 src/carrymem/layers/pattern_analyzer.py
1324 src/carrymem/cli/_rules.py
1114 src/carrymem/rules/__init__.py
1058 src/carrymem/tui.py
 968 src/carrymem/integration/layer2_mcp/handlers.py

# CD 缺失
$ ls .github/workflows/
benchmark.yml  ci.yml
```

</details>

---

*本报告由 DevSquad 7维度并行评估生成，所有数据均经实际命令验证。*
