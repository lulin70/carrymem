# CarryMem インストールガイド

**バージョン**: v0.4.1

---

## 必要条件

- **Python**: 3.12 以上（64 ビット）
- **OS**: macOS、Linux、Windows (WSL2)
- **ディスク容量**: 10 MB 以上

---

## インストール

### 基本インストール

```bash
pip install carrymem
```

> ⚠️ **パッケージ名とインポート名**: `pip install carrymem` でインストール、`from carrymem import CarryMem` または `from carrymem import CarryMem` でインポート。v1.0.0 で統一予定。

### pipxを使用（推奨）

```bash
pipx install carrymem
```

### 仮想環境にインストール

```bash
python3 -m venv carrymem-env
source carrymem-env/bin/activate
pip install carrymem
```

---

## インストール確認

### 1. バージョン確認

```bash
carrymem version
```

期待される出力：
```
CarryMem v0.4.1
```

### 2. インポート確認

```python
python3 -c "from carrymem import CarryMem; print('OK')"
```

### 3. インストール検証テスト

```bash
python -m pytest tests/test_rules/test_installation.py -v
```

検証内容：
- すべてのモジュールがインポート可能
- CLIコマンドが登録済み
- データベースが初期化可能

---

## 初期設定

### 初期化

```bash
carrymem init
```

作成されるもの：
- `~/.carrymem/config.json` — 設定ファイル
- `~/.carrymem/memories.db` — SQLiteデータベース

### ヘルスチェック

```bash
carrymem doctor
```

すべての項目が `ok` であることを確認してください。

---

## PATH設定

### `carrymem`コマンドが見つからない場合

pipは`carrymem`スクリプトをPythonのbinディレクトリにインストールしますが、このディレクトリがPATHに含まれていない場合があります。

**macOS**:
```bash
echo 'export PATH="$HOME/Library/Python/3.12/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Linux**:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (WSL2)**:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (ネイティブ)**:
```powershell
python -m carrymem.cli version
```

### PATH確認

```bash
carrymem doctor
# cli_path が ok を表示すれば正しく設定されています
```

---

## オプション依存関係

### 暗号化サポート

```bash
pip install cryptography
```

### 言語検出

```bash
pip install pycld2 langdetect
```

### ターミナルUI

```bash
pip install textual
```

### すべてのオプション依存関係をインストール

```bash
pip install carrymem[all]
```

---

## MCP統合セットアップ

### Cursor用

```bash
carrymem setup-mcp --tool cursor
```

Cursorを再起動すると、CarryMemツールが利用可能になります。

### Claude Code用

```bash
carrymem setup-mcp --tool claude-code
```

### 両方に設定

```bash
carrymem setup-mcp --tool all
```

---

## トラブルシューティング

インストールに関する問題は[トラブルシューティングガイド](../TROUBLESHOOTING.md)を参照してください。

一般的な問題：
- **command not found**: PATH設定を確認
- **ImportError**: Pythonバージョンと仮想環境を確認
- **データベースエラー**: `carrymem doctor --fix` を実行

---

## アップグレード

```bash
pip install --upgrade carrymem
```

アップグレード後：
```bash
carrymem doctor
```

---

## アンインストール

```bash
pip uninstall carrymem
```

データを保持する場合、`~/.carrymem/` ディレクトリは手動で削除する必要があります：

```bash
rm -rf ~/.carrymem
```
