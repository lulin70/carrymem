# CarryMem MCP Tools Reference

**Last Updated**: 2026-11-06  
**Version**: v0.11.2  
**Total Tools**: 35

This document provides a complete classification and coverage status of all CarryMem MCP tools.

---

## Tool Classification

CarryMem's 35 MCP tools are organized into 9 functional categories:

### 1. CORE (3 tools)

Always available, no storage adapter required.

| Tool | Description | User Guide |
|------|-------------|------------|
| `batch_classify` | Batch classify multiple messages | ✅ Covered in Memory System |
| `classify_message` | Analyze if a message contains memorable information | ✅ Covered in Memory System |
| `get_classification_schema` | Return CarryMem's classification schema (7 types, 4 tiers) | ✅ Covered in Memory System |

### 2. OPTIONAL (7 tools)

Requires storage adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `classify_and_remember` | Classify AND store a message in one step | ✅ Covered in Getting Started |
| `forget_memory` | Delete a memory permanently | ✅ Covered in Memory Control |
| `get_memory_history` | Retrieve version history of a memory | ✅ Covered in Memory Control |
| `pause_memory` | Temporarily exclude memory from recall | ✅ Covered in Memory Control |
| `recall_memories` | Search and retrieve memories | ✅ Covered in Getting Started |
| `resume_memory` | Re-activate a paused memory | ✅ Covered in Memory Control |
| `update_memory` | Modify an existing memory | ✅ Covered in Memory Control |

### 3. KNOWLEDGE (3 tools)

Requires knowledge adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `index_knowledge` | Index external knowledge sources | ⚠️ Limited coverage |
| `recall_all` | Recall memories from all sources | ✅ Covered in 多模式检索 |
| `recall_from_knowledge` | Recall from knowledge base | ⚠️ Limited coverage |

### 4. PROFILE (2 tools)

Requires storage adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `declare_preference` | Declare user preferences | ✅ Covered in Common Use Cases |
| `get_memory_profile` | Get user memory profile summary | ⚠️ Limited coverage |

### 5. PROMPT (2 tools)

Requires storage adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `get_system_prompt` | Generate context-aware system prompt | ⚠️ Limited coverage |
| `summarize_and_store` | Summarize conversation and store | ⚠️ Limited coverage |

### 6. CONSOLIDATION (3 tools)

Requires storage adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `consolidate_memories` | Merge similar memories | ✅ Covered in Memory Consolidation |
| `schedule_consolidation` | Schedule auto consolidation | ✅ Covered in Memory Consolidation |
| `stop_consolidation` | Stop scheduled consolidation | ✅ Covered in Memory Consolidation |

### 7. RULE (11 tools)

Rule engine operations.

| Tool | Description | User Guide |
|------|-------------|------------|
| `add_rule` | Create a new rule | ✅ Covered in Rule Engine |
| `delete_rule` | Delete a rule | ✅ Covered in Rule Engine |
| `inject_rules` | Inject rules into context | ✅ Covered in Rule Engine |
| `list_rules` | List all rules | ✅ Covered in Rule Engine |
| `match_rules` | Match rules for current context | ✅ Covered in Rule Engine |
| `my_profile` | Get user profile from rules | ✅ Covered in Rule Engine |
| `my_rules` | Get personal rules | ✅ Covered in Rule Engine |
| `onboard` | Initialize user onboarding | ✅ Covered in Rule Engine |
| `promote_rules` | Promote rules across scopes | ✅ Covered in Rule Scopes |
| `suggest_rules` | AI-suggest rules from usage | ⚠️ Limited coverage |
| `update_rule` | Update an existing rule | ✅ Covered in Rule Engine |

### 8. HEALTH_CHECK (1 tool)

System diagnostics.

| Tool | Description | User Guide |
|------|-------------|------------|
| `health_check` | Verify CarryMem system health | ✅ Covered in Getting Started |

### 9. GRAPH (3 tools)

Knowledge graph operations, requires graph capability.

| Tool | Description | User Guide |
|------|-------------|------------|
| `get_memory_impact` | Compute graph impact score of a memory | ⚠️ Limited coverage |
| `query_graph` | Query knowledge graph with Cypher-like syntax | ✅ Covered in 图查询 MCP 工具 |
| `shortest_path` | Find shortest path between entities | ✅ Covered in 图查询 MCP 工具 |

---

## Coverage Status Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Fully Covered | 26 | 74% |
| ⚠️ Limited Coverage | 9 | 26% |
| ❌ No Coverage | 0 | 0% |

### Tools Needing Documentation Enhancement

The following 9 tools have limited or no user-facing examples in USER_GUIDE.md:

1. `index_knowledge`
2. `recall_from_knowledge`
3. `get_memory_profile`
4. `get_system_prompt`
5. `summarize_and_store`
6. `suggest_rules`
7. `get_memory_impact`

**Recommendation**: Add practical examples for these tools in USER_GUIDE.md before external user testing (Phase 6).

---

## Verification Commands

Verify tool count matches code:

```bash
cd /path/to/carrymem
python3 -c "
import sys
sys.path.insert(0, 'src')
from carrymem.integration.layer2_mcp.tools import TOOL_NAMES
print(f'Total tools: {len(TOOL_NAMES)}')
assert len(TOOL_NAMES) == 35, 'Tool count mismatch!'
"
```

List all tool names:

```bash
python3 -c "
import sys
sys.path.insert(0, 'src')
from carrymem.integration.layer2_mcp.tools import TOOL_NAMES
for tool in sorted(TOOL_NAMES):
    print(f'  - {tool}')
"
```

---

## Notes

- **Version alignment**: This reference is synchronized with `src/carrymem/integration/layer2_mcp/tools.py` as of 2026-11-06.
- **Living document**: Update this file when adding/removing MCP tools.
- **Test coverage**: All 35 tools have automated tests (406 + 47 = 453 tests passed per TD-078 completion record).
