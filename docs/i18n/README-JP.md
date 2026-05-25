# CarryMem — AI はついにあなたを覚えてくれた

**もう何度も AI に自己紹介する必要はありません。**

> ポータブル AI メモリ — 好み、決定、訂正がモデル、ツール、デバイスを越えてついてくる。

[English](../../README.md) | [中文](README-CN.md) | **日本語**

<p align="center">
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI バージョン"></a>
  <img src="https://img.shields.io/badge/tests-3000%2B%20passing-green" alt="テスト">
  <img src="https://img.shields.io/badge/coverage-78%25-green" alt="カバレッジ">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python">
</p>

---

## CarryMem ができること（30秒）

一言で：**AI にあなたが誰かを覚えさせる — 読んだ内容ではなく。**

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("ダークモードが好き")              # 自動分類：好み
cm.classify_and_remember("PostgreSQL でなく MySQL を使う")   # 自動分類：訂正
memories = cm.recall_memories("データベース")                # セマンティック検索
print(cm.build_system_prompt())                              # 任意の AI に注入
cm.close()
```

---

## CarryMem を選ぶ 3 つの理由

| # | 理由 | データ |
|---|------|--------|
| 🎯 | **嗜好注入精度** | **85.0%** — 学術検証（PrefEval, ICLR 2025 Oral）、リマインダー83.0%を超える |
| 💰 | **ゼロ LLM 分類** | **88%** のメモリは LLM 呼び出し不要、ゼロ Token 消費 |
| 🪶 | **軽量・ポータブル** | **SQLite 単一ファイル**、ゼロ依存、データを持ち運び |

---

## 仕組み

```
ユーザー入力
    ↓
自動分類（7タイプ、4層）  ← 88% ゼロ LLM
    ↓
重要度スコアリング（confidence × type × recency × access）
    ↓
スマートストレージ（SQLite + FTS5、重複排除、TTL、暗号化）
    ↓
記憶統合（P0: 重複排除+減衰 → P1: パターン→ルール → P2: 意味マージ）
    ↓
セマンティック検索（FTS5 + 同義語 + スペル修正 + 多言語）
    ↓
嗜好注入（トークン予算、関連性ランキング）  ← 87.9% 精度
    ↓
AI ツール（Cursor / Claude Code / 任意の MCP クライアント）
```

---

## クイックスタート

### インストール

```bash
pip install carrymem
```

> **PyPI**: [https://pypi.org/project/carrymem/](https://pypi.org/project/carrymem/)
>
> **開発モード**: `git clone https://github.com/lulin70/carrymem.git && cd carrymem && pip install -e ".[dev]"`

### インストール確認

```bash
carrymem version
```

**`command not found` の場合**、Python bin を PATH に追加：

```bash
# macOS（~/.zshrc に追加）
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Linux（~/.bashrc に追加）
export PATH="$HOME/.local/bin:$PATH"

# または Python モジュールを直接使用
python3 -m carrymem.cli version
```

その後 `carrymem doctor` で設定を確認。

### 5 行で始める

> ⚠️ **パッケージ名とインポート名**: `pip install carrymem` でインストール、`from carrymem import CarryMem` または `from carrymem import CarryMem` でインポート。v1.0.0 で統一予定。

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("ダークモードが好き")              # 自動分類：好み
cm.classify_and_remember("PostgreSQL でなく MySQL を使う")   # 自動分類：訂正
memories = cm.recall_memories("データベース")                # セマンティック検索
print(cm.build_system_prompt())                              # 任意の AI に注入
cm.close()
```

### CLI（22+ コマンド）

```bash
carrymem init                           # 初期化
carrymem add "ダークモードが好き"        # メモリを保存
carrymem add "テスト" --force           # 強制保存（分類スキップ）
carrymem list                           # メモリ一覧
carrymem search "テーマ"                # メモリ検索
carrymem show <key>                     # メモリ詳細
carrymem edit <key> "新しい内容"         # メモリ編集
carrymem forget <key>                   # メモリ削除
carrymem whoami                         # AI が思うあなた
carrymem profile export --output identity.json   # AI アイデンティティをエクスポート
carrymem stats                          # 統計
carrymem check                          # 品質チェック
carrymem clean --expired --dry-run      # クリーンアッププレビュー
carrymem doctor                         # インストール診断
carrymem setup-mcp --tool cursor        # MCP ワンライン設定
carrymem tui                            # ターミナル UI
carrymem export backup.json             # 全メモリをエクスポート
carrymem import backup.json             # メモリをインポート
carrymem version                        # バージョン表示
# ルールエンジンコマンド
carrymem add-rule "常にSSLを使用" --trigger "データベース" --type avoid   # ルール追加
carrymem list-rules --status active                            # アクティブルール一覧
carrymem skill-pack rules.json --name team-conventions         # Skill としてパック
carrymem skill-install team-conventions.json --scope company   # Skill インストール
carrymem skill-verify team-conventions.json                    # Skill 検証
```

---

## コア機能

### メモリがあなたを理解する

CarryMem はあなたが共有する情報のタイプを自動識別します。手動タグ付け不要：

| タイプ | アイコン | 例 |
|--------|----------|-----|
| `user_preference` | ⭐ | "ダークモードが好き" |
| `correction` | 🔧 | "いや、Python 3.11 だ、3.10 じゃない" |
| `decision` | 🎯 | "フロントエンドは React" |
| `fact_declaration` | 📌 | "東京のスタートアップで働いている" |
| `task_pattern` | 🔄 | "いつもテストを先に書く" |
| `relationship` | 👥 | "田中さんはダークモードが好き" |
| `sentiment_marker` | 💡 | "マイクロサービスに積極的" |

セマンティック検索（多言語対応）：

```python
cm.classify_and_remember("PostgreSQLを使うのが好き")

# 以下のクエリすべてで見つかります：
cm.recall_memories("PostgreSQL")     # 完全一致
cm.recall_memories("データベース")    # 同義語展開
cm.recall_memories("Postgres")       # スペル修正
cm.recall_memories("database")       # 言語横断（英語）
```

アイデンティティレイヤー（whoami）：

```python
identity = cm.whoami()
print(identity["preferences"])   # ["ダークモードが好き", ...]
print(identity["decisions"])     # ["フロントエンドは React", ...]
print(identity["corrections"])   # ["ポート番号は 5432", ...]
```

### 嗜好注入

CarryMem は単純なリマインダーではなく、構造化された嗜好をシステムプロンプトに注入します：

```python
print(cm.build_system_prompt())   # 嗜好注入プロンプトを自動生成
```

**なぜ嗜好注入 > フルリマインダーか**：リマインダーは毎ターン「ユーザーの嗜好を覚えて」と注入。CarryMem はシステムプロンプトに構造化された嗜好を注入 — より正確、より持続的、役立たず回答46%削減。

### メモリライフサイクル

すべての記憶には時間とともに進化する重要度スコアがあります：

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30日半減期減衰** — 古い記憶はアクセスされなければ薄れる
- **アクセス強化** — 頻繁に呼び出される記憶は新鮮に保たれる
- **タイプ重み付け** — 修正(1.3x) > 決定(1.2x) > 好み(1.1x)

品質管理：

```bash
carrymem check                    # 全体チェック
carrymem check --conflicts        # 矛盾を検出
carrymem check --quality          # 低品質の記憶を発見
carrymem check --expired          # 期限切れの記憶を発見
carrymem clean --expired --dry-run # クリーンアップをプレビュー
```

記憶統合（3フェーズ）：

```python
# 統合のプレビュー
report = cm.consolidate(dry_run=True)
print(f"重複: {report['stats']['duplicates_found']}")
print(f"減衰: {len(report['to_decay'])}")

# 統合を実行（P0: 重複排除+減衰, P1: パターン→ルール, P2: 意味マージ）
report = cm.consolidate(dry_run=False, run_p1=True, run_p2=True)
```

| フェーズ | 機能 | メカニズム |
|----------|------|------------|
| **P0** | 重複排除 + 減衰 | Jaccard 類似度で重複排除、指数半減期減衰（好み: 270日, 事実: 90日, 感情: 45日） |
| **P1** | パターン → ルール | 繰り返しパターンを検出 → レビュー用ルール候補を生成 |
| **P2** | 意味マージ | 関連メモリをクラスタリング → ホスト LLM に統合を依頼 |

好みは常に保持 — 減衰も重複排除もされません。

### セキュリティとポータビリティ

| 機能 | 説明 |
|------|------|
| **暗号化** | AES-128 (Fernet) または HMAC-CTR フォールバック、ゼロ依存 |
| **バックアップ** | ゼロダウンタイム SQLite VACUUM INTO |
| **監査ログ** | 追記専用の操作履歴 |
| **バージョン履歴** | すべての編集を追跡、ロールバック対応 |
| **入力検証** | SQLインジェクション、XSS、パストラバーサル対策 |

---

## サポート機能

### MCP 統合

```bash
# Cursor用設定
carrymem setup-mcp --tool cursor

# Claude Code用設定
carrymem setup-mcp --tool claude-code

# すべてのツール用設定
carrymem setup-mcp --tool all
```

25のMCPツール：Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (1) · Rules (11)

### ルールエンジン

行動ルールは3つのスコープレベルをサポートし、チーム/組織のアラインメントを実現：

```python
from carrymem.rules import RuleEngine

engine = RuleEngine()

# 会社の強制ルール（最優先、上書き不可）
engine.add_rule("データベース", "常にSSL接続を使用", scope="company", override=True)

# 個人の好み（最優先度低）
engine.add_rule("データベース", "PostgreSQLを好む", scope="personal")

# スコープ対応マッチング
results = engine.match("データベース設計", scopes=["company"])
```

| スコープ | 優先度 | 説明 |
|----------|--------|------|
| `company` | 3（最高） | 組織の強制ルール、上書き不可 |
| `negotiated` | 2 | 会社ルールから適応 |
| `personal` | 1（最低） | ユーザーの好み |

マージプロトコル — 異なるソースからのルールを3つの戦略でマージ：

| 戦略 | 説明 |
|------|------|
| `company_overrides` | 高スコープが常に勝つ |
| `negotiate` | 競合ルールを "negotiated" スコープに適応 |
| `keep_both` | 両方のルールを保持、ユーザーが手動レビュー |

### Skill フォーマット

暗号整合性検証付きでチーム間ルールセットを共有：

```python
# ルールをポータブル Skill バンドルにパック
bundle = engine.skill_pack(
    name="チーム規約",
    version="1.0.0",
    scope="company",
    author="チームリーダー",
)

# インストール前に整合性を検証
result = engine.skill_verify(bundle)
assert result["valid"] is True

# 別のマシンにインストール
engine.skill_install(bundle, scope_override="company", mode="skip")
```

### ターミナル UI

```bash
pip install textual
carrymem tui
```

サイドバーフィルター、検索、追加モード付きインタラクティブターミナルインターフェース。

### VS Code 拡張機能

エディタ内でルールを直接管理：

- スコープバッジ付きルールサイドバー
- Webview でルールを追加/編集/削除
- 有効性レポートパネル
- Skill パック/インストールファイルダイアログ

---

## 競合比較

|  | CarryMem | Mem0 | OpenChronicle | ima |
|--|----------|------|---------------|-----|
| **ゼロ依存** | ✅ SQLite のみ | ⚠️ ベクタDB任意 | ✅ | ❌ クラウド |
| **自動分類** | ✅ 7タイプ | ❌ | ❌ 手動 | ❌ |
| **アイデンティティ** | ✅ whoami | ❌ | ❌ | ❌ |
| **ルールエンジン** | ✅ スコープ + Skill | ❌ | ❌ | ❌ |
| **Skill フォーマット** | ✅ SHA-256 署名 | ❌ | ❌ | ❌ |
| **マージプロトコル** | ✅ 3戦略 | ❌ | ❌ | ❌ |
| **VS Code 拡張** | ✅ | ❌ | ❌ | ❌ |
| **CLI** | ✅ 22+ コマンド | ❌ | ❌ | ❌ |
| **ターミナル UI** | ✅ textual | ❌ | ❌ | ✅ App |
| **暗号化** | ✅ 内蔵 | ❌ | ❌ | ❌ |
| **バージョン履歴** | ✅ ロールバック | ❌ | ❌ | ❌ |
| **競合検出** | ✅ 内蔵 | ❌ | ❌ | ❌ |
| **データ所有権** | ✅ ローカル | ⚠️ セルフホスト | ✅ ローカル | ❌ クラウド |
| **5行統合** | ✅ | ⚠️ SDK必要 | ❌ | ❌ |
| **多言語検索** | ✅ 日/中/英 | ❌ | ❌ | ❌ |
| **核心の違い** | **あなたが誰かを覚える** | 読んだ内容を保存 | 読んだ内容を保存 | 読んだ内容を保存 |

> **注**：比較は公開情報に基づきます。製品は急速に進化するため、最新機能をご確認ください。

---

### 🏆 PrefEval — 嗜好遵守率ベンチマーク

> ICLR 2025 Oral、Amazon Science 製。10ターンの干渉後もAIがユーザーの嗜好に従うかを測定。

**CarryMem が単純リマインダーを超越 — プロアクティブ注入 > フルリマインダーを証明した初のシステム。**

| 条件 | 精度 | 違反 | 幻覚 | 役立たず |
|------|------|------|------|----------|
| zero-shot | 69.5% | 31 | 2 | 31 |
| reminder | 83.0% | 1 | 1 | 33 |
| **CarryMem** | **85.0%** | 5 | 4 | **25** |

**バージョンごとの進歩（200サンプル、3条件比較）**：

| バージョン | 精度 | 主な変更 |
|-----------|------|----------|
| v0.2.1 修正前 | 82.7% | 共参照解決 + 自動秘匿化 |
| v0.2.1 修正後 | 85.5% | メモリクエリ指示の削除 |
| v0.2.1 最適化後 | 87.0% | QAプロンプト簡素化 |
| v0.2.2 | 87.9% | トークン予算 + デッドコード修正 + セキュリティ |
| v0.2.3 | 87.9% | 統合スケジューリング + PrefEval標準化 |
| **v0.2.3-rc2** | **85.0%** | **3条件公平比較：force_type + ノイズ除去 + DBロック修正** |

**なぜ重要か**：リマインダーは毎ターン「ユーザーの嗜好を覚えて」と注入。CarryMem はシステムプロンプトに構造化された嗜好を注入 — より正確、より持続的、役立たず回答24%削減。

| | 利点 | 結果 |
|---|------|------|
| 💰 | ゼロLLM取り込み | **88%** のメモリはLLMトークン不要 |
| ⚡ | P99レイテンシ | **1.3ms** — Mem0より**93倍高速** |
| 🪶 | 依存関係 | **SQLiteのみ** — ベクトルDB不要 |
| 🛡️ | ルールエンジン | **唯一**ルールエンジン搭載（競合：0%） |

---

## アーキテクチャ

```
ユーザー入力
    ↓
自動分類（7タイプ、4層）
    ↓
重要度スコアリング（confidence × type × recency × access）
    ↓
スマートストレージ（SQLite + FTS5、重複排除、TTL、暗号化）
    ↓
記憶統合（P0: 重複排除+減衰 → P1: パターン→ルール → P2: 意味マージ）
    ↓
セマンティック検索（FTS5 + 同義語 + スペル修正 + 多言語）
    ↓
コンテキスト注入（トークン予算、関連性ランキング）
    ↓
AI ツール（Cursor / Claude Code / 任意の MCP クライアント）
```

---

## 高度な使い方

### Obsidian ナレッジベース

```python
from carrymem import CarryMem, ObsidianAdapter

cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
cm.index_knowledge()
results = cm.recall_from_knowledge("Python デザインパターン")
```

### 非同期 API

```python
from carrymem import AsyncCarryMem

async with AsyncCarryMem() as cm:
    await cm.classify_and_remember("ダークモードが好き")
    memories = await cm.recall_memories("テーマ")
```

### JSON アダプター（SQLite 不要）

```python
from carrymem import CarryMem, JSONAdapter

cm = CarryMem(adapter=JSONAdapter(path="/path/to/memories.json"))
```

### 暗号化

```python
cm = CarryMem(encryption_key="my-secret-key")
# すべてのコンテンツは保存時暗号化、読み取り時復号
```

### メモリバージョニング

```python
cm.update_memory(key, "更新された内容")     # バージョン 2 を作成
history = cm.get_memory_history(key)        # [v1, v2]
cm.rollback_memory(key, version=1)          # v1 に復元
```

### 他の AI 用にアイデンティティをエクスポート

```python
# AI アイデンティティをエクスポート
cm.export_profile(output_path="my_identity.json")

# 別のデバイスや AI ツールで
cm.import_memories(input_path="backup.json")
```

---

## どんな人向け？

**何度も自己紹介するのに疲れていませんか？**
毎日 Cursor、Claude Code、ChatGPT を使っています。技術スタック、コーディングスタイル、設計の決定を100回伝えたのに、AI はまだ「どのフレームワークがお好みですか？」と聞いてきます。CarryMem は AI に覚えさせます。もう二度と言う必要はありません。

**手動で CLAUDE.md をメンテナンスしていますか？**
AI にはメモリが必要だと知っている。プロンプトファイルがあちこちにあって、矛盾して、古くなって、ツールを変えると使えない。CarryMem は好み、決定、訂正を自動分類し、自動的に最新に保ちます。

**AI エージェントを開発していますか？**
エージェントはセッション間でユーザーを忘れます。軽量、ローカル、どんな LLM でも動くメモリレイヤーが必要。CarryMem は 5 行の統合、7 種類のメモリタイプ、ルールエンジンを提供。SQLite 以外の依存関係はゼロ。

---

## ドキュメント

- [クイックスタートガイド](../QUICK_START_GUIDE.md)
- [インストールガイド](../INSTALL.md)
- [ユーザーガイド](../USER_GUIDE.md)
- [アーキテクチャ](../ARCHITECTURE.md)
- [API リファレンス](../API_REFERENCE.md)
- [API 安定性ポリシー](../API_STABILITY.md)
- [ロードマップ](ROADMAP-JP.md)
- [コントリビューション](../../CONTRIBUTING.md)

---

## プロジェクトステータス

**現在のバージョン**: v0.2.3
**テスト**: 3000+ passing
**カバレッジ**: ~78%

**チェンジログ**:
- **v0.3.0**: 記憶統合エンジン（P0/P1/P2）、PrefEval 96.0%、嗜好注入修正、25のMCPツール
- **v0.3.0**: バージョンリセット — セキュリティ強化（FTS5サニタイズ、パス検証、ルールコンテンツフィルタリング）、スレッドセーフ、ドキュメント整理、テストクリーンアップ
- **v0.4.1**: コアループ修正 — 自動ルール提案、MCP ルールツール、プロンプト注入防御、コネクションプーリング
- **v0.4.0**: エンタープライズ機能 — ルールスコープ、Skill フォーマット（SHA-256）、マージプロトコル、VS Code 拡張
- **v0.3.0**: GA リリース — ナレッジアダプター、有効性レポート、コンテキストエンジニアリング
- **v0.2.6**: 経験学習 — 失敗→回避ルール、learn-experience/review-lessons CLI
- **v0.2.5**: 自動プロモーションパイプライン — メモリパターン→ルール候補、promotion-log CLI
- **v0.2.4**: メモリからのパターン検出、suggest-rules CLI、候補ルールジェネレーター
- **v0.2.3**: 定期統合（schedule_consolidation/stop_consolidation）、ルールエクスポート/インポート、インタラクティブ CLI、ルールテンプレート、edit-rule、12 CLI コマンド
- **v0.2.2**: パフォーマンスベンチマーク + 競合検出（check-rules コマンド）
- **v0.2.1**: ルールエンジン Alpha — 手動 CRUD、FTS5 マッチング、セキュリティ、8 CLI コマンド
- **v0.3.0**: PyPI リリース、アイデンティティレイヤー（whoami、profile エクスポート）、490 テスト

---

## コントリビューション

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
pytest
```

詳細は [コントリビューションガイド](../../CONTRIBUTING.md) を参照。

---

## ライセンス

MIT ライセンス — 詳細は [LICENSE](../../LICENSE) を参照

---

**CarryMem — AI はついにあなたを覚えてくれた。データはあなたのもの。**
