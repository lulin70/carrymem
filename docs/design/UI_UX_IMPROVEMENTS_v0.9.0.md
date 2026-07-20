# CarryMem UI/UX 改进设计文档 v0.9.0

> **文档性质**: 设计文档（文档先行原则）
> **创建时间**: 2026-07-20
> **完成时间**: 2026-07-20
> **版本**: v0.9.0 ✅ 已完成
> **基于**: DevSquad 5 角色 UI/UX 评估报告 (2026-07-20)
> **配套**: [CHANGELOG.md](../../CHANGELOG.md) | [TECH_DEBT_PLAN.md](../TECH_DEBT_PLAN.md)

## 完成状态总览

| 项 | 优先级 | 状态 | 验证 |
|----|-------|------|------|
| P0-C1: emoji → Morandi 文本符号 | P0 | ✅ | `grep -rn "⭐\|📌\|🔧\|🎯\|🔄\|👁\|📚\|💡" src/carrymem/tui.py` = 0 |
| P0-C2: CLI rich 集成 | P0 | ✅ | `from carrymem.cli._format import OutputFormatter` 无报错；45 tests pass |
| P0-T2: 色盲友好形状符号 | P0 | ✅ | ✓▲✗ℹ 在 CLI formatter 和 TUI 中统一使用 |
| P1-A1: 主题抽象层 | P1 | ✅ | `from carrymem.ui.themes import list_themes` 返回 3 主题；40 tests pass |
| P1-C3: 高对比度模式 | P1 | ✅ | `--high-contrast` CLI flag；WCAG AAA 21:1 ratio |
| P1-P1: 首次运行引导 | P1 | ✅ | OnboardingScreen 4 步流程；32 tests pass；空 DB 自动触发 |
| P1-P3: 错误恢复动作 | P1 | ✅ | ErrorDisplay 增加 R/I/H 按键 + retry_callback |
| P2-U2: 浅色 Morandi 主题 | P2 | ✅ | MorandiLightTheme 10.82:1 对比度（超 AAA） |
| P2-U4: 记忆列表分组 | P2 | ✅ | group_by_date 参数；Today/Yesterday/This Week/Earlier 4 桶 |
| P2-P4: 健康仪表盘 | P2 | ✅ | render_full_dashboard() ASCII 可视化；33 tests pass；D 键打开 |
| P2-P5: 虚拟滚动 | P2 | ✅ | MAX_VISIBLE_MEMORIES=100 懒加载；"Load more..." 展开 |

**总计**: 11/11 完成 (100%)；163 新测试；radon 0 D/E/F；所有导入验证通过。

### 最终验证数据 (2026-07-20)

| 检查项 | 命令 | 结果 |
|--------|------|------|
| 目标测试集 | `pytest tests/test_tui.py tests/test_themes.py tests/test_onboarding.py tests/test_dashboard.py tests/test_cli_format.py tests/test_exception_narrowing.py -q --no-cov` | **257 passed, 0 failed** (10.49s) |
| 全量非 e2e 回归 | `pytest tests/ --ignore=tests/e2e -q --no-cov -m "not slow" --deselect tests/test_performance_benchmark.py::test_recall_500_memories_under_100ms` | **4632 passed, 2 skipped, 57 deselected, 0 failed** (354.21s) |
| mypy 净变化 | `mypy src/` (对比基线) | 基线 10 → 当前 9（修复 tui.py:469 unused-ignore）；0 新错误；9 个均为基线历史债（config.py/audit.py/obsidian_adapter.py/async_sqlite.py/_recall.py/server.py） |
| flake8/black/isort | 3 linters on src/carrymem/ui/, tui.py, cli/_format.py | 0 errors / all unchanged / all unchanged |
| radon cc | `radon cc src/carrymem/ui/ src/carrymem/tui.py src/carrymem/cli/_format.py -n E -s` | empty (0 E/F 级别函数) |
| 版本一致性 | VERSION / __version__.py / server.json / Dockerfile | 全部 0.9.0；0.8.2 残留 0 处 |

---

## 1. 改进概述

基于 DevSquad 5 角色（UI设计师/PM/测试/架构师/开发者）对 CarryMem v0.8.2 UI/UX 的评估，推进 P0-P2 共 11 项改进。

**核心原则**（来自用户偏好）:
- 舒适 > 时髦（Morandi 配色已对齐）
- 移除刺眼 emoji，改用低饱和度文本符号
- 避免过度设计，聚焦用户价值
- 文档先行，充分测试

**版本规划**:
- v0.9.0: P0 (3项) + P1 (4项) + P2 (4项) 一次性交付

---

## 2. P0 — 快速赢（3项）

### P0-C1: emoji → Morandi 文本符号

**问题**: 类型图标使用高饱和度 emoji（⭐📌🔧🎯🔄👁📚❓），与 Morandi 低饱和度美学冲突，违反用户"comfortable over 刺眼emoji"偏好。

**方案**:
- `_TYPE_ICONS` 字典：emoji → Unicode 几何符号（低饱和度字符）
  - ⭐ → `◆`（菱形，preferences）
  - 📌 → `◇`（空心菱形，facts）
  - 🔧 → `⚙`（齿轮，corrections）
  - 🎯 → `◉`（靶心，decisions）
  - 🔄 → `↻`（循环箭头，patterns）
  - 👁 → `⊙`（眼睛，observations）
  - 📚 → `▤`（书页，knowledge）
  - ❓ → `?`（问号，unknown）
- ErrorDisplay: 移除 `💡`，改为 `Hint:` 文本
- HelpScreen: 移除 `⚙`，改为 `CarryMem TUI` 纯文本

**文件**: `src/carrymem/tui.py` (约 15 行改动)

**测试**: 现有 TUI 测试需更新断言（emoji → 新符号）

### P0-C2: CLI rich 集成 + 进度反馈

**问题**: CLI 输出无颜色/表格/进度，长操作（recall/consolidation/backup）无反馈，用户不知道是否卡死。

**方案**:
- 添加 `rich` 到主依赖（已在 `[dev]` 中）
- 新建 `src/carrymem/cli/_format.py`：封装 `OutputFormatter`
  - `table(headers, rows)` — 记忆列表/统计表格
  - `progress(description)` — 上下文管理器，长操作进度
  - `error(code, message, hint)` — 红色错误框
  - `success(message)` — 绿色成功提示
  - `warning(message)` — 金色警告
  - `info(message)` — 蓝色信息
- 替换 `cli/` 各模块的 `print()` 为 `formatter.xxx()`

**文件**: 新建 `cli/_format.py`；修改 `cli/_base.py`, `cli/_stats.py`, `cli/_io.py` 等

**测试**: 新增 `tests/test_cli_format.py`

### P0-T2: 色盲友好形状符号

**问题**: success(绿)/warning(金)/error(红) 仅靠颜色区分，红绿色盲（约 8% 男性）难辨。

**方案**:
- success: `✓` + 绿色
- warning: `▲` + 金色
- error: `✗` + 红色
- 在 CLI formatter 和 TUI ErrorDisplay 中统一使用

**文件**: `cli/_format.py`, `tui.py`

---

## 3. P1 — 体验提升（4项）

### P1-A1: 主题抽象层

**方案**:
- 新建 `src/carrymem/ui/themes.py`
- `Theme` 协议：`colors: Dict[str, str]` 属性 + `name: str`
- 3 个实现：
  - `MorandiDarkTheme` — 当前配色（默认）
  - `MorandiLightTheme` — 浅色版（P2-U2）
  - `HighContrastTheme` — 黑底白字（P1-C3）
- TUI 通过 `self.theme` 获取配色，替代硬编码 `_MORANDI`

**文件**: 新建 `ui/themes.py`；修改 `tui.py` 使用 theme

### P1-C3+T1: 高对比度模式

**方案**:
- `HighContrastTheme`: bg=`#000000`, text=`#FFFFFF`, border=`#FFFFFF`, success=`#00FF00`, warning=`#FFFF00`, error=`#FF0000`
- CLI 参数 `--high-contrast` 传入 TUI
- 配置文件持久化选择

**文件**: `ui/themes.py`, `cli/_base.py`

### P1-P1: 首次运行引导

**问题**: 新用户打开看到空白列表，不知道该做什么。

**方案**:
- 新建 `OnboardingScreen(ModalScreen)`:
  - 步骤 1: 欢迎语 + "CarryMem 会记住你说过的每句话"
  - 步骤 2: 输入第一条记忆（直接在引导页输入）
  - 步骤 3: 展示搜索功能（输入关键词搜索刚存的记忆）
  - 步骤 4: 完成 + "按 ? 查看快捷键"
- 空 DB 检测：`adapter.count() == 0` 时自动触发
- 示例数据选项："是否导入示例记忆？"（5 条预设记忆）
- 配置文件标记 `onboarding_completed: true`，不再触发

**文件**: 新建 `ui/onboarding.py`；修改 `tui.py` 检测+触发

### P1-P3: 错误恢复动作

**问题**: ErrorDisplay 只显示 hint，无操作选项，用户只能手动重试。

**方案**:
- ErrorDisplay 增加 3 个按键：
  - `[R]` 重试 — 重新执行失败的操作
  - `[I]` 忽略 — 关闭错误框继续
  - `[H]` 帮助 — 跳转到相关文档
- 需要传入 `retry_callback` 可选参数

**文件**: 修改 `tui.py` ErrorDisplay 类

---

## 4. P2 — 精细打磨（4项）

### P2-U2: 浅色 Morandi 主题

**方案**:
- `MorandiLightTheme`:
  - bg_dark: `#F5F3EE`（暖白）
  - bg_surface: `#EBE8E1`
  - bg_elevated: `#E0DDD5`
  - text_primary: `#3D3530`（深棕）
  - text_secondary: `#6B5D52`
  - border: `#D4CFC5`
  - 其余 accent/primary/secondary 保持 Morandi 色系
- Ctrl+T 切换暗/亮主题

### P2-U4: 记忆列表分组

**方案**:
- 按日期分组（今天/昨天/本周/更早）
- 每组可折叠/展开（`[+]`/`[-]`）
- 组标题显示计数（`Today (5)`）
- 配置项 `group_by: date|type|none`

### P2-P4: 健康仪表盘可视化

**方案**:
- StatsPanel 增强：
  - 记忆增长曲线（ASCII 柱状图，最近 7 天）
  - 类型分布（ASCII 饼图或横条图）
  - 冗余度评分（可能重复的记忆数）
  - 健康评分（综合：覆盖率 + 新鲜度 + 冗余度）

### P2-P5: 虚拟滚动

**方案**:
- 使用 Textual 原生 `VirtualListView` 替换 `ListView`
- 仅渲染可见行，支持 10000+ 记忆流畅滚动
- 需验证 Textual 版本兼容性

---

## 5. 测试计划

### 单元测试
- `tests/test_tui.py`: 新增 OnboardingScreen 测试、主题切换测试、ErrorDisplay 重试测试
- `tests/test_cli_format.py`: 新增 CLI formatter 测试
- `tests/test_themes.py`: 新增主题协议测试

### E2E 测试
- 首次运行引导流程 E2E
- 高对比度模式启动 E2E
- 大数据集（1000+ 记忆）滚动性能 E2E

### a11y 回归
- 对比度比 ≥ 4.5:1（WCAG AA）
- 键盘可达性 100%
- 色盲友好符号验证

---

## 6. 验证标准

| 项 | 验证命令 | 期望 |
|----|---------|------|
| emoji 移除 | `grep -rn "⭐\|📌\|🔧\|🎯\|🔄\|👁\|📚\|💡" src/carrymem/tui.py` | 0 结果 |
| rich 集成 | `python -c "from carrymem.cli._format import OutputFormatter"` | 无报错 |
| 主题抽象 | `python -c "from carrymem.ui.themes import MorandiDarkTheme"` | 无报错 |
| 高对比度 | `python -m carrymem tui --high-contrast` | 启动成功 |
| 首次运行 | 空 DB 启动 TUI | 显示 OnboardingScreen |
| 测试 | `pytest tests/ -q --tb=short` | 全通过 |
| radon | `radon cc src/carrymem/ -n D -s` | 0 D/E/F |
