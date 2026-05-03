# CarryMem v0.1.5 技术债务备忘录

**日期**: 2026-05-03
**状态**: v0.1.5 已修复 CRITICAL/HIGH 问题，以下为后续版本需处理的技术债务

---

## 🔒 安全（待后续版本处理）

### H-2: HTTP 服务器无速率限制
- **文件**: `integration/layer2_mcp/http_server.py`
- **问题**: 无请求频率限制，可被暴力枚举 API Key 或 DoS
- **建议**: 实现基于 IP 的令牌桶限流（每分钟 60 次）
- **优先级**: v0.2.0

### H-4: 备份文件未加密
- **文件**: `backup.py` L46-75
- **问题**: 即使主库启用加密，备份文件仍为明文
- **建议**: 备份后加密，或确保导出加密数据
- **优先级**: v0.2.0

### M-1: SSE 客户端连接数无上限
- **文件**: `http_server.py`
- **问题**: 已在 v0.1.5 添加 `_MAX_SSE_CLIENTS=100`，但需验证边界条件
- **优先级**: v0.1.6 验证

### M-2: Prompt 注入检测可被 Unicode 绕过
- **文件**: `rules/sanitizer.py` L15-40
- **问题**: 正则匹配固定模式，Unicode 同形字/零宽字符可绕过
- **建议**: NFKC 归一化 + 移除零宽字符 + 扩展模式列表
- **优先级**: v0.2.0

### M-4: list_backups 对每个文件执行 SQL 查询
- **文件**: `backup.py` L113-125
- **问题**: 恶意 SQLite 文件可利用触发器攻击
- **建议**: 验证文件头魔数 + 只读模式打开
- **优先级**: v0.2.0

### M-5: InputValidator 严格模式 HTML 转义破坏合法内容
- **文件**: `security/input_validator.py` L180-200
- **问题**: 存储时转义 `<` `>` `&`，破坏代码片段和数学表达式
- **建议**: 转义移到输出层
- **优先级**: v0.2.0

### M-6: get_stats() 返回数据库文件路径
- **文件**: `carrymem.py` L950-980
- **问题**: MCP 工具远程调用可获取服务器路径信息
- **建议**: MCP 返回中移除 db_path
- **优先级**: v0.1.6

### M-7: 加密密钥无轮换机制
- **文件**: `security/encryption.py` L97-112
- **问题**: 密钥泄露后无法更换
- **建议**: 实现密钥轮换功能
- **优先级**: v0.3.0

### L-1: InputValidator 路径遍历检测过于宽泛
- **文件**: `security/input_validator.py` L250-270
- **问题**: `r"\.\."` 匹配任何连续两个点（如 "U.S.A."）
- **建议**: 使用 `r"(?:^|[/\\])\.\.(?:$|[/\\])"` 或 `os.path.realpath`
- **优先级**: v0.2.0

### L-2: 命令注入检测仅覆盖 Unix
- **文件**: `security/input_validator.py` L280-300
- **问题**: 不覆盖 Windows 场景
- **建议**: 增加 Windows 命令注入模式
- **优先级**: v0.2.0

### L-3: obsidian_adapter 未验证 vault_path 安全性
- **文件**: `adapters/obsidian_adapter.py` L138
- **建议**: 验证路径在用户主目录或白名单内
- **优先级**: v0.2.0

### L-4: 日志记录加密失败信息
- **文件**: `adapters/sqlite_adapter.py` L187
- **建议**: 日志级别降为 DEBUG
- **优先级**: v0.1.6

### L-5: generate_memory_id 使用 random 而非 secrets
- **文件**: `utils/helpers.py` L29-32
- **建议**: 改用 `secrets.randbelow(9000) + 1000`
- **优先级**: v0.2.0

---

## ⚡ 性能（待后续版本处理）

### C4: 多处全量加载 `recall("", limit=10000)`
- **文件**: `carrymem.py` L248/1139/1439/1453
- **问题**: merge_memories/export_memories/check_conflicts/check_quality 全量加载
- **影响**: 10万条记忆 = 内存爆炸 + 10万次 importance 计算 + 10万次 UPDATE
- **建议**: 使用游标/分页迭代，提供 `_iterate_all()` 方法
- **优先级**: v0.2.0（涉及 API 变更）

### C5: `_recalculate_all_importance()` 全表逐行 UPDATE
- **文件**: `adapters/sqlite_adapter.py` L337-363
- **问题**: 迁移时 1 次 SELECT + N 次 UPDATE
- **建议**: 使用单条 SQL 表达式批量更新
- **优先级**: v0.2.0

### H4: SQLite 全局互斥锁导致读写串行化
- **文件**: `adapters/sqlite_adapter.py` L172
- **问题**: 所有操作共用一个 Lock，WAL 模式下并发读被串行化
- **建议**: 使用读写锁（ReadWriteLock）允许并发读
- **优先级**: v0.2.0（需并发测试）

### H5: `_spell_correct` 线性扫描整个词汇表
- **文件**: `semantic/expander.py` L249-275
- **问题**: O(V * L1 * L2) 复杂度
- **建议**: 缓存结果 + BK-tree/SymSpell 算法
- **优先级**: v0.2.0

### H6: `whoami()` 执行 10+ 次数据库查询
- **文件**: `carrymem.py` L1034-1050
- **建议**: 合并为一次 GROUP BY + 窗口函数查询
- **优先级**: v0.2.0

### H7: PatternAnalyzer 与 Engine 重复存储 message_history
- **文件**: `layers/pattern_analyzer.py` L10
- **建议**: 共享引用或改 deque
- **优先级**: v0.1.6

### M1: remember() 重复查询
- **文件**: `adapters/sqlite_adapter.py` L437-448
- **建议**: 第一次就 SELECT *
- **优先级**: v0.1.6

### M2: get_profile() 执行 8+ 次独立查询
- **文件**: `adapters/sqlite_adapter.py` L1029-1112
- **建议**: 合并统计查询
- **优先级**: v0.2.0

### M3: 缓存失效策略过于粗粒度
- **文件**: `adapters/sqlite_adapter.py` L429-431
- **问题**: 每次 remember/forget 都 invalidate 整个 namespace
- **建议**: 基于关键词局部失效或 TTL 过期
- **优先级**: v0.2.0

### M4: build_context() 重复匹配规则
- **文件**: `carrymem.py` L1324-1398
- **建议**: inject() 返回匹配结果复用
- **优先级**: v0.1.6

### M5: _auto_suggest_rules 和 _detect_implicit_preferences 重复查询
- **文件**: `carrymem.py` L642/685
- **建议**: 查询一次传入
- **优先级**: v0.1.6

### M6: AsyncCarryMem 使用已废弃的 get_event_loop()
- **文件**: `async_carrymem.py` L43
- **建议**: 改为 get_running_loop()
- **优先级**: v0.1.6

### M7: ClassificationPipeline 重复检测语言
- **文件**: `layers/rule_matcher.py` L34
- **建议**: 传递已检测语言给 RuleMatcher
- **优先级**: v0.1.6

### L1: _row_to_stored 每次都执行 JSON + 日期 + 解密解析
- **文件**: `adapters/sqlite_adapter.py` L1127-1210
- **建议**: RecallCache 层缓存已解析对象
- **优先级**: v0.2.0

### L2: _dict_to_stored 与 _row_to_stored 重复逻辑
- **文件**: `adapters/sqlite_adapter.py` L1212-1283
- **建议**: 提取公共方法
- **优先级**: v0.2.0

### L3: ConfigManager 每次实例化都读文件
- **文件**: `utils/config.py` L23
- **建议**: 模块级单例或类级缓存
- **优先级**: v0.2.0

### L4: RuleEngine 初始化创建 10 个子组件
- **文件**: `rules/__init__.py` L120-141
- **建议**: 懒加载
- **优先级**: v0.2.0

### L5: CarryMem() 初始化可能触发全表 importance 重算
- **文件**: `adapters/sqlite_adapter.py` L199-203
- **建议**: 改为后台异步任务
- **优先级**: v0.2.0

### L6: RuleStorage 先查全部再过滤
- **文件**: `rules/storage.py` L590-598
- **建议**: SQL 级别 WHERE 过滤
- **优先级**: v0.1.6

---

## 📝 文档（待后续版本处理）

### L12: CLI _TYPE_ICONS 含非标准类型
- **文件**: `cli.py` L49-58
- **问题**: `contextual_observation` 和 `knowledge` 不在合法类型集合中
- **优先级**: v0.1.6

### L14: 英文 RULES_USER_MANUAL 路径冗余
- **文件**: `docs/RULES_USER_MANUAL.md` L722-736
- **问题**: `../docs/ARCHITECTURE.md` 可简化为 `ARCHITECTURE.md`
- **优先级**: v0.2.0

---

## 版本规划建议

| 版本 | 重点 | 关键债务 |
|------|------|---------|
| v0.1.6 | 小修快补 | M6(get_stats路径), M1(重复查询), M4(重复匹配), M6(async), L4(日志级别), L6(SQL过滤) |
| v0.2.0 | 性能重构 | C4(全量加载), C5(全表UPDATE), H4(读写锁), H5(拼写纠正), H6(whoami查询), M2/M3(缓存优化) |
| v0.3.0 | 安全增强 | H2(速率限制), H4(备份加密), M7(密钥轮换), M2(Prompt注入) |
