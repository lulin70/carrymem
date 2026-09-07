# CarryMem 入口点功能对照表

> 版本: v0.10.1 | 更新日期: 2026-09-07
> 目标: 确保 CLI/TUI/MCP 三入口功能对等、文案一致

## 一、入口概述

| 入口 | 文件位置 | 启动方式 | 用途 |
|------|----------|----------|------|
| **CLI** | `src/carrymem/cli/__init__.py` | `carrymem <command>` | 命令行完整功能入口 |
| **TUI** | `src/carrymem/tui.py` | `carrymem tui` | 终端图形界面（基于 Textual） |
| **MCP** | `src/carrymem/cli/_mcp.py` + `integration/layer2_mcp/` | `carrymem mcp` / `carrymem serve` | AI 工具集成协议 |

## 二、核心功能矩阵

### 2.1 记忆管理 (Memory Operations)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **存储记忆** | `add` / `remember` / `save` | ✅ (a 键) | `classify_and_remember` | 三入口均支持 |
| **列出记忆** | `list` / `ls` | ✅ (主界面) | `recall_memories` | 三入口均支持 |
| **搜索记忆** | `search` / `find` | ✅ (/ 或 s 键) | `recall_memories` (带 query) | 三入口均支持 |
| **查看详情** | `show` / `get` | ✅ (Enter 键) | ❌ (返回完整数据) | TUI 有弹窗展示 |
| **编辑记忆** | `edit` / `update` | ✅ (e 键) | ❌ | **仅 CLI/TUI** |
| **删除记忆** | `forget` / `delete` / `rm` | ✅ (d 键) | `forget_memory` | 三入口均支持 |
| **清理过期** | `clean` / `consolidate` | ❌ | `consolidate_memories` | **仅 CLI/MCP** |

### 2.2 规则引擎 (Rules Engine)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **添加规则** | `rules add` | ❌ | `add_rule` | **仅 CLI/MCP** |
| **列出规则** | `rules list` / `rules` | ❌ | `list_rules` / `my_rules` | **仅 CLI/MCP** |
| **匹配规则** | `rules match` | ❌ | `match_rules` / `inject_rules` | **仅 CLI/MCP** |
| **编辑规则** | `rules edit` | ❌ | `update_rule` | **仅 CLI/MCP** |
| **删除规则** | `rules delete` | ❌ | `delete_rule` | **仅 CLI/MCP** |
| **暂停/恢复** | `rules pause` / `rules resume` | ❌ | ❌ | **仅 CLI** |
| **规则统计** | `rules stats` | ❌ | ❌ | **仅 CLI** |
| **规则检查** | `rules check` | ❌ | ❌ | **仅 CLI** |
| **导出/导入** | `rules export` / `rules import` | ❌ | ❌ | **仅 CLI** |
| **模板列表** | `rules templates` | ❌ | ❌ | **仅 CLI** |
| **建议规则** | `rules suggest` | ❌ | `suggest_rules` | **仅 CLI/MCP** |
| **规则提升** | `rules promote` | ❌ | `promote_rules` | **仅 CLI/MCP** |
| **经验学习** | `rules learn` | ❌ | ❌ | **仅 CLI** |
| **规则精炼** | `rules refine` | ❌ | ❌ | **仅 CLI** |

### 2.3 身份与统计 (Identity & Stats)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **查看身份** | `whoami` | ❌ | `my_profile` | **仅 CLI/MCP** |
| **导出身份** | `profile export` | ❌ | `my_profile` (含 memories) | **仅 CLI/MCP** |
| **统计信息** | `stats` / `status` | ✅ (侧边栏) | `my_profile` (部分) | TUI 仅显示基础统计 |
| **质量检查** | `check` | ❌ | ❌ | **仅 CLI** |
| **诊断工具** | `doctor` | ❌ | ❌ | **仅 CLI** |
| **价值报告** | `stats --value-report` | ❌ | ❌ | **仅 CLI** |

### 2.4 数据管理 (Data Management)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **备份** | `backup` | ❌ | ❌ | **仅 CLI** |
| **导出** | `export` | ❌ | ❌ | **仅 CLI** |
| **导入** | `import` | ❌ | ❌ | **仅 CLI** |
| **打包** | `pack` | ❌ | ❌ | **仅 CLI** |
| **解包** | `unpack` | ❌ | ❌ | **仅 CLI** |

### 2.5 集成与系统 (Integration & System)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **MCP 配置** | `setup-mcp` | ❌ | ❌ | **仅 CLI** |
| **MCP Server** | `mcp` (stdio) | ❌ | N/A (自身) | **仅 CLI** |
| **HTTP Server** | `serve` | ❌ | N/A (自身) | **仅 CLI** |
| **初始化** | `init` | ❌ | ❌ | **仅 CLI** |
| **教程** | `tutorial` | ❌ | `onboard` | CLI/MCP 均有，形式不同 |
| **版本信息** | `version` / `-v` | ❌ | `mce_status` | **仅 CLI/MCP**（内部诊断工具，不在 tools/list 中发布，仅可 tools/call） |
| **帮助** | `help` / `-h` | ✅ (? 键) | ❌ | TUI 有快捷键帮助 |

### 2.6 知识库 (Knowledge Base)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **索引知识** | ❌ | ❌ | `index_knowledge` | **仅 MCP** |
| **召回知识** | ❌ | ❌ | `recall_from_knowledge` | **仅 MCP** |
| **联合召回** | ❌ | ❌ | `recall_all` | **仅 MCP** |

### 2.7 高级功能 (Advanced Features)

| 功能 | CLI 命令 | TUI 支持 | MCP 工具 | 说明 |
|------|----------|----------|----------|------|
| **合并计划** | `consolidate schedule` | ❌ | `schedule_consolidation` | **仅 CLI/MCP** |
| **停止合并** | `consolidate stop` | ❌ | `stop_consolidation` | **仅 CLI/MCP** |
| **会话摘要** | ❌ | ❌ | `summarize_and_store` | **仅 MCP** |
| **技能包** | `rules pack` / `rules install` / `rules verify` | ❌ | ❌ | **仅 CLI** |

## 三、功能覆盖统计

| 入口 | 支持功能数 | 覆盖率 | 特色功能 |
|------|-----------|--------|----------|
| **CLI** | ~60+ | 100% | 完整命令行、备份恢复、数据迁移 |
| **TUI** | ~8 | ~13% | 图形化浏览、实时过滤、交互式添加 |
| **MCP** | 31 | ~52% | AI 工具原生集成、知识库、会话摘要、知识图谱 |

## 四、不一致问题清单

### 4.1 严重问题 (P0)

1. **TUI 功能严重缺失**
   - 缺少规则引擎全部操作
   - 缺少记忆编辑/删除实现
   - 缺少身份管理功能
   - 缺少数据导入导出

2. **错误码使用不统一**
   - CLI 使用 `CarryMemError.code` (CM-xxx)
   - TUI 使用自定义错误显示组件（未标准化）
   - MCP 使用字符串错误类型 (`storage_not_configured`, `internal_error` 等)
   - **建议**: 统一三入口错误码格式为 CM-xxx

### 4.2 中等问题 (P1)

3. **输出格式不统一**
   - CLI: 彩色文本 + 格式化表格
   - TUI: Textual Widget 渲染
   - MCP: JSON 结构化响应
   - **建议**: 定义统一的输出 schema 规范

4. **成功/失败反馈不一致**
   - CLI: 退出码 + 彩色消息
   - TUI: 状态栏 + 弹窗
   - MCP: `{"success": true/false, "data/error": ...}`
   - **建议**: 统一成功/失败的标准响应格式

5. **初始化流程差异**
   - CLI: 显式 `init` 命令 + 自动检测
   - TUI: 构造函数中自动初始化
   - MCP: Handlers 构造时自动初始化
   - **建议**: 统一初始化策略文档

### 4.3 低优先级 (P2)

6. **文案风格不统一**
   - CLI: 中英混合（主要中文提示）
   - TUI: 英文 UI 元素 + 中文内容
   - MCP: 英文工具名 + 多语言响应
   - **建议**: 制定多语言文案规范

7. **参数命名差异**
   - CLI: `--namespace` / `-n`
   - TUI: 构造函数参数 `namespace`
   - MCP: 参数 `namespace`
   - **基本一致**, 但文档需统一说明

8. **帮助信息完整性**
   - CLI: 完整命令参考 + 示例
   - TUI: 快捷键帮助屏
   - MCP: 无内置帮助（依赖客户端）
   - **建议**: MCP 增加 `help` 工具或元数据

## 五、改进路线图 (TODO)

### Phase 1: 统一错误处理 (1-2 天)

- [ ] **CM-ERROR-001**: 创建 `EntryPointError` 基类，统一三入口错误格式
- [ ] **CM-ERROR-002**: MCP handler 返回值增加 `code` 字段（CM-xxx 格式）
- [ ] **CM-ERROR-003**: TUI ErrorDisplay 组件增加错误码显示
- [ ] **CM-ERROR-004**: 编写跨入口错误码映射表

### Phase 2: TUI 功能补全 (3-5 天)

- [ ] **CM-TUI-001**: 实现记忆删除功能（d 键）
- [ ] **CM-TUI-002**: 添加规则管理面板（Tab 页）
- [ ] **CM-TUI-003**: 实现记忆编辑功能
- [ ] **CM-TUI-004**: 添加身份概览页面
- [ ] **CM-TUI-005**: 添加数据导入/导出对话框
- [ ] **CM-TUI-006**: 实现诊断结果可视化

### Phase 3: 输出格式标准化 (2-3 天)

- [ ] **CM-FMT-001**: 定义 `OutputSchema` 协议类
- [ ] **CM-FMT-002**: CLI 输出增加 `--json` 选项
- [ ] **CM-FMT-003**: MCP 响应增加 `schema_version` 字段
- [ ] **CM-FMT-004**: 编写输出格式转换工具函数

### Phase 4: 文案与体验优化 (持续)

- [ ] **CM-I18N-001**: 提取所有用户可见文案到 i18n 资源文件
- [ ] **CM-I18N-002**: TUI UI 元素中文化
- [ ] **CM-I18N-003**: MCP 工具描述多语言化
- [ ] **CM-I18N-004**: 编写文案一致性检查脚本

### Phase 5: 测试覆盖 (2-3 天)

- [ ] **CM-TEST-001**: 编写三入口功能对比测试矩阵
- [ ] **CM-TEST-002**: 编写跨入口行为一致性测试
- [ ] **CM-TEST-003**: 编写错误码传播链路测试
- [ ] **CM-TEST-004**: 性能基准测试（CLI vs TUI vs MCP 启动时间）

## 六、技术约束与注意事项

### 6.1 TUI 技术限制

- 依赖 `textual` 库（可选依赖）
- 不适合复杂表单操作（如规则编辑）
- 移动端/远程场景不可用
- **适用场景**: 本地快速浏览、简单操作

### 6.2 MCP 技术限制

- 无状态请求-响应模式（需考虑上下文传递）
- 受限于 AI 工具的参数类型（主要是 string）
- 无法直接访问文件系统（安全限制）
- **适用场景**: AI Agent 集成、自动化工作流

### 6.3 CLI 技术优势

- 完整功能覆盖
- 可脚本化、可管道组合
- 适合 CI/CD 和自动化
- **适用场景**: 开发者工具、运维脚本、批量操作

## 七、最佳实践建议

### 7.1 用户引导

```bash
# 新用户推荐路径
carrymem tutorial        # 5 分钟教程
carrymem init            # 初始化
carrymem add "偏好"      # 存储第一条记忆
carrymem tui             # 切换到 TUI 浏览

# 开发者推荐路径
carrymem setup-mcp       # 配置 AI 工具集成
carrymem doctor          # 运行诊断
carrymem stats           # 查看统计
```

### 7.2 AI 工具集成示例

```json
{
  "mcpServers": {
    "carrymem": {
      "command": "carrymem",
      "args": ["mcp"],
      "env": {
        "CARRYMEM_DATA_PATH": "$HOME/.carrymem/memories.db"
      }
    }
  }
}
```

---

## 附录 A: MCP 工具完整列表

| 工具名 | 类别 | 目标对象 | 状态 |
|--------|------|----------|------|
| `classify_message` | Core | engine | ✅ |
| `get_classification_schema` | Core | engine | ✅ |
| `batch_classify` | Core | engine | ✅ |
| `classify_and_remember` | Storage | carrymem | ✅ |
| `recall_memories` | Storage | carrymem | ✅ |
| `forget_memory` | Storage | carrymem | ✅ |
| `index_knowledge` | Knowledge | carrymem | ✅ |
| `recall_from_knowledge` | Knowledge | carrymem | ✅ |
| `recall_all` | Knowledge | carrymem | ✅ |
| `query_graph` | Graph | carrymem | ✅ |
| `shortest_path` | Graph | carrymem | ✅ |
| `get_memory_impact` | Graph | carrymem | ✅ |
| `declare_preference` | Profile | carrymem | ✅ |
| `get_memory_profile` | Profile | carrymem | ✅ |
| `get_system_prompt` | Prompt | carrymem | ✅ |
| `summarize_and_store` | Advanced | carrymem | ✅ |
| `consolidate_memories` | Advanced | carrymem | ✅ |
| `schedule_consolidation` | Advanced | carrymem | ✅ |
| `stop_consolidation` | Advanced | carrymem | ✅ |
| `add_rule` | Rules | rule_engine | ✅ |
| `list_rules` | Rules | rule_engine | ✅ |
| `match_rules` | Rules | rule_engine | ✅ |
| `inject_rules` | Rules | rule_engine | ✅ |
| `my_rules` | Rules | rule_engine | ✅ |
| `delete_rule` | Rules | rule_engine | ✅ |
| `suggest_rules` | Rules | rule_engine | ✅ |
| `promote_rules` | Rules | rule_engine | ✅ |
| `update_rule` | Rules | rule_engine | ✅ |
| `my_profile` | Profile | carrymem | ✅ |
| `onboard` | Guide | carrymem | ✅ |
| `health_check` | Health | carrymem | ✅ |

**总计**: 31 个 MCP 工具

## 附录 B: CLI 命令别名表

| 主命令 | 别名 | 说明 |
|--------|------|------|
| `add` | `remember`, `save` | 存储记忆 |
| `list` | `ls` | 列出记忆 |
| `search` | `find` | 搜索记忆 |
| `show` | `get` | 查看详情 |
| `edit` | `update` | 编辑记忆 |
| `forget` | `delete`, `rm` | 删除记忆 |
| `stats` | `status` | 统计信息 |
| `setup-mcp` | `init-integration` | MCP 配置 |
| `version` | `--version`, `-v` | 版本信息 |
| `help` | `--help`, `-h` | 帮助信息 |

---

*文档维护者: CarryMem Team*
*下次审查日期: 2026-07-14*
