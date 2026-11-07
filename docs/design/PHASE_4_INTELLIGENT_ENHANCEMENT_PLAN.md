# Phase 4: 智能增强层（可选LLM支持）

**日期**: 2026-11-07  
**版本**: v0.12.0（计划）  
**设计原则**: LLM作为可选增强，保持核心功能零依赖

---

## 设计哲学

### 核心原则

**✅ 保持不变**：
1. 便携性优先（单SQLite文件）
2. 本地优先（离线可用）
3. 零强制依赖（核心功能无需API key）

**✅ 新增能力**：
1. 可选LLM增强（提升质量，非必需）
2. 本地LLM优先（Ollama/LM Studio）
3. 优雅降级（无LLM时自动回退基于规则实现）

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────┐
│  Tier 3: 云端LLM增强（可选）              │
│  OpenAI GPT-4, Anthropic Claude         │
│  - 需要API key                          │
│  - 网络依赖                             │
└─────────────────────────────────────────┘
              ↓ 降级
┌─────────────────────────────────────────┐
│  Tier 2: 本地LLM增强（推荐）              │
│  Ollama, LM Studio, llama.cpp           │
│  - 无需API key                          │
│  - 完全离线                             │
└─────────────────────────────────────────┘
              ↓ 降级
┌─────────────────────────────────────────┐
│  Tier 1: 核心功能（零依赖）               │
│  基于规则、模式匹配、FTS5                │
│  - 无需LLM                              │
│  - 保证基础可用性                        │
└─────────────────────────────────────────┘
```

### 功能矩阵

| 功能 | 无LLM (Tier 1) | 本地LLM (Tier 2) | 云端LLM (Tier 3) |
|------|---------------|-----------------|-----------------|
| **classify_and_remember** | ✅ 规则分类（7类） | ✅ LLM辅助分类 | ✅ GPT-4精确分类 |
| **recall_memories** | ✅ FTS5 + BM25 | ✅ 语义扩展 | ✅ 嵌入优化 |
| **suggest_rules** | ✅ 频率模式识别 | ✅ 本地推理建议 | ✅ GPT-4智能建议 |
| **summarize_and_store** | ✅ 模板式摘要 | ✅ 本地模型总结 | ✅ Claude长文本总结 |
| **build_system_prompt** | ✅ 模板拼接 | ✅ 上下文优化 | ✅ 动态提示工程 |
| **知识图谱抽取** | ✅ 正则规则 | ✅ NER模型 | ✅ GPT-4关系抽取 |

---

## Phase 4 任务清单

### 4.1 本地LLM集成（P0，必做）

**目标**: 支持Ollama/LM Studio，保持离线可用

**子任务**:
1. ✅ 创建`LLMClient`抽象层
2. ✅ 实现Ollama provider
3. ✅ 实现LM Studio provider
4. ✅ 自动检测本地LLM可用性
5. ✅ 零配置降级到Tier 1

**验收标准**:
- 无Ollama/LM Studio时，功能正常（Tier 1）
- 检测到本地LLM时，自动启用增强
- 无需用户配置API key
- 完全离线运行

**预估时间**: 3-4天

---

### 4.2 LLM驱动的高级功能（P1，推荐）

#### 4.2.1 智能规则建议（suggest_rules）

**Tier 1实现**（无LLM）:
```python
def suggest_rules_pattern_based(memories: List[Memory]) -> List[Rule]:
    """基于频率模式识别建议规则"""
    # 1. 统计高频关键词共现
    # 2. 识别"总是"、"从不"等模式
    # 3. 提取"当...则..."结构
    return suggested_rules
```

**Tier 2实现**（本地LLM）:
```python
def suggest_rules_local_llm(memories: List[Memory], llm: LLMClient) -> List[Rule]:
    """使用本地LLM推理行为模式"""
    prompt = f"""分析以下记忆，提取行为规则：
    {format_memories(memories)}
    
    输出格式：trigger → action"""
    
    return llm.generate(prompt, model="llama3:8b")
```

**Tier 3实现**（云端LLM）:
```python
def suggest_rules_gpt4(memories: List[Memory], llm: LLMClient) -> List[Rule]:
    """使用GPT-4深度分析"""
    # 多轮对话、反思、验证
    return llm.chat(messages, model="gpt-4")
```

#### 4.2.2 会话总结（summarize_and_store）

**Tier 1实现**（模板式）:
- 按type分组
- 提取关键词
- 模板拼接

**Tier 2实现**（本地LLM）:
- Ollama llama3总结
- 保留关键上下文

**Tier 3实现**（Claude）:
- Claude 3长文本总结
- 结构化输出

**预估时间**: 2-3天

---

### 4.3 优雅降级机制（P0，必做）

**设计**:
```python
class CarryMem:
    def __init__(self, llm_provider: Optional[str] = None, **config):
        # 1. 尝试检测本地LLM
        self.llm = self._init_llm(llm_provider, config)
        
        # 2. 选择实现tier
        self.tier = self._determine_tier(self.llm)
        
        # 3. 根据tier选择功能实现
        self._select_implementations()
    
    def _determine_tier(self, llm: Optional[LLMClient]) -> int:
        if llm is None:
            return 1  # 零依赖
        if llm.is_local:
            return 2  # 本地LLM
        return 3      # 云端LLM
    
    def suggest_rules(self, **kwargs):
        if self.tier == 1:
            return self._suggest_rules_pattern_based(**kwargs)
        elif self.tier == 2:
            return self._suggest_rules_local_llm(**kwargs)
        else:
            return self._suggest_rules_gpt4(**kwargs)
```

**测试场景**:
- ✅ 无LLM环境：所有功能正常（Tier 1）
- ✅ Ollama环境：自动启用增强（Tier 2）
- ✅ API key环境：使用云端API（Tier 3）
- ✅ Ollama停止运行：自动降级到Tier 1

**预估时间**: 1-2天

---

### 4.4 云端LLM可选支持（P2，可选）

**仅当用户显式配置时启用**:
```python
# 用户需要主动提供API key
cm = CarryMem(
    llm_provider="openai",
    llm_config={"api_key": "sk-...", "model": "gpt-4"}
)
```

**支持的provider**:
1. OpenAI (gpt-4, gpt-3.5-turbo)
2. Anthropic (claude-3-opus, claude-3-sonnet)
3. Azure OpenAI

**预估时间**: 2天

---

### 4.5 文档更新（P1）

**新增章节**:
1. `docs/LLM_INTEGRATION_GUIDE.md`
   - 三层架构说明
   - 本地LLM安装指南（Ollama/LM Studio）
   - 云端API配置（可选）
   - 降级行为说明

2. `USER_GUIDE.md`更新
   - 标注哪些功能有LLM增强
   - 展示Tier 1 vs Tier 2 vs Tier 3差异

3. `README.md`更新
   - 强调"零依赖核心 + 可选增强"
   - 本地LLM推荐配置

**预估时间**: 1天

---

## 依赖管理

### pyproject.toml调整

```toml
[project.optional-dependencies]
# 核心依赖（无变化）
language = ["pycld2>=0.41", "langdetect>=1.0.9"]
semantic = ["sqlite-vec>=0.1.0", "sentence-transformers>=5.6.0"]

# 新增：本地LLM支持（推荐）
llm-local = [
    "ollama>=0.1.0",
    "requests>=2.31.0",
]

# 新增：云端LLM支持（可选）
llm-cloud = [
    "openai>=1.0.0",
    "anthropic>=0.18.0",
]

# 完整LLM支持
llm = [
    "carrymem[llm-local]",
    "carrymem[llm-cloud]",
]
```

### 安装指南

```bash
# Tier 1: 零依赖安装（推荐大多数用户）
pip install carrymem

# Tier 2: 本地LLM增强（推荐高级用户）
pip install carrymem[llm-local]
# 然后安装Ollama: https://ollama.ai

# Tier 3: 云端LLM支持（可选）
pip install carrymem[llm-cloud]
# 需要配置API key
```

---

## 性能指标

### 预期延迟对比

| 操作 | Tier 1 (无LLM) | Tier 2 (本地) | Tier 3 (云端) |
|------|---------------|--------------|--------------|
| classify_and_remember | 0.5ms | 50-200ms | 500-2000ms |
| suggest_rules | 10ms | 1-5s | 2-10s |
| summarize_and_store | 5ms | 2-10s | 5-30s |

**结论**: Tier 1保持超低延迟（<10ms），适合高频操作

---

## 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 用户误以为必须有LLM | 高 | 文档强调可选性，默认Tier 1 |
| 本地LLM资源消耗大 | 中 | 提供轻量模型推荐（llama3:8b） |
| 云端API成本 | 中 | 仅在显式配置时启用，提供token估算 |
| 降级逻辑复杂 | 低 | 充分测试三层降级场景 |

---

## 测试策略

### 单元测试

```python
def test_tier1_no_llm():
    """无LLM时所有功能正常"""
    cm = CarryMem()  # 无llm_provider
    assert cm.tier == 1
    assert cm.suggest_rules() is not None  # 基于规则

def test_tier2_local_llm():
    """本地LLM自动检测"""
    with mock_ollama_running():
        cm = CarryMem()
        assert cm.tier == 2

def test_tier3_cloud_api():
    """云端API显式配置"""
    cm = CarryMem(llm_provider="openai", llm_config={"api_key": "sk-..."})
    assert cm.tier == 3

def test_graceful_degradation():
    """LLM失败时自动降级"""
    cm = CarryMem(llm_provider="ollama")
    with mock_ollama_failure():
        result = cm.suggest_rules()  # 应降级到Tier 1
        assert result is not None
```

### E2E测试

- ✅ 完全离线环境（Tier 1验证）
- ✅ Ollama环境（Tier 2验证）
- ✅ OpenAI环境（Tier 3验证）
- ✅ Ollama运行中突然停止（降级验证）

---

## 发布计划

### v0.12.0-alpha（Phase 4.1-4.3）

**包含**:
- 本地LLM集成（Ollama/LM Studio）
- 优雅降级机制
- suggest_rules三层实现
- 基础文档

**不包含**:
- 云端API支持（延后到beta）

### v0.12.0-beta（Phase 4.4）

**新增**:
- OpenAI/Claude支持
- 完整LLM文档
- 性能基准对比

### v0.12.0（正式版）

**条件**:
- 三层架构测试通过
- 文档完整
- 社区反馈良好

---

## 成功标准

**Phase 4完成标记** ✅：
1. ✅ 无LLM时100%功能可用（Tier 1）
2. ✅ 本地LLM自动检测和启用（Tier 2）
3. ✅ 云端API可选配置（Tier 3）
4. ✅ 降级逻辑测试覆盖率>90%
5. ✅ 文档明确标注"可选增强"
6. ✅ README突出"零依赖核心"

---

## 下一步

**立即执行** Phase 4.1:
1. 创建`src/carrymem/llm/`目录结构
2. 实现`LLMClient`抽象基类
3. 实现`OllamaProvider`
4. 添加自动检测逻辑
5. 编写Tier 1降级测试

**预计完成时间**: 3-4天

---

**设计负责人**: Kiro AI  
**审核状态**: 待用户确认  
**日期**: 2026-11-07
