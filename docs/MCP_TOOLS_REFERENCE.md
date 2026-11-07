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
| `index_knowledge` | Index external knowledge sources | ✅ Covered in Common Use Cases #17 |
| `recall_all` | Recall memories from all sources | ✅ Covered in 多模式检索 |
| `recall_from_knowledge` | Recall from knowledge base | ✅ Covered in Common Use Cases #18 |

### 4. PROFILE (2 tools)

Requires storage adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `declare_preference` | Declare user preferences | ✅ Covered in Common Use Cases |
| `get_memory_profile` | Get user memory profile summary | ✅ Covered in Common Use Cases #13 |

### 5. PROMPT (2 tools)

Requires storage adapter.

| Tool | Description | User Guide |
|------|-------------|------------|
| `get_system_prompt` | Generate context-aware system prompt | ✅ Covered in Common Use Cases #15 |
| `summarize_and_store` | Summarize conversation and store | ✅ Covered in Common Use Cases #14 |

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
| `suggest_rules` | AI-suggest rules from usage | ✅ Covered in Common Use Cases #16 |
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
| `get_memory_impact` | Compute graph impact score of a memory | ✅ Covered in Common Use Cases #19 |
| `query_graph` | Query knowledge graph with Cypher-like syntax | ✅ Covered in 图查询 MCP 工具 |
| `shortest_path` | Find shortest path between entities | ✅ Covered in 图查询 MCP 工具 |

---

## Coverage Status Summary

| Status | Count | Percentage |
|--------|-------|------------|
| ✅ Fully Covered | 35 | 100% |
| ⚠️ Limited Coverage | 0 | 0% |
| ❌ No Coverage | 0 | 0% |

### Documentation Milestone: 100% Coverage ✅

All 35 MCP tools now have practical examples and usage documentation in USER_GUIDE.md. Phase 2-3 documentation requirement completed (2026-11-07).

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
