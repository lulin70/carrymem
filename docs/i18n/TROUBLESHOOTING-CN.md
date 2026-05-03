# CarryMem 故障排查指南

**版本**: v0.1.5

---

## 目录

- [快速诊断](#快速诊断)
- [错误信息索引](#错误信息索引)
- [安装与配置](#安装与配置)
  - [1. CLI 命令未找到](#1-cli-命令未找到)
  - [2. 导入错误](#2-导入错误)
  - [3. 版本不匹配](#3-版本不匹配)
  - [4. pip 安装失败](#4-pip-安装失败)
- [核心记忆操作](#核心记忆操作)
  - [5. 记忆未存储](#5-记忆未存储)
  - [6. 召回无结果](#6-召回无结果)
  - [7. 记忆分类错误](#7-记忆分类错误)
  - [8. 数据库锁定](#8-数据库锁定)
  - [9. 数据库损坏](#9-数据库损坏)
- [规则引擎](#规则引擎)
  - [10. 规则未注入](#10-规则未注入)
  - [11. 规则作用域冲突](#11-规则作用域冲突)
  - [12. Skill 验证失败](#12-skill-验证失败)
  - [13. 规则建议质量差](#13-规则建议质量差)
- [MCP 集成](#mcp-集成)
  - [14. MCP 集成不工作](#14-mcp-集成不工作)
  - [15. MCP 工具超时](#15-mcp-工具超时)
- [安全与加密](#安全与加密)
  - [16. 加密/解密错误](#16-加密解密错误)
  - [17. 路径验证错误](#17-路径验证错误)
- [高级功能](#高级功能)
  - [18. Obsidian 适配器问题](#18-obsidian-适配器问题)
  - [19. TUI 显示问题](#19-tui-显示问题)
  - [20. VS Code 扩展问题](#20-vs-code-扩展问题)
  - [21. 异步 API 问题](#21-异步-api-问题)
  - [22. 备份/恢复问题](#22-备份恢复问题)
- [性能](#性能)
  - [23. 召回或规则匹配缓慢](#23-召回或规则匹配缓慢)
  - [24. 大型数据库优化](#24-大型数据库优化)
- [升级与迁移](#升级与迁移)
  - [25. 升级破坏性变更](#25-升级破坏性变更)
- [获取帮助](#获取帮助)

---

## 快速诊断

运行 `carrymem doctor` 进行全面健康检查。使用 `--fix` 自动修复，`--json` 输出结构化结果。

**输出解读表：**

| 检查项 | ok | warn | fail | 相关问题 |
|---|---|---|---|---|
| `python_version` | ≥ 3.9 | — | < 3.9 | [#4](#4-pip-安装失败) |
| `carrymem_import` | 可导入 | — | ImportError | [#2](#2-导入错误) |
| `config_dir` | 存在 | 缺失 | — | [#1](#1-cli-命令未找到) |
| `database_file` | 存在 | 缺失 | — | [#6](#6-召回无结果) |
| `db_integrity` | 通过 | — | 失败 | [#9](#9-数据库损坏) |
| `db_permissions` | 可写 | — | 只读 | [#22](#22-备份恢复问题) |
| `disk_space` | > 1 GB | < 1 GB | < 0.1 GB | [#24](#24-大型数据库优化) |
| `db_lock` | 未锁定 | 已锁定 | — | [#8](#8-数据库锁定) |
| `write_permissions` | 可写 | — | 拒绝 | [#22](#22-备份恢复问题) |
| `optional_deps` | 全部安装 | 缺失 | — | [#16](#16-加密解密错误), [#19](#19-tui-显示问题) |
| `fts5` | 支持 | — | 不支持 | [#6](#6-召回无结果) |
| `security` | 可用 | — | 不可用 | [#16](#16-加密解密错误), [#17](#17-路径验证错误) |
| `mcp_configs` | 已找到 | 未找到 | — | [#14](#14-mcp-集成不工作) |
| `memory_count` | > 0 | 0 | — | [#5](#5-记忆未存储) |
| `rules_engine` | 活跃 | 过期 | — | [#10](#10-规则未注入), [#11](#11-规则作用域冲突) |
| `auto_inject` | 已启用 | 未启用 | — | [#10](#10-规则未注入) |
| `cli_path` | 在 PATH 中 | 不在 PATH | — | [#1](#1-cli-命令未找到) |

---

## 错误信息索引

| 错误信息 | 问题编号 |
|---|---|
| `command not found: carrymem` | [#1](#1-cli-命令未找到) |
| `No module named 'memory_classification_engine'` | [#2](#2-导入错误) |
| `No module named 'carrymem'` | [#2](#2-导入错误) |
| `carrymem version 显示版本错误` | [#3](#3-版本不匹配) |
| `error: externally-managed-environment` | [#4](#4-pip-安装失败) |
| `should_remember: False` | [#5](#5-记忆未存储) |
| `recall_memories 返回空列表` | [#6](#6-召回无结果) |
| `sqlite3.OperationalError: database is locked` | [#8](#8-数据库锁定) |
| `database disk image is malformed` | [#9](#9-数据库损坏) |
| `No matching rules found` | [#10](#10-规则未注入) |
| `Scope conflict detected` | [#11](#11-规则作用域冲突) |
| `Skill signature mismatch` | [#12](#12-skill-验证失败) |
| `ValueError: Path traversal` | [#17](#17-路径验证错误) |
| `ValueError: Path escapes allowed directory` | [#17](#17-路径验证错误) |
| `HMAC verification failed` | [#16](#16-加密解密错误) |
| `ImportError: No module named 'cryptography'` | [#16](#16-加密解密错误) |
| `ImportError: No module named 'textual'` | [#19](#19-tui-显示问题) |
| `RuntimeError: Cannot be used across threads` | [#21](#21-异步-api-问题) |
| `Connection refused (MCP)` | [#14](#14-mcp-集成不工作) |
| `FTS5 module not found` | [#6](#6-召回无结果) |

---

## 安装与配置

### 1. CLI 命令未找到

**严重度**: 🟡 警告  
**doctor 检查项**: `cli_path`, `config_dir`

**问题**: `carrymem` 命令返回 "command not found"

**根因**: pip 将 `carrymem` 脚本安装到不在 PATH 中的 Python bin 目录。

**快速修复**（通用）:
```bash
python3 -m memory_classification_engine.cli version
```

**标准修复**:

**macOS** — 查找并添加 Python bin 到 PATH:
```bash
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"
# 然后将输出路径添加到 ~/.zshrc：
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
source ~/.zshrc
carrymem version
```

**Linux** — 添加用户 bin 到 PATH:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
carrymem version
```

**Windows (WSL2)**:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (原生 PowerShell)**:
```powershell
pip install carrymem
python -m memory_classification_engine.cli version
```

**深度修复** — 如果以上方法无效，使用 pipx 隔离安装:
```bash
pipx install carrymem
carrymem version
```

**验证**:
```bash
carrymem doctor
# cli_path 应显示: ok
```

---

### 2. 导入错误

**严重度**: 🔴 严重  
**doctor 检查项**: `carrymem_import`

**问题**: `ImportError: No module named 'memory_classification_engine'` 或 `No module named 'carrymem'`

**错误示例**:
```
ModuleNotFoundError: No module named 'memory_classification_engine'
```

**根因**: CarryMem 未安装在当前 Python 环境中。

**快速修复**:
```bash
pip install carrymem
```

**标准修复**:

1. 检查当前使用的 Python:
   ```bash
   which python3
   python3 --version
   ```

2. 为正确的 Python 安装:
   ```bash
   python3 -m pip install carrymem
   ```

3. 开发模式安装:
   ```bash
   cd /path/to/carrymem
   pip install -e .
   ```

4. 使用兼容导入路径:
   ```python
   from carrymem import CarryMem  # 与 from memory_classification_engine 等效
   ```

**深度修复** — 虚拟环境冲突:
```bash
# 确保虚拟环境已激活
source .venv/bin/activate  # 或 conda activate myenv
pip install carrymem

# 多个 Python 版本时，使用显式路径
/usr/bin/python3.11 -m pip install carrymem
```

**验证**:
```bash
python3 -c "from memory_classification_engine import CarryMem; print('OK')"
carrymem doctor
# carrymem_import 应显示: ok
```

---

### 3. 版本不匹配

**严重度**: 🟡 警告  
**doctor 检查项**: `carrymem_import`

**问题**: `carrymem version` 显示错误版本，或与 `pip show carrymem` 不一致

**根因**: 多个环境存在不同安装，或缓存版本过期。

**快速修复**:
```bash
pip install --force-reinstall carrymem
```

**标准修复**:

1. 检查所有已安装版本:
   ```bash
   pip show carrymem
   carrymem version
   python3 -c "from memory_classification_engine.__version__ import __version__; print(__version__)"
   ```

2. 版本不一致时清理:
   ```bash
   pip uninstall carrymem -y
   pip install carrymem
   ```

**深度修复** — 多个 Python 环境:
```bash
# 查找所有 carrymem 安装
find / -name "__version__.py" -path "*/memory_classification_engine/*" 2>/dev/null

# 删除旧版本并重新安装
pipx install --force carrymem
```

**验证**:
```bash
carrymem version
# 应显示: 0.1.5
```

---

### 4. pip 安装失败

**严重度**: 🔴 严重  
**doctor 检查项**: `python_version`, `carrymem_import`

**问题**: `pip install carrymem` 报错

**错误示例**:
```
error: externally-managed-environment
× This environment is externally managed
```

**根因**: 系统 Python 受保护（PEP 668）、依赖冲突或网络问题。

**快速修复**:
```bash
pip install --user carrymem
```

**标准修复**:

1. 外部管理环境错误（Ubuntu 23.04+, Fedora 38+）:
   ```bash
   # 方案 A: 使用 pipx（推荐）
   pipx install carrymem

   # 方案 B: 使用虚拟环境
   python3 -m venv ~/carrymem-env
   source ~/carrymem-env/bin/activate
   pip install carrymem
   ```

2. 依赖冲突:
   ```bash
   pip install carrymem --no-deps
   pip install click rich prompt-toolkit
   ```

3. 网络/代理问题:
   ```bash
   pip install carrymem --proxy http://proxy:port
   pip install carrymem -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

**深度修复** — Python 版本过低:
```bash
# CarryMem 需要 Python >= 3.9
python3 --version
# 如果 < 3.9，通过 pyenv 或系统包管理器安装更新版本
```

**验证**:
```bash
carrymem version
carrymem doctor
# python_version 和 carrymem_import 应显示: ok
```

---

## 核心记忆操作

### 5. 记忆未存储

**严重度**: 🟡 警告  
**doctor 检查项**: `memory_count`, `rules_engine`

**问题**: `classify_and_remember()` 返回 `should_remember: False`，或 `carrymem add` 未持久化

**根因**: 内容被分类为不值得记忆（太模糊、重复或重要性低）。

**快速修复**:
```bash
carrymem add "你的内容" --force
```

**标准修复**:

1. 检查内容是否满足最低要求（≥ 3 个字符，非重复）:
   ```bash
   carrymem add "我偏好所有编辑器使用深色模式" --type user_preference
   ```

2. 检查当前记忆数量:
   ```bash
   carrymem stats
   ```

3. 使用显式类型改善分类:
   ```bash
   carrymem add "你的内容" --type user_preference
   # 类型: user_preference, decision, correction, task_pattern, sentiment_marker, identity
   ```

**深度修复** — 分类逻辑调试:
```python
from memory_classification_engine import CarryMem
cm = CarryMem()
result = cm.classify_and_remember("你的内容")
print(result)
# 检查: memory_type, should_remember, importance_score, reason
cm.close()
```

**验证**:
```bash
carrymem stats
carrymem doctor
# memory_count 应显示: ok (> 0)
```

---

### 6. 召回无结果

**严重度**: 🟡 警告  
**doctor 检查项**: `fts5`, `memory_count`

**问题**: `recall_memories()` 或 `carrymem search` 返回空结果

**根因**: FTS5 不可用、无记忆存储或查询不匹配。

**快速修复**:
```bash
carrymem search "你的查询" --limit 10
```

**标准修复**:

1. 检查 FTS5 是否支持:
   ```bash
   carrymem doctor
   # fts5 应显示: ok
   ```

2. 检查记忆数量:
   ```bash
   carrymem stats
   # 如果为 0，先添加一些记忆
   carrymem add "测试记忆"
   ```

3. 尝试更宽泛的查询:
   ```bash
   carrymem search "模式"
   # 而非过于具体的查询如 "VS Code 中的深色模式偏好"
   ```

**深度修复** — FTS5 不可用:
```bash
# 检查 SQLite FTS5 支持
python3 -c "import sqlite3; print(sqlite3.sqlite_version); conn = sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(c)')"

# 如果 FTS5 不可用，重新编译 Python 启用 SQLite FTS5
# Ubuntu: sudo apt install python3-full
# macOS: brew install python@3.11
```

**验证**:
```bash
carrymem search "test"
carrymem doctor
# fts5 和 memory_count 应显示: ok
```

---

### 7. 记忆分类错误

**严重度**: 🔵 信息  
**doctor 检查项**: `rules_engine`

**问题**: 记忆被分为错误类型（如 decision 被分为 task_pattern）

**根因**: 规则引擎模式不匹配，或默认分类器误判。

**快速修复**:
```bash
carrymem add "你的内容" --type user_preference
```

**标准修复**:

1. 检查活跃规则:
   ```bash
   carrymem rules list
   ```

2. 为你的场景添加特定规则:
   ```bash
   carrymem rules add --trigger "我偏好" --action "分类为 user_preference"
   ```

3. 编辑已有规则:
   ```bash
   carrymem rules edit <rule-id>
   ```

**深度修复** — 分类优先级:
```python
from memory_classification_engine import CarryMem
cm = CarryMem()
result = cm.classify_and_remember("我总是用 vim 编辑")
print(f"类型: {result['memory_type']}, 原因: {result.get('reason', 'N/A')}")
cm.close()
```

**验证**:
```bash
carrymem rules check
carrymem doctor
# rules_engine 应显示: ok
```

---

### 8. 数据库锁定

**严重度**: 🔴 严重  
**doctor 检查项**: `db_lock`

**问题**: `sqlite3.OperationalError: database is locked`

**错误示例**:
```
sqlite3.OperationalError: database is locked
```

**根因**: 另一个进程正在使用数据库，或残留锁文件。

**快速修复**:
```bash
pkill -f memory_classification_engine
```

**标准修复**:

1. 关闭其他 CarryMem 实例:
   ```bash
   pkill -f memory_classification_engine
   ```

2. 删除残留 WAL/SHM 文件:
   ```bash
   rm -f ~/.carrymem/memories.db-shm ~/.carrymem/memories.db-wal
   ```

3. 运行诊断:
   ```bash
   carrymem doctor
   ```

**深度修复** — 持续锁定:

CarryMem 使用 SQLite WAL 模式支持并发读取。如果锁定持续:

1. 检查僵尸进程:
   ```bash
   lsof ~/.carrymem/memories.db
   ```

2. 强制检查点 WAL:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.carrymem/memories.db')
   conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   conn.close()
   "
   ```

3. 如果 MCP 服务器正在运行，重启它:
   ```bash
   carrymem serve  # 重启 MCP 服务器
   ```

**验证**:
```bash
carrymem doctor
# db_lock 应显示: ok
```

---

### 9. 数据库损坏

**严重度**: 🔴 严重  
**doctor 检查项**: `db_integrity`

**问题**: `database disk image is malformed` 或 `PRAGMA integrity_check` 失败

**错误示例**:
```
sqlite3.DatabaseError: database disk image is malformed
```

**根因**: 异常关机、磁盘满或硬件错误导致 SQLite 文件损坏。

**快速修复**:
```bash
carrymem doctor --fix
```

**标准修复**:

1. **先备份**:
   ```bash
   cp ~/.carrymem/memories.db ~/.carrymem/memories.db.bak
   ```

2. 运行完整性检查:
   ```bash
   carrymem doctor
   # db_integrity 将显示: fail
   ```

3. 尝试恢复:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.carrymem/memories.db')
   result = conn.execute('PRAGMA integrity_check').fetchone()
   print(f'完整性: {result[0]}')
   conn.close()
   "
   ```

**深度修复** — 完整数据库重建:
```bash
# 导出所有可恢复数据
carrymem export ~/carrymem_backup.json

# 删除损坏的数据库
rm ~/.carrymem/memories.db

# 重新初始化（carrymem doctor --fix 会重建）
carrymem doctor --fix

# 重新导入数据
carrymem import ~/carrymem_backup.json
```

**验证**:
```bash
carrymem doctor
# db_integrity 应显示: ok
```

---

## 规则引擎

### 10. 规则未注入

**严重度**: 🟡 警告  
**doctor 检查项**: `rules_engine`, `auto_inject`

**问题**: 规则存在但未注入到 AI 提示中

**根因**: 自动注入未启用，或没有规则匹配当前上下文。

**快速修复**:
```bash
export CARRYMEM_AUTO_INJECT=true
```

**标准修复**:

1. 检查规则状态:
   ```bash
   carrymem rules list
   carrymem rules check
   ```

2. 验证规则匹配:
   ```bash
   carrymem match-rules "你的场景描述"
   ```

3. 永久启用自动注入:
   ```bash
   echo 'export CARRYMEM_AUTO_INJECT=true' >> ~/.zshrc
   source ~/.zshrc
   ```

**深度修复** — 规则优先级和作用域:
```bash
# 检查规则是否暂停
carrymem rules list
# 查找 status: paused

# 恢复暂停的规则
carrymem rules resume <rule-id>

# 检查作用域优先级: company > negotiated > personal
carrymem rules stats
```

**验证**:
```bash
carrymem doctor
# rules_engine 应显示: ok
# auto_inject 应显示: ok (已启用)
```

---

### 11. 规则作用域冲突

**严重度**: 🔵 信息  
**doctor 检查项**: `rules_engine`

**问题**: 不同作用域（company/negotiated/personal）的规则相互冲突

**根因**: 作用域优先级为 company > negotiated > personal；高作用域规则可能覆盖个人规则。

**快速修复**:
```bash
carrymem rules list
# 查看每条规则的作用域
```

**标准修复**:

1. 按作用域查看规则:
   ```bash
   carrymem rules list
   # 每条规则显示其 scope 字段
   ```

2. 在适当作用域创建规则:
   ```bash
   carrymem add-rule --trigger "编码风格" --action "使用4空格缩进"
   ```

3. 检查冲突:
   ```bash
   carrymem rules check
   ```

**深度修复** — 理解作用域优先级:

| 作用域 | 优先级 | 适用场景 |
|--------|--------|----------|
| `company` | 最高 | 组织级标准 |
| `negotiated` | 中等 | 团队级协议 |
| `personal` | 最低 | 个人偏好 |

`company` 作用域的规则始终覆盖相同触发器的 `personal` 规则。

**验证**:
```bash
carrymem rules stats
carrymem doctor
# rules_engine 应显示: ok
```

---

### 12. Skill 验证失败

**严重度**: 🟡 警告  
**doctor 检查项**: `security`

**问题**: `skill-verify` 返回签名不匹配

**错误示例**:
```
Skill signature mismatch: expected abc123..., got def456...
```

**根因**: Skill 文件在签名后被修改，或 SHA-256 哈希不匹配。

**快速修复**:
```bash
carrymem skill-verify <skill文件>
# 查看输出详情
```

**标准修复**:

1. 验证 skill 文件未被篡改:
   ```bash
   carrymem skill-verify <skill文件>
   ```

2. 如果你是 skill 创建者，重新打包:
   ```bash
   carrymem skill-pack my-skill.json --name "my-skill"
   ```

3. 检查版本兼容性:
   ```bash
   carrymem version
   # 确保打包方和验证方使用相同版本
   ```

**深度修复** — 手动完整性检查:
```bash
sha256sum <skill文件>
# 与 skill JSON 中嵌入的签名比较
```

**验证**:
```bash
carrymem skill-verify <skill文件>
# 应显示: valid
```

---

### 13. 规则建议质量差

**严重度**: 🔵 信息  
**doctor 检查项**: `rules_engine`

**问题**: `suggest-rules` 产生低质量或不相关的建议

**根因**: 检测到的记忆模式不足，或 `--min-count` 阈值过低。

**快速修复**:
```bash
carrymem suggest-rules --min-count 5
```

**标准修复**:

1. 提高最低出现次数阈值:
   ```bash
   carrymem suggest-rules --min-count 5
   ```

2. 按记忆类型过滤:
   ```bash
   carrymem suggest-rules --type user_preference
   carrymem suggest-rules --type correction
   ```

3. 审核并选择性接受:
   ```bash
   carrymem suggest-rules
   # 审核每条建议，然后:
   carrymem suggest-rules --accept  # 接受全部
   ```

**深度修复** — 改善建议质量:

建议从重复的记忆模式生成。改善方法：
- 添加更详细的记忆（不要只写"我喜欢 X"）
- 添加记忆时使用显式 `--type`
- 运行建议前确保至少有 3-5 条相似记忆

**验证**:
```bash
carrymem suggest-rules --min-count 5
# 应显示相关建议
```

---

## MCP 集成

### 14. MCP 集成不工作

**严重度**: 🟡 警告  
**doctor 检查项**: `mcp_configs`

**问题**: AI 工具（Cursor、Claude Code）看不到 CarryMem 工具

**根因**: MCP 配置文件缺失或不正确。

**快速修复**:
```bash
carrymem setup-mcp --tool cursor
# 或
carrymem setup-mcp --tool claude-code
```

**标准修复**:

1. 为你的工具运行配置:
   ```bash
   carrymem setup-mcp --tool cursor
   carrymem setup-mcp --tool claude-code
   ```

2. 配置后重启 AI 工具

3. 验证 MCP 配置文件存在:
   ```bash
   # Cursor
   cat .cursor/mcp.json
   # Claude Code
   cat .claude/mcp.json
   ```

4. 验证配置内容:
   ```json
   {
     "mcpServers": {
       "carrymem": {
         "command": "python3",
         "args": ["-m", "memory_classification_engine.integration.layer2_mcp"]
       }
     }
   }
   ```

**深度修复** — 手动创建 MCP 配置:

如果 `setup-mcp` 不工作，手动创建:

```bash
# Cursor
mkdir -p .cursor
cat > .cursor/mcp.json << 'EOF'
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "memory_classification_engine.integration.layer2_mcp"]
    }
  }
}
EOF

# Claude Code
mkdir -p .claude
cat > .claude/mcp.json << 'EOF'
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "memory_classification_engine.integration.layer2_mcp"]
    }
  }
}
EOF
```

**验证**:
```bash
carrymem doctor
# mcp_configs 应显示: ok (已找到)
```

---

### 15. MCP 工具超时

**严重度**: 🟡 警告  
**doctor 检查项**: `mcp_configs`

**问题**: MCP 工具调用超时或无响应

**根因**: MCP 服务器进程未运行，或 Python 导入耗时过长。

**快速修复**:
```bash
# 重启 AI 工具（它会启动新的 MCP 服务器进程）
```

**标准修复**:

1. 手动测试 MCP 服务器:
   ```bash
   python3 -m memory_classification_engine.integration.layer2_mcp
   # 应正常启动无报错
   ```

2. 检查进程是否运行:
   ```bash
   ps aux | grep layer2_mcp
   ```

3. 检查导入错误:
   ```bash
   python3 -c "from memory_classification_engine.integration.layer2_mcp import mcp; print('OK')"
   ```

**深度修复** — 首次导入缓慢:

首次 MCP 调用可能因 Python 模块加载而缓慢。预热方法:
```bash
# 添加到 shell 启动脚本
python3 -c "from memory_classification_engine import CarryMem" &
```

**验证**:
```bash
carrymem doctor
# mcp_configs 应显示: ok
```

---

## 安全与加密

### 16. 加密/解密错误

**严重度**: 🔴 严重  
**doctor 检查项**: `security`, `optional_deps`

**问题**: 加密或解密失败，或 HMAC 验证失败

**错误示例**:
```
ImportError: No module named 'cryptography'
HMAC verification failed
```

**根因**: `cryptography` 包未安装，或加密数据被篡改。

**快速修复**:
```bash
pip install cryptography
```

**标准修复**:

1. 安装 cryptography 包:
   ```bash
   pip install cryptography
   ```

2. 检查安全模块可用性:
   ```bash
   carrymem doctor
   # security 应显示: ok
   # optional_deps 应列出 cryptography 为已安装
   ```

3. 如果 HMAC 验证失败，数据可能被篡改:
   ```bash
   carrymem doctor
   # db_integrity 应显示: ok
   ```

**深度修复** — 密钥变更后重新加密:

如果更换了加密密钥，旧数据无法用新密钥解密:
```bash
# 先导出未加密数据（如果仍可访问）
carrymem export backup.json

# 重新初始化
rm ~/.carrymem/memories.db
carrymem doctor --fix

# 重新导入
carrymem import backup.json
```

**验证**:
```bash
carrymem doctor
# security 和 optional_deps 应显示: ok
```

---

### 17. 路径验证错误

**严重度**: 🟡 警告  
**doctor 检查项**: `security`

**问题**: `ValueError: Path traversal` 或 `ValueError: Path escapes allowed directory`

**错误示例**:
```
ValueError: Path traversal: system directory not allowed: /etc/passwd
```

**根因**: 指定路径解析到 CarryMem 出于安全考虑而阻止的系统目录。

**快速修复**:
```bash
# 使用主目录内的路径
carrymem export ~/my_export.json
```

**标准修复**:

1. 使用安全的输出路径:
   ```bash
   carrymem export ~/carrymem_backup.json
   carrymem import ~/carrymem_backup.json
   ```

2. 如需导出到特定目录，确保在主目录内:
   ```bash
   mkdir -p ~/backups
   carrymem export ~/backups/memories.json
   ```

3. 被阻止的系统目录: `/etc`, `/usr`, `/bin`, `/sbin`, `/System`, `/Library`, `/private/etc`

**深度修复** — allowed_base 参数:

使用 Python API 时，可以指定 `allowed_base`:
```python
from memory_classification_engine import CarryMem
cm = CarryMem()
cm.export_memories(output_path="/data/exports/backup.json")
# 如果 /data/exports 不是系统目录则可以工作
cm.close()
```

**验证**:
```bash
carrymem export ~/test_export.json && echo "OK" && rm ~/test_export.json
```

---

## 高级功能

### 18. Obsidian 适配器问题

**严重度**: 🔵 信息  
**doctor 检查项**: `config_dir`

**问题**: Obsidian vault 连接或同步失败

**根因**: Vault 路径未配置，或文件权限阻止读写。

**快速修复**:
```bash
carrymem doctor
# 检查 config_dir 状态
```

**标准修复**:

1. 验证 vault 路径存在:
   ```bash
   ls -la /path/to/your/obsidian/vault
   ```

2. 检查文件权限:
   ```bash
   chmod u+rw /path/to/your/obsidian/vault
   ```

3. 重新配置适配器:
   ```python
   from memory_classification_engine import CarryMem
   cm = CarryMem(storage_adapter="obsidian", vault_path="/path/to/vault")
   cm.close()
   ```

**验证**:
```bash
carrymem doctor
# config_dir 应显示: ok
```

---

### 19. TUI 显示问题

**严重度**: 🔵 信息  
**doctor 检查项**: `optional_deps`

**问题**: `carrymem tui` 显示异常或崩溃

**错误示例**:
```
ImportError: No module named 'textual'
```

**根因**: `textual` 包未安装，或终端不支持富文本输出。

**快速修复**:
```bash
pip install textual
```

**标准修复**:

1. 安装 textual:
   ```bash
   pip install textual
   ```

2. 检查终端兼容性:
   ```bash
   echo $TERM
   echo $COLORTERM
   # 应显示: xterm-256color 和 truecolor（或 24bit）
   ```

3. 使用显式终端设置:
   ```bash
   TERM=xterm-256color carrymem tui
   ```

**深度修复** — 终端不支持:

如果终端不支持富文本输出:
```bash
# 使用 CLI 命令代替 TUI
carrymem list
carrymem search "查询"
carrymem rules list
```

**验证**:
```bash
carrymem doctor
# optional_deps 应显示 textual 为已安装
```

---

### 20. VS Code 扩展问题

**严重度**: 🔵 信息  
**doctor 检查项**: `carrymem_import`, `cli_path`

**问题**: VS Code 扩展无法连接 CarryMem

**根因**: 扩展找不到 CarryMem Python 模块或 CLI。

**快速修复**:
```bash
carrymem doctor
# 确保 carrymem_import 和 cli_path 都显示: ok
```

**标准修复**:

1. 验证 VS Code 终端可访问 CarryMem:
   ```bash
   carrymem version
   ```

2. 检查扩展的 Python 路径设置:
   - 打开 VS Code 设置
   - 搜索 "carrymem"
   - 确保 Python 路径指向安装了 CarryMem 的环境

3. 重装扩展:
   ```bash
   code --install-extension vscode-carrymem-0.1.5.vsix
   ```

**深度修复** — VS Code 中的 Python 路径:

如果 VS Code 使用的 Python 与终端不同:
```bash
# 找到安装了 CarryMem 的 Python
which python3
python3 -c "import memory_classification_engine; print(memory_classification_engine.__file__)"

# 配置 VS Code 使用此 Python
# 命令面板 → Python: Select Interpreter → 选择正确的解释器
```

**验证**:
```bash
carrymem doctor
# carrymem_import 和 cli_path 应显示: ok
```

---

### 21. 异步 API 问题

**严重度**: 🔵 信息  
**doctor 检查项**: `carrymem_import`

**问题**: 异步 API 调用失败，出现 `RuntimeError` 或事件循环错误

**错误示例**:
```
RuntimeError: Cannot be used across threads
RuntimeError: Event loop is closed
```

**根因**: CarryMem 的 SQLite 连接不是线程安全的；异步调用必须使用同一事件循环。

**快速修复**:
```python
import asyncio
from memory_classification_engine import CarryMem

async def main():
    cm = CarryMem()
    result = await cm.classify_and_remember_async("内容")
    print(result)
    cm.close()

asyncio.run(main())
```

**标准修复**:

1. 确保所有异步调用在同一事件循环内:
   ```python
   # 正确
   async def app():
       cm = CarryMem()
       result = await cm.classify_and_remember_async("内容")
       cm.close()

   # 错误 — 不要在事件循环外创建 CarryMem
   cm = CarryMem()  # 这创建了同步连接
   result = await cm.classify_and_remember_async("内容")  # 可能失败
   ```

2. 不要跨线程共享 CarryMem 实例:
   ```python
   # 每个线程应创建自己的实例
   def worker():
       cm = CarryMem()
       result = cm.classify_and_remember("内容")
       cm.close()
   ```

**验证**:
```python
python3 -c "
import asyncio
from memory_classification_engine import CarryMem
async def test():
    cm = CarryMem()
    print('异步 API 可用:', hasattr(cm, 'classify_and_remember_async'))
    cm.close()
asyncio.run(test())
"
```

---

### 22. 备份/恢复问题

**严重度**: 🟡 警告  
**doctor 检查项**: `db_permissions`, `write_permissions`, `disk_space`

**问题**: `carrymem export` 或 `carrymem import` 失败

**根因**: 权限不足、磁盘满或文件格式无效。

**快速修复**:
```bash
carrymem export ~/backup.json
```

**标准修复**:

1. 检查写入权限:
   ```bash
   carrymem doctor
   # write_permissions 和 db_permissions 应显示: ok
   ```

2. 检查磁盘空间:
   ```bash
   carrymem doctor
   # disk_space 应显示: ok
   ```

3. 导入时使用正确的合并策略:
   ```bash
   # 跳过已有记忆（默认）
   carrymem import ~/backup.json --merge skip_existing

   # 覆盖已有记忆
   carrymem import ~/backup.json --merge overwrite
   ```

**深度修复** — 部分导入恢复:

如果导入部分失败:
```bash
# 检查 JSON 文件完整性
python3 -c "
import json
with open('$HOME/backup.json') as f:
    data = json.load(f)
print(f'记忆数: {len(data.get(\"memories\", []))}')
print(f'规则数: {len(data.get(\"rules\", []))}')
"

# 带详细输出导入
carrymem import ~/backup.json 2>&1 | tee import.log
```

**验证**:
```bash
carrymem stats
carrymem doctor
# 所有检查应显示: ok
```

---

## 性能

### 23. 召回或规则匹配缓慢

**严重度**: 🟡 警告  
**doctor 检查项**: `database_file`, `disk_space`

**问题**: 记忆召回或规则匹配明显缓慢

**根因**: 数据库增大、过期记忆积累或 FTS 索引过期。

**快速修复**:
```bash
carrymem clean --expired --force
```

**标准修复**:

1. 清理过期记忆:
   ```bash
   carrymem clean --expired --dry-run  # 先预览
   carrymem clean --expired --force
   ```

2. 检查数据库大小:
   ```bash
   carrymem doctor
   # database_file 显示大小
   ```

3. 运行优化:
   ```python
   from memory_classification_engine import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   ```

**深度修复** — 手动 VACUUM 和索引重建:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.carrymem/memories.db')
conn.execute('VACUUM')
print('VACUUM 完成')
conn.close()
"
```

**验证**:
```bash
carrymem search "test" --limit 5
# 应快速返回结果（< 1 秒）
```

---

### 24. 大型数据库优化

**严重度**: 🔵 信息  
**doctor 检查项**: `database_file`, `disk_space`

**问题**: 数据库超过 100 MB，操作持续缓慢

**根因**: 大量记忆和规则缺乏定期维护。

**快速修复**:
```bash
carrymem clean --expired --force
carrymem clean --quality 0.3 --force
```

**标准修复**:

1. 检查数据库大小和记忆数量:
   ```bash
   carrymem doctor
   carrymem stats
   ```

2. 清理低质量和过期记忆:
   ```bash
   carrymem clean --expired --dry-run
   carrymem clean --quality 0.3 --dry-run
   carrymem clean --expired --quality 0.3 --force
   ```

3. VACUUM 数据库:
   ```python
   from memory_classification_engine import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   ```

**深度修复** — 归档旧数据:

对于非常大的数据库，考虑归档:
```bash
# 导出旧记忆
carrymem export ~/archive_$(date +%Y%m%d).json

# 然后从活跃数据库中清理
carrymem clean --expired --force
```

**验证**:
```bash
ls -lh ~/.carrymem/memories.db
# 清理后应明显缩小
```

---

## 升级与迁移

### 25. 升级破坏性变更

**严重度**: 🔵 信息  
**doctor 检查项**: `carrymem_import`

**问题**: 升级 CarryMem 后，已有代码或 CLI 命令行为不同

**根因**: 版本间的 API 或 CLI 变更。

**快速修复**:
```bash
# 查看更新日志
pip show carrymem
# 访问: https://github.com/lulin70/carrymem/blob/main/CHANGELOG.md
```

**标准修复**:

1. 检查当前版本:
   ```bash
   carrymem version
   ```

2. 查看 CHANGELOG 中的破坏性变更:
   ```bash
   # 参见: 仓库根目录的 CHANGELOG.md
   ```

3. 使用兼容的导入路径:
   ```python
   # v0.1.5+ 两种均可
   from memory_classification_engine import CarryMem
   from carrymem import CarryMem
   ```

4. 使用 `carrymem rules` 中心命令代替单独命令:
   ```bash
   # 新方式（推荐）
   carrymem rules list
   carrymem rules add --trigger "..." --action "..."
   carrymem rules match "场景"

   # 旧方式（仍可用但已弃用）
   carrymem list-rules
   carrymem add-rule --trigger "..." --action "..."
   carrymem match-rules "场景"
   ```

**深度修复** — API 稳定性参考:

参见 [API_STABILITY.md](../API_STABILITY.md) 获取稳定、实验性和已弃用 API 的完整列表。

**验证**:
```bash
carrymem doctor
# 所有检查应显示: ok
```

---

## 获取帮助

- **诊断**: `carrymem doctor` — 遇到任何问题先运行此命令
- **GitHub Issues**: https://github.com/lulin70/carrymem/issues
- **文档**: https://github.com/lulin70/carrymem
- **更新日志**: [CHANGELOG.md](../../CHANGELOG.md)
- **API 稳定性**: [API_STABILITY.md](../API_STABILITY.md)
