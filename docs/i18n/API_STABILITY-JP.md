# CarryMem API 安定性保証

**バージョン**: v0.2.0  
**発効**: v0.1.6+

---

## 安定性レベル

CarryMemは3つの安定性レベルを定義しています：

| レベル | 保証 | 変更時の通知 |
|--------|------|-------------|
| **Stable** | 破壊的変更なし。非推奨の場合、最低1バージョンの移行期間 | CHANGELOG + DeprecationWarning |
| **Experimental** | マイナーバージョン内で変更される可能性あり | CHANGELOGのみ |
| **Internal** | いつでも変更される可能性あり。外部使用は非推奨 | 通知なし |

---

## 1. Stable API (v0.1.x 保証)

以下の公開インターフェースは**Stable**であり、v0.1.xシリーズ内で破壊的変更は行われません：

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

### Stable - CLIコマンド

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

### Stable - データ形式

- メモリJSON形式（エクスポート/インポート）
- ルールJSON形式
- Skill形式（SHA-256署名付き）
- MCP設定形式

---

## 2. Experimental API

以下のインターフェースは**Experimental**であり、マイナーバージョン更新で変更される可能性があります：

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

# Experimental - Skill形式
CarryMem.skill_pack(name, version="1.0.0", scope="personal", ...) -> Dict
CarryMem.skill_verify(data) -> Dict
CarryMem.skill_install(data, scope_override=None, mode="skip") -> Dict

# Experimental - マージプロトコル
CarryMem.review_incoming_rules(incoming, target_scope=None) -> Dict
CarryMem.accept_rules(incoming, strategy="negotiate", target_scope=None) -> Dict
MergeStrategy / MergeDecision / MergeConflict / MergeResult

# Experimental - ルールスコープタイプ
RuleScope / VALID_RULE_SCOPES / SCOPE_PRIORITY

---

## 3. Internal API

以下は内部実装の詳細であり、**いつでも変更される可能性**があります。外部コードでの使用は推奨されません：

```python
carrymem.classification.pattern_analyzer.*
carrymem.classification.semantic_classifier.*
carrymem.storage.sqlite_adapter.*
carrymem.rules.storage.*
carrymem.security.validator.*
```

---

## バージョン管理ポリシー

- **パッチバージョン** (0.1.x → 0.2.2): バグ修正、新機能（Stable APIは変更なし）
- **マイナーバージョン** (0.1.x → 0.2.2): 新機能、Experimental→Stable昇格の可能性
- **メジャーバージョン** (0.x → 1.0.0): 破壊的変更が発生する可能性

### 非推奨プロセス

1. APIに`DeprecationWarning`を追加
2. CHANGELOGに移行ガイドを記載
3. 最低1マイナーバージョンは旧APIを維持
4. 次のメジャーバージョンで削除

---

## 互換性

### Python バージョン

| Python バージョン | サポート状況 |
|------------------|-------------|
| 3.9 | ✅ サポート |
| 3.10 | ✅ サポート |
| 3.11 | ✅ サポート（推奨） |
| 3.12 | ✅ サポート |
| 3.8 以前 | ❌ 非サポート |

### インポートパス

v0.1.6以降、以下の2つのインポートパスがサポートされています：

```python
from carrymem import CarryMem  # 公式パッケージ名
from carrymem import CarryMem                       # 互換エイリアス
```

両方とも同じ動作をします。v1.0.0で統一される予定です。

---

## 変更履歴

- **v0.1.6**: バージョンリセット — セキュリティ強化、スレッドセーフ、ドキュメント整理
- 初期開発では0.4.x-0.8.xのバージョン番号が使用されていましたが、後に0.2.xシリーズに統合されました。現在のv0.2.0は、v0.1.6バージョンリセットのセキュリティ強化と品質改善、およびその後の機能強化を含んでいます。
