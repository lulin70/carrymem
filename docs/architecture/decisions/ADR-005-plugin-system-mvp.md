# ADR-005: 插件系统 MVP

## 状态: 已采纳
## 日期: 2026-06-11
## 决策者: CarryMem 核心团队

---

## 上下文

CarryMem 作为 AI 记忆中间件，需要具备**可扩展性**以支持多样化的集成场景：

- **通知推送**：记忆存储后发送到 Slack/Telegram/邮件。
- **外部同步**：与 Obsidian、Notion 等知识库双向同步。
- **自定义处理**：企业用户可能有特定的数据处理合规要求。
- **分析增强**：接入外部 LLM 进行更深入的记忆分析。

插件系统需要在**轻量级 MVP** 和**未来可扩展**之间取得平衡。过度设计会增加核心代码复杂度，而过于简陋则无法满足实际需求。

## 候选方案

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A: Hook 点 + 动态加载** ✅ | 定义固定钩子点；插件目录扫描 .py 文件动态导入 | 实现简单；无需额外框架；插件开发门槛低 | 钩子点固定，灵活性有限；无沙箱隔离 |
| **B: pluggy (pytest 插件框架)** | 复用 pytest 的 pluggy 框架 | 成熟稳定；支持 hookspec/hookimpl 声明 | 引入重量级依赖；API 设计受 pluggy 约束 |
| **C: stevedore (OpenStack 风格)** | 基于 entry_points 的插件发现 | 标准 Python 打包方式；pip install 即装即用 | 配置较复杂；需要 setup.py/config 配合 |
| **D: MCP 工具扩展** | 仅通过 MCP 协议扩展 | 与 AI 生态天然融合 | 仅限于 MCP 场景；本地 CLI 无法使用 |

## 决策

**采用方案 A：基于 Hook 点 + 动态加载的轻量级插件系统 MVP。**

核心组件：

```
plugins/
├── __init__.py                 # PluginProtocol + PluginManager + HookPoint
└── example_notification_plugin.py  # 示例插件
```

### PluginProtocol（插件契约）

```python
@runtime_checkable
class PluginProtocol(Protocol):
    """所有 CarryMem 插件必须实现的协议。"""
    name: str           # 唯一标识符
    version: str        # 语义版本号

    def on_load(self, carrymem: Any) -> None:
        """插件加载时调用（传入 CarryMem 实例引用）。"""
        ...

    def on_unload(self) -> None:
        """插件卸载时调用。"""
        ...
```

### HookPoint（钩子点定义）

| 钩子点 | 触发时机 | 参数 | 用途 |
|--------|---------|------|------|
| `on_memory_stored` | 记忆成功存储后 | key, content, memory_type | 通知推送、日志记录 |
| `on_memory_recalled` | 记忆被召回后 | query, results | 分析增强、访问统计 |
| `on_classified` | 记忆分类完成后 | content, classification | 自定义分类后处理 |
| `on_error` | 错误发生时 | error_code, message | 错误告警、监控上报 |

### PluginManager（生命周期管理）

```python
class PluginManager:
    def discover(plugin_dir) -> List[str]      # 扫描目录发现插件
    def load(name) -> PluginProtocol           # 动态导入并加载
    def unload(name) -> None                   # 卸载并清理
    def dispatch(hook_name, **kwargs) -> List  # 事件分发
    def list_plugins() -> Dict                 # 查询状态
```

### 设计约束（MVP 边界）

1. **同步执行**：钩子处理器同步串行执行，不引入异步。
2. **无沙箱**：插件与主进程在同一 Python 解释器中运行（信任模型）。
3. **无热加载**：加载/卸载需要重启或手动调用。
4. **无依赖管理**：插件自行负责其依赖。
5. **错误隔离**：单个插件异常不影响主流程和其他插件。

## 后果

### 正面
- **极低门槛**：编写一个插件只需创建一个 `.py` 文件并实现 2 个方法。
- **零外部依赖**：不引入 pluggy/stevedore 等框架，保持 CarryMem 轻量。
- **清晰的扩展点**：4 个精心选择的钩子点覆盖了主要的事件流。
- **线程安全**：PluginManager 使用 RLock 保护内部状态。
- **示例驱动**：随附 `example_notification_plugin.py` 降低上手难度。

### 负面
- **钩子点有限**：MVP 只有 4 个钩子点，可能无法满足所有扩展需求。新增钩子点需要改核心代码。
- **无隔离机制**：恶意或有 bug 的插件可能影响主进程稳定性（删除文件、耗尽内存等）。
- **无版本协商**：插件无法声明其兼容的 CarryMem 版本范围。
- **无依赖声明**：插件无法声明其所需的第三方库。
- **发现机制简单**：仅支持目录扫描，不支持 entry_points 或远程注册表。

### 未来演进方向（超出 MVP 范围）
- 引入 **HookRegistry** 支持插件自定义注册新钩子点。
- 增加 **插件元数据**（requires、author、license 等字段）。
- 支持 **entry_points 发现** 以支持 `pip install carrymem-plugin-xxx`。
- 考虑 **进程级隔离**（subprocess 或 threading with resource limits）。
- 引入 **插件权限系统**（白名单式 API 访问控制）。
