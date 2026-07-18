# CarryMem 发布回滚 Runbook

> **文档性质**: 运维操作手册 (Runbook) — 发布与回滚的标准操作流程
> **创建时间**: 2026-07-18
> **配套文档**: [.github/workflows/release.yml](../.github/workflows/release.yml) — 自动化发布流水线
> **适用范围**: CarryMem v0.8.0+ 的 PyPI 发布与 GitHub Release

---

## 1. 概述

本文档定义 CarryMem 发布到 PyPI 和 GitHub Release 的标准操作流程，包括发布前检查、发布步骤、故障回滚和紧急联系人。

**发布渠道**:
- **PyPI**: `https://pypi.org/project/carrymem/` (用户 `pip install carrymem` 的来源)
- **GitHub Release**: `https://github.com/lulin70/carrymem/releases`

**发布触发方式**: 推送 `v*` 格式的 git tag（如 `v0.8.0`），自动触发 [release.yml](../.github/workflows/release.yml) 工作流。

**关键约束**:
- PyPI 不支持删除已上传的版本，只能 **yank**（隐藏，不影响已安装用户）
- git tag 一旦推送，不建议强制删除（会破坏下游 CI 缓存）
- 发布是**不可逆**的，只能通过发新版本修复

---

## 2. 发布前检查清单

### 2.1 代码准备

- [ ] 确认 `src/carrymem/__version__.py` 中的 `__version__` 已更新为目标版本号
- [ ] 确认 `CHANGELOG.md` 已添加新版本条目（Keep a Changelog 风格）
- [ ] 确认 `docs/TECH_DEBT_PLAN.md` 中相关 TD 项状态已更新
- [ ] 确认 `docs/ROADMAP_P0_P3.md` 中 Wave 推进表已更新
- [ ] 所有 P0/P1 技术债项已完成或标注阻塞原因
- [ ] 主分支 `new-main` 处于绿色状态（CI 全通过）

### 2.2 测试验证

- [ ] 本地运行 `pytest tests/ -m "not slow" -q` 全通过
- [ ] 本地运行 `pytest tests/e2e/ -m "not slow" -v` 全通过（用户规则3：发布前必须做模拟真实用户使用的测试）
- [ ] 本地运行 `pre-commit run --all-files` 全通过
- [ ] 本地运行 `flake8 src/ tests/ --max-line-length=120` 无错误
- [ ] 本地运行 `mypy src/` 无新增错误
- [ ] 本地运行 `bandit -r src/ -lll` 无 HIGH 漏洞
- [ ] 本地运行 `pip-audit` 无已知 CVE
- [ ] 覆盖率 `pytest --cov=carrymem` ≥ 80%

### 2.3 版本一致性验证

- [ ] `__version__.py` 版本号 == `CHANGELOG.md` 最新条目版本号
- [ ] `__version__.py` 版本号 == 即将推送的 git tag 版本号（去掉 `v` 前缀）
- [ ] `setup.py` 中 `python_requires=">=3.12"` 未被意外修改

### 2.4 发布环境检查

- [ ] PyPI 账号 `lulin70` 可登录
- [ ] GitHub 仓库 `lulin70/carrymem` 有 `contents: write` 权限
- [ ] GitHub Secrets 中 `PYPI_API_TOKEN` 有效（TD-015 完成后改为 OIDC Trusted Publisher）
- [ ] `new-main` 分支已 protected（禁止 force push）

### 2.5 OIDC Trusted Publisher 迁移清单 (TD-015)

> **背景**: PyPI 已推出 OIDC Trusted Publisher，可让 GitHub Actions 不再依赖长期 API Token，从 OIDC 短期令牌直接发布。详细原理见 https://docs.pypi.org/trusted-publishers/。

迁移共 6 步，其中 **步骤 2/3/6 已由代码完成**（见 `.github/workflows/release.yml`），**步骤 1/4/5 需要仓库管理员在 PyPI / GitHub Web UI 手动操作**。

#### 步骤 1 — 添加 PyPI Trusted Publisher（**用户手动**）

> 必须先完成此步骤，否则步骤 4 之后 OIDC 发布会失败。

1. 登录 PyPI: `https://pypi.org/manage/account/publishing/`
2. 在 "Add a publisher" 区段选择 **GitHub**
3. 填写以下信息（**严格匹配大小写**）:
   - **PyPI Project Name**: `carrymem`
   - **Owner**: `lulin70`
   - **Repository**: `carrymem`
   - **Workflow filename**: `release.yml`（相对 `.github/workflows/`）
   - **Environment name**: `pypi`（必须与 release.yml 中 `environment: pypi` 一致）
4. 点击 "Add publisher" — PyPI 会校验仓库和工作流是否存在
5. **验证**: 在 PyPI 项目页 `https://pypi.org/manage/project/carrymem/publishing/` 看到 Trusted Publisher 条目

#### 步骤 2 — release.yml 添加 environment: pypi（**代码已完成**）

参见 `.github/workflows/release.yml` 中 `release` job 的 `environment: pypi` 字段（TD-015 step 2 注释）。

#### 步骤 3 — 保留 PYPI_API_TOKEN 直至 OIDC 验证成功（**代码已完成**）

`release.yml` 的 "Publish to PyPI" step 仍保留 `password: ${{ secrets.PYPI_API_TOKEN }}`，**不要删除**。注释中明确指出在 OIDC 验证通过前需保留该 secret，作为发布回退兜底。

#### 步骤 4 — 创建 GitHub Environment `pypi` 并配置保护（**用户手动**）

1. 进入 GitHub 仓库 Settings → Environments → "New environment"
2. 名称填 `pypi`（与 release.yml 中 `environment: pypi` 完全一致）
3. 配置保护规则（至少选一项）:
   - **Required reviewers**: 添加 `lulin70` 作为审批人（推荐 — 发布前需人工 approve）
   - **Deployment branches**: 选 "Selected branches" → `new-main`（限制只能在主分支触发发布）
   - **Wait timer**: 可选 0~30 分钟（用于人工 sanity check）
4. 保存环境配置

#### 步骤 5 — 验证 OIDC 发布成功后删除 PYPI_API_TOKEN（**用户手动，最后一步**）

> ⚠️ **顺序至关重要**：必须先用一个真实版本（如 `v0.8.0`）跑通 OIDC 发布后，再删除 token。否则会导致下次发布无法上传。

1. **预演验证**: 在 PyPI 上观察一次正常的 `v*` tag 推送触发的 release.yml 工作流：
   - 确认 `release` job 中 "Publish to PyPI" 步骤**未使用** `password`（需要先编辑 release.yml 移除 `with: password:` 块，仅保留 `uses: pypa/gh-action-pypi-publish@release/v1`）
   - 确认 PyPI 上出现新版本且 `Published via GitHub OIDC` 显示在 release metadata
2. **删除 secret**:
   - 进入 GitHub 仓库 Settings → Secrets and variables → Actions
   - 找到 `PYPI_API_TOKEN` → 点击删除
3. **再次验证**: 推送下一个 patch tag（如 `v0.8.1`），确认工作流不依赖 secret 也能成功发布
4. **如失败回滚**: 重新创建 `PYPI_API_TOKEN` secret，并将 release.yml 还原为带 `password:` 的版本

#### 步骤 6 — main 分支保护要求（**代码注释已完成**）

`.github/workflows/release.yml` 中已添加详细注释说明 PyPI Trusted Publisher 的安全模型依赖 GitHub 分支保护。要求管理员在 GitHub Settings → Branches → Branch protection rules 中为 `new-main` 配置：
- Require pull request reviews before merging (≥1 reviewer)
- Require status checks to pass (pre-release-test, e2e-gate)
- Restrict who can push to matching branches（禁止直接 push）

#### OIDC 迁移进度跟踪

| 步骤 | 类型 | 状态 | 责任人 |
|------|------|------|--------|
| 1. 添加 PyPI Trusted Publisher | 手动 (PyPI Web UI) | ⏳ 待办 | Release Manager |
| 2. release.yml 加 environment: pypi | 代码 | ✅ 完成 (DevSquad DevOps) | DevOps |
| 3. 保留 PYPI_API_TOKEN + 注释 | 代码 | ✅ 完成 (DevSquad DevOps) | DevOps |
| 4. 创建 GitHub `pypi` Environment | 手动 (GitHub Web UI) | ⏳ 待办 | Release Manager |
| 5. 验证 OIDC + 删除 PYPI_API_TOKEN | 手动 (PyPI + GitHub) | ⏳ 待办 (在 v0.8.0 验证后) | Release Manager |
| 6. main 分支保护注释 | 代码 | ✅ 完成 (DevSquad DevOps) | DevOps |

---

## 3. 发布步骤

### 3.1 自动化发布流程（推荐）

release.yml 工作流包含 4 个 job，按依赖顺序执行：

```
pre-release-test (lint+test+coverage)
        ├── e2e-gate (E2E 用户旅程测试)
        ├── vscode-e2e (VSCode Tier 2 UI E2E)
        └── release (build + PyPI publish + GitHub Release)
              [needs: pre-release-test, e2e-gate, vscode-e2e]
```

**操作步骤**:

1. **创建 git tag 并推送**:
   ```bash
   git checkout new-main
   git pull origin new-main
   git tag -a v0.8.0 -m "Release v0.8.0"
   git push origin v0.8.0
   ```

2. **监控工作流**:
   - 访问 `https://github.com/lulin70/carrymem/actions`
   - 确认 "Release" 工作流已触发
   - 等待 `pre-release-test` → `e2e-gate` → `vscode-e2e` → `release` 依次通过

3. **验证发布结果**:
   ```bash
   # 验证 PyPI
   pip index versions carrymem  # 或访问 https://pypi.org/project/carrymem/
   # 验证 GitHub Release
   gh release view v0.8.0  # 或访问 https://github.com/lulin70/carrymem/releases
   # 验证 fresh install
   python -m venv /tmp/verify_venv
   /tmp/verify_venv/bin/pip install carrymem==0.8.0
   /tmp/verify_venv/bin/python -c "import carrymem; print(carrymem.__version__)"
   ```

4. **发布后通知**:
   - 更新 `docs/PROJECT_STATUS.md`
   - 在 GitHub Release 描述中补充重要变更摘要
   - 通知用户社区（如有）

### 3.2 手动发布（应急方案）

仅在 release.yml 工作流故障时使用：

```bash
# 1. 构建包
python -m build
twine check dist/*

# 2. 上传到 PyPI（需要 PYPI_API_TOKEN）
twine upload dist/carrymem-0.8.0*

# 3. 创建 GitHub Release
gh release create v0.8.0 dist/carrymem-0.8.0* --generate-notes --title "v0.8.0"
```

---

## 4. 回滚步骤

### 4.1 回滚决策矩阵

| 故障类型 | 严重程度 | 回滚方式 | 时效要求 |
|---------|---------|---------|---------|
| 安装即崩溃（import 失败） | 🔴 严重 | yank + 紧急修复版本 | 1h 内 |
| 核心功能不可用 | 🔴 严重 | yank + 紧急修复版本 | 2h 内 |
| 非核心功能故障 | 🟡 中等 | 发 patch 修复版本 | 24h 内 |
| 文档错误 | 🟢 轻微 | 无需回滚，发 patch 修正 | 下次发布 |

### 4.2 PyPI Yank 操作（隐藏故障版本）

> **注意**: yank 不会删除版本，已安装用户不受影响。新 `pip install carrymem` 会跳过 yanked 版本，安装上一个稳定版。

1. **登录 PyPI**:
   - 访问 `https://pypi.org/manage/account/`
   - 使用 `lulin70` 账号登录

2. **进入项目管理**:
   - 访问 `https://pypi.org/manage/project/carrymem/releases/`

3. **Yank 故障版本**:
   - 找到故障版本（如 `0.8.0`）
   - 点击 "Options" → "Yank"
   - 确认 yank 操作
   - 或使用 API: `curl -X POST "https://pypi.org/simple/carrymem/" -H "Authorization: Basic <base64-token>" -d "yank=0.8.0"`

4. **验证 yank 生效**:
   ```bash
   pip install carrymem==0.8.0  # 应提示版本不可用或安装失败
   pip install carrymem         # 应安装上一个稳定版
   ```

### 4.3 紧急修复版本发布（bump + 重发布）

1. **创建 hotfix 分支**:
   ```bash
   git checkout -b hotfix/v0.8.1 new-main
   ```

2. **修复故障 + bump 版本号**:
   ```bash
   # 修改 src/carrymem/__version__.py
   __version__ = "0.8.1"
   # 更新 CHANGELOG.md
   ```

3. **验证修复**:
   ```bash
   pytest tests/ -m "not slow" -q
   pytest tests/e2e/ -m "not slow" -v
   ```

4. **合并到 main 并发布**:
   ```bash
   git add -A && git commit -m "hotfix: v0.8.1 — fix <issue description>"
   git checkout new-main
   git merge hotfix/v0.8.1
   git tag -a v0.8.1 -m "Hotfix release v0.8.1"
   git push origin new-main v0.8.1
   ```

5. **验证新版本**:
   ```bash
   pip install carrymem==0.8.1
   python -c "import carrymem; print(carrymem.__version__)"
   ```

### 4.4 GitHub Release 回滚

GitHub Release 不需要回滚（它只是 PyPI 发布的镜像）。如果 Release 描述有误：

1. 访问 `https://github.com/lulin70/carrymem/releases/edit/v0.8.0`
2. 修改描述并保存

如果需要将 Release 标记为 pre-release（降级）：
1. 访问 release 编辑页
2. 勾选 "Set as a pre-release"
3. 保存

### 4.5 git Tag 处理

> **警告**: 强制删除已推送的 git tag 会破坏下游 CI 缓存，**不建议**操作。

如果必须删除 tag（极端情况）：
```bash
# 删除本地 tag
git tag -d v0.8.0
# 删除远程 tag（需要管理员权限）
git push origin :refs/tags/v0.8.0
# 重新打 tag
git tag -a v0.8.0 -m "Release v0.8.0 (re-tagged)"
git push origin v0.8.0
```

---

## 5. 发布后验证

### 5.1 自动化验证

```bash
# 1. PyPI 可安装
pip install carrymem==<VERSION>
python -c "import carrymem; print(carrymem.__version__)"

# 2. fresh install 无残留问题
python -m venv /tmp/fresh_test
/tmp/fresh_test/bin/pip install carrymem
/tmp/fresh_test/bin/python -c "from carrymem import CarryMem; cm = CarryMem(); print('OK'); cm.close()"

# 3. Docker 镜像可用（如已发布）
docker pull carrymem:<VERSION>  # 如果有 Docker Hub 镜像

# 4. MCP server 可启动
python -m carrymem mcp --help
```

### 5.2 用户旅程 E2E 验证（用户规则3）

```bash
# 模拟真实用户使用流程
python -m carrymem tutorial
python -m carrymem remember "test memory"
python -m carrymem recall "test"
python -m carrymem doctor
```

---

## 6. 紧急联系人

### 6.1 发布相关

| 角色 | 负责人 | 联系方式 | 职责 |
|------|--------|---------|------|
| **Release Manager** | lulin70 | lulin70@gmail.com | 发布决策、tag 推送、PyPI 操作 |
| **DevOps** | DevSquad DevOps | GitHub Issues | CI/CD 故障、工作流调试 |
| **Security** | DevSquad Security | GitHub Issues | 安全漏洞评估、yank 决策 |

### 6.2 升级路径

1. **L1 — 自动告警**: nightly.yml `notify-failure` job 自动创建 GitHub Issue（TD-042）
2. **L2 — DevOps 响应**: DevOps 角色监控 GitHub Issues，24h 内响应
3. **L3 — Release Manager 决策**: 严重故障由 Release Manager 决定是否 yank + 紧急修复
4. **L4 — 用户通知**: 严重故障需在 PyPI 项目描述和 GitHub Release 中公告

### 6.3 外部依赖联系

| 服务 | 用途 | 状态页 | 故障影响 |
|------|------|--------|---------|
| PyPI | 包发布 | `https://status.python.org/` | 无法上传/安装 |
| GitHub Actions | CI/CD | `https://www.githubstatus.com/` | 工作流无法运行 |
| GitHub Releases | Release 页面 | `https://www.githubstatus.com/` | 无法创建 Release |

---

## 7. 常见问题

### Q1: release.yml 工作流失败怎么办？

1. 查看 Actions 页面定位失败的 job
2. 如果是 `pre-release-test` 失败：修复代码/测试后重新推送 tag（需先删除旧 tag）
3. 如果是 `e2e-gate`/`vscode-e2e` 失败：检查是否 flaky test，可 `gh run rerun` 重试
4. 如果是 `release` job 失败（PyPI 上传失败）：检查 `PYPI_API_TOKEN` 是否有效

### Q2: PyPI 上传报 "File already exists"？

说明该版本号已被上传过。PyPI 不允许覆盖。解决方案：
1. bump 版本号（如 `0.8.0` → `0.8.1`）
2. 如果是 rc 预发布，使用 `0.8.0rc1` 格式

### Q3: 如何发布预发布版本（rc/beta）？

```bash
# 版本号格式
__version__ = "0.8.0rc1"  # 或 "0.8.0b1" for beta

# tag 格式
git tag -a v0.8.0rc1 -m "Release candidate v0.8.0rc1"
git push origin v0.8.0rc1

# 用户安装
pip install carrymem==0.8.0rc1
```

### Q4: Docker 镜像如何发布？

当前 Dockerfile 仅用于本地构建，Docker Hub 镜像发布流程待定义（TD-050 相关）。手动构建：
```bash
docker build -t carrymem:0.8.0 .
docker tag carrymem:0.8.0 carrymem:latest
# docker push carrymem:0.8.0  # 需要 Docker Hub 账号
```

---

## 8. 变更记录

| 日期 | 变更 | 操作者 |
|------|------|--------|
| 2026-07-18 | 创建文档 (TD-043) | DevOps (DevSquad) |
| 2026-07-18 | 新增 §2.5 OIDC Trusted Publisher 迁移清单 (TD-015 代码部分 + 手动步骤说明) | DevOps+Security (DevSquad) |
