# CarryMem API 稳定性保证

**版本**: v0.2.1  
**生效**: v0.1.6+

---

## 稳定性级别

CarryMem 定义了三个稳定性级别：

| 级别 | 保证 | 变更通知 |
|------|------|---------|
| **Stable** | 无破坏性变更。如需废弃，至少1个版本的迁移期 | CHANGELOG + DeprecationWarning |
| **Experimental** | 可能在次版本内变更 | 仅 CHANGELOG |
| **Internal** | 随时可能变更。不建议外部使用 | 无通知 |

---

## 1. Stable API (v0.1.x 保证)

以下公开接口是 **Stable** 的，在 v0.1.x 系列内不会有破坏性变更：

```python
CarryMem(db_path, namespace, storage_adapter, vault_path)
CarryMem.classify_and_remember(content, source, metadata) -> Dict
CarryMem.recall_memories(query, limit, memory_type) -> List[Dict]
CarryMem.declare(content, memory_type, confidence, source) -> Dict
CarryMem.forget_memory(memory_id) -> bool
CarryMem.get_memory_profile() -> Dict
CarryMem.export_memories(output_path, format) -> Dict
CarryMem.import_memories(input_path, merge_strategy) -> Dict
CarryMem.close()

CarryMem.add_rule(trigger, action, rule_type, scope, priority) -> Dict
CarryMem.match_rules(scene, limit) -> List[Dict]
CarryMem.list_rules(status, rule_type, scope) -> List[Dict]
CarryMem.delete_rule(rule_id) -> bool
CarryMem.suggest_rules(min_count) -> List[Dict]
CarryMem.skill_pack(name, version, scope) -> Dict
CarryMem.skill_verify(data) -> Dict
CarryMem.skill_install(data, scope_override, mode) -> Dict

CarryMem.review_incoming_rules(incoming, target_scope) -> Dict
CarryMem.accept_rules(incoming, strategy, target_scope) -> Dict
```

### Stable - CLI 命令

```bash
carrymem add|remember|save
carrymem list|ls
carrymem search|find
carrymem show|get
carrymem edit|update
carrymem forget|delete|rm
carrymem clean
carrymem export
carrymem import
carrymem stats|status
carrymem check
carrymem whoami
carrymem profile
carrymem doctor
carrymem setup-mcp|init-integration
carrymem tui
carrymem serve
carrymem init
carrymem tutorial
carrymem version|--version|-v
carrymem rules [list|add|delete|match|edit|pause|resume|stats|check|export|import|suggest]
carrymem match-rules
carrymem suggest-rules
```

### Stable - 数据格式

- 记忆 JSON 格式（导出/导入）
- 规则 JSON 格式
- Skill 格式（SHA-256 签名）
- MCP 配置格式

---

## 2. Experimental API

以下接口是 **Experimental** 的，可能在次版本更新中变更：

```python
CarryMem.classify_and_remember_async(content) -> Dict
CarryMem.recall_memories_async(query) -> List[Dict]

CarryMem.build_system_prompt(context, format) -> str
CarryMem.optimize() -> Dict

CarryMem.promote_rules(min_trigger_count) -> List[Dict]
CarryMem.review_promotions() -> List[Dict]
CarryMem.learn_experience(content, memory_type) -> Dict
CarryMem.review_lessons() -> List[Dict]
CarryMem.refine_rule(rule_id, feedback) -> Dict
```

# Experimental - Skill 格式
CarryMem.skill_pack(name, version="1.0.0", scope="personal", ...) -> Dict
CarryMem.skill_verify(data) -> Dict
CarryMem.skill_install(data, scope_override=None, mode="skip") -> Dict

# Experimental - 合并协议
CarryMem.review_incoming_rules(incoming, target_scope=None) -> Dict
CarryMem.accept_rules(incoming, strategy="negotiate", target_scope=None) -> Dict
MergeStrategy / MergeDecision / MergeConflict / MergeResult

# Experimental - 规则作用域类型
RuleScope / VALID_RULE_SCOPES / SCOPE_PRIORITY

---

## 3. Internal API

以下是内部实现细节，**随时可能变更**。不建议在外部代码中使用：

```python
carrymem.classification.pattern_analyzer.*
carrymem.classification.semantic_classifier.*
carrymem.storage.sqlite_adapter.*
carrymem.rules.storage.*
carrymem.security.validator.*
```

---

## 版本管理策略

- **补丁版本** (0.1.x → 0.2.1): Bug 修复、新功能（Stable API 不变）
- **次版本** (0.1.x → 0.2.1): 新功能、Experimental→Stable 升级可能
- **主版本** (0.x → 1.0.0): 可能有破坏性变更

### 废弃流程

1. 在 API 上添加 `DeprecationWarning`
2. 在 CHANGELOG 中记录迁移指南
3. 至少保留1个次版本的旧 API
4. 在下一个主版本中删除

---

## 兼容性

### Python 版本

| Python 版本 | 支持状态 |
|------------|---------|
| 3.9 | ✅ 支持 |
| 3.10 | ✅ 支持 |
| 3.11 | ✅ 支持（推荐） |
| 3.12 | ✅ 支持 |
| 3.8 及更早 | ❌ 不支持 |

### 导入路径

v0.1.6 起支持以下两种导入路径：

```python
from carrymem import CarryMem  # 官方包名
from carrymem import CarryMem                       # 兼容别名
```

两者行为完全一致。将在 v1.0.0 统一。

---

## 变更历史

- **v0.1.6**: 版本重置 — 安全加固、线程安全、文档整理
- 早期开发使用了 0.4.x-0.8.x 版本号，后统一为 0.2.x 系列。当前 v0.2.1 包含了 v0.1.6 版本重置的安全加固和质量改进，以及后续功能增强。
