# CarryMem 安裝指南

## 系統需求

- **Python**: ≥3.12（64 位元）
- **作業系統**: macOS、Linux、Windows（建議 WSL2）
- **磁碟空間**: 套件約 10MB，每個資料庫約 1MB
- **選用**: Node.js 18+（用於 VS Code 擴充功能）

## 安裝方式

### 1. PyPI 安裝（建議）

```bash
pip install carrymem
```

驗證安裝：
```bash
carrymem version
```

**如果出現 `command not found`**，表示 pip 指令碼目錄不在 PATH 中。修正方法：

**macOS**：
```bash
# 找到你的 Python bin 目錄
python3 -c "import os, sys; print(os.path.join(os.path.dirname(sys.executable), '..', 'bin'))"

# 新增到 PATH（將此行加入 ~/.zshrc）
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

# 重新載入
source ~/.zshrc

# 驗證
carrymem version
```

**Linux**：
```bash
# 新增到 PATH（將此行加入 ~/.bashrc）
export PATH="$HOME/.local/bin:$PATH"

# 重新載入
source ~/.bashrc

# 驗證
carrymem version
```

**通用替代方案**：
```bash
python3 -m carrymem.cli version
```

> ⚠️ **套件名稱與匯入名稱**：安裝時使用 `pip install carrymem`，匯入時使用 `from carrymem import CarryMem` 或 `from carrymem import CarryMem`。

### 2. 開發模式安裝

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
```

執行測試：
```bash
pytest
```

### 3. VS Code 擴充功能

```bash
cd extensions/vscode-carrymem
npm install
npm run compile
```

然後在 VS Code 中：擴充功能 →「從 VSIX 安裝」，或按 F5 以偵錯模式執行。

## 設定

### 環境變數

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `CARRYMEM_DB_PATH` | `~/.carrymem/memories.db` | 資料庫檔案路徑 |
| `CARRYMEM_ENCRYPTION_KEY` | 無 | Fernet 加密金鑰 |

### VS Code 設定

```json
{
  "carrymem.dbPath": "~/.carrymem/memories.db",
  "carrymem.autoMatch": false,
  "carrymem.defaultScope": "personal"
}
```

## 驗證

執行安裝驗證測試套件：

```bash
python -m pytest tests/test_rules/test_installation.py -v
```

驗證內容：
- 所有模組可匯入
- 版本號正確
- 資料庫支援 scope 欄位初始化
- CLI skill 指令已註冊
- VS Code 擴充功能檔案存在
- 完整生命週期冒煙測試通過

## 常見問題

### 「Module not found: carrymem」

PyPI 套件名稱是 `carrymem`，但匯入名稱是 `carrymem`：
```python
from carrymem import CarryMem  # 正確
from carrymem import CarryMem  # 錯誤
```

### 「carrymem 命令未找到」

確保 `~/.local/bin`（或同等路徑）在 PATH 中：
```bash
pip install --user carrymem
export PATH="$HOME/.local/bin:$PATH"
```

### 資料庫權限錯誤

確保對資料庫目錄有寫入權限：
```bash
mkdir -p ~/.carrymem
chmod 755 ~/.carrymem
```
