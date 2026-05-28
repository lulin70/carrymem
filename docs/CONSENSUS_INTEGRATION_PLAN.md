# CarryMem Client Integration Consensus Document

**Date**: 2026-05-28
**Version**: 1.0
**Participants**: PM, Architect, Developer, DevOps (DevSquad Multi-Role Review)
**Status**: Final

---

## Executive Summary

CarryMem v0.2.4 is technically ready for client integration launch. The MCP server implementation is mature (27 tools, 7 categories, protocol 2024-11-05), and the `setup-mcp --global` command works for the top 3 clients (Claude Code, Cursor, TRAE). However, critical gaps exist: PyPI version lag (0.1.6 vs 0.2.4), missing client support in setup-mcp (Windsurf, Cline, OpenClaw, etc.), and no automated PyPI publishing. This document captures the multi-role consensus on feasibility, priority, and action plan.

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
| PyPI 0.2.4 release | Not done | Still at 0.1.6, 8 versions behind |

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
| **TRAE** | `~/.trae/mcp.json` | Global | Same format as Cursor |
| **TRAE-CN** | `~/.trae-cn/mcp.json` | Global | Same format, detected if dir exists |
| **Windsurf** | `~/.windsurf/mcp.json` | Global | Same format as Cursor |
| **Cline** | `~/.cline/mcp.json` | Global | Same format |
| **OpenClaw** | Same as Claude Code | Global | Uses `~/.claude.json` or `.claude/mcp.json` |
| **Kimi Code CLI** | Same as Claude Code | Global | Uses `~/.claude.json` format |

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
| Concurrent access | Per-file write lock | Low | Fixed in v0.2.4 |

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

#### 1.4.1 PyPI Publishing: 0.1.6 → 0.2.4

**Current state:**

- Source version: `0.2.4` (in `__version__.py`)
- PyPI version: `0.1.6` (8 versions behind)
- Build system: setuptools + wheel
- CI build gate: Already tests `python -m build` + `twine check`

**Steps to publish 0.2.4:**

1. Verify `__version__.py` = `0.2.4` (confirmed)
2. Verify `setup.py` reads version dynamically (confirmed via `get_version()`)
3. Verify CHANGELOG.md has 0.2.4 entry (confirmed)
4. Run full CI pipeline locally: `python scripts/ci_local_check.py`
5. Build: `python -m build`
6. Check: `twine check dist/*`
7. Upload: `twine upload dist/*`
8. Verify: `pip install carrymem==0.2.4`

**Risk**: Skipping versions (0.1.6 → 0.2.4) may confuse users who are on 0.1.6 and see a jump. But since this is pre-1.0, it's acceptable.

**Recommendation**: Publish 0.2.4 immediately. Do not publish intermediate versions.

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

1. **Tag format**: `v0.2.4` (semver with `v` prefix)
2. **Release process**:
   - Update `__version__.py`
   - Update `CHANGELOG.md`
   - Commit with message `chore: release v0.2.4`
   - Tag: `git tag v0.2.4`
   - Push: `git push origin new-main --tags`
   - CI auto-publishes to PyPI
   - GitHub Release auto-created from tag

---

## 2. Client Integration Feasibility Final Assessment

### 2.1 Feasibility Matrix (Revised)

| Client | MCP Support | Integration Effort | Setup Method | Feasibility | Priority |
|---|---|---|---|---|---|
| **Cursor** | Direct | Zero (done) | `setup-mcp --tool cursor --global` | **Confirmed** | P0 |
| **Claude Code** | Direct | Zero (done) | `setup-mcp --tool claude-code --global` | **Confirmed** | P0 |
| **TRAE** | Direct | Zero (done) | `setup-mcp --tool trae --global` | **Confirmed** | P0 |
| **Windsurf** | Direct | Low (30 min) | `setup-mcp --tool windsurf --global` | **High** | P1 |
| **Cline** | Direct | Low (30 min) | `setup-mcp --tool cline --global` | **High** | P1 |
| **OpenClaw** | Direct | Zero | Same config as Claude Code | **High** | P1 |
| **Kimi Code CLI** | Direct | Zero | Same config as Claude Code | **High** | P1 |
| **Aider** | Direct | Low (30 min) | `setup-mcp --tool aider --global` | **Medium** | P2 |
| **Continue** | Indirect | Medium (2 hr) | Different config format (`config.json`) | **Medium** | P2 |
| **WorkBuddy** | Direct | Medium (4 hr) | MCP Marketplace submission | **High** | P1 |
| **CodeBuddy** | Direct | Medium (4 hr) | MCP Marketplace submission | **High** | P1 |
| **DeepSeek CLI** | Indirect | High (2+ days) | Third-party TUI adapter needed | **Low** | P2 |
| **Kimi Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |
| **DeepSeek Desktop** | None | N/A | Closed desktop, no MCP | **Not feasible** | N/A |

### 2.2 Key Insight: Claude Code Format is the De Facto Standard

OpenClaw and Kimi Code CLI both use the same configuration format as Claude Code. This means:

- **No additional code needed** for these clients
- **Documentation only**: Add a note saying "If you use OpenClaw or Kimi Code CLI, run `carrymem setup-mcp --tool claude-code --global`"
- **Future**: Consider adding aliases (`--tool openclaw` → same as `--tool claude-code`)

---

## 3. Revised Launch Plan (P0/P1/P2)

### P0: Must Complete Before Launch (Target: 3 days)

| # | Item | Owner | Effort | Status | Notes |
|---|---|---|---|---|---|
| P0-1 | PyPI 0.2.4 publish | DevOps | 1 hr | Pending | Manual publish first, automate later |
| P0-2 | Add Windsurf + Cline to setup-mcp | Developer | 1 hr | Pending | Copy-paste pattern from existing |
| P0-3 | Add `--uninstall` flag to setup-mcp | Developer | 2 hr | Pending | Remove carrymem from client configs |
| P0-4 | Post-setup smoke test | Developer | 1 hr | Pending | Verify MCP server starts after config |
| P0-5 | Auto-init in setup-mcp | Developer | 30 min | Pending | Run init if ~/.carrymem/ doesn't exist |
| P0-6 | MCP integration issue template | DevOps | 30 min | Pending | New template for client-specific issues |
| P0-7 | Quick Start Guide update | PM | 1 hr | Pending | Add setup-mcp --global to guide |
| P0-8 | E2E test: full user journey | Developer | 2 hr | Pending | Install → setup-mcp → add → recall → pack |

### P1: Within 1 Week After Launch (Target: 7 days)

| # | Item | Owner | Effort | Notes |
|---|---|---|---|---|
| P1-1 | WorkBuddy MCP Marketplace submission | Architect | 4 hr | Prepare assets, submit, iterate on review |
| P1-2 | CodeBuddy MCP Marketplace submission | Architect | 2 hr | Reuse WorkBuddy assets |
| P1-3 | OpenClaw config verification | Developer | 2 hr | Install OpenClaw, test setup-mcp, document |
| P1-4 | Kimi Code CLI config verification | Developer | 2 hr | Install Kimi Code, test setup-mcp, document |
| P1-5 | GitHub Actions: auto-publish on tag | DevOps | 2 hr | publish.yml workflow |
| P1-6 | GitHub Actions: auto-release on tag | DevOps | 1 hr | release.yml with changelog extraction |
| P1-7 | MCP Registry submission | Architect | 3 hr | server.json + mcp-publisher CLI |
| P1-8 | Add Aider to setup-mcp | Developer | 30 min | Low priority but easy |

### P2: Ongoing (Target: 30 days)

| # | Item | Owner | Effort | Notes |
|---|---|---|---|---|
| P2-1 | Continue adapter (config.json format) | Developer | 2 hr | Different JSON structure |
| P2-2 | DeepSeek CLI community adapter | Architect | 2+ days | Needs third-party TUI, community effort |
| P2-3 | Web UI for non-technical users | Architect | 2+ weeks | Dashboard for memory management |
| P2-4 | SSE/HTTP transport for MCP server | Architect | 1 week | Wire http_server.py to MCP protocol |
| P2-5 | Multi-language docs completion | PM | Ongoing | i18n docs already exist, keep updated |
| P2-6 | MCP server integration test in CI | DevOps | 4 hr | Verify initialize/tools-list in pipeline |
| P2-7 | Community directory submissions | PM | 2 hr | Glama, Smithery, MCP Market |

---

## 4. Action Item Checklist

### Immediate (This Week)

| Who | What | When | Deliverable |
|---|---|---|---|
| DevOps | Publish v0.2.4 to PyPI | Day 1 | `pip install carrymem==0.2.4` works |
| Developer | Add Windsurf + Cline to setup-mcp | Day 1 | `--tool windsurf` and `--tool cline` work |
| Developer | Add `--uninstall` flag | Day 2 | `carrymem setup-mcp --uninstall --global` works |
| Developer | Post-setup smoke test | Day 2 | Verifies MCP server starts after config |
| Developer | Auto-init in setup-mcp | Day 2 | No separate `carrymem init` needed |
| DevOps | Add MCP integration issue template | Day 2 | `.github/ISSUE_TEMPLATE/mcp_integration.md` |
| PM | Update Quick Start Guide | Day 3 | setup-mcp --global prominently featured |
| Developer | E2E user journey test | Day 3 | Automated test covering full flow |

### Week 2

| Who | What | When | Deliverable |
|---|---|---|---|
| Architect | Prepare MCP Marketplace assets | Day 4-5 | Logo, description, docs, demo video |
| Architect | Submit to WorkBuddy/CodeBuddy Marketplace | Day 5 | Submission live, pending review |
| Developer | Verify OpenClaw + Kimi Code CLI | Day 5-6 | Documented working config |
| DevOps | Create publish.yml workflow | Day 6 | Auto-publish on tag push |
| DevOps | Create release.yml workflow | Day 7 | Auto-release with changelog |
| Architect | Submit to MCP Registry | Day 7 | server.json published |

---

## 5. Risks and Mitigations

### 5.1 High Risks

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| PyPI publish fails (build error) | Launch blocked | Low | CI already tests build; pre-publish dry run |
| MCP Marketplace rejects submission | Delayed WorkBuddy/CodeBuddy support | Medium | Follow guidelines strictly; prepare demo video |
| Client config format changes | setup-mcp breaks | Low | MCP protocol is stable; monitor client changelogs |
| Version confusion (0.1.6 → 0.2.4 jump) | User confusion | Medium | Clear CHANGELOG; pin version in docs |

### 5.2 Medium Risks

| Risk | Impact | Probability | Mitigation |
|---|---|---|---|
| OpenClaw/Kimi CLI format differs from Claude Code | Extra dev work | Low | Test early; community feedback |
| Continue config.json incompatible | Cannot support Continue | Medium | Defer to P2; document limitation |
| MCP server crash on specific client | Bad first impression | Low | Smoke test after setup; error recovery |
| PyPI API token not configured | Cannot auto-publish | Medium | Set up token before first tag push |

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
2. **PyPI 0.2.4 is the launch version** — no backfilling intermediate versions
3. **No adapter layer needed** — all clients use the same mcpServers JSON format
4. **No SSE/HTTP transport for launch** — stdio is sufficient and more secure
5. **MCP Marketplace submission is P1, not P0** — requires asset preparation
6. **OpenClaw and Kimi Code CLI use Claude Code config** — no code changes, documentation only
7. **Desktop clients (Kimi/DeepSeek) are not supported** — closed platforms, CLI versions work
8. **`setup-mcp --global` is the primary onboarding path** — must be rock-solid

### 6.2 Deferred Decisions

1. **Web UI timing**: Defer to P2, but begin design exploration in P1
2. **Cloud sync pricing model**: Defer to post-launch, observe user demand
3. **MCP Registry vs Marketplace priority**: Start with Marketplace (direct user base), then Registry
4. **Continue support**: Defer until config format is verified

### 6.3 Disagreements Resolved

1. **Should we add all clients to setup-mcp before launch?**
   - PM: Yes, maximize coverage
   - Developer: No, ship fast with top 5, add rest in P1
   - **Resolution**: Ship with top 5 (Cursor, Claude Code, TRAE, Windsurf, Cline), add rest in P1

2. **Should PyPI publish be automated before launch?**
   - DevOps: Yes, prevents manual errors
   - PM: No, manual first to ensure quality, automate in P1
   - **Resolution**: Manual publish for 0.2.4, automate for subsequent releases

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

---

## Appendix A: File Reference

| File | Path | Role |
|---|---|---|
| MCP Server | `src/carrymem/integration/layer2_mcp/server.py` | Core MCP protocol implementation |
| MCP Tools | `src/carrymem/integration/layer2_mcp/tools.py` | 27 tool definitions |
| MCP Handlers | `src/carrymem/integration/layer2_mcp/handlers.py` | Tool execution logic |
| CLI | `src/carrymem/cli.py` | setup-mcp command (line 1880) |
| Constants | `src/carrymem/constants.py` | Path configurations |
| Version | `src/carrymem/__version__.py` | `0.2.4` |
| Setup | `setup.py` | Package build configuration |
| CI | `.github/workflows/ci.yml` | 6-gate CI pipeline |
| Issue Templates | `.github/ISSUE_TEMPLATE/` | bug, feature, question |
| Integration Examples | `integrations/claude_code/mcp.json`, `integrations/cursor/mcp.json` | Reference configs |

## Appendix B: Competitor Feature Comparison

| Feature | CarryMem v0.2.4 | Mem0 OpenMemory | Mem0 Cloud |
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
