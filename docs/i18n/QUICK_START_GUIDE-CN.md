# CarryMem 快速入门指南

**5 分钟上手 CarryMem**

---

## CarryMem 是什么？

CarryMem 让 AI 记住你，而不是反过来。

**一句话**：跨模型、跨工具、跨设备的 AI 记忆层。

**核心价值**：
- 🧠 AI 自动记住你的偏好、纠正和决策
- 🔄 记忆可移植 — 切换工具不丢数据
- ⚡ 60%+ 零成本分类 — 不浪费 Token

---

## 安装

```bash
pip install carrymem
```

验证安装：
```bash
carrymem version
```

---

## 首次设置

### 1. 初始化（30 秒）

```bash
carrymem init
```

创建：
- 配置文件：`~/.carrymem/config.json`
- 数据库：`~/.carrymem/memories.db`

### 2. 存储第一条记忆（1 分钟）

```python
from carrymem import CarryMem

with CarryMem() as cm:
    cm.classify_and_remember("我偏好深色模式")
    cm.classify_and_remember("我用 PostgreSQL 做数据库")
    cm.classify_and_remember("我在东京的一家创业公司工作")
```

### 3. 查看记忆（30 秒）

```bash
carrymem list
```

或用代码：
```python
with CarryMem() as cm:
    memories = cm.recall_memories(query="数据库")
    for mem in memories:
        print(f"{mem['type']}: {mem['content']}")
```

### 4. 查看统计（30 秒）

```bash
carrymem stats
```

---

## 核心功能

### 自动分类

CarryMem 自动识别 7 种记忆类型：

```python
with CarryMem() as cm:
    # 偏好
    cm.classify_and_remember("我偏好深色模式")
    # → type: user_preference

    # 纠正
    cm.classify_and_remember("不，我说的是 Python 3.11，不是 3.10")
    # → type: correction

    # 事实
    cm.classify_and_remember("我在一家创业公司工作")
    # → type: fact_declaration

    # 决策
    cm.classify_and_remember("前端用 React")
    # → type: decision
```

### 主动声明

告诉 AI 关于你的信息：

```python
with CarryMem() as cm:
    cm.declare("我偏好 PostgreSQL 而不是 MySQL")
    # → confidence=1.0，保证被记住
```

### 智能召回

```python
with CarryMem() as cm:
    # 精确匹配
    memories = cm.recall_memories(query="PostgreSQL")

    # 语义搜索
    memories = cm.recall_memories(query="数据库偏好")

    # 跨语言（中文存储，英文查询）
    cm.classify_and_remember("我喜欢用 PostgreSQL")
    memories = cm.recall_memories(query="database")  # 有效！
```

### 查看记忆画像

```python
with CarryMem() as cm:
    profile = cm.get_memory_profile()
    print(profile['summary'])
    # → "AI 记住了关于你的 12 件事：5 个偏好、3 个纠正、2 个决策"
```

### 记忆整合

```python
# 记忆整合（定期运行）
report = cm.consolidate(dry_run=True)  # 预览变更
print(f"发现 {report['stats']['duplicates_found']} 个重复")
report = cm.consolidate(dry_run=False)  # 执行
```

---

## 实际场景

### 场景 1：代码助手记住你的风格

```python
with CarryMem() as cm:
    # 第一次对话
    cm.classify_and_remember("我偏好 Python 中使用类型提示")
    cm.classify_and_remember("我喜欢用 dataclass 而不是 dict")

    # 下次对话，AI 自动知道你的偏好
    memories = cm.recall_memories(query="Python 编码风格")
    # AI 生成带类型提示和 dataclass 的代码
```

### 场景 2：跨工具使用

```python
# 在 Cursor 中
with CarryMem(namespace="cursor") as cm_cursor:
    cm_cursor.classify_and_remember("我偏好深色模式")

# 在 Windsurf 中，使用相同的记忆
with CarryMem(namespace="cursor") as cm_windsurf:
    memories = cm_windsurf.recall_memories(query="主题")  # 找到了！
```

### 场景 3：项目隔离

```python
# 项目 A
with CarryMem(namespace="project-a") as cm_a:
    cm_a.classify_and_remember("前端用 React")

# 项目 B
with CarryMem(namespace="project-b") as cm_b:
    cm_b.classify_and_remember("前端用 Vue")

# 互不干扰！
```

### 场景 4：携带记忆到新设备

```bash
# 在旧设备上打包（可加密）
carrymem pack --encrypt
# 输入密码后生成 carrymem_identity_20260527.carry

# 拷贝到 U盘 / 网盘 / 新机器

# 在新设备上恢复
carrymem unpack carrymem_identity_20260527.carry
# 输入密码 → 所有记忆恢复
```

### 场景 5：备份与恢复

```bash
# 手动创建备份
carrymem backup

# 查看所有备份
carrymem backup --list

# 从备份恢复
carrymem backup --restore ~/.carrymem/backups/memories_backup_20260527_103000_123456.db
```

> 💡 CarryMem 还会每 20 次写操作自动创建备份，无需手动操作。

---

## 导出和导入

### 导出记忆

```python
with CarryMem() as cm:
    cm.export_memories(output_path="my_memories.json")
    cm.export_memories(output_path="my_memories.md", format="markdown")
```

### 在新设备上导入

```python
with CarryMem() as cm_new:
    cm_new.import_memories(input_path="my_memories.json")
    # 所有记忆已恢复！
```

---

## CLI 工具

```bash
carrymem init                          # 初始化
carrymem list                          # 列出记忆
carrymem list --type user_preference   # 按类型筛选
carrymem list --limit 20               # 限制数量
carrymem stats                         # 统计
carrymem doctor                        # 健康检查
carrymem version                       # 版本信息
```

---

## 常见问题

### 数据存在哪里？
默认 `~/.carrymem/memories.db`。可以指定自定义路径。

### 数据安全吗？
数据存储在本地机器上，从不上传到任何服务器。

### 可以删除记忆吗？
可以！
```python
with CarryMem() as cm:
    cm.forget_memory(memory_id)
```

### 支持哪些语言？
中文、英文、日文，支持跨语言搜索。

### 会消耗很多 Token 吗？
不会！60%+ 的分类是零成本的，只有复杂情况才调用 LLM。

### 可以用其他数据库吗？
可以！支持 SQLite（默认）、Obsidian 和自定义适配器。

---

## 下一步

- 📖 阅读 [完整文档](../../README.md)
- 🎯 查看 [用户指南](../USER_GUIDE.md)
- 🏗️ 了解 [架构设计](../ARCHITECTURE.md)
- 🤝 贡献 [贡献指南](../../CONTRIBUTING.md)

---

## 获取帮助

- 报告问题：[GitHub Issues](https://github.com/lulin70/carrymem/issues)
- 诊断工具：`carrymem doctor`

---

**开始使用 CarryMem，让 AI 记住你！** 🚀
