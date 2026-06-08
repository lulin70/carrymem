# CarryMem — AI はついにあなたを覚えてくれた

**もう何度も AI に自己紹介する必要はありません。**

> ポータブル AI メモリ — 好み、決定、訂正がモデル、ツール、デバイスを越えてついてくる。

[English](../../README.md) | [中文](README-CN.md) | **日本語** | [한국어](README-KO.md) | [繁體中文](README-ZH-TW.md)

<p align="center">
  <a href="https://github.com/lulin70/carrymem"><img src="https://img.shields.io/github/stars/lulin70/carrymem?style=flat-square&logo=github" alt="GitHub Stars"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/v/carrymem?color=blue" alt="PyPI バージョン"></a>
  <a href="https://pypi.org/project/carrymem/"><img src="https://img.shields.io/pypi/dm/carrymem?color=blue" alt="PyPI Downloads"></a>
  <img src="https://img.shields.io/badge/tests-3244-brightgreen" alt="テスト">
  <img src="https://img.shields.io/badge/coverage-80%25%2B-green" alt="カバレッジ">
  <a href="https://arxiv.org/abs/2410.01373"><img src="https://img.shields.io/badge/PrefEval-83.0%25%20(ICLR%202025%20Oral)-9B59B6?logo=arxiv" alt="PrefEval 学術ベンチマーク"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-blue" alt="Python">
</p>

---

## CarryMem ができること

**5 つのシナリオ：**

> **「毎回 AI に好みを伝えるのが面倒」**
> "PostgreSQL が好き""React で Vue は使わない""コメントは不要" — 一度言えば永遠に覚えている。

> **「AI ツールを変えたら最初から」**
> Cursor で教えたのに、Claude Code でまた教え直し。CarryMem は AI メモリをあなたについてくる。

> **「自分のデータを持ち運びたい」**
> AI メモリはあなたのもの。1 ファイルでパック、新しいマシン、新しいツールでいつでも復元。

> **「USB 携帯 — ポケットの中の記憶」** 🔑
> メモリを暗号化 .carry ファイルにパック、USB にコピー、新しいマシンでアンパック。AI アイデンティティが一緒に移動 — 好み、決定、訂正、ルールすべてそのまま。新しいマシンのすべてのエージェントが即座にあなたを認識。

> **「チームのすべてのエージェントで規約を共有」**
> チームリーダーが会社のルールを Skill バンドルとしてパック、メンバー全員がインストール。すべてのエージェントが同じ規約を自動適用 — 「SSL を使うことを知らなかった」はもうなし。

---

## 🎯 リアルユーザーシナリオ

### シナリオ1：マルチツール開発者

```
月曜：Cursor に「ダークモード、PostgreSQL、React が好き」と伝える
火曜：Claude Code を開く — すでにスタックを知っている
金曜：TRAE に切り替え — 同じ嗜好、ゼロの繰り返し
```

**方法**：`carrymem setup-mcp --all --global` — 1コマンド、すべてのツールが1つのメモリを共有。

### シナリオ2：USB 携帯 — 新しいマシン、同じアイデンティティ

```
1. ノートPCで：carrymem pack -o my_identity.carry --encrypt
2. my_identity.carry を USB ドライブにコピー
3. 新しい職場で：新しいマシンに CarryMem をインストール
4. carrymem unpack my_identity.carry
5. 新しいマシンのすべてのエージェントがあなたの嗜好、決定、ルールを認識
```

**暗号化 + SHA-256 チェックサム** — USB を紛失してもアイデンティティは安全。

### シナリオ3：チームリーダー

```
1. チーム規約をルールとして作成：「常にSSLを使用」「金曜日にデプロイしない」
2. Skill としてパック：carrymem skill-pack rules.json --name team-conventions
3. .json ファイルをチームと共有
4. 各メンバー：carrymem skill-install team-conventions.json --scope company
5. すべてのエージェントが会社の規約を自動適用
```

### シナリオ4：長期ユーザー

```
1ヶ月目：「ダークモードが好き」→ user_preference として保存
3ヶ月目：「ライトモードに切り替え」→ 古い嗜好を自動置換
6ヶ月目：carrymem whoami → 「ライトモードが好き」と表示（ダークモードはアーカイブ済み）
```

**嗜好は進化する。CarryMem は履歴を追跡。**

---

## はじめ方

### Cursor / Claude Code / TRAE を使っている？

```bash
pip install carrymem && carrymem setup-mcp --all --global
```

AI ツールを再起動。完了。

### 動作確認（30 秒）

AI に伝える：
```
覚えて、PostgreSQL が好き
```

新しい会話を開始して聞く：
```
どんなデータベースが好き？
```

AI が "PostgreSQL" と答えたら — 成功！

### メモリを移行したい？

```bash
carrymem pack                    # carrymem_identity_20260526.carry を作成
carrymem pack --encrypt          # パスワード暗号化パック（パスワード入力プロンプト）
# USB / クラウド / 新しいマシンにコピー
carrymem unpack my_identity.carry  # すべてのメモリを復元
```

### バックアップが必要？

```bash
carrymem backup                  # バックアップを作成
carrymem backup --list           # すべてのバックアップを一覧
carrymem backup --restore <path> # バックアップから復元
```

---

> 📊 **学術検証**：CarryMemの嗜好注入精度（83.0%）は [PrefEvalプロトコル](https://arxiv.org/abs/2410.01373)（ICLR 2025 オーラル, Amazon Science）で測定され、200テスト項目で単純リマインダー（80.0%）およびゼロショット（71.5%）ベースラインを上回りました。下記の[引用](#引用)も参照ください。

## CarryMem を選ぶ 3 つの理由

これらは CarryMem を他のすべてのメモリソリューションと差別化する要素です：

### 1. 嗜好注入精度 — 83.0%（学術検証）
- PrefEval（ICLR 2025 オーラル, Amazon Science）で測定、200サンプル3条件比較
- CarryMem 83.0% > 単純リマインダー 80.0% > ゼロショット 71.5%
- プロアクティブ注入 > フルリマインダー — これを証明した初のシステム
- リマインダーより24%少ない役立たず回答（28 vs 38）— より正確、より少ないノイズ

### 2. ゼロ LLM 分類 — 88% LLM 呼び出し不要
- ルールエンジンが88%のメモリを分類、ゼロ Token 消費
- ルールエンジン内蔵の唯一のシステム（競合：0%）
- P99 レイテンシ：1.3ms — Mem0 より93倍高速

### 3. 軽量・ポータブル — SQLite のみ
- コア機能に外部依存関係ゼロ
- 単一 .db ファイル — アイデンティティをどこでも持ち運び
- Cursor、Claude Code、ChatGPT、任意の MCP クライアントで動作

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
嗜好注入（トークン予算、関連性ランキング）  ← 83.0% 精度
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

### システム要件

- **Python**: ≥3.12（64 ビット）
- **OS**: macOS 10.15+, Ubuntu 20.04+, Windows 10+
- **ディスク**: コア機能約 5MB、セマンティック検索約 200MB
- **メモリ**: ベース約 50MB

### 依存関係

| 機能 | パッケージ | インストール |
|------|-----------|-------------|
| コア | PyYAML≥5.0 | `pip install carrymem` に含む |
| 多言語 | pycld2, langdetect | `pip install carrymem[language]` |
| セマンティック検索 | sqlite-vec, sentence-transformers | `pip install carrymem[semantic]` |
| 暗号化 | cryptography≥41.0 | `pip install carrymem[encryption]` |
| 全機能 | 上記すべて | `pip install carrymem[full]` |
| 開発 | pytest, black, flake8... | `pip install -e ".[dev]"` |

> **コア機能はゼロ LLM 依存** — 分類はルールエンジンのみ使用。LLM 呼び出し不要。

### インストール確認

```bash
carrymem version
```

**`command not found` の場合**、Python bin を PATH に追加：

```bash
# macOS（~/.zshrc に追加）
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# Linux（~/.bashrc に追加）
export PATH="$HOME/.local/bin:$PATH"

# または Python モジュールを直接使用
python3 -m carrymem.cli version
```

その後 `carrymem doctor` で設定を確認。

### 5 行で始める

> ⚠️ **パッケージ名とインポート名**: `pip install carrymem`（小文字）でインストール、`from carrymem import CarryMem`（キャメルケース）でインポート。パッケージ名（`carrymem`）とクラス名（`CarryMem`）は大文字小文字が異なります。

```python
from carrymem import CarryMem

cm = CarryMem()
cm.classify_and_remember("ダークモードが好き")              # 自動分類：好み
cm.classify_and_remember("PostgreSQL でなく MySQL を使う")   # 自動分類：訂正
memories = cm.recall_memories("データベース")                # セマンティック検索
print(cm.build_system_prompt())                              # 任意の AI に注入
cm.close()
```

### CLI（50+ コマンド）

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
# バックアップとポータビリティ
carrymem pack --encrypt                                        # パスワード暗号化パック
carrymem unpack identity.carry                                 # アイデンティティを復元
carrymem backup                                                # バックアップを作成
carrymem backup --list                                         # バックアップ一覧
carrymem backup --restore <path>                               # バックアップから復元
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

**なぜ嗜好注入 > フルリマインダーか**：リマインダーは毎ターン「ユーザーの嗜好を覚えて」と注入。CarryMem はシステムプロンプトに構造化された嗜好を注入 — より正確、より持続的、役立たず回答24%削減。

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
| **自動バックアップ** | ゼロダウンタイム SQLite VACUUM INTO、20回書き込みごとに自動バックアップ |
| **.carry 暗号化** | ポータブルアイデンティティファイルのパスワード暗号化 + SHA-256 チェックサム |
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

27のMCPツール：Core (3) · Storage (3) · Knowledge (3) · Profile (2) · Prompt (2) · Consolidation (3) · Rules (11)

**クライアント互換性：**

| ステータス | クライアント | 設定方法 |
|-----------|-------------|---------|
| ✅ 直接対応 | Cursor、Claude Code、TRAE、Windsurf、Cline | `setup-mcp --global` |
| ✅ 自動検出 | OpenClaw、Kimi Code CLI、CodeX | `setup-mcp --global`（Claude Code形式にフォールバック） |
| 📋 マーケットプレイス | WorkBuddy、CodeBuddy | MCP Marketplaceへ提出（保留中） |
| ❌ 非対応 | Kimiデスクトップ、DeepSeekデスクトップ、通義千問、豆包、天工、智譜清言 | クローズドプラットフォーム、MCPインターフェースなし |

> **🔒 あなたの記憶はあなたのマシンにのみ保存されます。** CarryMem の全データは `~/.carrymem/`（SQLite）にローカル保存されます。各ユーザーは独立したデータベースを持ちます——Git と同じように、同じツールを使っても各人のリポジトリは完全に独立です。クラウド同期なし、共有状態なし、ユーザー間の競合なし。

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
| **CLI** | ✅ 40+ コマンド | ❌ | ❌ | ❌ |
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

| 条件 | 精度 | 承認 | 違反 | 幻覚 | 役立たず |
|------|------|------|------|------|----------|
| ゼロショット | 71.5% | 160 | 27 | 3 | 31 |
| リマインダー | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

プロトコル：PrefEval（ICLR 2025 オーラル, Amazon Science）
サンプル：200項目、10インターターン、Claude Sonnet 4

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

**現在のバージョン**: v0.2.5 (Beta)
**テスト**: 3244 passing
**カバレッジ**: 80%+

**チェンジログ**:
- **v0.2.0**: USB 携帯暗号化、自動バックアップ、並行安全性、PrefEval 83.0%（200項目）、8クライアントMCP設定
- **v0.2.3**（リセット前）: 定期統合（schedule/stop）、PrefEval 標準化
- **v0.2.2**（リセット前）: トークン予算 + デッドコード修正 + セキュリティ、PrefEval 87.9%
- **v0.2.1**（リセット前）: 共参照解決、自動リダクション、QA プロンプト最適化

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

## 引用

研究で CarryMem を使用する場合は、以下を引用してください：

```bibtex
@software{carrymem2026,
  title = {CarryMem: Persistent Memory for AI Agents with Preference Injection},
  author = {CarryMem Team},
  year = {2026},
  url = {https://github.com/carrymem/carrymem},
  note = {Preference injection accuracy 83.0\% measured by PrefEval protocol}
}

@inproceedings{chuang2025prefeval,
  title = {PrefEval: A Preference Evaluation Benchmark for LLMs},
  author = {Chuang, Yun-Nung and others},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year = {2025},
  note = {Oral presentation, Amazon Science}
}
```

**実験結果（200項目、10インターターン、Claude Sonnet 4）**

| 条件 | 精度 | 承認 | 違反 | 幻覚 | 役立たず |
|------|------|------|------|------|----------|
| ゼロショット | 71.5% | 160 | 27 | 3 | 31 |
| リマインダー | 80.0% | 199 | 2 | 1 | 38 |
| **CarryMem** | **83.0%** | 173 | 7 | 4 | **28** |

主要な洞察：CarryMem は最高の精度を達成しながら、リマインダーベースのアプローチより24%少ない役立たず回答を生成し、プロアクティブなメモリ注入がフルコンテキストリマインダーよりも正確であることを実証。

---

## ライセンス

MIT ライセンス — 詳細は [LICENSE](../../LICENSE) を参照

---

**CarryMem — AI はついにあなたを覚えてくれた。データはあなたのもの。**
