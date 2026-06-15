# CarryMem 测试覆盖率提升快速执行策略

**目标**: 15.69% → 75%+ (需提升 ~60%)  
**时间**: 2-3周  
**策略**: 聚焦高价值、低覆盖率模块

---

## 📊 当前状况分析

### 覆盖率现状
- **总测试数**: 4,127个测试用例
- **当前覆盖率**: 15.69%
- **目标覆盖率**: 75%
- **缺口**: 59.31%

### 问题诊断
根据之前报告，4,127个测试用例已经存在，但覆盖率仅15.69%，说明：
1. **测试分布不均**: 部分模块过度测试，部分模块零测试
2. **测试质量问题**: 测试未真正执行代码路径
3. **模块孤立**: CLI/TUI/MCP入口点测试不足

---

## 🎯 分阶段提升计划

### Phase 1: 快速见效（1周，+30%覆盖率）

重点模块优先级：

#### P0: CLI入口点（预计+15%）
**现状**: CLI有50+命令，但入口点测试不足  
**行动**:
1. 补充 `cli/__init__.py` 主入口测试
2. 补充 `cli/_memory.py` 核心命令测试（add/list/search/forget）
3. 补充 `cli/_mcp.py` 设置命令测试（setup-mcp）
4. 补充 `cli/_rules.py` 规则命令测试

**测试清单** (预计50个测试):
```python
# tests/cli/test_cli_memory_commands.py
- test_add_command_basic()
- test_add_command_with_metadata()
- test_list_command_empty()
- test_list_command_with_filters()
- test_search_command_basic()
- test_forget_command_by_key()
- test_whoami_command()
- test_stats_command()
...
```

#### P1: 核心引擎路径（预计+10%）
**现状**: 核心Mixin有测试，但边界情况未覆盖  
**行动**:
1. 补充 `core/_classification.py` 边界测试（空输入、超长文本）
2. 补充 `core/_recall.py` 复杂查询测试（多过滤器组合）
3. 补充 `core/_maintenance.py` consolidation路径测试

**测试清单** (预计40个测试):
```python
# tests/core/test_classification_edge_cases.py
- test_classify_empty_string()
- test_classify_very_long_text()
- test_classify_special_characters()
- test_classify_multilingual_text()
...
```

#### P2: 适配器层（预计+5%）
**现状**: SQLite适配器部分测试，JSON/Obsidian适配器几乎无测试  
**行动**:
1. 补充 `adapters/json_adapter.py` 完整CRUD测试
2. 补充 `adapters/obsidian_adapter.py` 基础功能测试

**测试清单** (预计30个测试):
```python
# tests/adapters/test_json_adapter.py
- test_json_adapter_init()
- test_json_adapter_remember()
- test_json_adapter_recall()
- test_json_adapter_forget()
- test_json_adapter_file_corruption()
...
```

---

### Phase 2: 深度覆盖（1周，+20%覆盖率）

#### P0: Rules引擎（预计+12%）
**现状**: 规则引擎代码占比大，测试覆盖严重不足  
**行动**:
1. 补充 `rules/__init__.py` 规则匹配测试
2. 补充 `rules/storage.py` 规则存储测试
3. 补充 `rules/candidate_generator.py` 规则生成测试

**测试清单** (预计60个测试):
```python
# tests/rules/test_rule_engine_core.py
- test_add_rule_basic()
- test_rule_matching_exact()
- test_rule_matching_fuzzy()
- test_rule_priority_ordering()
- test_rule_scope_filtering()
...
```

#### P1: Layers层（预计+8%）
**现状**: Pattern分析器、语义分类器测试不足  
**行动**:
1. 补充 `layers/pattern_analyzer.py` 模式识别测试
2. 补充 `layers/semantic_classifier.py` 分类测试

**测试清单** (预计40个测试):
```python
# tests/layers/test_pattern_analyzer.py
- test_analyze_preference_pattern()
- test_analyze_correction_pattern()
- test_analyze_decision_pattern()
...
```

---

### Phase 3: 长尾清理（1周，+10%覆盖率）

#### P0: 工具集合（预计+5%）
**现状**: 监控、插件、i18n等新增模块测试不足  
**行动**:
1. 补充 `monitoring/__init__.py` 测试
2. 补充 `plugins/__init__.py` 插件加载测试
3. 补充 `i18n/__init__.py` 翻译测试

#### P1: 安全模块（预计+3%）
**现状**: 加密、审计测试部分完成  
**行动**:
1. 补充 `security/encryption.py` 密钥轮换测试
2. 补充 `security/audit.py` 审计查询测试

#### P2: 工具类（预计+2%）
**现状**: utils下各模块测试零散  
**行动**:
1. 补充 `utils/helpers.py` 工具函数测试
2. 补充 `utils/validators.py` 验证器测试

---

## 🚀 实施策略

### 测试编写原则
1. **优先Happy Path**: 先覆盖正常流程
2. **再补Error Case**: 异常情况测试
3. **最后Boundary**: 边界条件测试
4. **Mock外部依赖**: 使用pytest fixtures隔离

### 效率提升技巧
1. **复用现有fixture**: `tests/conftest.py`已有carrymem/tempdir fixtures
2. **参数化测试**: 使用`@pytest.mark.parametrize`批量测试
3. **分模块运行**: 避免全量测试超时
4. **CI并行**: 使用pytest-xdist并行执行

### 验证方法
```bash
# 单模块覆盖率检查
pytest tests/cli/ --cov=carrymem.cli --cov-report=term-missing

# 增量覆盖率检查
pytest tests/cli/ tests/core/ --cov=carrymem --cov-report=html
open htmlcov/index.html

# 快速验证（不生成报告）
pytest tests/cli/ -x --tb=short
```

---

## 📈 预期结果

| Phase | 时间 | 新增测试数 | 覆盖率提升 | 累计覆盖率 |
|-------|------|------------|------------|------------|
| Phase 1 | 1周 | ~120个 | +30% | ~45% |
| Phase 2 | 1周 | ~100个 | +20% | ~65% |
| Phase 3 | 1周 | ~80个 | +10% | **75%+** ✅ |
| **总计** | **3周** | **~300个** | **+59.31%** | **75%+** |

---

## ⚠️ 风险与应对

### 风险1: 测试运行超时
- **现象**: 4,127个测试全量运行需10分钟+
- **应对**: 分模块运行，CI并行执行

### 风险2: 覆盖率统计不准确
- **现象**: 新增测试未正确统计覆盖率
- **应对**: 使用`--cov-append`累积覆盖，检查`.coverage`文件

### 风险3: 测试依赖冲突
- **现象**: 新测试影响现有测试
- **应对**: 使用独立fixture，`--forked`隔离进程

---

## 🎯 立即行动项

### 本周任务（Phase 1启动）
1. ✅ 创建 `tests/cli/test_cli_memory_commands.py`（50个测试）
2. ✅ 创建 `tests/core/test_classification_edge_cases.py`（40个测试）
3. ✅ 创建 `tests/adapters/test_json_adapter.py`（30个测试）
4. ✅ 运行验证：`pytest tests/cli tests/core tests/adapters --cov=carrymem`

### 成功标准
- Phase 1结束覆盖率达到 45%+
- 所有新增测试通过
- CI pipeline保持绿色

---

## 📚 参考资源

- **现有测试模板**: `tests/core/test_memory_crud_coverage.py`
- **Fixture定义**: `tests/conftest.py`
- **覆盖率报告**: `htmlcov/index.html` (运行pytest后生成)
- **pytest文档**: https://docs.pytest.org/

---

**负责人**: DevSquad  
**审核人**: 项目维护者  
**更新日期**: 2026-06-15
