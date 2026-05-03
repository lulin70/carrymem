# CarryMem 用户体验整改方案

**文档版本**: v1.0  
**创建日期**: 2026-05-02  
**基于**: USER_EXPERIENCE_REVIEW.md + 实际验证结果  
**评审团队**: 架构师 / PM / 安全专家 / 测试专家 / 开发者 / DevOps / UI设计师  

---

## 一、实际验证发现（Review报告未覆盖）

### 验证环境
- macOS, Python 3.9.6
- `pip3 install -e .` 后测试

### 验证结果汇总

| # | 验证项 | 预期 | 实际 | 严重度 |
|---|--------|------|------|--------|
| V1 | `carrymem version` | 显示版本 | `carrymem not found` | P0 |
| V2 | `pip3 install -e .` 版本号 | 0.4.1 | 0.4.0.dev0 | P0 |
| V3 | `carrymem remember "xxx"` | 存储记忆 | `Unknown command: remember` | P1 |
| V4 | `carrymem rules list` | 列出规则 | `Unknown command: rules` | P1 |
| V5 | `classify_and_remember()` 自动规则建议 | 高质量规则 | 质量极差（复制原文/词语堆砌） | P0 |
| V6 | `result.get("rule_suggestions")` | 规则列表 | `None`（字段名是`auto_rules`） | P1 |
| V7 | `from layer2_mcp import build_system_prompt` | 可导入 | ImportError | P2 |
| V8 | `carrymem doctor` | 诊断通过 | 14/16通过，auto-inject disabled | P2 |
| V9 | `carrymem add "xxx"` | 正常存储 | 正常工作 | - |
| V10 | `carrymem list` | 列出记忆 | 正常工作 | - |

---

## 二、问题清单与整改方案（7角色评审共识）

### 🔴 P0 — 阻碍核心使用（必须立即修复）

---

#### P0-1: CLI命令不可用

**现象**: `carrymem` 命令不在 PATH 中  
**根因**: `pip install -e .` 安装脚本到 `~/Library/Python/3.9/bin/`，该路径不在 PATH  
**影响**: 新用户100%在第一步失败

**整改方案（DevOps + 开发者）**:

方案A（推荐）: 添加 `carrymem` 快捷脚本到项目根目录
```bash
#!/usr/bin/env python3
"""CarryMem CLI wrapper - ensures carrymem command works regardless of PATH"""
import sys
from memory_classification_engine.cli import main
if __name__ == "__main__":
    main()
```

方案B: 在 `setup.py` 中添加 `scripts` 字段
```python
scripts=['bin/carrymem'],
```

方案C: 在安装文档中明确提示用户添加 PATH
```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
# 或
python3 -m memory_classification_engine.cli version
```

**共识**: 采用方案A+B组合。创建 `bin/carrymem` 脚本，同时在 setup.py 添加 scripts 字段。

**工作量**: 0.5天

---

#### P0-2: 自动规则建议质量极差

**现象**: `classify_and_remember()` 返回的 `auto_rules` 质量极差
```python
# 输入: "I prefer dark mode for all editors"
# 返回:
[
  {"trigger": "dark mode", "action": "遵循: I prefer dark mode for all editors"},  # 复制原文
  {"trigger": "tech selection", "action": "prefer prefer, mode, dark"},             # 词语堆砌
  {"trigger": "related scenarios", "action": "consider prefer, decided, react first"} # 无意义
]
```

**根因**: `_auto_suggest_rules()` 的实现过于简单：
1. 直接复制原文作为 action，而非提取行为指令
2. 隐式偏好检测的 trigger/action 生成逻辑有缺陷
3. 没有对建议质量进行过滤

**整改方案（架构师 + 开发者）**:

1. 重写 `_auto_suggest_rules()` 的 action 生成逻辑：
```python
def _auto_suggest_rules(self, stored_memories):
    suggestions = []
    for mem in stored_memories:
        mem_type = mem.get("type", "")
        content = mem.get("content", "")
        
        if mem_type == "user_preference":
            # 从偏好中提取行为指令
            # "I prefer dark mode" → trigger="UI theme", action="use dark mode"
            trigger = self._extract_trigger_from_preference(content)
            action = self._extract_action_from_preference(content)
            suggestions.append({
                "trigger": trigger,
                "action": action,
                "rule_type": "prefer",
                "scope": "personal",
                "override": False,
                "confidence": 0.6,
            })
    return suggestions
```

2. 添加 `_extract_trigger_from_preference()` 和 `_extract_action_from_preference()` 方法
3. 添加建议质量过滤：confidence < 0.5 或 action 与原文完全相同的建议不返回
4. 限制每次最多返回 1 条建议（避免信息过载）

**工作量**: 1天

---

#### P0-3: pip 安装版本号错误

**现象**: `pip3 install -e .` 后显示 `carrymem-0.4.0.dev0` 而非 `0.4.1`  
**根因**: `setup.py` 的 `get_version()` 在安装时执行，但此时 `memory_classification_engine` 包可能未安装，回退到硬编码的 `"0.4.0-dev"`

**整改方案（开发者）**:

修改 `setup.py`，从 `__version__.py` 直接读取而非 import：
```python
def get_version():
    import re
    version_file = os.path.join(
        os.path.dirname(__file__), 
        "src", "memory_classification_engine", "__version__.py"
    )
    with open(version_file) as f:
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)', f.read())
        if match:
            return match.group(1)
    return "0.4.1"
```

**工作量**: 0.5小时

---

### 🟡 P1 — 影响体验（应尽快修复）

---

#### P1-1: CLI子命令不直观

**现象**: 用户直觉使用 `carrymem remember` / `carrymem rules list`，但实际命令是 `carrymem add` / `carrymem list-rules`  
**根因**: 命令命名不一致，记忆操作用 `add` 而非 `remember`，规则操作用 `list-rules` 而非 `rules list`

**整改方案（PM + UI设计师）**:

添加别名系统：
```python
commands = {
    # 记忆操作 - 两种风格都支持
    "add": cmd_add,
    "remember": cmd_add,       # 新增别名
    "save": cmd_add,           # 新增别名
    
    # 规则操作 - 支持子命令风格
    "list-rules": cmd_list_rules,
    "rules": cmd_rules_hub,    # 新增：子命令分发器
    # ...
}

def cmd_rules_hub(args):
    """Rules sub-command hub: rules list/add/delete/match"""
    if not args:
        cmd_list_rules([])
        return 0
    sub = args[0]
    sub_args = args[1:]
    sub_commands = {
        "list": cmd_list_rules,
        "add": cmd_add_rule,
        "delete": cmd_delete_rule,
        "match": cmd_match_rules,
        "edit": cmd_edit_rule,
    }
    handler = sub_commands.get(sub)
    if handler:
        return handler(sub_args)
    print(f"Unknown rules sub-command: {sub}")
    return 1
```

**工作量**: 0.5天

---

#### P1-2: 返回字段名不一致

**现象**: `classify_and_remember()` 返回 `auto_rules`，但文档和测试中引用 `rule_suggestions`  
**根因**: 开发过程中字段名变更但未同步

**整改方案（开发者 + 测试专家）**:

统一为 `rule_suggestions`（更直观）：
```python
return {
    "should_remember": True,
    "type": ...,
    "content": ...,
    "entries": stored_memories,
    "stored": len(stored_memories) > 0,
    "storage_keys": storage_keys,
    "rule_suggestions": auto_rules,  # 统一字段名
    "auto_rules": auto_rules,        # 保留兼容性，deprecated
    "updated_memories": updated_memories,
    "summary": classify_result["summary"],
}
```

**工作量**: 1小时

---

#### P1-3: 包名 vs 导入名混乱

**现象**: `pip install carrymem` 但 `from memory_classification_engine import CarryMem`  
**根因**: 历史原因，包名和模块名不一致

**整改方案（架构师 + PM 共识）**:

**短期（v0.4.2）**: 添加 `carrymem` 作为兼容导入路径
```python
# src/carrymem/__init__.py
from memory_classification_engine import *  # re-export
```

**中期（v1.0.0）**: 正式重命名为 `carrymem`
- 需要 `src/carrymem/` 替代 `src/memory_classification_engine/`
- Breaking change，需要版本号升级到 1.0.0
- 影响 422 处代码引用

**共识**: 短期方案立即执行，中期方案纳入 v1.0.0 规划。

**工作量**: 短期 2小时，中期 3天

---

#### P1-4: 缺少首次使用引导

**现象**: 新用户不知道从何开始  
**整改方案（PM + UI设计师）**:

1. 添加 `carrymem init` 交互式初始化
2. 添加 `carrymem tutorial` 5分钟快速入门
3. 首次运行 `carrymem` 自动触发引导

```python
def cmd_tutorial(args):
    print("""
  Welcome to CarryMem! Let's learn the basics in 5 minutes.
  
  [1/4] Store your first memory
  >>> carrymem add "I prefer dark mode"
  
  [2/4] View your memories
  >>> carrymem list
  
  [3/4] Search your memories
  >>> carrymem search "theme"
  
  [4/4] Connect to your AI tool
  >>> carrymem setup-mcp --tool cursor
  
  You're all set! CarryMem will now help your AI remember you.
""")
```

**工作量**: 1天

---

### 🟢 P2 — 可优化（中长期改进）

---

#### P2-1: MCP集成模块导出不完整

**现象**: `from layer2_mcp import build_system_prompt` 失败  
**根因**: `build_system_prompt` 是 `CarryMem` 实例方法，不是模块级函数

**整改方案（架构师）**:

在 `layer2_mcp/__init__.py` 添加便捷函数：
```python
def build_system_prompt(context=None, max_memories=10, language="en"):
    """Convenience function for building system prompts"""
    from memory_classification_engine import CarryMem
    cm = CarryMem()
    prompt = cm.build_system_prompt(context=context, max_memories=max_memories, language=language)
    cm.close()
    return prompt
```

**工作量**: 1小时

---

#### P2-2: 缺少故障排查文档

**整改方案（DevOps）**: 创建 `docs/TROUBLESHOOTING.md`

**工作量**: 4小时

---

#### P2-3: 缺少性能监控命令

**整改方案（开发者）**: 添加 `carrymem perf` 命令

**工作量**: 0.5天

---

## 三、核心循环验证

### 记忆→规则→注入 闭环验证

```
步骤1: 用户说 "I prefer Python over Java for backend"
  → classify_and_remember() ✅ 正确分类为 user_preference
  → 存储到 SQLite ✅
  → 自动规则建议 ❌ 质量差（P0-2）

步骤2: 规则注入到 AI prompt
  → RuleEngine.inject() ✅ 可注入
  → build_system_prompt() ✅ 可调用
  → MCP handler get_system_prompt ✅ 可用

步骤3: AI 使用规则
  → 规则匹配场景 ✅
  → 规则注入到 system prompt ✅
  → AI 遵循规则 ⚠️ 取决于AI模型，非CarryMem控制
```

**结论**: 核心循环基本闭环，但自动规则建议质量是短板。

---

## 四、5分钟首次使用验证

### 当前体验（失败）

```
1. pip install carrymem         → ✅ 安装成功
2. carrymem version             → ❌ command not found
3. 困惑，放弃
```

### 修复后体验（目标）

```
1. pip install carrymem         → ✅ 安装成功
2. carrymem version             → ✅ CarryMem v0.4.2
3. carrymem init                → ✅ 初始化数据库
4. carrymem add "I prefer..."   → ✅ 存储记忆 + 规则建议
5. carrymem setup-mcp --tool cursor → ✅ 配置AI工具
```

**预估时间**: 3分钟

---

## 五、修复优先级与排期

### Sprint 1（本周，v0.4.2）

| 优先级 | 问题 | 负责角色 | 工作量 | 验证标准 |
|--------|------|----------|--------|----------|
| P0-1 | CLI命令不可用 | DevOps+开发者 | 0.5天 | `carrymem version` 可执行 |
| P0-2 | 自动规则建议质量差 | 架构师+开发者 | 1天 | action 不再复制原文 |
| P0-3 | pip版本号错误 | 开发者 | 0.5小时 | `pip show carrymem` 显示 0.4.2 |
| P1-1 | CLI子命令不直观 | PM+UI | 0.5天 | `carrymem remember` 可用 |
| P1-2 | 返回字段名不一致 | 开发者+测试 | 1小时 | `result["rule_suggestions"]` 有值 |

### Sprint 2（下周，v0.4.3）

| 优先级 | 问题 | 负责角色 | 工作量 | 验证标准 |
|--------|------|----------|--------|----------|
| P1-3 | 包名导入兼容 | 架构师 | 2小时 | `from carrymem import CarryMem` 可用 |
| P1-4 | 首次使用引导 | PM+UI | 1天 | `carrymem init` + `carrymem tutorial` |
| P2-1 | MCP模块导出 | 架构师 | 1小时 | `from layer2_mcp import build_system_prompt` |
| P2-2 | 故障排查文档 | DevOps | 4小时 | TROUBLESHOOTING.md 存在且覆盖常见问题 |

### Sprint 3（v0.5.0，1-2月后）

| 优先级 | 问题 | 负责角色 | 工作量 |
|--------|------|----------|--------|
| P2-3 | 性能监控 | 开发者 | 0.5天 |
| - | Web UI | UI+开发者 | 5天 |
| - | VS Code扩展改进 | UI+开发者 | 3天 |
| - | 包名正式重命名 | 全员 | 3天 |

---

## 六、团队评审共识

### 达成共识的要点

1. **P0问题必须本周修复** — CLI不可用和规则建议质量差是产品可用性的致命伤
2. **5分钟首次使用是硬指标** — 修复后新用户必须能在5分钟内完成首次使用
3. **核心循环（记忆→规则→注入）已基本闭环** — 但自动规则建议质量需要提升
4. **包名重命名是v1.0.0的必要条件** — 短期通过兼容导入缓解
5. **文档必须与实际一致** — 每次发布前验证文档中的所有命令

### 分歧与决策

| 分歧 | PM观点 | 架构师观点 | 决策 |
|------|--------|-----------|------|
| 包名重命名时机 | 立即做 | v1.0.0再做 | 短期兼容导入，v1.0.0正式重命名 |
| 规则建议自动创建 | 自动创建规则 | 只建议不创建 | 只建议，用户确认后创建 |
| CLI子命令风格 | `carrymem remember` 更直观 | `carrymem add` 更简洁 | 两种都支持（别名） |

---

## 七、验收标准

### v0.4.2 验收清单

- [ ] `carrymem version` 可执行并显示正确版本
- [ ] `carrymem remember "xxx"` 等同于 `carrymem add "xxx"`
- [ ] `classify_and_remember()` 返回的 `rule_suggestions` 质量合格（action 不复制原文）
- [ ] `pip show carrymem` 版本号与 `__version__.py` 一致
- [ ] 所有文档中的 CLI 命令可直接复制使用
- [ ] 回归测试全部通过

---

**文档维护者**: CarryMem Team  
**下次评审**: v0.4.2 发布后
