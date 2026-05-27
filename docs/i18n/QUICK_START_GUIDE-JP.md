# CarryMem クイックスタートガイド

**5分でCarryMemを始めよう**

---

## CarryMemとは？

CarryMemは、AIにあなたを記憶させます。

**一言で**: モデル、ツール、デバイスをまたぐAIメモリレイヤー。

**コアバリュー**:
- 🧠 AIが自動的にあなたの好み、修正、決定を記憶
- 🔄 メモリはポータブル — ツールを変えてもデータは失わない
- ⚡ 60%以上ゼロコスト分類 — トークン無駄遣いなし

---

## インストール

```bash
pip install carrymem
```

インストール確認：
```bash
carrymem version
```

---

## 初回セットアップ

### 1. 初期化（30秒）

```bash
carrymem init
```

作成されるもの：
- 設定ファイル：`~/.carrymem/config.json`
- データベース：`~/.carrymem/memories.db`

### 2. 最初のメモリを保存（1分）

```python
from carrymem import CarryMem

with CarryMem() as cm:
    cm.classify_and_remember("ダークモードが好きです")
    cm.classify_and_remember("データベースにはPostgreSQLを使います")
    cm.classify_and_remember("東京のスタートアップで働いています")
```

### 3. メモリを確認（30秒）

```bash
carrymem list
```

コードで確認：
```python
with CarryMem() as cm:
    memories = cm.recall_memories(query="データベース")
    for mem in memories:
        print(f"{mem['type']}: {mem['content']}")
```

### 4. 統計を確認（30秒）

```bash
carrymem stats
```

---

## コア機能

### 自動分類

CarryMemは7種類のメモリタイプを自動識別：

```python
with CarryMem() as cm:
    # 好み
    cm.classify_and_remember("ダークモードが好きです")
    # → type: user_preference

    # 修正
    cm.classify_and_remember("いや、Python 3.11です、3.10じゃありません")
    # → type: correction

    # 事実
    cm.classify_and_remember("スタートアップで働いています")
    # → type: fact_declaration

    # 決定
    cm.classify_and_remember("フロントエンドはReactにしましょう")
    # → type: decision
```

### アクティブ宣言

AIに自分のことを伝える：

```python
with CarryMem() as cm:
    cm.declare("MySQLよりPostgreSQLが好きです")
    # → confidence=1.0、確実に記憶される
```

### スマートリコール

```python
with CarryMem() as cm:
    # 完全一致
    memories = cm.recall_memories(query="PostgreSQL")

    # セマンティック検索
    memories = cm.recall_memories(query="データベースの好み")

    # 言語横断（日本語で保存、英語で検索）
    cm.classify_and_remember("PostgreSQLが好きです")
    memories = cm.recall_memories(query="database")  # 動作する！
```

### メモリプロフィールの確認

```python
with CarryMem() as cm:
    profile = cm.get_memory_profile()
    print(profile['summary'])
    # → "AIはあなたについて12のことを記憶：5つの好み、3つの修正、2つの決定"
```

### 記憶統合

```python
# 記憶統合（定期的に実行）
report = cm.consolidate(dry_run=True)  # 変更をプレビュー
print(f"重複 {report['stats']['duplicates_found']} 件を発見")
report = cm.consolidate(dry_run=False)  # 実行
```

---

## 実際のシナリオ

### シナリオ1：コードアシスタントがスタイルを記憶

```python
with CarryMem() as cm:
    # 最初の会話
    cm.classify_and_remember("Pythonでは型ヒントを使うのが好きです")
    cm.classify_and_remember("dictの代わりにdataclassを使います")

    # 次の会話、AIは自動的に好みを知っている
    memories = cm.recall_memories(query="Pythonコーディングスタイル")
    # AIは型ヒントとdataclassを使ったコードを生成
```

### シナリオ2：ツール間の利用

```python
# Cursorで
with CarryMem(namespace="cursor") as cm_cursor:
    cm_cursor.classify_and_remember("ダークモードが好きです")

# Windsurfで、同じメモリを使用
with CarryMem(namespace="cursor") as cm_windsurf:
    memories = cm_windsurf.recall_memories(query="テーマ")  # 見つかった！
```

### シナリオ3：プロジェクト分離

```python
# プロジェクトA
with CarryMem(namespace="project-a") as cm_a:
    cm_a.classify_and_remember("フロントエンドはReact")

# プロジェクトB
with CarryMem(namespace="project-b") as cm_b:
    cm_b.classify_and_remember("フロントエンドはVue")

# 干渉なし！
```

### シナリオ4：メモリを新しいデバイスに持ち運ぶ

```bash
# 古いデバイスでパック（暗号化可能）
carrymem pack --encrypt
# パスワード入力後、carrymem_identity_20260527.carry を生成

# USB / クラウド / 新しいマシンにコピー

# 新しいデバイスで復元
carrymem unpack carrymem_identity_20260527.carry
# パスワード入力 → すべてのメモリが復元
```

### シナリオ5：バックアップとリストア

```bash
# 手動バックアップの作成
carrymem backup

# すべてのバックアップを一覧
carrymem backup --list

# バックアップからリストア
carrymem backup --restore ~/.carrymem/backups/memories_backup_20260527_103000_123456.db
```

> 💡 CarryMem は20回の書き込み操作ごとに自動バックアップも作成します。手動操作は不要です。

---

## エクスポートとインポート

### メモリのエクスポート

```python
with CarryMem() as cm:
    cm.export_memories(output_path="my_memories.json")
    cm.export_memories(output_path="my_memories.md", format="markdown")
```

### 新しいデバイスでインポート

```python
with CarryMem() as cm_new:
    cm_new.import_memories(input_path="my_memories.json")
    # すべてのメモリが復元！
```

---

## CLIツール

```bash
carrymem init                          # 初期化
carrymem list                          # メモリ一覧
carrymem list --type user_preference   # タイプで絞り込み
carrymem list --limit 20               # 件数制限
carrymem stats                         # 統計
carrymem doctor                        # ヘルスチェック
carrymem version                       # バージョン情報
```

---

## よくある質問

### データはどこに保存されますか？
デフォルトでは `~/.carrymem/memories.db`。カスタムパスも指定可能。

### データは安全ですか？
データはローカルマシンに保存され、サーバーにアップロードされることはありません。

### メモリを削除できますか？
はい！
```python
with CarryMem() as cm:
    cm.forget_memory(memory_id)
```

### どの言語がサポートされていますか？
中国語、英語、日本語、クロス言語検索対応。

### トークンを多く消費しますか？
いいえ！60%以上の分類はゼロコスト、複雑なケースのみLLMを呼び出します。

### 別のデータベースを使えますか？
はい！SQLite（デフォルト）、Obsidian、カスタムアダプターをサポート。

---

## 次のステップ

- 📖 [完全ドキュメント](../../README.md)を読む
- 🎯 [ユーザーガイド](../USER_GUIDE.md)を確認
- 🏗️ [アーキテクチャ設計](../ARCHITECTURE.md)を学ぶ
- 🤝 [コントリビューションガイド](../../CONTRIBUTING.md)で貢献

---

## ヘルプ

- 問題報告：[GitHub Issues](https://github.com/lulin70/carrymem/issues)
- 診断ツール：`carrymem doctor`

---

**CarryMemを使って、AIにあなたを記憶させましょう！** 🚀
