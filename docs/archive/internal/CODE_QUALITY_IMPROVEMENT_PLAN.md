# CarryMem 代码质量改进计划

**创建日期**: 2026-05-03  
**当前版本**: v0.1.5  
**目标**: 提升代码质量、可维护性和安全性

---

## 一、问题概览

### 问题分级

| 优先级 | 问题数量 | 影响范围 | 处理时间 |
|--------|---------|---------|---------|
| **P0** | 59项 | 核心功能稳定性 | 应尽快处理 |
| **P1** | 71项 | 代码质量 | 本迭代处理 |
| **P2/P3** | 若干 | 优化改进 | 可排期处理 |

---

## 二、P0问题（应尽快处理）

### 问题1：38处静默异常吞没 🔴 严重

**问题描述**：
代码中存在38处异常被捕获但未记录日志，导致问题难以追踪和调试。

**示例**：
```python
# 不好的做法
try:
    result = some_operation()
except Exception:
    pass  # 静默吞没异常

# 好的做法
try:
    result = some_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise  # 或者返回默认值
```

**影响**：
- ❌ 生产环境问题难以定位
- ❌ 用户遇到错误无法反馈
- ❌ 开发调试困难

**修复计划**：
1. **第1周**：修复核心模块（10处）
   - `src/memory_classification_engine/core/classifier.py`
   - `src/memory_classification_engine/core/memory_manager.py`
   - `src/memory_classification_engine/storage/sqlite_adapter.py`

2. **第2周**：修复适配器和工具（15处）
   - `src/memory_classification_engine/adapters/`
   - `src/memory_classification_engine/cli.py`
   - `src/memory_classification_engine/mcp/`

3. **第3周**：修复其他模块（13处）
   - `src/memory_classification_engine/rules/`
   - `src/memory_classification_engine/semantic/`
   - `src/memory_classification_engine/utils/`

**工作量估算**：
- 每处修复：15-30分钟
- 总计：10-20小时
- 建议：2-3周完成

---

### 问题2：21个核心模块缺少测试 🔴 严重

**问题描述**：
21个核心模块没有单元测试，测试覆盖率不足。

**当前测试覆盖率**：
- 总体：79%
- 核心模块：部分<50%
- 目标：>85%

**缺少测试的模块**：
```
1. src/memory_classification_engine/rules/rule_engine.py
2. src/memory_classification_engine/rules/rule_matcher.py
3. src/memory_classification_engine/semantic/cross_language.py
4. src/memory_classification_engine/adapters/obsidian_adapter.py
5. src/memory_classification_engine/mcp/server.py
6. src/memory_classification_engine/mcp/tools.py
7. src/memory_classification_engine/encryption/custom_encryption.py
8. src/memory_classification_engine/utils/language_detector.py
9. src/memory_classification_engine/utils/text_processor.py
10. src/memory_classification_engine/cli_commands/profile.py
... (共21个)
```

**修复计划**：

**第1周：核心功能测试（7个模块）**
```python
# 优先级最高
- rule_engine.py (规则引擎核心)
- rule_matcher.py (规则匹配)
- cross_language.py (跨语言支持)
- memory_manager.py (记忆管理)
- classifier.py (分类器)
- sqlite_adapter.py (存储适配器)
- mcp/server.py (MCP服务器)
```

**第2周：适配器和工具测试（7个模块）**
```python
- obsidian_adapter.py
- json_r.py
- mcp/tools.py
- encryption/custom_encryption.py
- utils/language_detector.py
- utils/text_processor.py
- cli_commands/profile.py
```

**第3周：其他模块测试（7个模块）**
```python
- cli_commands/rules.py
- cli_commands/export.py
- semantic/embedding.py
- semantic/similarity.py
- utils/config_loader.py
- utils/path_resolver.py
- integrations/cursor.py
```

**测试模板**：
```python
import pytest
from memory_classification_engine.rules import RuleEngine

class TestRuleEngine:
    @pytest.fixture
    def rule_engine(self):
        return Rgine()
    
    def test_add_rule(self, rule_engine):
        """测试添加规则"""
        rule = {
            "trigger": "test",
            "action": "test_action",
            "scope": "personal"
        }
        result = rule_engine.add_rule(rule)
        assert result is not None
        assert result["trigger"] == "test"
    
    def test_match_rules(self, rule_engine):
        """测试规则匹配"""
        rule_engine.add_rule({
            "trigger": "database",
            "action": "use PostgreSQL",
            "se": "personal"
        })
        matches = rule_engine.match_rules("working with database")
        assert len(matches) > 0
    
    def test_rule_priority(self, rule_engine):
        """测试规则优先级"""
        # 添加多个规则测试优先级
        pass
    
    def test_error_handling(self, rule_engine):
        """测试错误处理"""
        with pytest.raises(ValueError):
            rule_engine.add_rule(None)
```

**工作量估算**：
- 每个模块：2-4小时（编写测试+修复bug）
- 总计：42-84小时
- 建议：3-4周完成

---

## 三、P1问题（本迭代处理）

### 问题3：9个文件硬编码路径 🟡 中等

**问题描述**：
代码中存在硬编码路径，降低了可移植性和可配置性。

**示例**：
```python
#法
DB_PATH = "/Users/lin/.carrymem/memories.db"
CONFIG_PATH = "/Users/lin/.carrymem/config.yaml"

# 好的做法
import os
from pathlib import Path

DEFAULT_CONFIG_DIR = Path.home() / ".carrymem"
DB_PATH = os.getenv("CARRYMEM_DB_PATH", DEFAULT_CONFIG_DIR / "memories.db")
CONFIG_PATH = os.getenv("CARRYMEM_CONFIG_PATH", DEFAULT_CONFIG_DIR / "config.yaml")
```

**需要修复的文件**：
```
1. src/memory_classification_engine/storage/sqlite_adapter.py
2. src/memory_classification_engine/config/default_config.py
3. srory_classification_engine/cli.py
4. src/memory_classification_engine/mcp/server.py
5. src/memory_classification_engine/adapters/obsidian_adapter.py
6. tests/test_storage.py
7. tests/test_config.py
8. examples/basic_usage.py
9. scripts/setup.py
```

**修复方案**：

**步骤1：创建路径常量模块**
```python
# src/memory_classification_engine/constants.py
import os
from pathlib import Path

# 基础路径
HOME_DIR = Path.home()
DEFAULT_CONFIG_DIR = HOME_DIR / ".carrymem"

# 可配置路径
CONFIG_DIR = Path(os.getenv("CARRYMEM_CONFIG_DIR", DEFAULT_CONFIG_DIR))
DB_PATH = Path(os.getenv("CARRYMEM_DB_PATH", CONFIG_DIR / "memories.db"))\FILE = Path(os.getenv("CARRYMEM_CONFIG_FILE", CONFIG_DIR / "config.yaml"))
LOG_DIR = Path(os.getenv("CARRYMEM_LOG_DIR", CONFIG_DIR / "logs"))

# MCP相关路径
MCP_CONFIG_CURSOR = HOME_DIR / ".cursor" / "mcp.json"
MCP_CONFIG_CLAUDE = HOME_DIR / ".claude" / "mcp.json"
MCP_CONFIG_WINDSURF = HOME_DIR / ".windsurf" / "mcp.json"

# Obsidian相关路径
OBSIDIAN_DEFAULT_VAULT = HOME_DIR / "Documents" / "Obsidian"
```

**步骤2：逐文件替换硬编码路径**
```python
# 修改前
DB_PATH = "/Users/lin/.carrymem/memories.db"

# 修改后
from memory_classification_engine.constants import DB_PATH
```

**工作量估算**：
- 创建constants.py：1小时
- 每个文件修复：30分钟
- 总计：5-6小时
- 建议：1周完成

---

### 问题4：覆盖率阈值 55%→70% 🟡 中等

**问题描述**：
当前测试覆盖率阈值设置为55%，需要提升到70%。

**当前状态**：
```ini
# pytest.ini 或 pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=memory_classification_engine --cov-report=html --cov-fail-under=55"
```

**目标状态**：
```ini
[tool.pytest.ini_options]
addopts = "--cov=memory_classification_engine --cov-report=html --cov-fail-under=70"
```

**实现路径**：
1. 补充P0问题2中的21个模块测试 → 覆盖率提升到~85%
2. 修复现有测试中的边界情况 → 覆盖率提升到~88%
3. 添加集成测试 → 覆盖率提升到~90%
4. 更新阈值配置

**工作量估算**：
- 依赖P0问题2的完成
- 配置更新：10分钟
- 建议：与P0问题2同步完成

-
### 问题5：62处宽泛异常捕获分批重构 🟡 中等

**问题描述**：
代码中存在62处使用`except Exception`的宽泛异常捕获，应该捕获具体异常类型。

**示例**：
```python
# 不好的做法
try:
    result = db.query(sql)
except Exception as e:  # 太宽泛
    logger.error(f"Query failed: {e}")

# 好的做法
try:
    result = db.query(sql)
except sqlite3.OperationalError as e:
    logger.error(f"Database locked: {e}")
    raise DatabaseLockError() from e
except sqlite3.IntegrityError as e:
    logger.error(f"Constraint violation: {e}")
    raise DataIntegrityError() from e
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

**分批重构计划**：

**第1批（20处）：存储层**
```python
# 文件
- src/memory_classification_engine/storage/sqlite_adapter.py (10处)
- src/memory_classification_engine/storage/base_adapter.py (5处)
- src/memory_classification_engine/adapters/obsidian_adapter.py (5处)

# 具体异常类型
- sqlite3.OperationalError (数据库锁定)
- sqlite3.IntegrityError (约束违反)
- sqlite3.DatabaseError (数据库错误)
- IOError (文件操作错误)
- PermissionError (权限错误)
```

**第2批（20处）：核心逻辑层**
```python
# 文件
- src/memory_classification_engine/core/classifier.py (8处)
- src/memory_classification_engine/core/memory_manager.py (7处)
- src/memory_classification_engine/rules/rule_engine.py (5处)

# 具体异常类型
- ValueError (参数错误)
- TypeError (类型错误)
- KeyError (键不存在)
- AttributeError (属性不存在)
```

**第3批（22处）：工具和CLI层**
```python
# 文件
- src/memory_classification_engine/cli.py (10处)
- src/memory_classification_engine/mcp/server.py (7处)
- src/memory_classification_engine/utils/*.py (5处)

# 具体异常类型
- FileNotFoundError (文件不存在)
- json.JSONDecodeError (JSON解析错误)
- yaml.YAMLError (YAML解析错误)
- ImportError (导入错误)
```

**工作量估算**：
- 每处重构：10-20分钟
- 总计：10-20小时
- 建议：分3周完成，每周一批

---

## 四、P2/P3问题（可排期处理）

### 问题6：自定义加密回退方案安全评估 🟢 低

**问题描述**：
当cryptography库不可用时，使用自定义加密方案，需要安全评估。

**当前实现**：
```python
# src/memory_classification_engine/encryption/custom_encryption.py
def encrypt(data, key):
    # 简单的XOR加密（不安全）
    return bytes(a ^ b for a, b in zip(data, itertools.cycle(key)))
```

**建议方案**：
1. **短期**：添加明确警告
```python
import warnings

def encrypt(data, key):
    warnings.warn(
        "Using fallback encryption (XOR). "
        "Install cryptography for secure encryption: "
        "pip install 'carrymem[encryption]'",
        SecurityWarning
    )
    return bytes(a ^ b for a, b in zip(data, itertools.cycle(key)))
```

2. **长期**：使用标准库hashlib
```python
import hashlib
from cryptography.fernet import Fernet

def encrypt(data, key):
    try:
        from cryptography.fernet import Fernet
        # 使用Fernet加密
    except ImportError:
        # 使用hashlib作为回退
        import hashlib
        derived_key = hashlib.pbkdf2_hmac('sha256', key, b'salt', 100000)
        # 使用AES加密（需要pycryptodome）
```

**工作量估算**：
- 短期方案：1小时
- 长期方案：4-6小时
- 建议：v0.2.0版本处理

---

### 问题7：CORS匹配加固 🟢 低

**问题描述**：
MCP服务器的CORS配置可能过于宽松。

**当前实现**：
```python
# src/memory_classification_engine/mcp/server.py
ALLOWED_ORIGINS = ["*"]  # 允许所有来源
```

**建议方案**：
```python
# 更严格的CORS配置
ALLOWED_ORIGINS = [
    "http://localhost:*",
    "https://cursor.sh",
    "https://claude.ai",
    "https://windsurf.ai",
]

def is_origin_allowed(origin):
    for pattern in ALLOWED_ORIGINS:
        if fnmatch.fnmatch(origin, pattern):
            return True
    return False
```

**工作量估算**：
- 2-3小时
- 建议：v0.2.0版本处理

---

### 问题8：HTTP错误响应脱敏 🟢 低

**问题描述**：
HTTP错误响应可能泄露敏感信息（如文件路径、堆栈跟踪）。

**当前实现**：
```python
@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": str(error)}), 500  # 可能泄露堆栈信息
```

**建议方案**：
```python
@app.errorhandler(500)
def internal_error(error):
    # 记录详细错误到日志
    logger.error(f"Internal error: {error}", exc_info=True)
    
    # 返回通用错误信息
    if app.debug:
        return jsonify({"error": str(error)}), 500
    else:
        return jsonify({"error": "Internal server error"}), 500
```

**工作量估算**：
- 2-3小时
- 建议：v0.2.0版本处理

---

### 问题9：无消费者导出清理 🟢 低

**问题描述**：
代码中存在未使用的导出（exports）。

**修复方案**：
```bash
# 使用工具检测
pip install vulture
vulture src/memory_classification_en或使用pylint
pylint --disable=all --enable=unused-import src/
```

**工作量估算**：
- 2-3小时
- 建议：v0.2.0版本处理

---

### 问题10：多余依赖移除 🟢 低

**问题描述**：
requirements.txt中可能存在未使用的依赖。

**修复方案**：
```bash
# 使用pipdeptree检查
pip install pipdeptree
pipdeptree --warn silence

# 使用pip-autoremove
pip install pip-autoremove
pip-autoremove <package> --list
```

**工作量估算**：
- 1-2小时
- 建议：v0.2.0版本处理

---

## 五、实施时间表

### 第1周（P0优先）
- [ ] 修复核心模块静默异常（10处）
- [ ] 添加核心功能测试（7个模块）
- [ ] 创建路径常量模块

### 第2周（P0继续）
- [ ] 修复适配器静默异常（15处）
- [ ] 添加适配器测试（7个模块）
- [ ] 替换硬编码路径（）

### 第3周（P0完成）
- [ ] 修复其他模块静默异常（13处）
- [ ] 添加其他模块测试（7个模块）
- [ ] 提升覆盖率阈值到70%

### 第4周（P1开始）
- [ ] 重构存储层异常捕获（20处）
- [ ] 代码review和测试

### 第5周（P1继续）
- [ ] 重构核心逻辑层异常捕获（20处）
- [ ] 代码review和测试

### 第6周（P1完成）
- [ ] 重构工具层异常捕获（22处）
- [ ] 代码review和测试
- [ ] 发布v0.1.6

### v0.2.0规划（P2/P3）
- [ ] 加密方案安全评估
- [ ] CORS配置加固
- [ ] HTTP错误响应脱敏
- [ ] 清理无用导出和依赖

---

## 六、质量指标

### 当前状态
- 测试覆盖率：79%
- 静默异常：38处
- 缺少测试模块：21个
- 硬编码路径：9处
- 宽泛异常捕获：62处

### 目标状态（6周后）
- 测试覆盖率：>85%
- 静默异常：0处
- 缺少测试模块：0个
- 硬编码路径：0处
- 宽泛异常捕获：<10处（仅保留必要的）

### 长期目标（v0.2.0）
- 测试覆盖率：>90%
- 代码质量评分：A级
- 安全评分：A级
- 技术债务：<5%

---

## 七、风险评估

### 高风险
- ❌ 静默异常可能隐藏生产问题
- ❌ 缺少测试导致回归风险高

### 中风险
- ⚠️ 硬编码路径影响可移植性
- ⚠️ 宽泛异常捕获难以调试

### 低风险
- ✅ 加密回退方案（已有警告）
- ✅ CORS配置（仅开发环境）

---

## 八、资源需求

### 人力
- 1名开发者全职
- 或2名开发者兼职

### 时间
- P0+P1：6周
- P2/P3：2周（v0.2.0）

### 工具
- pytest, pytest-cov
- pylint, flake8, mypy
- vulture, pipdeptree

---

## 九、成功标准

### P0完成标准
- ✅ 所有静默异常都有日志
- ✅ 所有核心模块都有测试
- ✅ 测试覆盖率>85%

### P1完成标准
- ✅ 无硬编码路径
- ✅ 测试覆盖率>70%（阈值）
- ✅ 宽泛异常捕获<10处

### P2/P3完成标准
- ✅ 加密方案有安全评估
- ✅ CORS配置加固
- ✅ 无未使用的导出和依赖

---

## 十、总结

这是一个系统性的代码质量提升计划，重点解决：
1. **可观测性**：消除静默异常，添加日志
2. **可测试性**：补充单元测试，提升覆盖率
3. **可维护性**：消除硬编码，规范异常处理
4. **安全性**：加固加密、CORS、错误响应

**建议优先级**：P0 > P1 > P2/P3

**预期收益**：
- 提升代码质量和可维护性
- 降低生产环境问题风险
- 提升开发效率和调试体验
- 增强用户信心

---

**文档维护者**: AI Assistant  
**创建日期**: 2026-05-03  
**下次更新**: 每周更新进度
