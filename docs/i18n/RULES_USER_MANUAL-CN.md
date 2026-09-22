# CarryMem 规则用户手册

**版本**: v0.11.2
**日期**: 2026-09-21
**Audience**: End Users (Developers, Power Users, Teams)  
**Prerequisites**: Python 3.12+, pip

> Every command output in this manual was captured from a real `carrymem`
> v0.11.2 installation. Where behaviour is surprising, the manual says so
> instead of describing what the engine *ought* to do.

---

## 🚀 Quick Start (5 Minutes to First Rule)

### Step 1: Install CarryMem

```bash
pip install carrymem
```

**Verify installation:**
```bash
$ carrymem version

  CarryMem v0.11.2
  Python: 3.14.7
  Config: /Users/you/.carrymem
  Database: /Users/you/.carrymem/memories.db
```

### Step 2: Initialize

```bash
carrymem init
```

This creates:
- `~/.carrymem/` directory (config)
- `~/.carrymem/memories.db` (SQLite database)
- Rules table automatically created

### Step 3: Create Your First Rule

```bash
carrymem rules add "报告控制在三页以内" --trigger "写报告" --type format
```

**Actual output:**
```

  Rule created: rule_11bf62e4
    Trigger: 写报告
    Action:  报告控制在三页以内
    Type:    format
    Status:  active
    Force:   HARD
```

`Force: HARD` means the rule is marked non-overridable. Pass `--soft` to
create an overridable rule (`Force: SOFT`) instead.

### Step 4: Test It!

```bash
$ carrymem rules match "写报告"

  Matching rules for: "写报告"
  ────────────────────────────────────────────────────────────
  🔴 [exact] FORMAT: 报告控制在三页以内
     Trigger: "写报告" | Score: 1.00
```

**Read the matching rules honestly** — the scene must share *contiguous* wording
with the trigger. Matching is string-based (see [How Matching Works](#how-matching-works)),
so a scene that interleaves the trigger's characters does **not** match:

```bash
$ carrymem rules match "帮我写一份Q2销售报告"

  No matching rules found for: 帮我写一份Q2销售报告
```

`写报告` never appears as a contiguous run in that sentence (`写一份…报告`), and
the tokenizer emits character n-grams rather than word-level segmentation unless
`jieba` is installed. Give the trigger the wording users actually say
(`--trigger "写报告"` → `--trigger "写一份报告"`), or add one rule per phrasing.

### Step 5: Verify Integration

```bash
$ carrymem doctor

  CarryMem Doctor - Diagnostics

  =============================================
  [OK] Python 3.14.7 (>= 3.12)
  [OK] CarryMem v0.11.2
  [OK] Config directory: /Users/you/.carrymem
  [OK] Database: /Users/you/.carrymem/memories.db (8.16 MB)
  [OK] Database integrity: OK
  [OK] Database file writable
  [OK] Disk space: 33.09 GB free
  [OK] Database not locked
  [OK] Write permissions OK
  [INFO] No optional deps
  [OK] SQLite FTS5 support
  [OK] Security module (InputValidator)
  [INFO] No MCP configs in current directory
  [OK] Memory count: 726
  [OK] Active rules: 8
  [INFO] Auto-inject: disabled (set CARRYMEM_AUTO_INJECT=true)
  [WARN] CLI command 'carrymem' NOT on PATH. Fix: export PATH="$HOME/Library/Python/3.14/bin:$PATH"
  [OK] Backups: 5 file(s), latest: 4h ago

  =============================================
  All checks passed (14/18)
```

The `(14/18)` summary counts passed checks; the `[WARN]` on `PATH` is expected
when you invoke the CLI through `python3 -m carrymem` instead of an installed
console script.

---

## 📖 Complete Feature Guide

### What Are Rules? (Concept)

**CarryMem has two layers:**

| Layer | Purpose | Example | Activation |
|-------|---------|---------|------------|
| **Memory Layer** | Remembers who you are | "I prefer PostgreSQL" | Passive (always included) |
| **Rules Engine** | Tells AI how to act | "**When writing reports**, keep it under 3 pages" | Active (only when scene matches) |

**Key difference:** Memories are facts about you. Rules are **behavioral instructions** that only apply in specific situations.

---

### Rule Types Explained

CarryMem supports **5 rule types**, each with different semantics:

| Type | Meaning | Use When |
|------|---------|----------|
| `avoid` | Avoid this behavior | "Skip Indian vendors" |
| `always` | Always do this | "Check for SQL injection" |
| `prefer` | Prefer this option | "Use Python over JavaScript" |
| `forbid` | Absolutely forbidden | "Never say 'market is trillion-dollar'" |
| `format` | Formatting requirement | "Reports under 3 pages" |

The CLI prints the type **lower-case** in `rules add` / `rules list`
(`Type: format`) and **upper-case** in `rules match` / injected prompts
(`FORMAT`). There are no localized `[回避]` / `[硬性]` labels — those existed
only in earlier drafts of this manual.

**Force marker:**

| Marker | Meaning | How to set |
|--------|---------|------------|
| `HARD` (🔴) | Non-overridable; injected under "Mandatory Actions" | default, or `--hard` when editing |
| `SOFT` (🟡) | Overridable; injected under "Recommended" | `--soft` on `rules add` / `rules edit` |

Inside an injected system prompt, a hard rule is labelled `[ALWAYS]` /
`[FORBID]` / … by its type and the section it lands in — see
[Rules in System Prompts](#rules-in-system-prompts).

---

### Creating Rules

#### Method 1: Command Line (Recommended for Power Users)

```bash
carrymem rules add "<action>" --trigger "<scene>" --type <type> [options]
```

**Parameters** (exactly the flags the CLI accepts):

- `<action>` (required): What should the AI do?
- `--trigger`, `-t` (required): When does this apply? (Describe the scene)
- `--type` (required): One of: `avoid`, `always`, `prefer`, `forbid`, `format`
- `--soft` (optional): Mark the rule overridable (`Force: SOFT`)
- `--template` (optional): Use a predefined rule template
- `--interactive`, `-i` (optional): Interactive mode for rule creation
- `--db` (optional): Database path

> `--note` and `--source-memories` are **not** supported by the CLI and will
> fail with `unrecognized arguments`. The underlying `RuleEngine.add_rule()`
> Python API does accept `source_memories`.

**Examples:**

```bash
# Basic rule
carrymem rules add "跳过印度供应商" --trigger "写供应商调研" --type avoid

# Soft preference (AI can override if needed)
carrymem rules add "优先用Python" --trigger "写脚本" --type prefer --soft

# Hard constraint (AI cannot ignore)
carrymem rules add "必须检查SQL注入" --trigger "代码评审" --type always

# Formatting rule
carrymem rules add "报告控制在3页内" --trigger "写报告" --type format

# From a built-in template
carrymem rules add --template report-format
```

#### Method 2: Interactive Mode (Recommended for New Users)

```bash
carrymem rules add --interactive
```

**Guided flow:**
```

  CarryMem Rule Creator
  ────────────────────────────────────────
  Trigger (when does this apply)? 写供应商调研报告时
  Action (what should AI do)? 跳过印度供应商
  Rule Type:
    1) avoid   — Avoid doing something
    2) always  — Always do this
    3) prefer  — Prefer this approach
    4) forbid  — Never do this
    5) format  — Format output this way
  Choose [1-5, default=1]: 1
  Hard rule? (AI cannot ignore) [Y/n]: y

  Rule created: rule_1c0d9a44
    Trigger: 写供应商调研报告时
    Action:  跳过印度供应商
    Type:    avoid
    Status:  active
    Force:   HARD
```

The wizard does **not** offer to test the rule for you; run
`carrymem rules match "<scene>"` yourself afterwards.

#### Method 3: Built-in Templates

```bash
carrymem rules templates
```

```
  Rule Templates (10 available)
  ──────────────────────────────────────────────────
  api-design
    API design: RESTful, with error codes and documentation

  code-review
    Code review checklist: security, style, performance

  competitor-analysis
    Competitor analysis: mark rival official data as [Unverified]

  doc-first
    Project start: docs before code
  ...
  Usage: carrymem rules add --template <name>
```

---

### Managing Rules

The `rules` command exposes: `list`, `add`, `delete`, `match`, `edit`, `pause`,
`resume`, `stats`, `check`, `export`, `import`, `templates`, `suggest`,
`promote`, `learn`, `refine`. There is **no** `show` and no `add-rule`
sub-command (the underlying parser names are `add-rule`, `delete-rule`, … but
you invoke them as `rules add`, `rules delete`).

#### List All Rules

```bash
# Default: detail view
carrymem rules list

# Tabular view
carrymem rules list --format table

# Compact one-line-per-rule view
carrymem rules list --format compact

# Filter
carrymem rules list --status paused
carrymem rules list --status deprecated
carrymem rules list --type forbid
carrymem rules list --limit 50
```

**Detail output (default):**
```

  Rules (5 found)
  ────────────────────────────────────────────────────────────
  💡 🔴 rule_feefc555
     Trigger: *
     Action:  g2
     Type: prefer | Used: 1x | Confidence: 80%

  📝 🔴 rule_00772d35
     Trigger: 写报告
     Action:  报告控制在3页内
     Type: format | Used: 2x | Confidence: 80%
```

The icon encodes the rule type (🚫 avoid, ✅ always, 💡 prefer, ⛔ forbid,
📝 format) and 🔴/🟡 encodes HARD/SOFT. The counter is `Used: Nx` — there is no
separate "Hits" column.

**Table output:**
```

  ID             Type     Scope      Override Trigger              Action
  ────────────── ──────── ────────── ──────── ──────────────────── ──────────────────────────────
  rule_00772d35  format   personal   HARD     写报告                  报告控制在3页内

  Total: 5 rules
```

#### Inspect a Single Rule

There is no `rules show`. Use `rules list --format table`, or read the record
programmatically:

```python
from carrymem import CarryMem

cm = CarryMem()
rule = cm.rules.get_rule("rule_00772d35")
print(rule.trigger, rule.action, rule.rule_type, rule.override, rule.trigger_count)
```

#### Edit a Rule

`rules edit` takes the rule id as a positional argument and the new values as
flags:

```bash
carrymem rules edit rule_00772d35 --action "报告控制在2页以内（更严格）"
carrymem rules edit rule_00772d35 --trigger "写周报" --type format
carrymem rules edit rule_00772d35 --soft     # downgrade to SOFT
carrymem rules edit rule_00772d35 --hard     # back to HARD
```

A bare second positional argument (as earlier drafts of this manual showed) is
rejected with `unrecognized arguments`.

#### Pause / Resume (Temporary Disable)

```bash
$ carrymem rules pause rule_feefc555

  Rule paused: rule_feefc555
    Trigger: *

$ carrymem rules resume rule_feefc555

  Rule resumed: rule_feefc555
    Trigger: *
```

**Use cases for pausing:**
- Testing if a rule causes issues
- Temporarily disabling during specific projects
- A/B testing alternative approaches

#### Delete

`rules delete` is a **single-step hard delete** — there is no interactive
"deprecate with a reason" flow, and no separate permanent-delete flag:

```bash
$ carrymem rules delete rule_feefc555

  Deleting rule: rule_feefc555
    Trigger: *
    Action:  g2

  Rule deleted successfully.
```

**Warning:** deleted rules cannot be recovered. To disable a rule reversibly,
use `rules pause` instead.

---

### Matching Rules to Scenarios

#### Find Which Rules Apply

```bash
carrymem rules match "<describe your current task or context>"
```

**Examples** (captured from a database holding exactly two rules —
`竞品分析 → 不要夸大市场规模` and `写报告 → 报告控制在3页内`):

```bash
# Exact trigger match
$ carrymem rules match "竞品分析"

  Matching rules for: "竞品分析"
  ────────────────────────────────────────────────────────────
  🔴 [exact] FORBID: 不要夸大市场规模
     Trigger: "竞品分析" | Score: 1.00

# Trigger contained in a longer scene → partial match
$ carrymem rules match "帮我做竞品分析"

  Matching rules for: "帮我做竞品分析"
  ────────────────────────────────────────────────────────────
  🔴 [partial] FORBID: 不要夸大市场规模
     Trigger: "竞品分析" | Score: 0.64

# No matches
$ carrymem rules match "部署到Kubernetes"

  No matching rules found for: 部署到Kubernetes
```

Each hit is printed as `[match_type] TYPE: action`, then the trigger and its
score. `[exact]` scores 1.00; `[partial]` starts from 0.50 and then gains three
bonuses — `+0.10` for a hard rule, up to `+0.10` from usage frequency, and
`confidence × 0.05`. The example above reads 0.64 because the rule is hard
(`+0.10`) and carries confidence 0.8 (`+0.04`), plus a small frequency term.

If global (`trigger="*"`) rules exist they are always listed first, tagged
`[global]`.

#### How Matching Works

`RuleMatcher.match()` tries four strategies in order and keeps the first hits,
filling up to `limit` (default 5):

1. **Global rules** — rules with a wildcard trigger always participate (base 0.60)
2. **Exact** — trigger equals the scene verbatim (1.00)
3. **FTS5** — the scene is run against the rules' FTS5 index, score normalised
   from the rank into `0.30–0.95`
4. **Partial** — fallback string matching (base 0.50): trigger is a substring of
   the scene or vice versa, or the two share at least two tokens

Supporting behaviour:

- **Status filter** — only `active`, non-expired rules participate; paused and
  deprecated rules are excluded.
- **Ranking** — every strategy adds bonuses (hard rule `+0.10`, frequency up to
  `+0.10`, `confidence × 0.05`), results are capped at 1.00 and sorted by score
  descending.
- **No similarity threshold.** Every partial hit is returned regardless of score,
  so a 0.50–0.64 result is a weak match, not a strong one. Read the score.
- **Tokenisation** — non-CJK text is split on whitespace. CJK text uses `jieba`
  when it is installed, and otherwise falls back to character 1/2/3-grams. This
  is why matching is sensitive to wording: `写报告` matches `写报告` and `报告`,
  but not `帮我写一份Q2销售报告`, because the trigger never appears as a
  contiguous run in that sentence. Write triggers using the words users
  actually say, and add one rule per phrasing when it matters.

---

### Export / Import Rules

#### Export All Rules

```bash
$ carrymem rules export my_rules_backup.json

  Exported 5 rules to my_rules_backup.json
```

**Exports:**
- All rules (active + paused + deprecated)
- Full metadata (timestamps, statistics, etc.)
- JSON format (human-readable)

**Example output file structure:**
```json
[
  {
    "id": "rule_001",
    "trigger": "写报告",
    "action": "控制在3页以内",
    "rule_type": "format",
    "status": "active",
    "override": true,
    "trigger_count": 23,
    "created_at": "2026-04-29T10:30:00Z",
    ...
  },
  ...
]
```

#### Import Rules

```bash
$ carrymem rules import my_rules_backup.json

  Import complete
    Imported:    1
    Skipped:     4
    Overwritten: 0
```

**Import behavior:**
- Validates JSON structure before importing
- Preserves original IDs (if no conflict)
- Generates new IDs for conflicts
- Does **not** overwrite existing rules with the same ID — those are counted as
  `Skipped`

**Use case:** Sync rules across multiple machines (work laptop ↔ home computer)

---

### Monitoring & Statistics

#### View Usage Stats

```bash
$ carrymem rules stats

  Rules Engine Statistics
  ────────────────────────────────────────
  Total rules:    5
  Active rules:   5
  Global rules:   3/3
  Capacity:       5/200 (2.5%)

  By Type:
    prefer: 2
    always: 1
    format: 1
    forbid: 1

  By Status:
    active: 5
```

`Capacity` is the `total/200` rule budget; `Global rules` is the `used/3`
wildcard budget.

#### Check Rule Health

```bash
$ carrymem rules check

  Rules Health: ISSUES FOUND ⚠️
  ────────────────────────────────────────
  Active rules:    5
  Conflicts:       9
  Unused rules:    0
  Global rules:    3

  Conflicts by Severity:
    🟡 medium: 6
    🔴 critical: 3

  Conflict Details:
    [MEDIUM] overlap: Overlapping prefer rules with different actions for similar triggers
      Rules: [rule_feefc555] PREFER: '*' → 'g2' (Hard, active) | [rule_5de214bd] PREFER: '*' → 'g1' (Hard, active)
      Suggestion: Consider merging or differentiating the triggers
    [CRITICAL] contradiction: Contradictory types: prefer vs forbid with overlapping triggers
      Rules: [rule_feefc555] PREFER: '*' → 'g2' (Hard, active) | [rule_aec505d5] FORBID: '竞品分析' → '不要夸大市场规模' (Hard, active)
      Suggestion: Review which rule should take precedence. Consider pausing one or adjusting triggers.
```

This is a **static health report**, not an interactive cleanup wizard — it
detects overlapping and contradictory rules and exits non-zero when issues are
found. Resolve conflicts yourself with `rules pause` / `rules edit` / `rules
delete`.

---

## 🔧 Advanced Usage

### Using Rules with Python API

```python
from carrymem import CarryMem
from carrymem.rules import RuleEngine

# Initialize (rules auto-enabled)
cm = CarryMem()

# Access rules engine directly
engine = cm.rules  # or: RuleEngine(cm.db_path)

# Create rule programmatically
rule = engine.add_rule(
    trigger="数据库选型",
    action="优先PostgreSQL",
    rule_type="prefer",
    override=False,
    confidence=0.95,
)
print(f"Created rule: {rule.id}")

# Match rules to context
matches = engine.match("我们用什么数据库好？")
for m in matches:
    print(f"[{m.score:.0%}] {m.rule.action}")

# Generate prompt section
prompt_section = engine.inject("设计一个新的数据库schema")
print(prompt_section)
# Output includes formatted rules section!

# Cleanup
cm.close()
```

### Integrating with MCP Tools

If using Cursor / Claude Code / Trae / Windsurf / Cline with MCP:

```bash
# Setup MCP (one-time)
carrymem setup-mcp --tool cursor

# Now AI tools can call rules functions directly
# In your AI chat:
# User: "Add a rule: when doing code reviews, always check for SQL injection"
# AI: [calls the carrymem rule tool]
# AI: Rule created: rule_xyz123
```

### Rules in System Prompts

When you use CarryMem with any AI tool, rules are **automatically injected** into the system prompt:

**Before (Memory Only):**
```
## System Instructions
You are an AI assistant...

## 用户记忆
- I prefer dark mode
- Port is 5432 not 3306
...
```

**After (Memory + Rules):**
```
## System Instructions
You are an AI assistant...

## 用户行为规则                    ← NEW! Higher priority
When handling requests related to: _Q2销售报告_
Follow these behavioral guidelines:
1. [FORMAT] 报告控制在三页以内
   _Applies when: 写报告_

## 用户记忆                     ← Existing, lower priority
- I prefer dark mode
- Port is 5432 not 3306
...
```

**Key point:** Rules appear BEFORE memories, so AI sees behavioral guidelines first!

---

## 🛡️ Security Best Practices

### What CarryMem Protects You From

1. **Prompt Injection Prevention** — two layers:
   - **At creation time**, `RuleSanitizer.BLOCKED_PATTERNS` rejects
     **English-language** payloads (`ignore all previous instructions`,
     `you are now`, `act as`, `<system>`, `eval(`, `base64…decode`, …) and
     enforces length limits (`trigger` ≤ 200 chars, `action` ≤ 500 chars).
   - **At injection time**, `RuleInjector` re-checks the stored text against a
     wider pattern set that also covers Chinese (`忽略之前的指令`,
     `忘记所有规则`, …) and replaces the offending text with
     `[REDACTED: potential prompt injection in rule content]`.
   See [the troubleshooting entry](#issue-rule-with-a-prompt-injection-action-still-gets-created)
   for what this means in practice — a Chinese payload *is* stored.

2. **SQL Injection Prevention**
   - All database queries use parameterized bindings
   - `;`, `--`, `/*`, `*/` are rejected in triggers. The single quote `'` is
     **allowed** in triggers (it is only special in SQL contexts that CarryMem
     does not build by string concatenation).

3. **Global Rule Abuse Prevention**
   - Maximum 3 global rules (trigger=`*`)
   - Prevents hijacking all AI responses

4. **Database Bloat Prevention**
   - Maximum 200 total rules
   - Encourages regular cleanup

### What YOU Should Do

✅ **DO:**
- Review rules before creating (especially from untrusted sources)
- Use `carrymem doctor` regularly to check health
- Export rules periodically as backup
- Pause rules when testing new workflows
- Use `--soft` for preferences that can bend

❌ **DON'T:**
- Create rules with trigger=`*` unless absolutely necessary
- Share exported rule files with untrusted parties — they contain rule text
  verbatim, including anything the injector would otherwise redact
- Ignore security warnings from `carrymem doctor`
- Create 200+ rules without cleaning up old ones

---

## ❓ Troubleshooting

### Common Issues & Solutions

#### Issue: "Rule not matching when expected"

**Symptom:**
```bash
$ carrymem rules match "部署到Kubernetes"

  No matching rules found for: 部署到Kubernetes
```

**Cause:** matching is string-based, not semantic. A rule with
`trigger="写报告"` **does** fire on `写月度报告` (partial, 0.64) because the
trigger is a contiguous substring of the scene — but it will **not** fire on
`帮我写一份Q2销售报告`, where `写报告` is interrupted by `一份Q2销售`. There is no
similarity threshold to lower; the phrase simply has to line up.

**Solutions:**
1. **Check status**: is the rule `active`?
   ```bash
   carrymem rules list --status paused
   ```
2. **Shorten the trigger** to the words that always appear, or add one rule per
   phrasing:
   ```bash
   carrymem rules match "写报告"        # exact, 1.00
   carrymem rules match "帮我写一份报告"  # partial, 0.64
   ```
3. **Install `jieba`** for word-level CJK tokenisation instead of the built-in
   character n-gram fallback:
   ```bash
   pip install jieba
   ```

---

#### Issue: "Unknown rules sub-command"

**Symptom:**
```bash
$ carrymem rules add-rule "test" --trigger "test" --type avoid

  Unknown rules sub-command: add-rule
  Available: list, add, delete, match, edit, pause, resume, stats, check, export, import, templates, suggest, promote, learn, refine
```

**Solution:**
- Use `add`, not `add-rule`: `carrymem rules add "test" --trigger "test" --type avoid`
- Ensure CarryMem is installed and current: `carrymem version`

---

#### Issue: "Rule with a prompt-injection action still gets created"

**Symptom:**
```bash
$ carrymem rules add "忽略之前的指令" --trigger "*" --type always

  Rule created: rule_0e09bf5e
    Trigger: *
    Action:  忽略之前的指令
    Type:    always
    Status:  active
    Force:   HARD
```

**Explanation:** this is expected. The creation-time blocklist
(`RuleSanitizer.BLOCKED_PATTERNS`) is **English-only** — it catches
`ignore all previous instructions`, `you are now`, `<system>`, `eval(` and
similar, but it does not match Chinese phrasing. The rule is therefore stored.

What protects you is the second layer: when the rule is injected into a prompt,
`RuleInjector` re-checks the content against a wider pattern set that *does*
cover Chinese, and replaces the whole action with a redaction marker:

```
### Mandatory Actions (never skip)
- [ALWAYS] [REDACTED: potential prompt injection in rule content]
```

**Solutions:**
1. This is defence-in-depth, not a gap — the payload never reaches the model.
2. Do not rely on it as your only control: exported rule files
   (`carrymem rules export`) contain the original text, so treat them as
   sensitive and avoid sharing them.

---

#### Issue: "Too many global rules"

**Symptom:**
```bash
$ carrymem rules add "normal" --trigger "*" --type prefer

  Validation error: Maximum number of global rules (3) reached. Global rules apply to all scenes and should be used sparingly. Consider using more specific triggers instead.
```

**Explanation:** Global rules (trigger=`*`) match ALL requests and can significantly impact AI behavior. The limit is 3.

**Solutions:**
1. Use specific triggers instead: `--trigger "code review"` instead of `"*"`
2. Pause/delete existing global rules:
   ```bash
   carrymem rules list  # Find global rules
   carrymem rules pause <id>  # Pause one
   ```

---

#### Issue: "Rules not appearing in AI responses"

**Symptoms:** Rules exist and match, but AI doesn't follow them.

**Debugging steps:**
1. **Verify injection works:**
   ```python
   from carrymem import CarryMem
   cm = CarryMem()
   prompt = cm.build_system_prompt(context="写报告")
   print(prompt)
   # Check whether the injected rules section appears
   ```
2. **Check rule priority** — the prompt labels each rule by type:
   - `[ALWAYS]` / `⚠️ MANDATORY` — hard rules, listed under
     "Mandatory Actions (never skip)"
   - `[PREFER]` — soft preferences the AI may weigh against other context
   - `[FORBID]` / `[FORMAT]` / `[AVOID]` — the other rule types
   A rule created without `--soft` is hard (`Force: HARD`) and lands in the
   mandatory section.
3. **Check AI model compatibility:**
   - Some models may ignore long system prompts
   - Try shorter, more concise rule actions

---

## 📚 Additional Resources

### Documentation Links
- **Full README**: [README.md](../../README.md)
- **Architecture**: [ARCHITECTURE.md](../ARCHITECTURE.md)
- **API Reference**: [API_REFERENCE.md](../API_REFERENCE.md)
- **Roadmap**: [ROADMAP.md](../ROADMAP.md)
- **Contributing**: [CONTRIBUTING.md](../../CONTRIBUTING.md)

### Getting Help
- **GitHub Issues**: https://github.com/lulin70/carrymem/issues
- **Discussions**: https://github.com/lulin70/carrymem/discussions
- **Security Reports**: Please email maintainers (do NOT post publicly)

### Version History
- **v0.11.2** (Current): completes the `recall` metric correction; storing a memory no longer counts as a user recall
- **v0.11.1**: release-gate fix, first `recall` metric correction, full regression added as a blocking local CI gate
- **v0.11.0**: **breaking** — `AsyncCarryMem(native_async=True)` removed, `cryptography>=50.0.0` required, plugin system and `SummaryLayer` class deleted, observability instrumentation made real
- **v0.10.0**: repeat-correction upgrade (`detect_repeat_correction()` + semantic dedup + security-keyword bypass)
- **v0.9.0**: UI/UX overhaul — Morandi palette, accessibility, onboarding
- **v0.8.0**: Graphify — 3 MCP graph tools (query_graph, shortest_path, get_memory_impact), edge confidence labels (EXTRACTED/INFERRED/AMBIGUOUS), schema migration v100
- **v0.7.3**: Security hardening — Fernet-only encryption, migration script, input validator defense-in-depth, WAL throttle
- **v0.5.2**: Summary Layer + Progressive Disclosure (token-efficient prompt injection, rule-based + LLM-optional summarization, schema migration _V052)
- **v0.3.0**: Memory layer foundation, Rules Engine, PyPI release
- **Changelog**: See [CHANGELOG.md](../../CHANGELOG.md)

---

## 🎯 Next Steps After Installation

1. ✅ **Create 3-5 core rules** for your most common tasks
2. ✅ **Test matching** with `carrymem rules match` to verify they activate correctly
3. ✅ **Use with AI tool** (Cursor/Claude Code) and observe behavior changes
4. ✅ **Run `carrymem rules stats` after 1 week** to see which rules are most useful
5. ✅ **Clean up stale rules** monthly with `carrymem rules check`

---

**Happy Rule-Making! 🎉**

Your AI now knows not just *who you are*, but *how you act*. That's the power of CarryMem Rules Engine.
