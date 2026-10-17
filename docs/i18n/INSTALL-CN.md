# CarryMem 安装指南

## 系统要求

- **Python**: ≥3.12（64 位）
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
export PATH="$HOME/Library/Python/3.12/bin:$PATH"

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
python3 -m carrymem version
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
| `CARRYMEM_DB_PATH` | `~/.carrymem/memories.db` | CLI 和 Python API 使用的数据库文件路径 |
| `CARRYMEM_DATA_PATH` | 未设置 | 传给 MCP 服务的数据库文件路径；手动配置 MCP 时应设置为同一个数据库文件 |
| `CARRYMEM_ENCRYPTION_KEY` | 无 | Fernet 加密密钥 |

### VS Code 设置

```json
{
  "carrymem.dbPath": "~/.carrymem/memories.db",
  "carrymem.defaultScope": "personal"
}
```

## MCP 客户端配置

CarryMem 通过 MCP 接入客户端。不需要把 CarryMem 安装为 Skill。配置 MCP 后重启客户端，再在客户端对话框中使用自然语言。

### 配置 CLI 支持的客户端

```bash
carrymem init
carrymem setup-mcp --all --global
carrymem doctor
```

`--all` 只配置 setup 命令支持的客户端。配置后重启客户端。

### 手动配置 Workbuddy

CarryMem 当前不会自动修改 Workbuddy 配置。请把下面的服务加入 Workbuddy 的 MCP 配置文件（通常是 `~/.workbuddy/mcp.json`），并保留已有服务：

```json
{
  "mcpServers": {
    "carrymem": {
      "command": "carrymem",
      "args": ["mcp"],
      "env": {
        "CARRYMEM_DATA_PATH": "/Users/你的用户名/.carrymem/memories.db"
      }
    }
  }
}
```

如果 `carrymem` 不在 PATH 中，请使用包含 CarryMem 的 Python 绝对路径：

```json
{
  "command": "/你的 Python 绝对路径",
  "args": ["-m", "carrymem.integration.layer2_mcp"]
}
```

保存后重启 Workbuddy。在客户端对话框中验证：

```text
请调用 CarryMem 的 health_check，检查服务是否正常。
请记住：我偏好使用 PostgreSQL。
```

开启新对话后查询：

```text
请查询 CarryMem，告诉我偏好使用什么数据库。
```

要保持对记忆的控制，请先查询并取得 `storage_key`，再执行：

```text
请查询 CarryMem，显示 PostgreSQL 偏好的 storage_key、来源、作用域和版本。
请调用 update_memory，使用这个 storage_key，把偏好修改为：我在本地开发中偏好使用 SQLite。
请调用 get_memory_history，查询这个 storage_key 的版本历史。
请调用 forget_memory 删除这个 storage_key，然后再次查询，确认它已经消失。
```

CarryMem 当前支持记忆修改、版本历史、删除和导出/导入。当前没有统一的“记忆级暂停”操作；不要把规则暂停和记忆暂停混淆。

### 可选向量模型

CarryMem 可能会尝试下载用于语义搜索的可选向量模型。如果因为设备离线或模型服务不可用而下载失败，CarryMem 仍可使用基于规则的分类和 SQLite FTS5 搜索。这个警告不会阻止安装、MCP、记忆写入、召回、修改、历史、删除、备份或恢复。只有在需要下载或使用可选向量模型时才需要网络连接。

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
