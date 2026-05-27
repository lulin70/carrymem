# P0-2 实施规格文档：向量检索（sqlite-vec + sentence-transformers）

> 日期：2026-05-11
> 版本：v1.1（实施完成，验证通过）
> 前序文档：BENCHMARK_OPTIMIZATION_DECISION_v2.md
> 状态：✅ 实施完成

---

## 一、背景与目标

### 1.1 P0-1 验证结果

P0-1（Verbatim 存储 + FTS5 双索引）已完成并验证。LoCoMo 重跑结果：

| 指标 | P0-1 前 | P0-1 后 | 变化 |
|------|---------|---------|------|
| LoCoMo Overall F1 | 0.003（API 失败） | **0.241** | 首次有效数据 |
| LoCoMo Adversarial | 0.0004 | **0.996** | ✅ 优秀 |
| LoCoMo 非 Adversarial F1 | ~0.003 | **0.023** | 🔴 极低 |
| LongMemEval F1 | 0.165 | 待重跑 | — |

**结论**：P0-1 的直接提升有限（非 Adversarial 仅 2.3%），符合预期。Adversarial 99.6% 证明分类引擎+规则引擎在"判断自己不知道"上表现优秀。但 FTS5 词匹配无法解决语义检索问题，需要 P0-2。

### 1.2 P0-2 目标

解决"无语义检索能力"问题，使 CarryMem 能通过向量相似度检索到措辞不同但语义相关的记忆。

**量化目标**：

| Benchmark | 当前 F1 | P0-2 目标 F1 | 提升幅度 |
|-----------|---------|-------------|---------|
| LongMemEval | 0.165 | 0.30-0.40 | +82-143% |
| LoCoMo（非 Adversarial） | 0.023 | 0.15-0.25 | +552-987% |

**门控标准**（DevSquad 共识）：
- P0-2 完成后 F1 < 0.30 → 暂停 P0-3，评估是否换模型
- P0-2 完成后 F1 ≥ 0.30 → 继续 P0-3

---

## 二、技术方案

### 2.1 架构决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 向量存储 | sqlite-vec | SQLite 扩展，保持零外部服务依赖 |
| Embedding 模型 | all-MiniLM-L6-v2 | 80MB，384 维，英文效果好 |
| Embedding 目标 | raw_text（原文） | 原文措辞保留最完整，语义检索效果最好 |
| 安装方式 | `pip install carrymem[semantic]` | 可选依赖，不增加基础安装体积 |
| 计算时机 | 同步（写入时） | P1 再优化为异步 |
| 降级策略 | semantic 不可用时回退 FTS5 | 保证基础功能不受影响 |

### 2.2 依赖分析

**新增依赖**：

| 包 | 版本 | 大小 | 用途 | 验证状态 |
|----|------|------|------|---------|
| sqlite-vec | ≥0.1.0 | ~2MB | SQLite 向量扩展 | ✅ macOS ARM64 可用 |
| pysqlite3 | ≥0.6.0 | ~1MB | 替代 sqlite3（支持 load_extension） | ✅ macOS ARM64 可用 |
| sentence-transformers | ≥2.2.2 | ~80MB（含模型） | Embedding 计算 | ✅ 需 HF_ENDPOINT 镜像 |

**关键发现**（2026-05-11 验证）：
- Python 3.12 的 `sqlite3` 模块不支持 `load_extension`，必须使用 `pysqlite3`
- `sqlite_vec.load(db)` 需要 `db.enable_load_extension(True)`，只有 `pysqlite3` 支持
- `sentence-transformers` 首次运行需下载模型，HuggingFace 直连超时，需设置 `HF_ENDPOINT=https://hf-mirror.com`
- `all-MiniLM-L6-v2` 输出 384 维向量，模型大小 ~90MB

**传递依赖风险**：
- sentence-transformers → torch（~800MB）：PyTorch 是大依赖
- 缓解：考虑用 `onnxruntime` 替代 torch 推理（P1 优化）
- 首次运行时自动下载 all-MiniLM-L6-v2 模型（~90MB），需网络连接

### 2.3 数据库 Schema 变更

新增 sqlite-vec 虚拟表：

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
    memory_id TEXT PRIMARY KEY,
    embedding float[384]
);
```

**设计决策**：
- 使用独立虚拟表而非在 memories 表加 BLOB 列，因为 sqlite-vec 需要虚拟表格式
- `memory_id` 关联 memories.id（非 storage_key，因为 id 是 PRIMARY KEY）
- 384 维对应 all-MiniLM-L6-v2 的输出维度

### 2.4 代码改动清单

#### 2.4.1 setup.py

新增 `semantic` extras：

```python
extras_require={
    # ... 现有分组 ...
    "semantic": [
        "sqlite-vec>=0.1.0",
        "sentence-transformers>=2.2.2",
    ],
    "full": [
        # ... 现有依赖 ...
        "sqlite-vec>=0.1.0",
        "sentence-transformers>=2.2.2",
    ],
}
```

#### 2.4.2 sqlite_adapter.py

**改动 1：新增 import 和可用性检测**

```python
try:
    import sqlite_vec
    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
```

**改动 2：__init__ 新增参数**

```python
def __init__(
    self,
    db_path=None,
    namespace="default",
    enable_semantic_recall=True,
    semantic_config=None,
    enable_cache=True,
    cache_config=None,
    encryption_key=None,
    # P0-2 新增参数
    enable_vector_search=True,       # 是否启用向量检索
    embedding_model="all-MiniLM-L6-v2",  # embedding 模型名
):
```

**改动 3：__init__ 新增初始化逻辑**

```python
# P0-2: Initialize vector search
self._enable_vector = (
    enable_vector_search
    and SQLITE_VEC_AVAILABLE
    and SENTENCE_TRANSFORMERS_AVAILABLE
)
self._embedding_model_name = embedding_model
self._embedding_model = None
self._embedding_dim = 384  # all-MiniLM-L6-v2

if self._enable_vector:
    try:
        self._embedding_model = SentenceTransformer(embedding_model)
        self._embedding_dim = self._embedding_model.get_sentence_embedding_dimension()
        conn = self._get_connection()
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        self._init_vec_schema()
    except Exception as e:
        self._enable_vector = False
        logger.warning(f"Vector search initialization failed: {e}")
```

**改动 4：新增 _init_vec_schema()**

```python
def _init_vec_schema(self):
    conn = self._get_connection()
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0(
            memory_id TEXT PRIMARY KEY,
            embedding float[{self._embedding_dim}]
        )
    """)
    conn.commit()
```

**改动 5：remember() 新增 embedding 计算**

在 `_remember_impl()` 的 INSERT 成功后，计算并存储 embedding：

```python
# P0-2: Compute and store embedding
if self._enable_vector and self._embedding_model:
    text_to_embed = entry.raw_text or entry.content
    if text_to_embed:
        try:
            embedding = self._embedding_model.encode(text_to_embed)
            conn.execute(
                "INSERT OR REPLACE INTO memory_vectors(memory_id, embedding) VALUES(?, ?)",
                (entry.id or storage_key, embedding.tolist()),
            )
            if not _skip_commit:
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to store embedding: {e}")
```

**改动 6：recall() 新增向量搜索路径**

在 `_recall_impl()` 中，FTS5 搜索后增加向量搜索：

```python
# P0-2: Vector similarity search
if self._enable_vector and query and query.strip():
    vec_results = self._vector_search(query, where_clause, params, limit)
    # 合并 FTS5 和向量搜索结果
    seen_ids = {r["id"] for r in rows if r}
    for r in vec_results:
        if r["id"] not in seen_ids:
            rows.append(r)
            seen_ids.add(r["id"])
        if len(rows) >= limit:
            break
```

**改动 7：新增 _vector_search() 方法**

```python
def _vector_search(self, query, where_clause, params, limit):
    if not self._embedding_model:
        return []
    try:
        query_embedding = self._embedding_model.encode(query)
        conn = self._get_connection()
        results = conn.execute("""
            SELECT m.*, v.distance
            FROM memory_vectors v
            JOIN memories m ON m.id = v.memory_id
            {where_clause}
            AND v.embedding MATCH ?
            ORDER BY v.distance
            LIMIT ?
        """, params + [query_embedding.tolist(), limit]).fetchall()
        return results
    except Exception as e:
        logger.warning(f"Vector search failed: {e}")
        return []
```

**改动 8：capabilities 更新**

```python
@property
def capabilities(self):
    return {
        "vector_search": self._enable_vector,  # 改为动态
        "fts": True,
        "ttl": True,
        "batch": True,
        "graph": False,
        "semantic_recall": self._enable_semantic,
    }
```

**改动 9：forget() 同步删除向量**

在 forget() 删除 memories 记录后，同步删除 memory_vectors 记录：

```python
# P0-2: Delete associated embedding
if self._enable_vector:
    try:
        conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
    except Exception:
        pass
```

**改动 10：数据库迁移**

```python
def _migrate_v070(self):
    """v0.7.0: Add vector search support."""
    if not self._enable_vector:
        return
    conn = self._get_connection()
    try:
        conn.execute("SELECT memory_id FROM memory_vectors LIMIT 1")
    except sqlite3.OperationalError:
        self._init_vec_schema()
```

#### 2.4.3 carrymem.py

**改动：__init__ 传递新参数**

```python
elif storage == "sqlite":
    self._adapter = SQLiteAdapter(
        db_path=db_path, namespace=namespace,
        encryption_key=encryption_key,
        enable_vector_search=config.get("enable_vector_search", True) if config else True,
        embedding_model=config.get("embedding_model", "all-MiniLM-L6-v2") if config else "all-MiniLM-L6-v2",
    )
```

#### 2.4.4 base.py

**无需改动**。`StoredMemory.vector_embedding` 字段已预留。

---

## 三、降级策略

### 3.1 依赖不可用

| 场景 | 行为 |
|------|------|
| sqlite-vec 未安装 | `_enable_vector = False`，仅 FTS5 |
| sentence-transformers 未安装 | `_enable_vector = False`，仅 FTS5 |
| 模型下载失败 | `_enable_vector = False`，仅 FTS5 |
| sqlite-vec 加载失败 | `_enable_vector = False`，仅 FTS5 |

### 3.2 运行时错误

| 场景 | 行为 |
|------|------|
| embedding 计算超时（>2s） | 跳过向量搜索，仅返回 FTS5 结果 |
| 向量搜索 SQL 错误 | 静默降级到 FTS5，记录 warning 日志 |
| 内存不足 | 跳过向量搜索，仅返回 FTS5 结果 |

### 3.3 用户体验

- `capabilities["vector_search"]` 反映实际状态
- 日志中记录降级原因
- 不抛出异常，不影响基础功能

---

## 四、测试计划

### 4.1 单元测试

| 测试 | 说明 | 优先级 |
|------|------|--------|
| test_vector_search_enabled | 安装 semantic 依赖后 vector_search=True | P0 |
| test_vector_search_disabled | 未安装依赖时 vector_search=False | P0 |
| test_embedding_stored_on_remember | remember() 后 memory_vectors 有记录 | P0 |
| test_embedding_not_stored_without_raw_text | raw_text 为空时用 content 做 embedding | P0 |
| test_vector_recall_returns_similar | 语义相似查询能召回 | P0 |
| test_vector_recall_fallback_to_fts | 向量搜索失败时回退 FTS5 | P0 |
| test_forget_deletes_vector | forget() 同步删除向量记录 | P1 |
| test_batch_remember_stores_embeddings | remember_batch() 批量存储 embedding | P1 |
| test_migration_v070 | 旧数据库升级后 memory_vectors 表创建 | P1 |

### 4.2 集成测试

| 测试 | 说明 | 优先级 |
|------|------|--------|
| test_longmemeval_20q | LongMemEval 20 题快速验证 | P0 |
| test_locomo_subset | LoCoMo 子集验证 | P1 |

### 4.3 回归测试

确保现有功能不受影响：
- FTS5 搜索仍正常
- 语义扩展仍正常
- 缓存仍正常
- 加密仍正常
- 版本管理仍正常

---

## 五、执行步骤

| 步骤 | 内容 | 验证方式 | 预计耗时 |
|------|------|---------|---------|
| 1 | 验证 sqlite-vec + sentence-transformers 在 macOS 上可安装 | pip install 成功 | 0.5h |
| 2 | setup.py 加 semantic extras | pip install -e ".[semantic]" 成功 | 0.5h |
| 3 | sqlite_adapter.py 实现 embedding 计算+存储 | 单元测试通过 | 2h |
| 4 | sqlite_adapter.py 实现向量搜索 | 单元测试通过 | 2h |
| 5 | 降级策略实现 | 无依赖时正常降级 | 1h |
| 6 | carrymem.py 传递新参数 | 集成测试通过 | 0.5h |
| 7 | 数据库迁移 v0.7.0 | 旧数据库升级成功 | 0.5h |
| 8 | 单元测试全部通过 | pytest | 1h |
| 9 | LongMemEval 20 题验证 | F1 ≥ 0.30 | 2h |
| **总计** | | | **~10h** |

---

## 六、风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| sqlite-vec macOS wheel 不可用 | 阻断 | 中 | 提前验证；备选 faiss-cpu |
| sentence-transformers 安装失败 | 阻断 | 低 | pip install 通常可靠 |
| 模型下载慢/失败 | 延迟 | 中 | 预缓存模型；首次运行提示 |
| embedding 计算太慢 | 性能 | 低 | all-MiniLM-L6-v2 单次 <50ms |
| 向量搜索结果不如 FTS5 | 效果 | 中 | 保留 FTS5 作为主路径，向量作为补充 |
| P0-2 后 F1 < 0.30 | 方向 | 中 | 暂停 P0-3，评估换模型 |

---

## 七、验收标准

1. `pip install carrymem[semantic]` 安装成功
2. `CarryMem(storage="sqlite")` 自动检测并启用向量搜索
3. 未安装 semantic 依赖时，CarryMem 正常工作（仅 FTS5）
4. `capabilities["vector_search"]` 正确反映实际状态
5. remember() 后 memory_vectors 表有对应记录
6. recall() 能通过语义相似度检索到措辞不同的记忆
7. 向量搜索失败时静默降级到 FTS5
8. 现有单元测试全部通过
9. LongMemEval 20 题 F1 ≥ 0.30

---

*本文档基于 2026-05-11 LoCoMo 测试结果和代码库现状编写。*
*实施前需先验证 sqlite-vec 在 macOS 上的可用性。*
