# CarryMem 技术债改进计划 v0.5.0

**文档版本**: 1.0  
**创建日期**: 2026-06-14  
**目标版本**: v0.5.0  
**预计完成时间**: 2-3 周

---

## 📋 执行摘要

基于 v0.4.0 成熟度评估报告，本文档制定了三个优先改进方向的详细实施方案：

1. **P2 优先级 - CLI i18n 完整覆盖** (立即执行)
2. **P0 优先级 - 类型注解补全至 95%+**
3. **P0 优先级 - Docstring 补全至 100%**

---

## 🎯 改进项 #1: CLI i18n 完整覆盖

### 当前状态
✅ **已完成**:
- i18n 框架实现 (`I18nManager`, `zh-CN`, `en` 双语支持)
- 37 个错误码双语消息
- `show_help()` 函数使用 `_t()` 翻译核心命令描述

❌ **未完成**:
- **189 个 CLI 参数的 `help` 文本仍为英文**
- argparse 子命令描述未翻译
- CLI 错误提示消息未翻译

### 影响范围统计

| CLI 模块 | 参数数量 | 当前状态 | 优先级 |
|---------|---------|---------|--------|
| `_memory.py` | 42 | 全英文 | P0 |
| `_rules.py` | 89 | 全英文 | P0 |
| `_io.py` | 26 | 全英文 | P1 |
| `_stats.py` | 13 | 全英文 | P1 |
| `_mcp.py` | 10 | 全英文 | P2 |
| `_backup.py` | 9 | 全英文 | P2 |
| **总计** | **189** | **0% 中文化** | - |

### 技术方案

#### 方案 A: 动态语言切换 (推荐 ⭐)

**优势**:
- 用户可通过环境变量切换语言
- 国际化友好，易于扩展其他语言
- 符合现有 i18n 框架设计

**实现步骤**:

1. **扩展 i18n 消息库** (2小时)
   ```python
   # src/carrymem/i18n/zh_CN.py 新增
   ZH_CN_MESSAGES.update({
       # Memory 命令
       "cli.arg.message": "要记忆的消息内容",
       "cli.arg.namespace": "命名空间 (默认: default)",
       "cli.arg.context": "额外上下文信息 (JSON 格式)",
       "cli.arg.force": "强制存储，跳过分类",
       "cli.arg.type": "指定记忆类型 (需配合 --force)",
       "cli.arg.limit": "显示数量限制",
       "cli.arg.format": "输出格式",
       "cli.arg.db": "数据库路径",
       # ... 189 个参数翻译
   })
   ```

2. **修改 CLI 参数定义** (4小时)
   ```python
   # 修改前
   parser.add_argument("message", help="Message to remember")
   
   # 修改后
   from carrymem.i18n import _
   parser.add_argument("message", help=_("cli.arg.message"))
   ```

3. **语言切换机制** (1小时)
   ```python
   # src/carrymem/cli/_base.py
   import os
   from carrymem.i18n import set_locale
   
   # 在 CLI 入口初始化语言
   locale = os.getenv("CARRYMEM_LANG", "zh-CN")  # 默认中文
   if locale in ["en", "zh-CN"]:
       set_locale(locale)
   ```

4. **测试验证** (1小时)
   ```bash
   # 中文模式 (默认)
   carrymem add --help
   
   # 英文模式
   CARRYMEM_LANG=en carrymem add --help
   ```

**工作量估算**: **8 小时** (1 个工作日)

#### 方案 B: 直接中文替换 (快速但不灵活)

**优势**:
- 实现最快，无需 i18n 框架调用
- 适合中文用户为主的场景

**劣势**:
- 无法切换语言
- 不利于国际化

**实现**: 直接将所有 `help=` 参数改为中文字符串

**工作量估算**: **4 小时**

### 推荐方案: **方案 A** (动态语言切换)

---

## 🎯 改进项 #2: 类型注解补全至 95%+

### 当前状态
- **整体覆盖率**: 82% (109/132 文件)
- **目标覆盖率**: 95%+

### 待补全模块

| 模块 | 当前覆盖率 | 文件数 | 优先级 | 工作量 |
|------|-----------|-------|--------|--------|
| `rules/` | 75% | 12 | P0 | 4小时 |
| `layers/` | 70% | 8 | P0 | 3小时 |
| `adapters/` | 85% | 6 | P1 | 2小时 |
| `security/` | 88% | 5 | P1 | 1小时 |

### 技术方案

#### 1. 规则引擎模块类型补全 (`rules/`)

**目标文件**:
- `rules/engine.py` - 核心规则引擎
- `rules/storage.py` - 规则存储层
- `rules/matcher.py` - 规则匹配器
- `rules/injector.py` - 规则注入器

**改进示例**:
```python
# 修改前
def match(self, scene, limit=5):
    ...

# 修改后
from typing import List, Optional
from carrymem.rules.types import RuleMatch, Scene

def match(
    self, 
    scene: Scene, 
    limit: int = 5,
    scopes: Optional[List[str]] = None
) -> List[RuleMatch]:
    """匹配场景对应的规则。
    
    Args:
        scene: 场景描述或 Scene 对象
        limit: 最大返回数量
        scopes: 范围过滤列表
        
    Returns:
        匹配的规则列表，按相关性排序
    """
    ...
```

**关键改进点**:
- 函数参数和返回值完整类型注解
- 使用 `TypedDict` 定义复杂返回结构
- 使用 `Protocol` 定义接口约束
- 添加 `Optional`, `Union`, `List`, `Dict` 等泛型类型

**工作量**: 4 小时

#### 2. 分层模块类型补全 (`layers/`)

**工作量**: 3 小时

#### 3. 使用 `mypy --strict` 验证

```bash
cd carrymem
mypy src/carrymem/rules/ --strict
mypy src/carrymem/layers/ --strict
```

**目标**: 零错误零警告

---

## 🎯 改进项 #3: Docstring 补全至 100%

### 当前状态
- **覆盖率**: 61% (117/191 方法)
- **缺失数量**: 74 个方法
- **目标**: 100% 覆盖

### Docstring 标准格式

采用 **Google Style** (项目现有风格):

```python
def method_name(arg1: str, arg2: int = 0) -> Dict[str, Any]:
    """方法的简短描述（一句话）。
    
    更详细的说明段落，解释方法的用途、
    行为特点、注意事项等。
    
    Args:
        arg1: 第一个参数的说明
        arg2: 第二个参数的说明（默认值: 0）
        
    Returns:
        返回值的详细说明，包括结构和字段含义
        
    Raises:
        ValueError: 参数无效时抛出
        DatabaseError: 数据库操作失败时抛出
        
    Example:
        >>> result = method_name("test", 42)
        >>> print(result["status"])
        ok
    """
    ...
```

### 待补全方法分布

| 模块 | 缺失 Docstring | 优先级 | 工作量 |
|------|---------------|--------|--------|
| `core/_memory_crud.py` | 12 | P0 | 2小时 |
| `core/_recall.py` | 10 | P0 | 2小时 |
| `rules/engine.py` | 15 | P0 | 2小时 |
| `adapters/sqlite/` | 8 | P1 | 1小时 |
| `security/` | 7 | P1 | 1小时 |
| 其他模块 | 22 | P2 | 3小时 |
| **总计** | **74** | - | **11小时** |

### 实施步骤

1. **生成待补全清单** (30分钟)
   ```bash
   cd carrymem
   python scripts/analyze_docstring_coverage.py > docstring_todo.txt
   ```

2. **按优先级批量补全** (10小时)
   - P0: 核心业务逻辑 (6小时)
   - P1: 适配器和安全 (2小时)
   - P2: 其他模块 (2小时)

3. **验证覆盖率** (30分钟)
   ```bash
   interrogate -v src/carrymem/ --fail-under 100
   ```

**总工作量**: 11 小时 (1.5 个工作日)

---

## 📅 实施时间表

### Week 1: CLI i18n (P2 → P0 提升)

| 任务 | 工作量 | 负责人 | 状态 |
|------|--------|--------|------|
| 扩展 i18n 消息库 (189 条) | 2h | TBD | ⏳ |
| 修改 CLI 参数定义 | 4h | TBD | ⏳ |
| 实现语言切换机制 | 1h | TBD | ⏳ |
| 测试验证 | 1h | TBD | ⏳ |
| **小计** | **8h** | - | - |

### Week 2-3: 类型注解 + Docstring

| 任务 | 工作量 | 负责人 | 状态 |
|------|--------|--------|------|
| rules/ 类型补全 | 4h | TBD | ⏳ |
| layers/ 类型补全 | 3h | TBD | ⏳ |
| adapters/ 类型补全 | 2h | TBD | ⏳ |
| mypy strict 验证 | 1h | TBD | ⏳ |
| Docstring 补全 (P0) | 6h | TBD | ⏳ |
| Docstring 补全 (P1+P2) | 5h | TBD | ⏳ |
| 覆盖率验证 | 1h | TBD | ⏳ |
| **小计** | **22h** | - | - |

### 总工作量: **30 小时** (约 4 个工作日)

---

## ✅ 验收标准

### CLI i18n
- [ ] 所有 189 个 CLI 参数 `help` 文本支持中文
- [ ] 通过 `CARRYMEM_LANG` 环境变量切换语言
- [ ] 默认语言为中文 (`zh-CN`)
- [ ] 英文模式完整保留
- [ ] 至少 5 个 CLI 命令的集成测试

### 类型注解
- [ ] `mypy src/carrymem/rules/ --strict` 零错误
- [ ] `mypy src/carrymem/layers/ --strict` 零错误
- [ ] 整体类型覆盖率 ≥ 95%
- [ ] 所有 public API 函数有完整类型签名
- [ ] IDE 类型提示无警告

### Docstring
- [ ] `interrogate` 覆盖率 = 100%
- [ ] 所有 public 方法有 Google Style docstring
- [ ] 包含 Args, Returns, Raises 完整说明
- [ ] 至少 20 个方法有 Example 代码块
- [ ] 文档自动生成无警告

---

## 🚨 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| i18n 破坏现有测试 | 高 | 中 | 保持英文为可选项，增加语言切换测试 |
| 类型注解引入运行时错误 | 中 | 低 | 仅添加注解不改逻辑，mypy strict 验证 |
| Docstring 工作量超预期 | 低 | 中 | 分批完成，P0 优先 |
| 与并行开发冲突 | 中 | 中 | 使用独立分支，小步提交 |

---

## 📊 预期成果

完成后的改进指标:

| 指标 | 当前 (v0.4.0) | 目标 (v0.5.0) | 提升 |
|------|--------------|--------------|------|
| CLI i18n 覆盖率 | 0% | **100%** | +100% |
| 类型注解覆盖率 | 82% | **≥95%** | +13% |
| Docstring 覆盖率 | 61% | **100%** | +39% |
| 成熟度评分 | 82.4/100 (B+) | **≥88/100 (A-)** | +5.6 |

---

## 📚 参考资料

- [CarryMem v0.4.0 成熟度报告](./MATURITY_REPORT_v0.4.0.md)
- [Python i18n 最佳实践](https://docs.python.org/3/library/i18n.html)
- [MyPy 类型检查指南](https://mypy.readthedocs.io/)
- [Google Python Style Guide - Docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)

---

## 🔄 下一步行动

1. **立即**: 创建 `feature/cli-i18n-complete` 分支
2. **Day 1**: 完成 CLI i18n 改进
3. **Day 2-4**: 完成类型注解和 Docstring 补全
4. **Day 5**: 集成测试 + PR 提交

**预计完成日期**: 2026-06-21

---

*文档维护者*: AI 助手  
*审核者*: CarryMem 项目团队  
*最后更新*: 2026-06-14
