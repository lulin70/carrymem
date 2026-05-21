# CarryMem 安装指南

## 系统要求

- **Python**: 3.9+
- **操作系统**: macOS、Linux、Windows（推荐 WSL2）
- **磁盘**: 包体约 10MB，每个数据库约 1MB
- **可选**: Node.js 18+（用于 VS Code 扩展）

## 安装方式

### 1. PyPI 安装（推荐）

```bash
pip install carrymem
```

验证安装：
```bash
carrymem version
```

**如果提示 `command not found`**，说明 pip 脚本目录不在 PATH 中。修复方法：

**macOS**：
```bash
# 添加到 ~/.zshrc
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# 重新加载
source ~/.zshrc

# 验证
carrymem version
```

**Linux**：
```bash
# 添加到 ~/.bashrc
export PATH="$HOME/.local/bin:$PATH"

# 重新加载
source ~/.bashrc
```

**通用替代方案**：
```bash
python3 -m carrymem.cli version
```

> ⚠️ **包名与导入名**：安装用 `pip install carrymem`，导入用 `from carrymem import CarryMem` 或 `from carrymem import CarryMem`。

### 2. 开发模式安装

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
pip install -e ".[dev]"
```

运行测试：
```bash
pytest
```

### 3. VS Code 扩展

```bash
cd extensions/vscode-carrymem
npm install
npm run compile
```

然后在 VS Code 中：扩展 → "从 VSIX 安装"，或按 F5 以调试模式运行。

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `CARRYMEM_DB_PATH` | `~/.carrymem/memories.db` | 数据库文件路径 |
| `CARRYMEM_ENCRYPTION_KEY` | 无 | Fernet 加密密钥 |

### VS Code 设置

```json
{
  "carrymem.dbPath": "~/.carrymem/memories.db",
  "carrymem.autoMatch": false,
  "carrymem.defaultScope": "personal"
}
```

## 验证

运行安装验证测试套件：

```bash
python -m pytest tests/test_rules/test_installation.py -v
```

验证内容：
- 所有模块可导入
- 版本号正确
- 数据库支持 scope 字段初始化
- CLI skill 命令已注册
- VS Code 扩展文件存在
- 完整生命周期冒烟测试通过

## 常见问题

### "Module not found: carrymem"

PyPI 包名是 `carrymem`，但导入名是 `carrymem`：
```python
from carrymem import CarryMem  # 正确
from carrymem import CarryMem  # 错误
```

### "carrymem 命令未找到"

确保 `~/.local/bin`（或等效路径）在 PATH 中：
```bash
pip install --user carrymem
export PATH="$HOME/.local/bin:$PATH"
```

### 数据库权限错误

确保对数据库目录有写权限：
```bash
mkdir -p ~/.carrymem
chmod 755 ~/.carrymem
```
