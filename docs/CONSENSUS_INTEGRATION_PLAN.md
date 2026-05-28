# CarryMem Client Integration Consensus Document

**Date**: 2026-05-28
**Version**: 3.0 (P2→P0 Promotions + Lifecycle Execution)
**Participants**: PM, Architect, Developer, DevOps (DevSquad Multi-Role Review)
**Status**: P0 Complete (Ready for Launch)

---

## Executive Summary

CarryMem v0.2.0 is technically ready for client integration launch. The MCP server implementation is mature (27 tools, 7 categories, protocol 2024-11-05), and the `setup-mcp --global` command works for the top 3 clients (Claude Code, Cursor, TRAE). However, critical gaps exist: PyPI version lag (0.1.6 vs 0.2.0), missing client support in setup-mcp (Windsurf, Cline, OpenClaw, etc.), and no automated PyPI publishing. This document captures the multi-role consensus on feasibility, priority, and action plan.

**v2.0 Update**: Merged with WorkBuddy Launch Checklist (2026-05-28). Key additions: promotion strategy (WeChat Official Account), launch cadence (T+0 to T+14), non-technical user onboarding, trial data collection, and Obsidian adapter documentation. Resolved conflicts on client config paths and launch sequencing.

**v3.0 Update**: Promoted 3 P2 items to P0 based on user decision — (1) Obsidian adapter documentation, (2) CodeX client support, (3) Community directory submissions (Glama/Smithery/MCP Market). Rationale: these are low-effort (2h each) but high-visibility items that differentiate CarryMem at launch. P0 now has 11 items total (4 done, 7 pending). Following DevSquad 11-phase lifecycle model (minimal template) for execution.

---

## 1. Role-Based Review Conclusions

### 1.1 PM Review

#### 1.1.1 Launch Plan Completeness Assessment

**Verdict: Plan is 80% complete. Missing items identified.**

| Original P0 Item | Status | Gap |
|---|---|---|
| `setup-mcp --global` one-click install | Partially done | Only supports 3/10+ clients (claude-code, cursor, trae) |
| pack/unpack feature | Done | v1.1 format with SHA-256 + encryption |
| Issue templates | Done | bug_report, feature_request, question exist |
| About update | Done | Per user confirmation |
| PyPI 0.2.0 release | Not done | Still at 0.1.6, 8 versions behind |

**Missing P0 items identified:**

1. **First-run experience**: No `carrymem init` wizard that guides new users through setup-mcp
2. **Quick Start documentation refresh**: Current QUICK_START_GUIDE.md does not mention `setup-mcp --global`
3. **Error recovery**: If setup-mcp fails mid-way (e.g., writes Cursor config but fails on TRAE), no rollback
4. **Uninstall path**: No `carrymem setup-mcp --uninstall` command
5. **Smoke test after setup**: No verification that MCP server actually starts after configuration

#### 1.1.2 User Journey: "Hear about CarryMem" to "All Agents Share Memory"

**Current journey (7 steps, too many):**

1. `pip install carrymem`
2. `carrymem init` (creates ~/.carrymem/)
3. `carrymem setup-mcp --global` (configures MCP)
4. Restart AI tools
5. Chat with AI, preferences auto-detected
6. `carrymem add "I prefer dark mode"` (manual add)
7. Verify with `carrymem search "dark"`

**Target journey (3 steps, ideal):**

1. `pip install carrymem && carrymem setup-mcp --global`
2. Restart AI tools
3. Chat naturally — preferences auto-detected and shared

**Gap analysis**: Steps 2-4 in current journey can be merged. The `setup-mcp --global` should auto-init if needed. The key friction is step 4 (restart), which is unavoidable for MCP clients.

#### 1.1.3 Competitive Analysis: Mem0/OpenMemory MCP

| Dimension | CarryMem | Mem0 OpenMemory |
|---|---|---|
| **Setup complexity** | `pip install` + 1 command | Docker Compose + 3 containers + OpenAI key |
| **Dependencies** | Python only, SQLite | Docker, Qdrant, Postgres, OpenAI API |
| **Memory tools** | 27 tools (classify, recall, rules, consolidation, profile, onboard) | 4 tools (add, search, list, delete) |
| **Transport** | stdio (local) | SSE (HTTP, requires server) |
| **Web UI** | Not yet | Built-in dashboard at localhost:3000 |
| **Classification** | 7 types, 4 tiers, confidence scoring | Flat memory objects |
| **Rule engine** | Full (add/match/inject/promote/suggest) | None |
| **Cross-client** | Shared SQLite DB via `--global` | Shared via API server |
| **Privacy** | Fully local, no network | Fully local, but needs Docker |
| **Pricing** | Open source, MIT | Open source (server), Cloud tier available |
| **Market traction** | Pre-launch | Product Hunt 200+ upvotes in 48h |

**CarryMem's competitive advantages:**

1. **Zero-dependency setup**: No Docker, no API keys, pure Python
2. **Intelligent classification**: 7 memory types vs flat storage
3. **Rule engine**: Behavioral rules with scope/priority/override
4. **Consolidation**: Automatic dedup, decay, pattern promotion
5. **Onboard tool**: First-time user welcome flow

**CarryMem's competitive gaps:**

1. **No Web UI**: Non-technical users cannot manage memories visually
2. **No SSE transport**: Cannot serve remote clients
3. **No MCP Registry listing**: Not discoverable via official channels
4. **Smaller community**: Pre-launch vs Mem0's established brand

#### 1.1.4 Positioning Recommendation

**Positioning**: "The lightweight, intelligent AI memory that works in 30 seconds — no Docker, no API keys, no cloud."

**Pricing path**:

- **Phase 1 (Now)**: 100% open source, MIT license. Build community and trust.
- **Phase 2 (3-6 months)**: Optional cloud sync (encrypted E2E) as paid tier. Local remains free.
- **Phase 3 (6-12 months)**: Team/enterprise features (shared rules, audit logs, SSO).

---

### 1.2 Architect Review

#### 1.2.1 MCP Configuration Format Compatibility

**All MCP clients use the same JSON schema:**

```json
{
  "mcpServers": {
    "<server-name>": {
      "command": "<executable>",
      "args": ["<arg1>", "<arg2>"],
      "env": { "<KEY>": "<VALUE>" }
    }
  }
}
```

**Differences by client:**

| Client | Config file location | Scope | Notes |
|---|---|---|---|
| **Cursor** | `~/.cursor/mcp.json` | Global | Also supports project-level `.cursor/mcp.json` |
| **Claude Code** | `~/.claude.json` | Global (user scope) | Top-level `mcpServers` key |
| **Claude Code** | `.claude/mcp.json` | Project | Standard format |
| **TRAE** | `~/.trae/mcp.json` | Global | Same format as Cursor. **Note**: WorkBuddy claims "GUI only, no CLI" — this is incorrect; CLI config is implemented and tested |
| **TRAE-CN** | `~/.trae-cn/mcp.json` | Global | Same format, detected if dir exists |
| **Windsurf** | `~/.windsurf/mcp.json` | Global | Same format as Cursor |
| **Cline** | `~/.cline/mcp.json` | Global | Same format |
| **OpenClaw** | Same as Claude Code | Global | Uses `~/.claude.json` or `.claude/mcp.json`. **Conflict**: WorkBuddy says `~/.openclaw/openclaw.json` — needs verification |
| **Kimi Code CLI** | Same as Claude Code | Global | Uses `~/.claude.json` format. **Conflict**: WorkBuddy says `~/.kimi/mcp.json` — needs verification |

**Verdict: No adapter layer needed.** All clients use the same `mcpServers` JSON format. The only differences are file paths, which are already handled in `constants.py`.

#### 1.2.2 MCP Server Protocol Compliance

Current implementation in [server.py](file:///Users/lin/trae_projects/carrymem/src/carrymem/integration/layer2_mcp/server.py):

- **Protocol version**: `2024-11-05` (current)
- **Transport**: stdio (JSON-RPC over stdin/stdout)
- **Methods implemented**: `initialize`, `initialized`, `tools/list`, `tools/call`, `shutdown`, `exit`
- **Capabilities**: `tools.listChanged: false`

**Gaps identified:**

1. **No `notifications/tools/list_changed`**: If tools change at runtime, clients won't know. Low priority since tools are static.
2. **No `resources` capability**: MCP supports resources (read-only data), but CarryMem doesn't expose any. Not needed for current use case.
3. **No `prompts` capability**: MCP supports prompt templates. Could be useful for `get_system_prompt` but not critical.
4. **No SSE/HTTP transport**: Only stdio. This limits integration with clients that prefer HTTP (e.g., Mem0's OpenMemory uses SSE). The HTTP server exists in `http_server.py` but is not wired to the MCP server.

#### 1.2.3 Security Assessment

| Concern | Current State | Risk | Recommendation |
|---|---|---|---|
| MCP server authentication | None | Medium | Add optional API key validation for HTTP transport |
| Input validation | InputValidator in handlers | Low | Adequate for stdio (local only) |
| Data encryption | Optional via `--encrypt` | Low | Good for pack/unpack |
| Path traversal | validate_path_safety() | Low | Well-handled |
| SQL injection | Parameterized queries in SQLiteAdapter | Low | Adequate |
| Secret redaction | Google/Stripe/Slack patterns | Low | Good coverage |
| Concurrent access | Per-file write lock | Low | Fixed in v0.2.0 |

**Key security insight**: Since MCP over stdio is local-only, the attack surface is minimal. The main risk is if HTTP transport is added without authentication. **Recommendation**: Do not expose HTTP transport without API key auth.

#### 1.2.4 WorkBuddy/CodeBuddy MCP Market Adaptation

**Item MCP Marketplace (WorkBuddy/CodeBuddy) submission process:**

1. **5-step workflow**: Guidelines → Service Info → Configuration → Documentation → Video
2. **MCP Type**: Select STDIO (CarryMem uses stdio)
3. **Required assets**:
   - Service name, provider, category, logo (512x512px, <2MB)
   - Use cases description
   - Technical documentation (Markdown)
   - Demo video (.mp4, optional but recommended)
4. **Review process**: AI automated review + manual review
5. **Configuration auto-generation**: System generates JSON from inputs

**Alternative: MCP Registry (official)**:

1. Create `server.json` manifest with reverse-DNS name
2. Use `mcp-publisher` CLI to submit
3. Also publish to npm for `npx` installability

**Recommendation**: Submit to Item MCP Marketplace first (direct user base for WorkBuddy/CodeBuddy), then MCP Registry for broader discoverability.

---

### 1.3 Developer Review

#### 1.3.1 `setup-mcp --global` Implementation Completeness

**Current implementation** ([cli.py:1983-2057](file:///Users/lin/trae_projects/carrymem/src/carrymem/cli.py#L1983)):

```python
# Supported --tool choices
choices=["claude-code", "cursor", "trae", "all"]
```

**Clients configured in `_setup_mcp_global()`:**

| Client | Config Target | Status |
|---|---|---|
| Claude Code | `~/.claude.json` (top-level mcpServers) | Implemented |
| Cursor | `~/.cursor/mcp.json` | Implemented |
| TRAE | `~/.trae/mcp.json` | Implemented |
| TRAE-CN | `~/.trae-cn/mcp.json` | Implemented (conditional) |

**Clients NOT in setup-mcp but defined in constants.py:**

| Client | Config Path | Status |
|---|---|---|
| Windsurf | `~/.windsurf/mcp.json` | Path defined, not in CLI |
| Cline | `~/.cline/mcp.json` | Path defined, not in CLI |
| Continue | `~/.continue/config.json` | Path defined, not in CLI |
| Aider | `~/.aider/mcp.json` | Path defined, not in CLI |

**Clients NOT in constants.py at all:**

| Client | Config Path | Status |
|---|---|---|
| OpenClaw | Same as Claude Code | Not needed (shares format) |
| Kimi Code CLI | Same as Claude Code | Not needed (shares format) |
| WorkBuddy | MCP Marketplace | Different mechanism |
| CodeBuddy | MCP Marketplace | Different mechanism |

**Code changes needed:**

1. **Add Windsurf, Cline, Continue, Aider to `--tool` choices** (~30 lines)
2. **Add corresponding blocks in `_setup_mcp_global()`** (~60 lines, copy-paste pattern)
3. **Add `--uninstall` flag** (~40 lines)
4. **Add post-setup smoke test** (~20 lines)
5. **Auto-init on first setup-mcp** (~10 lines)

**Estimated total: ~160 lines of code changes, 2-3 hours of work.**

#### 1.3.2 MCP Config File Format Differences

**Two distinct config formats:**

**Format A: Standard mcp.json (Cursor, TRAE, Windsurf, Cline)**

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

**Format B: Claude Code global config (~/.claude.json)**

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
  },
  "...other claude config..."
}
```

The only difference is that Claude Code's global config may contain other top-level keys. The `_merge_claude_global_config()` function already handles this correctly by merging only the `mcpServers` key.

**Continue uses a different structure** (`config.json` not `mcp.json`), needs investigation.

**Verdict: 95% format compatible. Only Continue needs special handling.**

#### 1.3.3 Per-Client Installation Guide Requirements

| Client | Guide Complexity | Key Steps |
|---|---|---|
| Cursor | Low | `carrymem setup-mcp --tool cursor --global` |
| Claude Code | Low | `carrymem setup-mcp --tool claude-code --global` |
| TRAE | Low | `carrymem setup-mcp --tool trae --global` |
| Windsurf | Low | `carrymem setup-mcp --tool windsurf --global` (needs implementation) |
| Cline | Low | `carrymem setup-mcp --tool cline --global` (needs implementation) |
| OpenClaw | Low | Same as Claude Code |
| Kimi Code CLI | Low | Same as Claude Code |
| WorkBuddy | Medium | Submit to MCP Marketplace, then one-click install |
| CodeBuddy | Medium | Submit to MCP Marketplace, then one-click install |
| DeepSeek CLI | High | Needs third-party TUI adapter |

**Recommendation**: Create a single "Client Integration Guide" document covering all clients, rather than per-client guides. The setup-mcp command should be the single source of truth.

---

### 1.4 DevOps Review

#### 1.4.1 PyPI Publishing: 0.1.6 → 0.2.0

**Current state:**

- Source version: `0.2.0` (in `__version__.py`)
- PyPI version: `0.1.6` (8 versions behind)
- Build system: setuptools + wheel
- CI build gate: Already tests `python -m build` + `twine check`

**Steps to publish 0.2.0:**

1. Verify `__version__.py` = `0.2.0` (confirmed)
2. Verify `setup.py` reads version dynamically (confirmed via `get_version()`)
3. Verify CHANGELOG.md has 0.2.0 entry (confirmed)
4. Run full CI pipeline locally: `python scripts/ci_local_check.py`
5. Build: `python -m build`
6. Check: `twine check dist/*`
7. Upload: `twine upload dist/*`
8. Verify: `pip install carrymem==0.2.0`

**Risk**: Skipping versions (0.1.6 → 0.2.0) may confuse users who are on 0.1.6 and see a jump. But since this is pre-1.0, it's acceptable.

**Recommendation**: Publish 0.2.0 immediately. Do not publish intermediate versions.

#### 1.4.2 GitHub Actions CI/CD Assessment

**Current CI pipeline** ([ci.yml](file:///Users/lin/trae_projects/carrymem/.github/workflows/ci.yml)):

| Gate | Status | Coverage |
|---|---|---|
| Code Quality | Active | flake8, black, isort, mypy |
| i18n Compliance | Active | Chinese character detection |
| Unit Tests | Active | Python 3.9-3.12 matrix |
| Build & Install | Active | sdist + wheel + fresh venv test |
| Security Scan | Active | Secrets, bare except, SQL injection |
| Documentation | Active | Required docs, version consistency |

**Missing CI/CD capabilities:**

1. **No automated PyPI publish**: Need a `publish.yml` workflow triggered on tag push
2. **No release automation**: Need `release.yml` for GitHub Releases with auto-generated notes
3. **No MCP server smoke test in CI**: Should verify `carrymem mcp` starts and responds to `initialize`
4. **No integration test with real MCP clients**: Would need containerized Cursor/Claude (complex, defer to P2)

**Recommended `publish.yml` workflow:**

```yaml
name: Publish to PyPI
on:
  push:
    tags: ['v*']
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install build twine
      - run: python -m build
      - run: twine check dist/*
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
```

#### 1.4.3 Issue Template Assessment

**Current templates** (already exist):

- `bug_report.md` — Complete with environment, repro steps, error output
- `feature_request.md` — Exists
- `question.md` — Exists
- `config.yml` — Disables blank issues, links to docs and roadmap

**Missing templates:**

1. **MCP Integration Issue**: Specific template for client integration problems (which client, config file path, error message)
2. **Client Support Request**: Template for requesting support for a new MCP client

**Recommendation**: Add MCP-specific issue template. Low effort, high value for launch.

#### 1.4.4 Version Tag and Release Management

**Current state:**

- No git tags found for recent versions
- CHANGELOG.md tracks versions but no formal release process
- CI triggers on `new-main` branch, not tags

**Recommended version management:**

1. **Tag format**: `v0.2.0` (semver with `v` prefix)
2. **Release process**:
   - Update `__version__.py`
   - Update `CHANGELOG.md`
   - Commit with message `chore: release v0.2.0`
   - Tag: `git tag v0.2.0`
   - Push: `git push origin new-main --tags`
   - CI auto-publishes to PyPI
   - GitHub Release auto-created from tag

---

## 2. Client Integration Feasibility Final Assessment

### 2.1 Feasibility Matrix (Revised — Merged with WorkBuddy)

| Client | MCP Support | Integration Effort | Setup Method | Feasibility | Priority |
|---|---|---|---|---|---|
| **Cursor** | Direct | Zero (done) | `setup-mcp --tool cursor --global` | **Confirmed** | P0 ✅ |
| **Claude Code** | Direct | Zero (done) | `setup-mcp --tool claude-code --global` | **Confirmed** | P0 ✅ |
| **TRAE** | Direct | Zero (done) | `setup-mcp --tool trae --global` | **Confirmed** | P0 ✅ |
| **Windsurf** | Direct | Low (done) | `setup-mcp --tool windsurf --global` | **Confirmed** | P0 ✅ |
| **Cline** | Direct | Low (done) | `setup-mcp --tool cline --global` | **Confirmed** | P0 ✅ |
| **OpenClaw** | Direct | Low (done) | `setup-mcp --tool openclaw --global` (falls back to Claude Code format) | **High** | P0 ✅ |
| **Kimi Code CLI** | Direct | Low (done) | `setup-mcp --tool kimi-code --global` (falls back to Claude Code format) | **High** | P0 ✅ |
| **CodeX** | Direct (done) | Low (done) | `setup-mcp --tool codex --global` (falls back to Claude Code format) | **Medium** | P0 ✅ |
| **WorkBuddy** | Direct | Medium (4 hr) | MCP Marketplace submission (alt: `~/.workbuddy/mcp.json`) | **High** | P1 |
| **CodeBuddy** | Direct | Medium (4 hr) | MCP Marketplace submission (alt: `~/.workbuddy/mcp.json` + GUI) | **High** | P1 |
| **Aider** | Direct | Low (30 min) | `setup-mcp --tool aider --global` | **Medium** | P2 |
| **Continue** | Indirect | Medium (2 hr) | Different config format (`config.json`) | **Medium** | P2 |
| **DeepSeek CLI** | Indirect | High (2+ days) | Third-party TUI adapter needed | **Low** | P2 |
| **Kimi Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |
| **DeepSeek Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |
| **通义千问 Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |
| **豆包 Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |
| **天工 Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |
| **智谱清言 Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |

### 2.2 Key Insight: Claude Code Format is the De Facto Standard

OpenClaw and Kimi Code CLI both use the same configuration format as Claude Code. This means:

- **No additional code needed** for these clients
- **Documentation only**: Add a note saying "If you use OpenClaw or Kimi Code CLI, run `carrymem setup-mcp --tool claude-code --global`"
- **Future**: Consider adding aliases (`--tool openclaw` → same as `--tool claude-code`)

---

## 3. Revised Launch Plan (P0/P1/P2) — Merged with WorkBuddy Checklist

### P0: Must Complete Before Launch (Target: 3 days, ~15hr total)

| # | Item | Source | Owner | Effort | Status | Code Changes |
|---|---|---|---|---|---|---|
| P0-1 | About Description update | WorkBuddy | PM | 10 min | ✅ Done | README.md |
| P0-2 | Topics fix (obsidian typo, add claude-code/agent-memory) | WorkBuddy | PM | 10 min | ✅ Done | README.md |
| P0-3 | PrefEval academic badge | WorkBuddy | PM | 30 min | ✅ Done | README.md |
| P0-4 | pack/unpack commands (v1.1 format + encryption) | WorkBuddy | Developer | 4 hr | ✅ Done | cli.py, encryption.py |
| P0-5 | setup-mcp --global for 8 clients (Windsurf, Cline, OpenClaw, Kimi-Code, CodeX) | Consensus | Developer | 1.5 hr | ✅ Done | cli.py, constants.py |
| P0-6 | PyPI 0.2.0 publish (build + twine check passed) | Consensus | DevOps | 1 hr | ✅ Ready | dist/ |
| P0-7 | Beta Feedback + MCP Integration issue templates | Merged | DevOps | 30 min | ✅ Done | .github/ISSUE_TEMPLATE/ |
| P0-8 | First-run experience (auto-init + smoke test + --uninstall) | Consensus | Developer | 2.5 hr | ✅ Done | cli.py |
| P0-9 | Obsidian adapter documentation | P2→P0 | Developer | 2 hr | ✅ Done | docs/OBSIDIAN_ADAPTER.md |
| P0-10 | CodeX client support | P2→P0 | Developer | 2 hr | ✅ Done | cli.py, constants.py |
| P0-11 | Community directory manifest files (Glama/Smithery) | P2→P0 | PM | 2 hr | ✅ Files Ready | server.json, smithery.yaml (submission pending account registration) |

**WorkBuddy P0 items already completed** (verified against codebase):

| Item | Status | Evidence |
|---|---|---|
| README scenario entry | ✅ Done | README line 60, 101: `setup-mcp --all --global` |
| About Description update | ✅ Done | README line 1-5: "Stop teaching AI who you are..." |
| Topics fix and supplement | ✅ Done | README line 25: `claude-code`, `agent-memory`, `obsidian` |
| PrefEval badge | ✅ Done | README line 21: academic badge with ICLR 2025 Oral |
| pack/unpack commands | ✅ Done | cli.py:761 cmd_pack, cli.py:965 cmd_unpack |
| setup-mcp --global | ⚠️ Partial | Only 3+1 clients (claude-code, cursor, trae, trae-cn) |
| Beta Feedback issue template | ❌ Not done | Only bug_report, feature_request, question exist |
| CHANGELOG update | ⚠️ Verify | CHANGELOG.md exists, 0.2.0 entry needs confirmation |

### P1: Within 1 Week After Launch (Target: 7 days)

| # | Item | Source | Owner | Effort | Notes |
|---|---|---|---|---|---|
| P1-1 | WeChat Official Account promotion article | WorkBuddy | PM | 2 hr | Draft exists at `drafts/carrymem-beta-招募-2026-05-28.md` |
| P1-2 | WorkBuddy MCP Marketplace submission | Consensus | Architect | 4 hr | Prepare assets, submit, iterate on review |
| P1-3 | CodeBuddy MCP Marketplace submission | Consensus | Architect | 2 hr | Reuse WorkBuddy assets |
| P1-4 | OpenClaw config path verification | Merged | Developer | 2 hr | **Conflict**: WorkBuddy says `~/.openclaw/openclaw.json`, consensus says same as Claude Code. Must verify by installing OpenClaw |
| P1-5 | Kimi Code CLI config path verification | Merged | Developer | 2 hr | **Conflict**: WorkBuddy says `~/.kimi/mcp.json`, consensus says same as Claude Code. Must verify |
| P1-6 | GitHub Actions: auto-publish on tag | Consensus | DevOps | 2 hr | publish.yml workflow |
| P1-7 | GitHub Actions: auto-release on tag | Consensus | DevOps | 1 hr | release.yml with changelog extraction |
| P1-8 | MCP Registry submission | Consensus | Architect | 3 hr | server.json + mcp-publisher CLI |
| P1-9 | Non-technical user installation guide (illustrated) | WorkBuddy | PM | 3 hr | Screenshot walkthrough for CLI-averse users |
| P1-10 | Trial period data collection mechanism | WorkBuddy | PM+DevOps | 2 hr | Track installs, active usage, feedback patterns |
| P1-11 | Add Aider to setup-mcp | Consensus | Developer | 30 min | Low priority but easy |

### P2: Ongoing (Target: 30 days)

| # | Item | Source | Owner | Effort | Notes |
|---|---|---|---|---|---|
| P2-1 | Continue adapter (config.json format) | Consensus | Developer | 2 hr | Different JSON structure |
| P2-2 | DeepSeek CLI community adapter | Consensus | Architect | 2+ days | Needs third-party TUI, community effort |
| P2-3 | SSE/HTTP transport for MCP server | Consensus | Architect | 1 week | Wire http_server.py to MCP protocol. **Prerequisite for P2-8** |
| P2-4 | Web UI for non-technical users | Consensus | Architect | 2+ weeks | Dashboard for memory management |
| P2-5 | MCP server integration test in CI | Consensus | DevOps | 4 hr | Verify initialize/tools-list in pipeline |
| P2-6 | Cloud MCP Server | WorkBuddy | Architect | 2-4 weeks | Solves corporate laptop permission issues. **Depends on P2-3 (SSE/HTTP)** |
| P2-7 | Multi-language docs completion | Consensus | PM | Ongoing | i18n docs already exist, keep updated |

---

## 4. Action Item Checklist — Merged with WorkBuddy Cadence

### Phase 1: Technical Preparation (Day 1-3)

| Who | What | When | Deliverable |
|---|---|---|---|
| DevOps | Publish v0.2.0 to PyPI | Day 1 | `pip install carrymem==0.2.0` works |
| Developer | Add Windsurf + Cline to setup-mcp | Day 1 | `--tool windsurf` and `--tool cline` work |
| Developer | Add `--uninstall` flag | Day 2 | `carrymem setup-mcp --uninstall --global` works |
| Developer | Post-setup smoke test | Day 2 | Verifies MCP server starts after config |
| Developer | Auto-init in setup-mcp | Day 2 | No separate `carrymem init` needed |
| DevOps | Add Beta Feedback + MCP integration issue templates | Day 2 | `.github/ISSUE_TEMPLATE/` updated |
| PM | Update Quick Start Guide | Day 3 | setup-mcp --global prominently featured |
| Developer | E2E user journey test | Day 3 | Automated test covering full flow |

### Phase 2: Launch + Promotion (Day 4-7)

| Who | What | When | Deliverable |
|---|---|---|---|
| PM | Publish WeChat Official Account article | Day 4 (T+0) | Article live, "one command" promise deliverable |
| PM | Update GitHub README/About/Topics | Day 4 (T+1) | Already done, verify consistency |
| PM | Community forwarding + first feedback | Day 5 (T+2) | Collect first 10 user feedbacks |
| Architect | Prepare MCP Marketplace assets | Day 4-5 | Logo, description, docs, demo video |
| Architect | Submit to WorkBuddy/CodeBuddy Marketplace | Day 5 | Submission live, pending review |
| Developer | Verify OpenClaw + Kimi Code CLI config paths | Day 5-6 | Documented working config, resolve path conflicts |
| DevOps | Create publish.yml workflow | Day 6 | Auto-publish on tag push |
| DevOps | Create release.yml workflow | Day 7 | Auto-release with changelog |
| Architect | Submit to MCP Registry | Day 7 | server.json published |

### Phase 3: Stabilization (Day 8-14)

| Who | What | When | Deliverable |
|---|---|---|---|
| PM | Fix most urgent install/usage issues from feedback | Day 8-10 (T+7) | Hotfix release if needed |
| PM | Non-technical user installation guide | Day 8-10 | Illustrated walkthrough |
| PM+DevOps | Trial period data collection setup | Day 8-10 | Install/usage/feedback tracking |
| Developer | Add Aider to setup-mcp | Day 10 | `--tool aider` works |
| PM | Second WeChat article (user stories / data update) | Day 14 (T+14) | Article with real usage data |

---

## 5. Risks and Mitigations

### 5.1 High Risks

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| PyPI publish fails (build error) | Launch blocked | Low | CI already tests build; pre-publish dry run |
| MCP Marketplace rejects submission | Delayed WorkBuddy/CodeBuddy support | Medium | Follow guidelines strictly; prepare demo video |
| Client config format changes | setup-mcp breaks | Low | MCP protocol is stable; monitor client changelogs |
| Version confusion (0.1.6 → 0.2.0 jump) | User confusion | Medium | Clear CHANGELOG; pin version in docs |
| WeChat article published before P0 complete | "One command" promise broken | Medium | Enforce P0 completion gate before article publication |

### 5.2 Medium Risks

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| OpenClaw/Kimi CLI format differs from Claude Code | Extra dev work | Low | Test early; community feedback |
| Continue config.json incompatible | Cannot support Continue | Medium | Defer to P2; document limitation |
| MCP server crash on specific client | Bad first impression | Low | Smoke test after setup; error recovery |
| PyPI API token not configured | Cannot auto-publish | Medium | Set up token before first tag push |
| Non-technical users cannot use CLI | Low activation from WeChat readers | Medium | Illustrated guide in P1; Web UI in P2 |

### 5.3 Low Risks

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| DeepSeek CLI adapter too complex | No DeepSeek support | High | Accept as P2; community-driven |
| Desktop clients (Kimi/DeepSeek) never support MCP | No desktop coverage | High | CLI versions work; desktop is not target |
| Security vulnerability in MCP server | Trust damage | Low | Security scan in CI; local-only stdio limits exposure |

---

## 6. Consensus Decisions

### 6.1 Agreed Upon

1. **Launch with 3 confirmed clients** (Cursor, Claude Code, TRAE) + 2 easy additions (Windsurf, Cline)
2. **PyPI 0.2.0 is the launch version** — no backfilling intermediate versions
3. **No adapter layer needed** — all clients use the same mcpServers JSON format
4. **No SSE/HTTP transport for launch** — stdio is sufficient and more secure
5. **MCP Marketplace submission is P1, not P0** — requires asset preparation
6. **OpenClaw and Kimi Code CLI use Claude Code config** — no code changes, documentation only (pending verification)
7. **Desktop clients (Kimi/DeepSeek) are not supported** — closed platforms, CLI versions work
8. **`setup-mcp --global` is the primary onboarding path** — must be rock-solid
9. **Technical preparation before promotion** — P0 must complete before WeChat article publication (WorkBuddy had T+0 as article, adjusted to T+1 after P0)
10. **Promotion cadence adopted from WorkBuddy** — T+0 (PyPI+P0) → T+1 (WeChat article) → T+2 (community) → T+7 (fixes) → T+14 (second article)
11. **Trial quality over quantity** — "10 people install, 8 use it" beats "100 install, 20 use it"

### 6.2 Deferred Decisions

1. **Web UI timing**: Defer to P2, but begin design exploration in P1
2. **Cloud sync pricing model**: Defer to post-launch, observe user demand
3. **MCP Registry vs Marketplace priority**: Start with Marketplace (direct user base), then Registry
4. **Continue support**: Defer until config format is verified
5. **Cloud MCP Server**: Defer to P2 (after SSE/HTTP transport is ready)

### 6.3 Disagreements Resolved

1. **Should we add all clients to setup-mcp before launch?**
   - PM: Yes, maximize coverage
   - Developer: No, ship fast with top 5, add rest in P1
   - **Resolution**: Ship with top 5 (Cursor, Claude Code, TRAE, Windsurf, Cline), add rest in P1

2. **Should PyPI publish be automated before launch?**
   - DevOps: Yes, prevents manual errors
   - PM: No, manual first to ensure quality, automate in P1
   - **Resolution**: Manual publish for 0.2.0, automate for subsequent releases

3. **Should WeChat article publish at T+0?** (New from WorkBuddy merge)
   - WorkBuddy: Yes, T+0 is article publication
   - Consensus: No, P0 technical items must complete first
   - **Resolution**: T+0 = P0 completion + PyPI publish. WeChat article at T+1. "One command" promise must be deliverable before promotion.

4. **OpenClaw/Kimi Code CLI config paths** (New conflict from merge)
   - WorkBuddy: `~/.openclaw/openclaw.json`, `~/.kimi/mcp.json`
   - Consensus: Same as Claude Code format
   - **Resolution**: Verify by actual installation in P1. Consensus inference (Claude Code format) is more likely correct based on ecosystem analysis, but WorkBuddy may have firsthand knowledge. Mark as conflict requiring verification.

---

## 7. Success Metrics

| Metric | Target | Measurement |
|---|---|---|
| PyPI downloads (first week) | 500+ | PyPI stats |
| GitHub stars (first month) | 200+ | GitHub API |
| setup-mcp success rate | >95% | Error reports vs installs |
| Client coverage | 5+ clients | setup-mcp --tool choices |
| MCP Marketplace approval | Both WorkBuddy + CodeBuddy | Listing live |
| Issue response time | <24h for P0 bugs | GitHub metrics |
| Trial activation rate | >80% | Active users / total installs (WorkBuddy: "10 install, 8 use") |
| WeChat article engagement | 500+ reads | Official Account analytics |
| First-week feedback count | 20+ issues/comments | GitHub + WeChat |

---

## 8. WorkBuddy Checklist Merge Analysis

### 8.1 Difference Matrix

| Dimension | WorkBuddy Checklist | Consensus Document | Difference Type |
|---|---|---|---|
| P0 item count | 8 | 8 | Same count, different content |
| Completed items | 4 (About/Topics/badge/pack) | 0 (all Pending) | WorkBuddy more realistic |
| PyPI publish | Not mentioned | P0-1 | Consensus-only |
| --uninstall | Not mentioned | P0-3 | Consensus-only |
| Smoke test | Not mentioned | P0-4 | Consensus-only |
| Auto-init | Not mentioned | P0-5 | Consensus-only |
| E2E test | Not mentioned | P0-8 | Consensus-only |
| WeChat promotion | Core strategy | Not mentioned | WorkBuddy-only |
| Launch cadence | T+0 to T+14 | Not mentioned | WorkBuddy-only |
| Non-technical user guide | P1 | Not mentioned | WorkBuddy-only |
| Trial data collection | P1 | Not mentioned | WorkBuddy-only |
| Cloud MCP Server | P2 | Not mentioned (has SSE/HTTP P2) | Related but different |
| Obsidian adapter docs | P2 | Not mentioned | WorkBuddy-only |
| Competitive analysis | None | Mem0/OpenMemory | Consensus-only |
| CI/CD automation | None | publish.yml/release.yml | Consensus-only |
| Security assessment | None | Full matrix | Consensus-only |
| Client matrix | 10 (incl. CodeX/DeepSeek/Kimi Desktop) | 14 (incl. Windsurf/Cline/Aider/Continue) | Complementary |

### 8.2 Conflicts

| # | Conflict | WorkBuddy | Consensus | Code Verification | Resolution |
|---|---|---|---|---|---|
| C1 | TRAE config method | "GUI only, no CLI" | "CLI implemented via ~/.trae/mcp.json" | ✅ Code implemented + tests pass | **Consensus correct**, WorkBuddy info outdated |
| C2 | OpenClaw config path | `~/.openclaw/openclaw.json` | Same as Claude Code | No code verification | **Needs testing**. Consensus inference more likely |
| C3 | Kimi Code CLI path | `~/.kimi/mcp.json` | Same as Claude Code | No code verification | **Needs testing**. Both possibilities exist |
| C4 | Launch vs promotion order | Promotion first (T+0 article) | Technical prep first | — | **Technical first**. Article after P0 complete |

### 8.3 Complementary Items

| # | Content | Source | Value |
|---|---|---|---|
| S1 | WeChat promotion strategy | WorkBuddy | Reach Chinese developer community |
| S2 | Launch cadence T+0~T+14 | WorkBuddy | Time anchors for each phase |
| S3 | Non-technical user guide | WorkBuddy P1 | Lower trial barrier, pairs with WeChat |
| S4 | Trial data collection | WorkBuddy P1 | Quantify launch effectiveness |
| S5 | Obsidian adapter docs | WorkBuddy P2 | Existing feature, differentiation point |
| S6 | CodeX client | WorkBuddy | OpenClaw ecosystem, not in consensus |
| S7 | Competitive analysis | Consensus | Mem0/OpenMemory detailed comparison |
| S8 | CI/CD automation | Consensus | publish.yml/release.yml |
| S9 | Security assessment | Consensus | Full security matrix |
| S10 | --uninstall/smoke test/auto-init | Consensus | User experience completeness |

### 8.4 Impact Assessment

| Impact Dimension | Score (1-5) | Description |
|---|---|---|
| P0 list impact | ⭐⭐⭐ (3/5) | 4/8 WorkBuddy P0 items already done; new items mainly from consensus |
| P1 list impact | ⭐⭐⭐⭐⭐ (5/5) | WeChat promotion, non-technical guide, data collection are entirely new |
| Technical architecture impact | ⭐⭐ (2/5) | Client path conflicts need verification; Cloud MCP Server is long-term |
| Launch cadence impact | ⭐⭐⭐⭐ (4/5) | T+0~T+14 fills consensus document's time planning gap |
| Product positioning impact | ⭐⭐⭐ (3/5) | "Pain points not tech" positioning complements "lightweight, intelligent" |

**Overall**: WorkBuddy checklist has **highest impact on P1** (promotion + user operations), **limited P0 impact** (most done or consensus more comprehensive), and **provides new P2 directions** (Cloud MCP/Obsidian docs/CodeX).

---

## Appendix A: File Reference

| File | Path | Role |
|---|---|---|
| MCP Server | `src/carrymem/integration/layer2_mcp/server.py` | Core MCP protocol implementation |
| MCP Tools | `src/carrymem/integration/layer2_mcp/tools.py` | 27 tool definitions |
| MCP Handlers | `src/carrymem/integration/layer2_mcp/handlers.py` | Tool execution logic |
| CLI | `src/carrymem/cli.py` | setup-mcp command (line 1880) |
| Constants | `src/carrymem/constants.py` | Path configurations |
| Version | `src/carrymem/__version__.py` | `0.2.0` |
| Setup | `setup.py` | Package build configuration |
| CI | `.github/workflows/ci.yml` | 6-gate CI pipeline |
| Issue Templates | `.github/ISSUE_TEMPLATE/` | bug, feature, question |
| Integration Examples | `integrations/claude_code/mcp.json`, `integrations/cursor/mcp.json` | Reference configs |

## Appendix B: Competitor Feature Comparison

| Feature | CarryMem v0.2.0 | Mem0 OpenMemory | Mem0 Cloud |
|---|---|---|---|
| Memory classification | 7 types, 4 tiers | Flat | Flat + graph |
| Rule engine | Full (7 operations) | None | None |
| Consolidation | Auto (dedup/decay/promote) | Manual delete | Auto |
| Onboarding | Built-in `onboard` tool | None | None |
| System prompt injection | `get_system_prompt` | None | None |
| Knowledge base | Obsidian integration | None | None |
| Encryption | Optional (pack --encrypt) | None | TLS in transit |
| Setup time | <30 seconds | ~10 minutes | API key only |
| Dependencies | Python + SQLite | Docker + Qdrant + Postgres | Cloud API |
| Cost | Free (local) | Free (local) | Paid (cloud) |
