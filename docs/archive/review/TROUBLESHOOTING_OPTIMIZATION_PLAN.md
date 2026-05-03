# CarryMem TROUBLESHOOTING.md 优化方案

> **版本**: v0.1.5  
> **日期**: 2026-05-03  
> **状态**: 待评审

---

## 一、现状分析

### 1.1 当前覆盖情况

| # | 问题条目 | 对应功能模块 | 覆盖深度 |
|---|---------|-------------|---------|
| 1 | CLI Command Not Found | 安装/PATH | ★★★★ |
| 2 | Import Error | 安装/导入 | ★★★ |
| 3 | Database Locked | 存储/并发 | ★★☆ |
| 4 | Version Mismatch | 版本管理 | ★★☆ |
| 5 | MCP Integration Not Working | MCP集成 | ★★★ |
| 6 | Memory Not Stored | 核心分类 | ★★☆ |
| 7 | Rules Not Injected | 规则引擎 | ★★☆ |
| 8 | Performance Issues | 性能 | ★☆☆ |

**总计**: 8 个问题条目，覆盖 5/12 功能模块（41.7%）

### 1.2 关键差距

| 差距类别 | 具体问题 | 影响 |
|---------|---------|------|
| **功能覆盖** | 缺少加密/解密、Obsidian适配器、TUI、VS Code扩展、Skill格式、合并协议、异步API、备份恢复等模块的故障排查 | 用户遇到这些模块问题时无文档可查 |
| **诊断参考** | `carrymem doctor` 检查17项，但文档未引用doctor输出与问题条目的映射 | 用户拿到doctor输出后仍需自行判断 |
| **错误信息索引** | 无错误消息→排查条目的快速映射 | 用户只能逐条翻阅 |
| **i18n** | 无中文版、无日文版 | 中文/日文用户无母语排查指南 |
| **结构** | 无目录、无严重度分级、无升级指引 | 查找效率低，无法快速判断紧急程度 |
| **CLI命令** | 文档中部分命令名与实际不一致（如 `list-rules` vs `rules list`） | 用户执行命令报错 |
| **版本信息** | 无版本特定说明（升级路径、breaking changes） | 升级后问题无法排查 |

---

## 二、优化目标

1. **功能覆盖率**: 8/12 → 12/12 模块（100%）
2. **问题条目数**: 8 → 20+ 条目
3. **诊断闭环**: 每条问题关联 `carrymem doctor` 检查项
4. **i18n覆盖**: 新增 CN/JP 版本
5. **结构化**: 目录 + 严重度分级 + 错误信息索引

---

## 三、优化方案

### 3.1 结构重组

**新文档结构**:

```
# CarryMem Troubleshooting Guide

## Quick Diagnostic（新增）
  → carrymem doctor 一键诊断 + 输出解读表

## Error Message Index（新增）
  → 常见错误消息 → 条目编号 快速映射表

## Installation & Setup
  1. CLI Command Not Found          [已有-优化]
  2. Import Error                   [已有-优化]
  3. Version Mismatch               [已有-优化]
  4. pip Install Fails              [新增]

## Core Memory Operations
  5. Memory Not Stored              [已有-优化]
  6. Recall Returns No Results      [新增]
  7. Memory Classification Wrong    [新增]
  8. Database Locked                [已有-优化]
  9. Database Corruption            [新增]

## Rule Engine
  10. Rules Not Injected            [已有-优化]
  11. Rule Scope Conflicts          [新增]
  12. Skill Verification Failed     [新增]
  13. Rule Suggestion Quality       [新增]

## MCP Integration
  14. MCP Integration Not Working   [已有-优化]
  15. MCP Tool Timeout              [新增]

## Security & Encryption
  16. Encryption/Decryption Error   [新增]
  17. Path Validation Error         [新增]

## Advanced Features
  18. Obsidian Adapter Issues       [新增]
  19. TUI Display Issues            [新增]
  20. VS Code Extension Issues      [新增]
  21. Async API Issues              [新增]
  22. Backup/Restore Issues         [新增]

## Performance
  23. Slow Recall/Match             [已有-优化]
  24. Large Database Optimization   [新增]

## Upgrade & Migration
  25. Upgrade Breaking Changes      [新增]

## Getting Help
```

### 3.2 条目格式标准化

每个条目统一为以下格式：

```markdown
## #N. 问题标题

**严重度**: 🔴 Critical / 🟡 Warning / 🔵 Info  
**doctor检查项**: `check_item_name`  
**影响版本**: v0.1.5+

**问题**: 一句话描述

**错误示例**:
\```
实际错误输出
\```

**根因**: 技术原因说明

**解决方案**:

1. **快速修复**（1分钟内）
2. **标准修复**（完整步骤）
3. **深度排查**（如果上述无效）

**验证**:
\```bash
carrymem doctor  # 应显示 check_item_name: ok
\```

**相关命令**: `carrymem xxx`
```

### 3.3 新增条目详细设计

#### #4 pip Install Fails
- **场景**: pip install carrymem 报错（网络/权限/依赖冲突）
- **doctor项**: carrymem_import
- **方案**: 检查Python版本、pip版本、网络代理、--user安装

#### #5 Recall Returns No Results
- **场景**: recall_memories() 返回空列表
- **doctor项**: fts5, memory_count
- **方案**: 检查FTS5支持、记忆数量、查询语法、语义扩展器状态

#### #6 Memory Classification Wrong
- **场景**: 记忆被分为错误类型
- **doctor项**: rules_engine
- **方案**: 检查规则优先级、显式指定--type、查看分类日志

#### #8 Database Corruption
- **场景**: PRAGMA integrity_check 失败
- **doctor项**: db_integrity
- **方案**: 备份→修复→重建索引

#### #10 Rule Scope Conflicts
- **场景**: company/negotiated/personal 规则冲突
- **doctor项**: rules_engine
- **方案**: 检查scope优先级、使用rules check、显式指定scope

#### #11 Skill Verification Failed
- **场景**: skill_verify 返回签名不匹配
- **doctor项**: security
- **方案**: 检查SHA-256签名、文件完整性、版本兼容性

#### #12 Rule Suggestion Quality
- **场景**: suggest-rules 建议质量差
- **doctor项**: rules_engine
- **方案**: 增加输入内容详细度、使用--force、手动编辑规则

#### #14 MCP Tool Timeout
- **场景**: MCP工具调用超时
- **doctor项**: mcp_configs
- **方案**: 检查进程状态、端口占用、重启AI工具

#### #15 Encryption/Decryption Error
- **场景**: 加密/解密失败
- **doctor项**: security, optional_deps
- **方案**: 检查cryptography包、密钥文件、HMAC状态

#### #16 Path Validation Error
- **场景**: ValueError: Path traversal / Path escapes
- **doctor项**: security
- **方案**: 检查路径是否在允许目录内、使用--output指定安全路径

#### #17 Obsidian Adapter Issues
- **场景**: Obsidian vault 连接/同步失败
- **doctor项**: config_dir
- **方案**: 检查vault路径、文件权限、适配器配置

#### #18 TUI Display Issues
- **场景**: textual TUI 显示异常
- **doctor项**: optional_deps
- **方案**: 检查textual版本、终端兼容性、COLORTERM

#### #19 VS Code Extension Issues
- **场景**: 扩展无法连接CarryMem
- **doctor项**: carrymem_import, cli_path
- **方案**: 检查扩展配置、Python路径、重装扩展

#### #20 Async API Issues
- **场景**: async classify_and_remember 报错
- **doctor项**: carrymem_import
- **方案**: 检查事件循环、await使用、线程安全

#### #21 Backup/Restore Issues
- **场景**: export/import 失败
- **doctor项**: db_permissions, write_permissions
- **方案**: 检查路径权限、磁盘空间、文件格式

#### #23 Large Database Optimization
- **场景**: 数据库>100MB，操作缓慢
- **doctor项**: database_file, disk_space
- **方案**: VACUUM、批量清理、重建FTS索引

#### #24 Upgrade Breaking Changes
- **场景**: 升级后API/CLI行为变化
- **doctor项**: carrymem_import
- **方案**: 查阅CHANGELOG、API_STABILITY.md、使用兼容导入

### 3.4 Quick Diagnostic 新增章节

```markdown
## Quick Diagnostic

Run `carrymem doctor` for a full health check. Here's how to read the output:

| Doctor Check | ok | warn | fail | Related Issue |
|-------------|-----|------|------|--------------|
| python_version | ≥3.9 | - | <3.9 | #4 |
| carrymem_import | importable | - | ImportError | #2 |
| config_dir | exists | missing | - | #1 |
| database_file | exists | missing | - | #5 |
| db_integrity | passed | - | FAILED | #8 |
| db_permissions | writable | - | read-only | #21 |
| disk_space | >1GB | <1GB | <0.1GB | #23 |
| db_lock | unlocked | locked | - | #7 |
| write_permissions | writable | - | denied | #21 |
| optional_deps | all installed | missing | - | #15,#18 |
| fts5 | supported | - | not supported | #5 |
| security | available | - | unavailable | #15,#16 |
| mcp_configs | found | not found | - | #13,#14 |
| memory_count | >0 | 0 | - | #5 |
| rules_engine | active | stale | - | #9,#10 |
| auto_inject | enabled | disabled | - | #9 |
| cli_path | on PATH | not on PATH | - | #1 |

Use `carrymem doctor --fix` to auto-repair where possible.
Use `carrymem doctor --json` for structured output.
```

### 3.5 Error Message Index 新增章节

```markdown
## Error Message Index

| Error Message | Issue # |
|--------------|---------|
| `command not found: carrymem` | #1 |
| `No module named 'memory_classification_engine'` | #2 |
| `sqlite3.OperationalError: database is locked` | #7 |
| `database disk image is malformed` | #8 |
| `ValueError: Path traversal` | #16 |
| `ValueError: Path escapes allowed directory` | #16 |
| `should_remember: False` | #5 |
| `HMAC verification failed` | #15 |
| `Skill signature mismatch` | #11 |
| `FTS5 module not found` | #6 |
| `RuntimeError: Cannot be used across threads` | #20 |
| `No matching rules found` | #9 |
| `Scope conflict detected` | #10 |
| `Connection refused (MCP)` | #13 |
| `ImportError: No module named 'cryptography'` | #15 |
| `ImportError: No module named 'textual'` | #18 |
```

### 3.6 现有条目优化

| # | 条目 | 优化内容 |
|---|------|---------|
| 1 | CLI Command Not Found | 添加严重度标签、doctor关联、Windows原生(非WSL)指引 |
| 2 | Import Error | 添加虚拟环境场景、Python多版本冲突场景 |
| 3 | Database Locked | 添加WAL模式说明、连接池排查、超时配置 |
| 4 | Version Mismatch | 添加多环境隔离说明、pipx场景 |
| 5 | MCP Integration | 添加具体工具名映射、JSON配置示例、端口排查 |
| 6 | Memory Not Stored | 添加分类策略说明、最小内容要求、调试日志 |
| 7 | Rules Not Injected | 添加scope优先级说明、环境变量完整列表 |
| 8 | Performance | 添加VACUUM操作、FTS重建、批量操作建议 |

### 3.7 i18n 计划

| 文档 | 优先级 | 理由 |
|------|--------|------|
| TROUBLESHOOTING-CN.md | P0 | 中文用户群最大，语义召回支持中文 |
| TROUBLESHOOTING-JP.md | P1 | 日文用户群次之，语义召回支持日文 |

翻译策略：英文版为主版本，CN/JP 同步翻译，条目编号一致便于跨语言引用。

---

## 四、实施计划

| 阶段 | 任务 | 交付物 |
|------|------|--------|
| **Phase 1** | 重构英文版结构 + 新增12个条目 | TROUBLESHOOTING.md v2 |
| **Phase 2** | 翻译中文版 | TROUBLESHOOTING-CN.md |
| **Phase 3** | 翻译日文版 | TROUBLESHOOTING-JP.md |
| **Phase 4** | 更新 docs/README.md 索引 | docs/README.md |
| **Phase 5** | 回归测试 + Git推送 | commit |

---

## 五、验收标准

1. ✅ 功能覆盖率 100%（12/12 模块）
2. ✅ 问题条目 ≥ 20
3. ✅ 每条目包含：严重度、doctor关联、错误示例、3级方案、验证步骤
4. ✅ Quick Diagnostic 章节包含 doctor 输出解读表
5. ✅ Error Message Index 包含 ≥ 15 条常见错误映射
6. ✅ CN/JP 版本同步完成
7. ✅ 所有 CLI 命令名与实际代码一致
8. ✅ 回归测试通过
