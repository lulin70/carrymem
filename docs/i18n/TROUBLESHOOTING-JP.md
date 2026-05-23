# CarryMem トラブルシューティングガイド

**バージョン**: v0.2.2

---

## 目次

- [クイック診断](#クイック診断)
- [エラーメッセージ索引](#エラーメッセージ索引)
- [インストールとセットアップ](#インストールとセットアップ)
  - [1. CLI コマンドが見つからない](#1-cli-コマンドが見つからない)
  - [2. インポートエラー](#2-インポートエラー)
  - [3. バージョンの不一致](#3-バージョンの不一致)
  - [4. pip インストール失敗](#4-pip-インストール失敗)
- [コアメモリ操作](#コアメモリ操作)
  - [5. メモリが保存されない](#5-メモリが保存されない)
  - [6. リコール結果なし](#6-リコール結果なし)
  - [7. メモリ分類エラー](#7-メモリ分類エラー)
  - [8. データベースがロックされている](#8-データベースがロックされている)
  - [9. データベース破損](#9-データベース破損)
- [ルールエンジン](#ルールエンジン)
  - [10. ルールが注入されない](#10-ルールが注入されない)
  - [11. ルールスコープの競合](#11-ルールスコープの競合)
  - [12. Skill 検証失敗](#12-skill-検証失敗)
  - [13. ルール提案の品質](#13-ルール提案の品質)
- [MCP 連携](#mcp-連携)
  - [14. MCP 連携が動作しない](#14-mcp-連携が動作しない)
  - [15. MCP ツールタイムアウト](#15-mcp-ツールタイムアウト)
- [セキュリティと暗号化](#セキュリティと暗号化)
  - [16. 暗号化/復号エラー](#16-暗号化復号エラー)
  - [17. パス検証エラー](#17-パス検証エラー)
- [高度な機能](#高度な機能)
  - [18. Obsidian アダプターの問題](#18-obsidian-アダプターの問題)
  - [19. TUI 表示の問題](#19-tui-表示の問題)
  - [20. VS Code 拡張機能の問題](#20-vs-code-拡張機能の問題)
  - [21. 非同期 API の問題](#21-非同期-api-の問題)
  - [22. バックアップ/リストアの問題](#22-バックアップリストアの問題)
- [パフォーマンス](#パフォーマンス)
  - [23. リコールまたはルールマッチングが遅い](#23-リコールまたはルールマッチングが遅い)
  - [24. 大規模データベースの最適化](#24-大規模データベースの最適化)
- [アップグレードと移行](#アップグレードと移行)
  - [25. アップグレードの破壊的変更](#25-アップグレードの破壊的変更)
- [ヘルプ](#ヘルプ)

---

## クイック診断

`carrymem doctor` を実行して全体のヘルスチェックを行います。`--fix` で自動修復、`--json` で構造化出力。

**出力の読み方：**

| チェック項目 | ok | warn | fail | 関連イシュー |
|---|---|---|---|---|
| `python_version` | ≥ 3.9 | — | < 3.9 | [#4](#4-pip-インストール失敗) |
| `carrymem_import` | インポート可能 | — | ImportError | [#2](#2-インポートエラー) |
| `config_dir` | 存在 | 欠落 | — | [#1](#1-cli-コマンドが見つからない) |
| `database_file` | 存在 | 欠落 | — | [#6](#6-リコール結果なし) |
| `db_integrity` | 合格 | — | 失敗 | [#9](#9-データベース破損) |
| `db_permissions` | 書込可能 | — | 読取専用 | [#22](#22-バックアップリストアの問題) |
| `disk_space` | > 1 GB | < 1 GB | < 0.1 GB | [#24](#24-大規模データベースの最適化) |
| `db_lock` | ロックなし | ロック中 | — | [#8](#8-データベースがロックされている) |
| `write_permissions` | 書込可能 | — | 拒否 | [#22](#22-バックアップリストアの問題) |
| `optional_deps` | 全インストール | 欠落 | — | [#16](#16-暗号化復号エラー), [#19](#19-tui-表示の問題) |
| `fts5` | サポート | — | 非サポート | [#6](#6-リコール結果なし) |
| `security` | 利用可能 | — | 利用不可 | [#16](#16-暗号化復号エラー), [#17](#17-パス検証エラー) |
| `mcp_configs` | 検出 | 未検出 | — | [#14](#14-mcp-連携が動作しない) |
| `memory_count` | > 0 | 0 | — | [#5](#5-メモリが保存されない) |
| `rules_engine` | アクティブ | 古い | — | [#10](#10-ルールが注入されない), [#11](#11-ルールスコープの競合) |
| `auto_inject` | 有効 | 無効 | — | [#10](#10-ルールが注入されない) |
| `cli_path` | PATH上 | PATH外 | — | [#1](#1-cli-コマンドが見つからない) |

---

## エラーメッセージ索引

| エラーメッセージ | イシュー |
|---|---|
| `command not found: carrymem` | [#1](#1-cli-コマンドが見つからない) |
| `No module named 'carrymem'` | [#2](#2-インポートエラー) |
| `No module named 'carrymem'` | [#2](#2-インポートエラー) |
| `carrymem version が間違ったバージョンを表示` | [#3](#3-バージョンの不一致) |
| `error: externally-managed-environment` | [#4](#4-pip-インストール失敗) |
| `should_remember: False` | [#5](#5-メモリが保存されない) |
| `recall_memories が空のリストを返す` | [#6](#6-リコール結果なし) |
| `sqlite3.OperationalError: database is locked` | [#8](#8-データベースがロックされている) |
| `database disk image is malformed` | [#9](#9-データベース破損) |
| `No matching rules found` | [#10](#10-ルールが注入されない) |
| `Scope conflict detected` | [#11](#11-ルールスコープの競合) |
| `Skill signature mismatch` | [#12](#12-skill-検証失敗) |
| `ValueError: Path traversal` | [#17](#17-パス検証エラー) |
| `ValueError: Path escapes allowed directory` | [#17](#17-パス検証エラー) |
| `HMAC verification failed` | [#16](#16-暗号化復号エラー) |
| `ImportError: No module named 'cryptography'` | [#16](#16-暗号化復号エラー) |
| `ImportError: No module named 'textual'` | [#19](#19-tui-表示の問題) |
| `RuntimeError: Cannot be used across threads` | [#21](#21-非同期-api-の問題) |
| `Connection refused (MCP)` | [#14](#14-mcp-連携が動作しない) |
| `FTS5 module not found` | [#6](#6-リコール結果なし) |

---

## インストールとセットアップ

### 1. CLI コマンドが見つからない

**重大度**: 🟡 警告  
**doctor チェック**: `cli_path`, `config_dir`

**問題**: `carrymem` コマンドが "command not found" を返す

**原因**: pip が `carrymem` スクリプトを PATH にない Python bin ディレクトリにインストールした。

**クイック修正**（どこでも動作）:
```bash
python3 -m carrymem.cli version
```

**標準修正**:

**macOS** — Python bin を見つけて PATH に追加:
```bash
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"
# 出力パスを ~/.zshrc に追加：
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
source ~/.zshrc
carrymem version
```

**Linux** — ユーザー bin を PATH に追加:
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

**Windows (ネイティブ PowerShell)**:
```powershell
pip install carrymem
python -m carrymem.cli version
```

**詳細修正** — 上記が機能しない場合、pipx で隔離インストール:
```bash
pipx install carrymem
carrymem version
```

**検証**:
```bash
carrymem doctor
# cli_path が ok を表示
```

---

### 2. インポートエラー

**重大度**: 🔴 クリティカル  
**doctor チェック**: `carrymem_import`

**問題**: `ImportError: No module named 'carrymem'` または `No module named 'carrymem'`

**エラー例**:
```
ModuleNotFoundError: No module named 'carrymem'
```

**原因**: CarryMem が現在の Python 環境にインストールされていない。

**クイック修正**:
```bash
pip install carrymem
```

**標準修正**:

1. 使用中の Python を確認:
   ```bash
   which python3
   python3 --version
   ```

2. 正しい Python にインストール:
   ```bash
   python3 -m pip install carrymem
   ```

3. 開発用（編集可能インストール）:
   ```bash
   cd /path/to/carrymem
   pip install -e .
   ```

4. 互換インポートパスを使用:
   ```python
   from carrymem import CarryMem  # from carrymem と同等
   ```

**詳細修正** — 仮想環境の競合:
```bash
# 仮想環境がアクティブか確認
source .venv/bin/activate  # または conda activate myenv
pip install carrymem

# 複数の Python バージョンがある場合、明示的なパスを使用
/usr/bin/python3.11 -m pip install carrymem
```

**検証**:
```bash
python3 -c "from carrymem import CarryMem; print('OK')"
carrymem doctor
# carrymem_import が ok を表示
```

---

### 3. バージョンの不一致

**重大度**: 🟡 警告  
**doctor チェック**: `carrymem_import`

**問題**: `carrymem version` が間違ったバージョンを表示、または `pip show carrymem` と異なる

**原因**: 異なる環境に複数のインストール、または古いキャッシュ。

**クイック修正**:
```bash
pip install --force-reinstall carrymem
```

**標準修正**:

1. インストール済みバージョンを確認:
   ```bash
   pip show carrymem
   carrymem version
   python3 -c "from carrymem.__version__ import __version__; print(__version__)"
   ```

2. バージョンが異なる場合、クリーンアップ:
   ```bash
   pip uninstall carrymem -y
   pip install carrymem
   ```

**詳細修正** — 複数の Python 環境:
```bash
# 全 carrymem インストールを検索
find / -name "__version__.py" -path "*/carrymem/*" 2>/dev/null

# 古いものを削除して再インストール
pipx install --force carrymem
```

**検証**:
```bash
carrymem version
# 0.2.2 を表示
```

---

### 4. pip インストール失敗

**重大度**: 🔴 クリティカル  
**doctor チェック**: `python_version`, `carrymem_import`

**問題**: `pip install carrymem` がエラーで失敗

**エラー例**:
```
error: externally-managed-environment
× This environment is externally managed
```

**原因**: システム Python が保護されている（PEP 668）、依存関係の競合、またはネットワーク問題。

**クイック修正**:
```bash
pip install --user carrymem
```

**標準修正**:

1. externally-managed-environment エラー（Ubuntu 23.04+, Fedora 38+）:
   ```bash
   # オプション A: pipx を使用（推奨）
   pipx install carrymem

   # オプション B: 仮想環境を使用
   python3 -m venv ~/carrymem-env
   source ~/carrymem-env/bin/activate
   pip install carrymem
   ```

2. 依存関係の競合:
   ```bash
   pip install carrymem --no-deps
   pip install click rich prompt-toolkit
   ```

3. ネットワーク/プロキシ問題:
   ```bash
   pip install carrymem --proxy http://proxy:port
   pip install carrymem -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

**詳細修正** — Python バージョンが古い:
```bash
# CarryMem は Python >= 3.9 が必要
python3 --version
# 3.9 未満の場合、pyenv または OS パッケージマネージャーで新しい Python をインストール
```

**検証**:
```bash
carrymem version
carrymem doctor
# python_version と carrymem_import が ok を表示
```

---

## コアメモリ操作

### 5. メモリが保存されない

**重大度**: 🟡 警告  
**doctor チェック**: `memory_count`, `rules_engine`

**問題**: `classify_and_remember()` が `should_remember: False` を返す、または `carrymem add` が保存されない

**原因**: コンテンツが記憶する価値なしと分類された（曖昧、重複、重要度低）。

**クイック修正**:
```bash
carrymem add "あなたのコンテンツ" --force
```

**標準修正**:

1. コンテンツが最低要件を満たすか確認（≥ 3 文字、重複なし）:
   ```bash
   carrymem add "すべてのエディタでダークモードを好む" --type user_preference
   ```

2. 現在のメモリ数を確認:
   ```bash
   carrymem stats
   ```

3. 明示的なタイプで分類を改善:
   ```bash
   carrymem add "コンテンツ" --type user_preference
   # タイプ: user_preference, decision, correction, task_pattern, sentiment_marker, identity
   ```

**詳細修正** — 分類ロジックのデバッグ:
```python
from carrymem import CarryMem
cm = CarryMem()
result = cm.classify_and_remember("コンテンツ")
print(result)
# 確認: memory_type, should_remember, importance_score, reason
cm.close()
```

**検証**:
```bash
carrymem stats
carrymem doctor
# memory_count が ok (> 0) を表示
```

---

### 6. リコール結果なし

**重大度**: 🟡 警告  
**doctor チェック**: `fts5`, `memory_count`

**問題**: `recall_memories()` または `carrymem search` が空の結果を返す

**原因**: FTS5 が利用不可、メモリが未保存、またはクエリが一致しない。

**クイック修正**:
```bash
carrymem search "クエリ" --limit 10
```

**標準修正**:

1. FTS5 サポートを確認:
   ```bash
   carrymem doctor
   # fts5 が ok を表示
   ```

2. メモリ数を確認:
   ```bash
   carrymem stats
   # 0 の場合、まずメモリを追加
   carrymem add "テストメモリ"
   ```

3. より広範なクエリを試行:
   ```bash
   carrymem search "モード"
   # 「VS Code のダークモード設定」のような具体的すぎるクエリではなく
   ```

**詳細修正** — FTS5 が利用不可:
```bash
# SQLite FTS5 サポートを確認
python3 -c "import sqlite3; print(sqlite3.sqlite_version); conn = sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(c)')"

# FTS5 が利用不可の場合、SQLite FTS5 サポート付きで Python を再ビルド
# Ubuntu: sudo apt install python3-full
# macOS: brew install python@3.11
```

**検証**:
```bash
carrymem search "test"
carrymem doctor
# fts5 と memory_count が ok を表示
```

---

### 7. メモリ分類エラー

**重大度**: 🔵 情報  
**doctor チェック**: `rules_engine`

**問題**: メモリが間違ったタイプに分類される（例: decision が task_pattern に分類される）

**原因**: ルールエンジンパターンが一致しない、またはデフォルト分類器が誤認識。

**クイック修正**:
```bash
carrymem add "コンテンツ" --type user_preference
```

**標準修正**:

1. アクティブなルールを確認:
   ```bash
   carrymem rules list
   ```

2. ユースケースに固有のルールを追加:
   ```bash
   carrymem rules add --trigger "好む" --action "user_preference として分類"
   ```

3. 既存のルールを編集:
   ```bash
   carrymem rules edit <rule-id>
   ```

**検証**:
```bash
carrymem rules check
carrymem doctor
# rules_engine が ok を表示
```

---

### 8. データベースがロックされている

**重大度**: 🔴 クリティカル  
**doctor チェック**: `db_lock`

**問題**: `sqlite3.OperationalError: database is locked`

**エラー例**:
```
sqlite3.OperationalError: database is locked
```

**原因**: 別のプロセスがデータベースを使用中、または古いロックファイルが残存。

**クイック修正**:
```bash
pkill -f carrymem
```

**標準修正**:

1. 他の CarryMem インスタンスを終了:
   ```bash
   pkill -f carrymem
   ```

2. 古い WAL/SHM ファイルを削除:
   ```bash
   rm -f ~/.carrymem/memories.db-shm ~/.carrymem/memories.db-wal
   ```

3. 診断を実行:
   ```bash
   carrymem doctor
   ```

**詳細修正** — 持続的なロック:

CarryMem は並列読み取りに SQLite WAL モードを使用。ロックが続く場合:

1. ゾンビプロセスを確認:
   ```bash
   lsof ~/.carrymem/memories.db
   ```

2. WAL チェックポイントを強制:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.carrymem/memories.db')
   conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   conn.close()
   "
   ```

3. MCP サーバーが実行中の場合、再起動:
   ```bash
   carrymem serve
   ```

**検証**:
```bash
carrymem doctor
# db_lock が ok を表示
```

---

### 9. データベース破損

**重大度**: 🔴 クリティカル  
**doctor チェック**: `db_integrity`

**問題**: `database disk image is malformed` または `PRAGMA integrity_check` が失敗

**エラー例**:
```
sqlite3.DatabaseError: database disk image is malformed
```

**原因**: 異常終了、ディスクフル、またはハードウェアエラーで SQLite ファイルが破損。

**クイック修正**:
```bash
carrymem doctor --fix
```

**標準修正**:

1. **まずバックアップ**:
   ```bash
   cp ~/.carrymem/memories.db ~/.carrymem/memories.db.bak
   ```

2. 整合性チェックを実行:
   ```bash
   carrymem doctor
   # db_integrity が fail を表示
   ```

3. 復旧を試行:
   ```bash
   python3 -c "
   import sqlite3
   conn = sqlite3.connect('$HOME/.carrymem/memories.db')
   result = conn.execute('PRAGMA integrity_check').fetchone()
   print(f'整合性: {result[0]}')
   conn.close()
   "
   ```

**詳細修正** — データベースの完全再構築:
```bash
# 復旧可能なデータをエクスポート
carrymem export ~/carrymem_backup.json

# 破損したデータベースを削除
rm ~/.carrymem/memories.db

# 再初期化（carrymem doctor --fix で再作成）
carrymem doctor --fix

# データを再インポート
carrymem import ~/carrymem_backup.json
```

**検証**:
```bash
carrymem doctor
# db_integrity が ok を表示
```

---

## ルールエンジン

### 10. ルールが注入されない

**重大度**: 🟡 警告  
**doctor チェック**: `rules_engine`, `auto_inject`

**問題**: ルールは存在するが AI プロンプトに注入されない

**原因**: 自動注入が無効、または現在のコンテキストに一致するルールがない。

**クイック修正**:
```bash
export CARRYMEM_AUTO_INJECT=true
```

**標準修正**:

1. ルールの状態を確認:
   ```bash
   carrymem rules list
   carrymem rules check
   ```

2. ルールマッチングを確認:
   ```bash
   carrymem match-rules "シーンの説明"
   ```

3. 自動注入を恒久的に有効化:
   ```bash
   echo 'export CARRYMEM_AUTO_INJECT=true' >> ~/.zshrc
   source ~/.zshrc
   ```

**詳細修正** — ルールの優先度とスコープ:
```bash
# ルールが一時停止されていないか確認
carrymem rules list
# status: paused を探す

# 一時停止されたルールを再開
carrymem rules resume <rule-id>

# スコープ優先度を確認: company > negotiated > personal
carrymem rules stats
```

**検証**:
```bash
carrymem doctor
# rules_engine が ok を表示
# auto_inject が ok（有効）を表示
```

---

### 11. ルールスコープの競合

**重大度**: 🔵 情報  
**doctor チェック**: `rules_engine`

**問題**: 異なるスコープ（company/negotiated/personal）のルールが競合

**原因**: スコープ優先度は company > negotiated > personal。上位スコープのルールが個人ルールを上書きする可能性。

**クイック修正**:
```bash
carrymem rules list
# 各ルールのスコープを確認
```

**標準修正**:

1. スコープ別にルールを表示:
   ```bash
   carrymem rules list
   # 各ルールの scope フィールドを確認
   ```

2. 適切なスコープでルールを作成:
   ```bash
   carrymem add-rule --trigger "コーディングスタイル" --action "4スペースインデントを使用"
   ```

3. 競合を確認:
   ```bash
   carrymem rules check
   ```

**詳細修正** — スコープ優先度の理解:

| スコープ | 優先度 | ユースケース |
|----------|--------|-------------|
| `company` | 最高 | 組織全体の標準 |
| `negotiated` | 中 | チームレベルの合意 |
| `personal` | 最低 | 個人の好み |

同じトリガーの `company` スコープルールは常に `personal` スコープルールを上書きします。

**検証**:
```bash
carrymem rules stats
carrymem doctor
# rules_engine が ok を表示
```

---

### 12. Skill 検証失敗

**重大度**: 🟡 警告  
**doctor チェック**: `security`

**問題**: `skill-verify` が署名の不一致を返す

**エラー例**:
```
Skill signature mismatch: expected abc123..., got def456...
```

**原因**: Skill ファイルが署名後に変更された、または SHA-256 ハッシュが一致しない。

**クイック修正**:
```bash
carrymem skill-verify <skillファイル>
# 出力の詳細を確認
```

**標準修正**:

1. Skill ファイルが改ざんされていないか確認:
   ```bash
   carrymem skill-verify <skillファイル>
   ```

2. Skill の作成者の場合、再パック:
   ```bash
   carrymem skill-pack my-skill.json --name "my-skill"
   ```

3. バージョン互換性を確認:
   ```bash
   carrymem version
   # パッカーと検証者が同じバージョンを使用していることを確認
   ```

**検証**:
```bash
carrymem skill-verify <skillファイル>
# valid を表示
```

---

### 13. ルール提案の品質

**重大度**: 🔵 情報  
**doctor チェック**: `rules_engine`

**問題**: `suggest-rules` が低品質または無関係な提案を生成

**原因**: 検出されたメモリパターンが不足、または `--min-count` 閾値が低すぎる。

**クイック修正**:
```bash
carrymem suggest-rules --min-count 5
```

**標準修正**:

1. 最小出現回数閾値を上げる:
   ```bash
   carrymem suggest-rules --min-count 5
   ```

2. メモリタイプでフィルタ:
   ```bash
   carrymem suggest-rules --type user_preference
   carrymem suggest-rules --type correction
   ```

3. レビューして選択的に承認:
   ```bash
   carrymem suggest-rules
   # 各提案をレビュー、その後:
   carrymem suggest-rules --accept  # 全て承認
   ```

**詳細修正** — 提案品質の改善:

提案は繰り返しのメモリパターンから生成されます。品質改善のヒント：
- より詳細なメモリを追加（「Xが好き」だけでなく）
- メモリ追加時に明示的な `--type` を使用
- suggest 実行前に少なくとも 3-5 件の類似メモリを確保

**検証**:
```bash
carrymem suggest-rules --min-count 5
# 関連する提案を表示
```

---

## MCP 連携

### 14. MCP 連携が動作しない

**重大度**: 🟡 警告  
**doctor チェック**: `mcp_configs`

**問題**: AI ツール（Cursor、Claude Code）が CarryMem ツールを認識しない

**原因**: MCP 設定ファイルが見つからない、または不正。

**クイック修正**:
```bash
carrymem setup-mcp --tool cursor
# または
carrymem setup-mcp --tool claude-code
```

**標準修正**:

1. ツールのセットアップを実行:
   ```bash
   carrymem setup-mcp --tool cursor
   carrymem setup-mcp --tool claude-code
   ```

2. セットアップ後に AI ツールを再起動

3. MCP 設定ファイルの存在を確認:
   ```bash
   # Cursor
   cat .cursor/mcp.json
   # Claude Code
   cat .claude/mcp.json
   ```

4. 設定内容を確認:
   ```json
   {
     "mcpServers": {
       "carrymem": {
         "command": "python3",
         "args": ["-m", "carrymem.integration.layer2_mcp"]
       }
     }
   }
   ```

**詳細修正** — 手動 MCP 設定:

`setup-mcp` が動作しない場合、手動で設定を作成:

```bash
# Cursor
mkdir -p .cursor
cat > .cursor/mcp.json << 'EOF'
{
  "mcpServers": {
    "carrymem": {
      "command": "python3",
      "args": ["-m", "carrymem.integration.layer2_mcp"]
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
      "args": ["-m", "carrymem.integration.layer2_mcp"]
    }
  }
}
EOF
```

**検証**:
```bash
carrymem doctor
# mcp_configs が ok（検出）を表示
```

---

### 15. MCP ツールタイムアウト

**重大度**: 🟡 警告  
**doctor チェック**: `mcp_configs`

**問題**: MCP ツール呼び出しがタイムアウトまたは応答なし

**原因**: MCP サーバープロセスが実行されていない、または Python インポートに時間がかかる。

**クイック修正**:
```bash
# AI ツールを再起動（新しい MCP サーバープロセスが起動）
```

**標準修正**:

1. MCP サーバーを手動テスト:
   ```bash
   python3 -m carrymem.integration.layer2_mcp
   # エラーなく起動するはず
   ```

2. プロセスが実行中か確認:
   ```bash
   ps aux | grep layer2_mcp
   ```

3. インポートエラーを確認:
   ```bash
   python3 -c "from carrymem.integration.layer2_mcp import mcp; print('OK')"
   ```

**詳細修正** — 初回インポートの遅延:

初回 MCP 呼び出しは Python モジュールの読み込みで遅くなる場合があります。プレウォーム:
```bash
# シェル起動スクリプトに追加
python3 -c "from carrymem import CarryMem" &
```

**検証**:
```bash
carrymem doctor
# mcp_configs が ok を表示
```

---

## セキュリティと暗号化

### 16. 暗号化/復号エラー

**重大度**: 🔴 クリティカル  
**doctor チェック**: `security`, `optional_deps`

**問題**: 暗号化または復号が失敗、または HMAC 検証が失敗

**エラー例**:
```
ImportError: No module named 'cryptography'
HMAC verification failed
```

**原因**: `cryptography` パッケージが未インストール、または暗号化データが改ざんされた。

**クイック修正**:
```bash
pip install cryptography
```

**標準修正**:

1. cryptography パッケージをインストール:
   ```bash
   pip install cryptography
   ```

2. セキュリティモジュールの可用性を確認:
   ```bash
   carrymem doctor
   # security が ok を表示
   # optional_deps に cryptography がインストール済みと表示
   ```

3. HMAC 検証が失敗する場合、データが改ざんされた可能性:
   ```bash
   carrymem doctor
   # db_integrity が ok を表示
   ```

**詳細修正** — キー変更後の再暗号化:

暗号化キーを変更した場合、古いデータは新しいキーで復号できません:
```bash
# まず未暗号化データをエクスポート（まだアクセス可能な場合）
carrymem export backup.json

# 再初期化
rm ~/.carrymem/memories.db
carrymem doctor --fix

# 再インポート
carrymem import backup.json
```

**検証**:
```bash
carrymem doctor
# security と optional_deps が ok を表示
```

---

### 17. パス検証エラー

**重大度**: 🟡 警告  
**doctor チェック**: `security`

**問題**: `ValueError: Path traversal` または `ValueError: Path escapes allowed directory`

**エラー例**:
```
ValueError: Path traversal: system directory not allowed: /etc/passwd
```

**原因**: 指定されたパスが CarryMem が安全上の理由でブロックするシステムディレクトリに解決される。

**クイック修正**:
```bash
# ホームディレクトリ内のパスを使用
carrymem export ~/my_export.json
```

**標準修正**:

1. 安全な出力パスを使用:
   ```bash
   carrymem export ~/carrymem_backup.json
   carrymem import ~/carrymem_backup.json
   ```

2. 特定のディレクトリにエクスポートする必要がある場合、ホーム内であることを確認:
   ```bash
   mkdir -p ~/backups
   carrymem export ~/backups/memories.json
   ```

3. ブロックされるシステムディレクトリ: `/etc`, `/usr`, `/bin`, `/sbin`, `/System`, `/Library`, `/private/etc`

**検証**:
```bash
carrymem export ~/test_export.json && echo "OK" && rm ~/test_export.json
```

---

## 高度な機能

### 18. Obsidian アダプターの問題

**重大度**: 🔵 情報  
**doctor チェック**: `config_dir`

**問題**: Obsidian vault の接続または同期が失敗

**原因**: Vault パスが未設定、またはファイル権限が読み書きを妨げている。

**クイック修正**:
```bash
carrymem doctor
# config_dir の状態を確認
```

**標準修正**:

1. vault パスの存在を確認:
   ```bash
   ls -la /path/to/your/obsidian/vault
   ```

2. ファイル権限を確認:
   ```bash
   chmod u+rw /path/to/your/obsidian/vault
   ```

3. アダプターを再設定:
   ```python
   from carrymem import CarryMem
   cm = CarryMem(storage_adapter="obsidian", vault_path="/path/to/vault")
   cm.close()
   ```

**検証**:
```bash
carrymem doctor
# config_dir が ok を表示
```

---

### 19. TUI 表示の問題

**重大度**: 🔵 情報  
**doctor チェック**: `optional_deps`

**問題**: `carrymem tui` が正しく表示されない、またはクラッシュする

**エラー例**:
```
ImportError: No module named 'textual'
```

**原因**: `textual` パッケージが未インストール、またはターミナルがリッチ出力をサポートしていない。

**クイック修正**:
```bash
pip install textual
```

**標準修正**:

1. textual をインストール:
   ```bash
   pip install textual
   ```

2. ターミナル互換性を確認:
   ```bash
   echo $TERM
   echo $COLORTERM
   # xterm-256color と truecolor（または 24bit）を表示
   ```

3. 明示的なターミナル設定で試行:
   ```bash
   TERM=xterm-256color carrymem tui
   ```

**詳細修正** — ターミナルが非対応:

ターミナルがリッチ出力をサポートしていない場合:
```bash
# TUI の代わりに CLI コマンドを使用
carrymem list
carrymem search "クエリ"
carrymem rules list
```

**検証**:
```bash
carrymem doctor
# optional_deps に textual がインストール済みと表示
```

---

### 20. VS Code 拡張機能の問題

**重大度**: 🔵 情報  
**doctor チェック**: `carrymem_import`, `cli_path`

**問題**: VS Code 拡張機能が CarryMem に接続できない

**原因**: 拡張機能が CarryMem Python モジュールまたは CLI を見つけられない。

**クイック修正**:
```bash
carrymem doctor
# carrymem_import と cli_path が両方 ok を表示
```

**標準修正**:

1. VS Code ターミナルから CarryMem にアクセスできるか確認:
   ```bash
   carrymem version
   ```

2. 拡張機能の Python パス設定を確認:
   - VS Code 設定を開く
   - "carrymem" を検索
   - Python パスが CarryMem がインストールされた環境を指していることを確認

3. 拡張機能を再インストール:
   ```bash
   code --install-extension vscode-carrymem-0.2.2.vsix
   ```

**詳細修正** — VS Code の Python パス:

VS Code がターミナルと異なる Python を使用している場合:
```bash
# CarryMem がインストールされた Python を見つける
which python3
python3 -c "import carrymem; print(carrymem.__file__)"

# VS Code でこの Python を設定
# コマンドパレット → Python: Select Interpreter → 正しいものを選択
```

**検証**:
```bash
carrymem doctor
# carrymem_import と cli_path が ok を表示
```

---

### 21. 非同期 API の問題

**重大度**: 🔵 情報  
**doctor チェック**: `carrymem_import`

**問題**: 非同期 API 呼び出しが `RuntimeError` またはイベントループエラーで失敗

**エラー例**:
```
RuntimeError: Cannot be used across threads
RuntimeError: Event loop is closed
```

**原因**: CarryMem の SQLite 接続はスレッドセーフではない。非同期呼び出しは同じイベントループを使用する必要がある。

**クイック修正**:
```python
import asyncio
from carrymem import CarryMem

async def main():
    cm = CarryMem()
    result = await cm.classify_and_remember_async("コンテンツ")
    print(result)
    cm.close()

asyncio.run(main())
```

**標準修正**:

1. すべての非同期呼び出しが同じイベントループ内であることを確認:
   ```python
   # 正しい
   async def app():
       cm = CarryMem()
       result = await cm.classify_and_remember_async("コンテンツ")
       cm.close()

   # 間違い — イベントループ外で CarryMem を作成しない
   cm = CarryMem()  # 同期接続が作成される
   result = await cm.classify_and_remember_async("コンテンツ")  # 失敗する可能性
   ```

2. CarryMem インスタンスをスレッド間で共有しない:
   ```python
   # 各スレッドは独自のインスタンスを作成
   def worker():
       cm = CarryMem()
       result = cm.classify_and_remember("コンテンツ")
       cm.close()
   ```

**検証**:
```python
python3 -c "
import asyncio
from carrymem import CarryMem
async def test():
    cm = CarryMem()
    print('非同期 API 利用可能:', hasattr(cm, 'classify_and_remember_async'))
    cm.close()
asyncio.run(test())
"
```

---

### 22. バックアップ/リストアの問題

**重大度**: 🟡 警告  
**doctor チェック**: `db_permissions`, `write_permissions`, `disk_space`

**問題**: `carrymem export` または `carrymem import` が失敗

**原因**: 権限不足、ディスクフル、または無効なファイル形式。

**クイック修正**:
```bash
carrymem export ~/backup.json
```

**標準修正**:

1. 書き込み権限を確認:
   ```bash
   carrymem doctor
   # write_permissions と db_permissions が ok を表示
   ```

2. ディスク容量を確認:
   ```bash
   carrymem doctor
   # disk_space が ok を表示
   ```

3. インポート時に正しいマージ戦略を使用:
   ```bash
   # 既存メモリをスキップ（デフォルト）
   carrymem import ~/backup.json --merge skip_existing

   # 既存メモリを上書き
   carrymem import ~/backup.json --merge overwrite
   ```

**検証**:
```bash
carrymem stats
carrymem doctor
# 全チェックが ok を表示
```

---

## パフォーマンス

### 23. リコールまたはルールマッチングが遅い

**重大度**: 🟡 警告  
**doctor チェック**: `database_file`, `disk_space`

**問題**: メモリリコールまたはルールマッチングが著しく遅い

**原因**: データベースが大きくなった、期限切れメモリが蓄積、または FTS インデックスが古い。

**クイック修正**:
```bash
carrymem clean --expired --force
```

**標準修正**:

1. 期限切れメモリをクリーン:
   ```bash
   carrymem clean --expired --dry-run  # まずプレビュー
   carrymem clean --expired --force
   ```

2. データベースサイズを確認:
   ```bash
   carrymem doctor
   # database_file がサイズを表示
   ```

3. 最適化を実行:
   ```python
   from carrymem import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   ```

**詳細修正** — 手動 VACUUM とインデックス再構築:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('$HOME/.carrymem/memories.db')
conn.execute('VACUUM')
print('VACUUM 完了')
conn.close()
"
```

**検証**:
```bash
carrymem search "test" --limit 5
# 高速に結果を返す（< 1 秒）
```

---

### 24. 大規模データベースの最適化

**重大度**: 🔵 情報  
**doctor チェック**: `database_file`, `disk_space`

**問題**: データベースが 100 MB を超え、操作が常に遅い

**原因**: 大量のメモリとルールが定期的なメンテナンスなしに蓄積。

**クイック修正**:
```bash
carrymem clean --expired --force
carrymem clean --quality 0.3 --force
```

**標準修正**:

1. データベースサイズとメモリ数を確認:
   ```bash
   carrymem doctor
   carrymem stats
   ```

2. 低品質および期限切れメモリをクリーン:
   ```bash
   carrymem clean --expired --dry-run
   carrymem clean --quality 0.3 --dry-run
   carrymem clean --expired --quality 0.3 --force
   ```

3. データベースを VACUUM:
   ```python
   from carrymem import CarryMem
   cm = CarryMem()
   cm.optimize()
   cm.close()
   ```

**詳細修正** — 古いデータのアーカイブ:

非常に大きなデータベースの場合、アーカイブを検討:
```bash
# 古いメモリをエクスポート
carrymem export ~/archive_$(date +%Y%m%d).json

# アクティブデータベースからクリーン
carrymem clean --expired --force
```

**検証**:
```bash
ls -lh ~/.carrymem/memories.db
# クリーンアップ後に大幅に小さくなる
```

---

## アップグレードと移行

### 25. アップグレードの破壊的変更

**重大度**: 🔵 情報  
**doctor チェック**: `carrymem_import`

**問題**: CarryMem のアップグレード後、既存のコードや CLI コマンドの動作が変わる

**原因**: バージョン間の API または CLI の変更。

**クイック修正**:
```bash
# チェンジログを確認
pip show carrymem
# 参照: https://github.com/lulin70/carrymem/blob/main/CHANGELOG.md
```

**標準修正**:

1. 現在のバージョンを確認:
   ```bash
   carrymem version
   ```

2. CHANGELOG で破壊的変更を確認:
   ```bash
   # 参照: リポジトリルートの CHANGELOG.md
   ```

3. 互換インポートパスを使用:
   ```python
   # v0.2.2+ では両方動作
   from carrymem import CarryMem
   from carrymem import CarryMem
   ```

4. 個別コマンドの代わりに `carrymem rules` ハブを使用:
   ```bash
   # 新方式（推奨）
   carrymem rules list
   carrymem rules add --trigger "..." --action "..."
   carrymem rules match "シーン"

   # 旧方式（動作するが非推奨）
   carrymem list-rules
   carrymem add-rule --trigger "..." --action "..."
   carrymem match-rules "シーン"
   ```

**詳細修正** — API 安定性リファレンス:

安定、実験的、非推奨 API の完全なリストは [API_STABILITY.md](../API_STABILITY.md) を参照。

**検証**:
```bash
carrymem doctor
# 全チェックが ok を表示
```

---

## ヘルプ

- **診断**: `carrymem doctor` — 問題に遭遇したらまず実行
- **GitHub Issues**: https://github.com/lulin70/carrymem/issues
- **ドキュメント**: https://github.com/lulin70/carrymem
- **チェンジログ**: [CHANGELOG.md](../../CHANGELOG.md)
- **API 安定性**: [API_STABILITY.md](../API_STABILITY.md)
