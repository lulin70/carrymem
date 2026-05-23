# CarryMem — AI はついにあなたを覚えてくれた

**もう何度も AI に自己紹介する必要はありません。**

> ポータブル AI メモリ — 好み、決定、訂正がモデル、ツール、デバイスを越えてついてくる。

新しいチャットを開くたびに、もう一度自己紹介。好みも、決定も、訂正も、全部忘れている。Cursor から Claude Code へ、GPT から Claude へ切り替えても、毎回ゼロから。

あなたは AI を使っているのではなく、AI を教え込んでいます。何度も何度も。

CarryMem はこれを解決します。軽量・ゼロ依存のメモリシステムで、**あなたが誰か**を保存し、あらゆる AI ツールで利用可能にします。AI は好み、過去の決定、訂正を覚えるので、あなたは自己紹介ではなく、本来の作業に集中できます。

[English](../../README.md) | [中文](README-CN.md) | **日本語**

<p align="center">
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI バージョン"></a>
  <img src="https://img.shields.io/badge/tests-2100%20passing-green" alt="テスト">
  <img src="https://img.shields.io/badge/coverage-78%25-green" alt="カバレッジ">
  <img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python">
</p>

---

## なぜ CarryMem が必要か？

### 問題：AI はいつもあなたが誰かを忘れる

新しい会話のたびに、AI はゼロから始まります：
- ダークモードがお好み？**忘れている。**
- 前回訂正したこと？**忘れている。**
- React を使うと決めたこと？**忘れている。**

ツールを変え（Cursor → Windsurf）、モデルを変え（Claude → GPT）— 毎回ゼロからやり直し。

### ソリューション：CarryMem アイデンティティレイヤー

CarryMem はテキストを保存するだけではなく — **あなたが誰か**を理解します：

```bash
$ carrymem whoami

  あなたは誰か（AI の視点から）
  ==================================================

  好み：
    ⭐ すべてのエディタでダークモードを好む
    ⭐ データベースは PostgreSQL を使う
    ⭐ データ分析は常に Python を使う

  決定：
    🎯 フロントエンドは React

  訂正：
    🔧 ポート番号は 5432

  メモリプロファイル：
    合計: 19 | 主要タイプ: user_preference | 平均信頼度: 73%
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

### 1. 自動分類（7 種類のメモリタイプ）

CarryMem はあなたが共有する情報のタイプを自動識別します：

| タイプ | アイコン | 例 |
|--------|----------|-----|
| `user_preference` | ⭐ | "ダークモードが好き" |
| `correction` | 🔧 | "いや、Python 3.11 だ、3.10 じゃない" |
| `decision` | 🎯 | "フロントエンドは React" |
| `fact_declaration` | 📌 | "東京のスタートアップで働いている" |
| `task_pattern` | 🔄 | "いつもテストを先に書く" |
| `relationship` | 👥 | "田中さんはダークモードが好き" |
| `sentiment_marker` | 💡 | "マイクロサービスに積極的" |

### 2. セマンティック検索（多言語対応）

```python
cm.classify_and_remember("PostgreSQLを使うのが好き")

# 以下のクエリすべてで見つかります：
cm.recall_memories("PostgreSQL")     # 完全一致
cm.recall_memories("データベース")    # 同義語展開
cm.recall_memories("Postgres")       # スペル修正
cm.recall_memories("database")       # 言語横断（英語）
```

### 3. アイデンティティレイヤー（whoami）

```python
identity = cm.whoami()
print(identity["preferences"])   # ["ダークモードが好き", ...]
print(identity["decisions"])     # ["フロントエンドは React", ...]
print(identity["corrections"])   # ["ポート番号は 5432", ...]
```

### 4. 重要度スコアリングとライフサイクル

すべての記憶には時間とともに進化する重要度スコアがあります：

```
importance = confidence × type_weight × recency_factor × access_factor
```

- **30日半減期減衰** — 古い記憶はアクセスされなければ薄れる
- **アクセス強化** — 頻繁に呼び出される記憶は新鮮に保たれる
- **タイプ重み付け** — 修正(1.3x) > 決定(1.2x) > 好み(1.1x)

### 5. 品質管理

```bash
carrymem check                    # 全体チェック
carrymem check --conflicts        # 矛盾を検出
carrymem check --quality          # 低品質の記憶を発見
carrymem check --expired          # 期限切れの記憶を発見
carrymem clean --expired --dry-run # クリーンアップをプレビュー
```

### 6. セキュリティと信頼性

| 機能 | 説明 |
|------|------|
| **暗号化** | AES-128 (Fernet) または HMAC-CTR フォールバック、ゼロ依存 |
| **バックアップ** | ゼロダウンタイム SQLite VACUUM INTO |
| **監査ログ** | 追記専用の操作履歴 |
| **バージョン履歴** | すべての編集を追跡、ロールバック対応 |
| **入力検証** | SQLインジェクション、XSS、パストラバーサル対策 |

### 7. MCP統合（1行設定）

```bash
# Cursor用設定
carrymem setup-mcp --tool cursor

# Claude Code用設定
carrymem setup-mcp --tool claude-code

# すべてのツール用設定
carrymem setup-mcp --tool all
```

25のMCPツール：Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (1) · Rules (11)

### 8. ルールエンジンとスコープ

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

### 9. Skill フォーマット — ポータブルルールバンドル

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

### 10. マージプロトコル — 競合解決

異なるソースからのルールを3つの戦略でマージ：

| 戦略 | 説明 |
|------|------|
| `company_overrides` | 高スコープが常に勝つ |
| `negotiate` | 競合ルールを "negotiated" スコープに適応 |
| `keep_both` | 両方のルールを保持、ユーザーが手動レビュー |

### 11. VS Code 拡張機能

エディタ内でルールを直接管理：

- スコープバッジ付きルールサイドバー
- Webview でルールを追加/編集/削除
- 有効性レポートパネル
- Skill パック/インストールファイルダイアログ

### 12. ターミナル UI

```bash
pip install textual
carrymem tui
```

サイドバーフィルター、検索、追加モード付きインタラクティブターミナルインターフェース。

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

> **注**：比較は公開情報に基づきます。製品は急速に進化するため、最新機能をご確認ください。

**核心の違い**：他の製品は*あなたが読んだもの*を保存します。CarryMem は*あなたが誰であるか*を保存します。

---

## パフォーマンス

### 🏆 ベンチマーク — v0.2.1 ベースライン

| ベンチマーク | スコア | 備考 |
|-------------|--------|------|
| **PrefEval** | **96.0%** | ICLR 2025 Oral、50項目、嗜好遵守率（zero-shot: 90%、reminder: 92%） |
| **LongMemEval** | **42.6%** | 公式 oracle データセット、500問 |
| **RuleEngine-Eval** | **93.3%** | CarryMem 独自 — ルールエンジンを持つ唯一のシステム |
| **MemEval** | *実行中* | 公式フレームワーク、CarryMem アダプタ |
| **MSC** | *保留* | データセット制限 |

| | 利点 | 結果 |
|---|------|------|
| 💰 | ゼロLLM取り込み | **88%** のメモリはLLMトークン不要 |
| ⚡ | P99レイテンシ | **1.3ms** — Mem0より**93倍高速** |
| 🪶 | 依存関係 | **SQLiteのみ** — ベクトルDB不要 |
| 🛡️ | ルールエンジン | **唯一**ルールエンジン搭載（競合：0%） |

> **透明性優先。** 初回ベースラインスコア — 完璧ではありませんが、正直です。詳細：[BENCHMARK_STRATEGY_FINAL.md](../BENCHMARK_STRATEGY_FINAL.md)

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

**現在のバージョン**: v0.2.1
**テスト**: 2100+ passing
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
- **v0.2.3**: ルールエクスポート/インポート、インタラクティブ CLI、ルールテンプレート、edit-rule、12 CLI コマンド
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
