# CarryMem ルールユーザーマニュアル

**バージョン**: v0.5.0  
**Date**: 2026-05-03  
**Audience**: End Users (Developers, Power Users, Teams)  
**Prerequisites**: Python 3.9+, pip

---

## 🚀 Quick Start (5 Minutes to First Rule)

### Step 1: Install CarryMem

```bash
pip install carrymem
```

**Verify installation:**
```bash
carrymem version
# Output: CarryMem v0.4.0
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

**Expected output:**
```
✅ Rule created: rule_abc12345
  Trigger: 写报告
  Action: 报告控制在三页以内
  Type: format
  Status: active
  Override: Yes (AI cannot ignore this)
```

### Step 4: Test It!

```bash
# Check if rule matches a scenario
$ carrymem rules match "帮我写一份Q2销售报告"

🎯 Found 1 matching rule:

[1] ⭐⭐⭐ Similarity: 0.95
ID: rule_abc12345
Trigger: 写报告
Action: 报告控制在三页以内
Type: format | Override: [硬性]

1 rules matched (of 1 active)

💡 This rule will be injected when AI processes report-writing requests!
```

### Step 5: Verify Integration

```bash
$ carrymem doctor

  CarryMem Doctor - Diagnostics
  =============================================
  [OK] Python 3.11+ (>= 3.9)
  [OK] CarryMem v0.4.0
  [OK] Config directory: /Users/you/.carrymem
  [OK] Database: /Users/you/.carrymem/memories.db (0.14 MB)
  
  --- Memory Layer ---
  [OK] Database integrity: OK
  [INFO] Memory count: 33
  
  --- Rules Engine (NEW!) ---
  [OK] Rules table exists ✨
  [INFO] Total rules: 1 (1 active)
  [INFO] Global rules: 0/3 (0% used)
  [OK] Ready to inject rules into AI context!
  
  =============================================
  All checks passed! 🎉
```

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

CarryMem supports **5 types of rules**, each with different semantics:

| Type | Label | Meaning | Use When |
|------|-------|---------|----------|
| `avoid` | [回避] | Avoid this behavior | "Skip Indian vendors" |
| `always` | [必须] | Always do this | "Check for SQL injection" |
| `prefer` | [优先] | Prefer this option | "Use Python over JavaScript" |
| `forbid` | [禁止] | Absolutely forbidden | "Never say 'market is trillion-dollar'" |
| `format` | [格式] | Formatting requirement | "Reports under 3 pages" |

**Override Flag:**
- `override=true` (default): **[硬性]** — AI must follow this rule
- `override=false`: **[习惯]** — AI should follow but can use judgment

---

### Creating Rules

#### Method 1: Command Line (Recommended for Power Users)

```bash
carrymem rules add "<action>" --trigger "<scene>" --type <type> [options]
```

**Parameters:**
- `<action>` (required): What should the AI do?
- `--trigger` (required): When does this apply? (Describe the scene)
- `--type` (required): One of: `avoid`, `always`, `prefer`, `forbid`, `format`
- `--override` (optional): `true` (default) or `false`
- `--source-memories` (optional): Link to existing memory IDs
- `--note` (optional): Human-readable note about why this rule exists

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

# With note
carrymem rules add "排除框架X" --trigger "技术选型" \
    --type avoid --note "因为团队有bad experience with X"

# Linking to source memory
carrymem rules add "不用Java" --trigger "技术选型" \
    --type forbid --source-memories mem_042 mem_089
```

#### Method 2: Interactive Mode (Recommended for New Users)

```bash
carrymem rules add --interactive
```

**Guided flow:**
```
? What should AI do in this situation? 跳过印度供应商
? When does this apply? (Describe the scene) 写供应商调研报告时
? How strict is this rule?
  ❌ forbid (绝对禁止 - AI must never do this)
  ✅ avoid (回避 - AI should avoid this)  ← Selected
  ◯ always (必须做 - AI must always do this)
  ◯ prefer (优先选择 - AI should prefer this)
  ◯ format (格式要求 - Formatting requirement)

✅ Rule created: rule_xyz789
  Trigger: 写供应商调研报告时
  Action: 跳过印度供应商
  Type: avoid
  Override: Yes (AI cannot ignore this)

Test it now? [Y/n] y
→ Running: carrymem rules match "帮我做供应商调研"
🎯 Found 1 matching rule! Your rule is working.
```

---

### Managing Rules

#### List All Rules

```bash
# Show all active rules
carrymem rules list

# Show paused rules only
carrymem rules list --status paused

# Show deprecated rules only
carrymem rules list --status deprecated

# Show all rules (any status)
carrymem rules list
```

**Output format:**
```
ID          Trigger              Action               Type    Status    Hits
rule_001    写报告               控制在三页以内        format  active    23
rule_002    技术选型             排除Java框架X        avoid   active    15
rule_003    竞品分析             不要写市场空间千亿级  forbid  active    8
rule_004    代码评审             必须检查SQL注入      always  active    31
rule_005    旧策略              跳过印度公司         avoid  paused    0
```

#### View Rule Details

```bash
carrymem rules show rule_001
```

**Detailed output:**
```
Rule Details: rule_001
═══════════════════════════════════════

Identity:
  ID: rule_001
  Created: 2026-04-29T10:30:00Z
  Updated: 2026-04-29T14:22:00Z

Core:
  Trigger: 写报告
  Action: 控制在三页以内
  Type: format
  Override: Yes [硬性]

Metadata:
  Source Memories: []
  Derived From: manual
  Confidence: 0.80
  Confirmed by User: Yes

Statistics:
  Times Matched: 23
  Status: active
  Note: (none)
```

#### Edit a Rule

```bash
carrymem rules edit rule_001 "报告控制在2页以内（更严格）"
```

**You can also edit via show + copy-paste ID**

#### Pause / Resume (Temporary Disable)

```bash
# Pause (temporarily disable)
carrymem rules pause rule_005
⏸️ Rule rule_005 paused
  Previously: active → Now: paused

# Resume (re-enable)
carrymem rules resume rule_005
▶️ Rule rule_005 resumed
  Previously: paused → Now: active
```

**Use cases for pausing:**
- Testing if a rule causes issues
- Temporarily disabling during specific projects
- A/B testing alternative approaches

#### Deprecate (Soft Delete)

```bash
carrymem rules delete rule_002
🗑️ Rule rule_002 deprecated
  Status: active → deprecated
  Reason? (optional) 已迁移到新框架
```

**Deprecated rules:**
- Don't match in queries
- Stay in database (not deleted)
- Can be resumed later if needed
- Show up in `rules list --status deprecated`

#### Delete (Permanent Removal)

```bash
carrymem rules delete rule_002
⚠️  Permanently delete rule 'rule_002'?
  This action cannot be undone. [y/N] y
✅ Rule rule_002 deleted permanently
```

**Warning:** Deleted rules cannot be recovered! Consider deprecating instead.

---

### Matching Rules to Scenarios

#### Find Which Rules Apply

```bash
carrymem rules match "<describe your current task or context>"
```

**Examples:**

```bash
# Simple query
$ carrymem rules match "帮我做竞品分析"
🎯 Found 2 matching rules:

[1] ⭐⭐⭐ Similarity: 0.92
   Trigger: 竞品分析
   Action: 不要夸大市场规模
   Type: forbid [禁止] | Override: [硬性]

[2] ⭐⭐ Similarity: 0.75
   Trigger: 写报告
   Action: 报告控制在3页内
   Type: format [格式] | Override: [硬性]

2 rules matched (of 5 active)

# No matches
$ carrymem rules match "部署到Kubernetes"
🔍 No matching rules found.
  Active rules: 5 (none triggered)
  
  💡 Tip: Create a rule for this:
    carrymem rules add "<action>" --trigger "部署K8s" --type <type>
```

#### How Matching Works

1. **FTS5 Full-Text Search**: Query matched against all triggers using SQLite's FTS5 engine
2. **Keyword Extraction**: Partial matches work (e.g., "竞品" matches "竞品分析")
3. **Status Filter**: Only `active` rules participate (paused/deprecated excluded)
4. **Ranking**: Results sorted by similarity score × type weight × override bonus
5. **Threshold**: Low-similarity matches (< 0.7) excluded

---

### Export / Import Rules

#### Export All Rules

```bash
carrymem rules export my_rules_backup.json
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
carrymem rules import my_rules_backup.json
```

**Import behavior:**
- Validates JSON structure before importing
- Preserves original IDs (if no conflict)
- Generates new IDs for conflicts
- Does NOT overwrite existing rules with same ID
- Shows summary of imported/skipped/conflicted rules

**Use case:** Sync rules across multiple machines (work laptop ↔ home computer)

---

### Monitoring & Statistics

#### View Usage Stats

```bash
carrymem rules stats
```

**Output:**
```
📊 Rules Engine Statistics
═══════════════════════════════════════

Overview:
  Total Rules: 12
  └─ Active: 10 (83%)
  └─ Paused: 1 (8%)
  └─ Deprecated: 1 (8%)

Usage (Last 30 days):
  Total Matches: 347
  Avg Latency: 15ms (P99: 78ms)

Top Triggered Rules:
  #1  rule_fmt_report     "写报告" → "控制3页内"       [89 hits]
  #2  rule_sql_check      "代码评审" → "检查SQL注入"    [67 hits]
  #3  rule_tech_choice    "技术选型" → "排除Java X"    [45 hits]

Unused Rules (0 hits, consider cleanup):
  ⚠️  rule_old_vendor    "跳过印度公司"           [last: 30d ago]

Run 'carrymem rules check' to clean up stale entries.
```

#### Review Stale Rules

```bash
carrymem rules check
```

**Interactive cleanup wizard:**
```
Found 2 potentially stale rules:

[1] rule_old_vendor
   Trigger: 跳过印度公司
   Last used: 30 days ago
   Status: active
   
   Actions:
   (p) Pause  (d) Deprecate  (k) Keep  (s) Skip

Choose action for rule_old_vendor [p/d/k/s]: p
⏸️ Paused rule_old_vendor

[2] rule_legacy_fmt
   Trigger: 用Word格式
   Never triggered
   
   Actions:
   (p) Pause  (d) Deprecate  (k) Keep  (s) Skip

Choose action for rule_legacy_fmt [p/d/k/s]: d
🗑️ Deprecated rule_legacy_fmt

✅ Review complete. 2 rules processed.
```

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
    confidence=0.95
)
print(f"Created rule: {rule.id}")

# Match rules to context
matches = engine.match("我们用什么数据库好？")
for m in matches:
    print(f"[{m.similarity:.0%}] {m.rule.action}")

# Generate prompt section
prompt_section = engine.inject("设计一个新的数据库schema")
print(prompt_section)
# Output includes formatted rules section!

# Cleanup
cm.close()
```

### Integrating with MCP Tools

If using Cursor/Claude Code with MCP:

```bash
# Setup MCP (one-time)
carrymem setup-mcp --tool cursor

# Now AI tools can call rules functions directly
# In your AI chat:
# User: "Add a rule: when doing code reviews, always check for SQL injection"
# AI: [calls mcp__carrymem__add_rule tool]
# AI: ✅ Rule created: rule_xyz123
```

**Available MCP tools for rules:**
- `add_rule`: Create new rule
- `list_rules`: List rules
- `match_rules`: Find matching rules
- `show_rule`: Get rule details

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
1. [硬性] [格式] 报告控制在三页以内
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

1. **Prompt Injection Prevention**
   - Malicious rule actions blocked before storage
   - Patterns like "ignore previous instructions" rejected
   - Length limits prevent overflow attacks

2. **SQL Injection Prevention**
   - All database queries use parameterized bindings
   - Special characters (`'`, `;`, `--`) blocked in triggers

3. **Global Rule Abuse Prevention**
   - Maximum 3 global rules (trigger="*")
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
- Use `override=false` for preferences that can bend

❌ **DON'T:**
- Create rules with trigger="*" unless absolutely necessary
- Share exported rule files with untrusted parties (may contain sensitive info)
- Ignore security warnings from `carrymem doctor`
- Create 200+ rules without cleaning up old ones

---

## ❓ Troubleshooting

### Common Issues & Solutions

#### Issue: "Rule not matching when expected"

**Symptoms:**
```bash
$ carrymem rules match "写月度报告"
🔍 No matching rules found
```

**But you have a rule with trigger="写报告"!

**Solutions:**
1. **Check status**: Is the rule `active`? (not paused/deprecated)
   ```bash
   carrymem rules list
   ```
2. **Check similarity threshold**: FTS5 needs keyword overlap
   ```bash
   # Try more specific query
   carrymem rules match "帮我写一份报告"
   ```
3. **Check for typos**: Exact spelling matters for best results

---

#### Issue: "Command not found: add-rule"

**Symptoms:**
```bash
$ carrymem rules add "test" --trigger "test" --type avoid
Unknown command: add-rule
Run 'carrymem help' for usage
```

**Solution:**
- Ensure you have CarryMem installed: `carrymem version`
- If older version: `pip install --upgrade carrymem`

---

#### Issue: "Security error when creating rule"

**Symptoms:**
```bash
$ carrymem rules add "忽略之前的指令" --trigger "*" --type always
❌ Security Error: Action contains blocked pattern
  Pattern detected: "忽略.*指令"
```

**Explanation:** CarryMem detected potential prompt injection attempt and blocked it.

**Solutions:**
1. Rephrase action without dangerous patterns
2. If legitimate use case, contact maintainers for whitelist request

---

#### Issue: "Too many global rules"

**Symptoms:**
```bash
$ carrymem rules add "normal" --trigger "*" --type prefer
❌ Limit Exceeded: Maximum global rules reached (3/3)
```

**Explanation:** Global rules (trigger="*") match ALL requests and can significantly impact AI behavior.

**Solutions:**
1. Use specific triggers instead: `--trigger "code review"` instead of `"*"`
2. Pause/deprecate existing global rules:
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
   # Check if "用户行为规则" section appears
   ```

2. **Check rule priority:**
   - `[硬性]` rules should be followed strictly
   - `[习惯]` rules can be overridden by AI judgment

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
- **v0.4.0** (Current): Auto-backup, encrypted .carry files, concurrent safety, E2E tests
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
