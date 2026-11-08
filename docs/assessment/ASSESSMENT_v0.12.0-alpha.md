# CarryMem 项目整理评估 — v0.12.0-alpha

**评估日期**: 2026-11-07（发布更新：2026-11-08）
**评估对象**: `v0.12.0-alpha1`（`0.12.0a1`）
**评估方法**: DevSquad 七维评估 + 真实命令取证
**结论**: **78/100（B−）**。可继续内测。不满足稳定版发布条件。

---

## 0. 结论摘要

| 项目 | 结果 |
|------|------|
| 代码规模 | 168 个源文件，58,908 行；176 个测试文件 |
| 全量回归（非 slow，2026-11-08 P1 修复后） | `5172 passed, 1 skipped, 77 deselected`，耗时 20 分 05 秒，exit 0 |
| 覆盖率 | 83.27%（同一轮；CI 门槛 80%） |
| 静态门禁 | flake8 0 / black 0 / isort 0 / mypy 0（168 文件）/ radon 0 个 D+ |
| 安全扫描 | bandit：0 High，45 Medium（全部为参数化 `IN (...)` 的 B608），64 Low；pip-audit：无已知漏洞 |
| 发布状态 | 旧 tag `v0.12.0-alpha` 失败并撤回。修复提交 `51277fd` 的 CI run `42387757587` **全绿**。Release run `42436293206` 全绿。`v0.12.0-alpha1`（`0.12.0a1`）已发布到 PyPI 与 GitHub Release |
| 主要风险 | 向量检索开启时分类 P99 仍为 368 ms；宿主 LLM 只验证了两个 stdio 用例 |

**一句话判断**：代码工程质量高。发布纪律和真实用户验证不足。本轮已修复 4 个 P0 缺陷，并统一版本源。下一步应推送修复、验证 CI 全绿，并用真实客户端验证宿主 LLM。

---

## 1. 架构（8.5/10）

**事实**
- 采用 `src/` 布局。核心为 Facade + 7 个 Mixin + Protocol。
- 存储适配器可插拔：SQLite、JSON、Obsidian、AsyncSQLite。
- MCP 层与业务层分离。35 个工具分布在 9 个域处理器中。
- 核心路径不依赖 LLM。LLM 只做可选增强。

**评价**
- 分层清楚。依赖方向正确。新增功能有明确落点。
- 四层 LLM 降级（宿主 → 云 API → 本地 → 规则）符合"核心零 LLM"原则。
- 本轮发现：LLM 客户端的同步契约被 alpha 版本删除。生产代码 3 处调用点会拿到协程对象。这是架构演进未做兼容迁移的典型问题。已修复。

**遗留**
- `CarryMem()` 默认 `enable_vector_search=True`。安装了 `[semantic]` extra 时，每条 CLI 命令都会加载 103 个模型权重。这是默认值造成的隐式重成本。

---

## 2. 正确性（7.5/10）

**已验证**
- MCP stdio 主循环收到 sampling 响应时，现在能正确路由到等待的 Future。修复前，`request_sampling` 创建了未连接的 `StreamReader`，请求必然 30 秒超时。这是"功能存在但从未激活"的幽灵功能。
- 规则增强与会话摘要只在 LLM 真正返回内容时上报 `tier="llm_enhanced"`。修复前，降级到规则路径也上报增强，结果失真。
- `RuleBasedProvider` 不再返回占位文本。它抛出 `LLMUnavailableError`，让上层显式降级。
- Tier 2/3 现在进入调度链。修复前，云 API 客户端只服务旧的同步 `chat()`。`generate()` 只看到 Tier 4 与 Tier 1。用户配置了 API Key，增强结果仍走规则路径。这是第二个幽灵功能。
- 6 个版本号来源统一为 `0.12.0a0`，校验脚本覆盖 `pyproject.toml`。

**问题**
- alpha tag 指向的提交有 31 个测试失败。生产调用点会收到协程。这说明发布前没有跑完整回归。
- 发布 tag 已公开。不能强移 tag。

---

## 3. 可维护性（8/10）

**事实**
- `TODO/FIXME/XXX/HACK` 全库仅 1 处。
- 复杂度门禁有效：`radon cc -n D src/` 无输出。
- 71 处 `except Exception`。测试要求每处写 `NOTE` 说明，并检查 ±3 行窗口。
- `tests/test_exception_narrowing.py` 曾使用硬编码工作目录。CI 中扫描不到文件，测试空跑通过。已改为仓库相对路径。

**评价**
- 模块边界清楚。命名一致。类型注解完整。
- 技术债清单可追踪。本轮关闭了 4 项：版本不一致、异常测试空跑、CI 分支未覆盖、幽灵采样。

---

## 4. 性能（6.5/10）

**实测（2026-11-07，本机 macOS）**

| 指标 | 实测 | 目标 | 判定 |
|------|------|------|------|
| FTS5 召回平均（100/500/1000 条） | 5.53 / 5.85 / 5.52 ms | < 5 ms | 略超 |
| FTS5 召回 p95 | 6.9–8.0 ms | — | — |
| LIKE 召回平均 | 10.5–15.1 ms | — | — |
| `classify_and_remember` 冷启动 | 16.4 ms | — | — |
| `classify_and_remember` 热平均 | 144.2 ms | — | — |
| `classify_and_remember` p95 | 398.3 ms | — | — |
| `classify_and_remember` P99 | 1260.8 ms | < 200 ms | **超标 6.3 倍** |
| 吞吐 | 7 ops/s | — | 偏低 |

**P1 复测（2026-11-08，本机 macOS，200 次写入）**

| 配置 | 启动 | 热平均 | p95 | P99 | 吞吐 |
|------|------|--------|-----|-----|------|
| 向量检索开（旧默认） | 11334 ms | 75.8 ms | 113.2 ms | 368.0 ms | 13 ops/s |
| 向量检索关（新默认） | 75 ms | 55.6 ms | 74.5 ms | 81.2 ms | 18 ops/s |

基准套件复测（`pytest tests/test_performance_benchmark.py`，新默认）：冷启动 3.7 ms，热平均 26.8 ms，p95 44.5 ms，P99 53.0 ms，37 ops/s。全部 16 项通过。

**原因与修复**
- 原因确认：默认 `enable_vector_search=True`。每条写入计算 embedding。启动加载 103 个模型权重。这是 P99 与启动成本的主因；不是 FTS5。
- 修复：`CarryMem` 门面改为默认关闭向量检索。用 `config={"enable_vector_search": True}` 或环境变量 `CARRYMEM_ENABLE_VECTOR_SEARCH=1` 开启。`SQLiteAdapter` 直接构造时的默认值不变。
- 结果：P99 从 1260.8 ms 降到 53–81 ms，进入 < 200 ms 目标。启动成本从 11.3 s 降到 75 ms。
- README 与 DESIGN_PRINCIPLES 的原数字（P99 1.3 ms、召回 2.54–3.01 ms）不可复现。已改为实测值并标注机器与日期。

**结论**
- 召回满足交互使用。
- 分类在默认配置下满足 SLO。开启向量检索后，P99 回到 368 ms。文档必须写明这一取舍。


---

## 5. 安全（8/10）

**事实**
- CI 有 bandit 与 pip-audit。bandit 阻断 HIGH 及以上。
- 本地 bandit：0 High。45 个 Medium 全部是 `B608 hardcoded_sql_expressions`。抽样确认使用 `?` 占位符与参数绑定，属于误报模式。
- pip-audit：`No known vulnerabilities found`。
- 敏感信息脱敏有 24 类模式。加密为硬依赖。访问控制失败时关闭（fail-closed）。
- CI 的密钥扫描已改为失败即阻断。旧写法恒返回 0。

**遗留**
- 45 个 B608 建议逐条加 `# nosec B608` 与理由，减少噪声。
- 宿主 LLM 会把记忆内容发给宿主客户端。需要在文档中写明数据边界。README 已补充。

---

## 6. 测试（8.5/10）

**事实**
- 5,167 个测试通过，1 个跳过，77 个按标记排除，覆盖率 83.49%，耗时 28 分 48 秒。E2E 目录包含并发、加密全链路、大数据集、MCP 工具、用户旅程等场景。
- 真实 CLI 旅程已执行：隔离配置下 `--version` → `whoami` → 3 次 `add` → `list`。记忆类型与键正确。
- 测试能发现真实缺陷：本轮 31 个失败全部指向 LLM 客户端契约破坏。
- 测试自身有缺陷：异常收窄测试曾空跑。已修复。

**不足**
- 宿主 LLM 已有真实 stdio 客户端用例。尚未覆盖 Claude Desktop / Cursor 的界面验收。
- UI E2E 只覆盖 VSCode 扩展，且在 nightly 运行。
- 热路径性能已设为阻塞门禁（`perf-gate`）。分类基准仍在建议性作业中运行。

---

## 7. 文档（7/10）

**本轮修复**
- README、4 个 i18n README、DESIGN_PRINCIPLES、PROJECT_STATUS、CLAUDE.md 的版本号与测试数已更新。
- 删除不可复现的性能宣传。改为"实测值 + 机器 + 日期 + 复现命令"。
- README 新增"可选宿主 LLM 增强"章节，写明四层降级、30 秒超时、tier 语义。
- 文档目录按约定归位：`docs/releases/`、`docs/runbooks/`、`docs/testing/`、`docs/design/`、`docs/archive/`。
- 删除 `.bak` 文件与临时调试文档。

**不足**
- `docs/archive/` 中仍有旧数字。归档文件保留原样，不参与对外宣传。
- 多语言文档靠人工同步，容易再次漂移。建议加一致性脚本。

---

## 8. CI/CD（当前不通过，修复待验证）

**失败证据**
- tag `v0.12.0-alpha` 的 CI（run 42377818937）失败。
- Release 工作流（run 42377818920）预检失败。
- 根因：31 个 LLM 测试失败，以及生产调用点契约破坏。

**本轮修复**
- 合并同步与异步 LLM 契约。保留 `is_available()`、`count_tokens()`、`chat()`。
- 新增 `run_coroutine_sync()`，修复 pytest-asyncio 下的事件循环冲突。
- 新增 `CloudLLMProvider`，让 Tier 2/3 真正进入调度链。
- CI 触发分支增加 `release/**`。
- 版本一致性检查覆盖 6 处。

**结果**
- 提交 `51277fd` 已推送。CI run `42387757587` 结论为 `success`。
- 全部作业通过：Syntax、Lint、Tests（Ubuntu/macOS）、Build & Install、Security、Docker Build、VSCode Extension、Docs、i18n、Optional Deps。
- 版本提升到 `0.12.0a1`。提交 `53b24f9` 的 CI run `42433593654` 全绿。
- Tag `v0.12.0a1` 触发 Release run `42436293206`：预发布测试、E2E、VSCode UI E2E、构建与发布全部成功。
- PyPI 已有 `carrymem-0.12.0a1` 的 wheel 与 sdist。GitHub Release 已标记为 pre-release。
- P1 修复提交 `fda30c5` 的 CI run `42451427643` 全绿。新增 `perf-gate` 作业通过。

**待办**
- 保留旧 tag `v0.12.0-alpha`，不要移动。
- 真实客户端宿主 LLM 验收已完成 stdio 层。界面验收待做。

---

## 9. 目录结构（已清理）

**已移动**
- 根目录文档移入 `docs/` 对应子目录。
- 4 个过程文档移入 `docs/archive/`。

**已删除**
- `requirements-dev.in.bak`
- `docs/PRODUCT_ROLLOUT_PLAN.md.bak`
- `debug-ci-regressions.md`（旧调试记录，已删除；结论收进本文档）

**说明**
- `build/`、`dist/`、`htmlcov/`、`coverage.xml`、`__pycache__/` 是本地构建产物。已被 `.gitignore` 忽略。发布前删除即可，不进入版本库。

---

## 10. 七维评分

| 维度 | 分数 | 依据 |
|------|------|------|
| 架构 | 8.5 | 分层清楚，适配器可插拔，核心零 LLM |
| 正确性 | 7.5 | 修复了 4 个 P0；alpha 曾带缺陷发布 |
| 可维护性 | 8.0 | 静态门禁全绿，债少，复杂度受控 |
| 性能 | 6.5 → 8.0 | P1 修复后，默认配置 P99 为 53–81 ms；开启向量检索为 368 ms |
| 安全 | 8.0 | 0 High，依赖无漏洞；需处理 45 个 Medium 噪声 |
| 测试 | 8.5 | 5,167 个测试；新增真实 stdio 宿主 LLM 用例；缺界面验收 |
| 文档 | 7.0 | 本轮修正；历史文档仍有旧数字 |
| **加权总分** | **78 → 80（B）** | P1 已解决；待全量回归复评 |

---

## 11. 下一步建议

### P0（发布阻断）
1. 提交并推送本轮修复。确认 CI 与 Release 预检全绿。**已完成**。
2. 用新 tag `v0.12.0-alpha1` 发布。旧 tag 保留，不移动。**已完成**。
3. 在 Release 说明中标注：旧 alpha 的 LLM 路径不可用。**已完成**。

### P1（内测质量）
4. 用真实支持 sampling 的客户端跑一次端到端：调用 `suggest_rules`，确认返回 `tier="llm_enhanced"`。客户端不支持时确认降级为规则结果。**已完成**。证据：`tests/e2e/test_host_sampling_stdio.py`。该测试启动真实 stdio 服务器进程，客户端应答 `sampling/createMessage`。两项用例通过：宿主应答时返回 `llm_enhanced`；宿主返回 -32601 时降级为 `rule_based`。修复内容：读循环改为按请求建任务，sampling Future 桥接到读循环，避免 30 秒超时。
5. 测量 `classify_and_remember` 的 P99。区分"向量检索开/关"两组。若确认是 embedding 成本，改为按需启用。**已完成**。证据见第 4 节。默认关闭后 P99 为 53–81 ms。
6. 把性能基准设为 CI 门禁。阈值用实测值加余量，不用历史宣传值。**已完成**。`ci.yml` 新增阻塞作业 `perf-gate`，运行低抖动的热路径基准（召回、批量写入、导出、图查询）。分类基准保留在 `benchmark.yml`（建议性）与 `nightly.yml`（失败即红）中运行。证据：提交 `fda30c5` 的 CI run `42451427643` 全绿，`Performance Gate (hot path)` 结论为 `success`。全量回归 `5172 passed, 1 skipped, 77 deselected`，覆盖率 83.27%。

### P2（工程卫生）
7. 为 45 个 B608 加 `# nosec` 与理由。
8. 多语言文档加一致性检查脚本。
9. 清理 `docs/archive/` 之外残留的旧性能数字。

---

## 12. 复现命令

```bash
# 全量回归（非 slow）
.venv/bin/python -m pytest tests/ -q --timeout=180 -m "not slow"

# 静态门禁
flake8 src/ tests/ --count --max-line-length=120
black --check --line-length=120 src/ tests/
isort --check-only src/ tests/
mypy src/
radon cc -s -n D src/

# 版本一致性
python3 scripts/check_version_consistency.py

# 性能
python tests/benchmark_phase3_recall.py
.venv/bin/python -m pytest tests/test_performance_benchmark.py -k classify_and_remember -s

# 宿主 LLM 真实 stdio 端到端
.venv/bin/python -m pytest tests/e2e/test_host_sampling_stdio.py -q --no-cov

# CI 热路径性能门禁（本地复刻）
CI=true .venv/bin/python -m pytest tests/test_performance_benchmark.py \
  -k "test_recall_1000_records or test_batch_insert_100_fast_path or TestExportProfileLarge or TestGraphPerformanceBenchmark" \
  --no-cov -q

# 安全
.venv/bin/python -m bandit -q -r src -ll
.venv/bin/python -m pip_audit
```
