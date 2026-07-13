"""
MCP Tools definitions for CarryMem.

3+3+3+2+1 Optional Mode:
  Core (always available): classify_message, get_classification_schema, batch_classify
  Storage Optional (requires storage adapter): classify_and_remember, recall_memories, forget_memory
  Knowledge Optional (requires knowledge adapter): index_knowledge, recall_from_knowledge, recall_all
  Profile Optional (requires storage adapter): declare_preference, get_memory_profile
  Prompt Optional (requires storage adapter): get_system_prompt
"""

from typing import Any, Dict, List

from carrymem.__version__ import __version__ as _version

CORE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "classify_message",
        "description": (
            "Analyze a message and determine if it contains memorable "
            "information. Returns a standardized MemoryEntry JSON with type, "
            "tier, confidence, and suggested_action. CarryMem is a CarryMem "
            "memory system with optional storage — it tells you WHAT to "
            "remember, and can optionally store it too."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message content to analyze for memorable information",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Conversation context (optional). When user "
                        "confirms/accepts AI suggestion, pass the previous "
                        "AI reply to improve decision/correction "
                        "classification quality."
                    ),
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "get_classification_schema",
        "description": (
            "Return CarryMem's complete classification schema definition "
            "including 7 memory types, 4 storage tiers, confidence "
            "thresholds, and downstream mapping tables."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["json", "markdown"],
                    "default": "json",
                    "description": "Output format",
                }
            },
        },
    },
    {
        "name": "batch_classify",
        "description": "Batch classify multiple messages, each returning an independent MemoryEntry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Message content"},
                            "context": {
                                "type": "string",
                                "description": "Message context (optional)",
                            },
                        },
                        "required": ["message"],
                    },
                    "description": "List of messages to batch classify",
                }
            },
            "required": ["messages"],
        },
    },
]

OPTIONAL_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "classify_and_remember",
        "description": (
            "Classify a message AND store it if worth remembering. "
            "One-step operation: classify → store → return. Requires "
            "storage adapter to be configured."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message content to classify and store",
                },
                "context": {"type": "string", "description": "Conversation context (optional)"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "recall_memories",
        "description": (
            "Retrieve stored memories. Supports filtering by type, tier, "
            "and confidence. Supports full-text search. "
            "Requires storage adapter."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for full-text search (optional)",
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": (
                                "Memory type filter (user_preference, "
                                "correction, fact_declaration, decision, "
                                "relationship, task_pattern, sentiment_marker)"
                            ),
                        },
                        "tier": {
                            "type": "integer",
                            "description": "Tier filter (1-4)",
                            "minimum": 1,
                            "maximum": 4,
                        },
                        "confidence_min": {
                            "type": "number",
                            "description": "Minimum confidence threshold (0.0-1.0)",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    },
    {
        "name": "forget_memory",
        "description": "Delete a stored memory by ID. Requires storage adapter.",
        "inputSchema": {
            "type": "object",
            "properties": {"memory_id": {"type": "string", "description": "Memory ID (storage_key) to delete"}},
            "required": ["memory_id"],
        },
    },
]

KNOWLEDGE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "index_knowledge",
        "description": (
            "Index an Obsidian vault or knowledge base for full-text search. "
            "Scans Markdown files, extracts YAML frontmatter tags and "
            "wiki-links, builds FTS5 index. Requires knowledge adapter "
            "(ObsidianAdapter)."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "recall_from_knowledge",
        "description": (
            "Search knowledge base (e.g., Obsidian vault) using full-text "
            "search. Returns matching notes with title, content preview, tags, "
            "and wiki-links. Requires knowledge adapter."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for full-text search"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "tags": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ],
                            "description": "Filter by tag(s)",
                        },
                        "title": {
                            "type": "string",
                            "description": "Filter by title (partial match)",
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (default 20)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "recall_all",
        "description": (
            "Unified retrieval across both memories (SQLite) and knowledge "
            "base (Obsidian). Returns results from both sources with "
            "priority: memories first, then knowledge. Requires at least one "
            "adapter configured."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "filters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Memory type filter (for memories only)",
                        },
                        "tags": {
                            "oneOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                            ],
                            "description": "Tag filter (for knowledge base)",
                        },
                    },
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results per source (default 20)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["query"],
        },
    },
]

PROFILE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "declare_preference",
        "description": (
            "Let the user proactively tell the AI about themselves. User "
            "declarations are classified by the engine but always stored "
            "with confidence=1.0 and source_layer='declaration'. Active "
            "declaration + passive classification = complete memory coverage."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": (
                        "What the user wants to declare (e.g., 'I prefer dark "
                        "mode', 'We use PostgreSQL', 'My timezone is UTC+8')"
                    ),
                }
            },
            "required": ["message"],
        },
    },
    {
        "name": "get_memory_profile",
        "description": (
            "Get a structured summary of what the AI remembers about the "
            "user. Returns highlights (top preferences, decisions, "
            "corrections), statistics (by type, by tier, avg confidence), "
            "and a human-readable summary. Lets users see and audit what AI "
            "remembers."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

PROMPT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_system_prompt",
        "description": (
            "Generate a system prompt with user memories and knowledge base "
            "context injected. The prompt follows the 'memory-first' "
            "retrieval priority: User Memories > Knowledge Base > General "
            "Knowledge. Use this to inject CarryMem context into any AI "
            "agent's system prompt."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": (
                        "Optional context/topic to filter relevant memories "
                        "(e.g., 'database setup', 'coding style'). If empty, "
                        "returns all memories."
                    ),
                },
                "max_memories": {
                    "type": "integer",
                    "description": "Maximum number of memories to include (default 10)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "max_knowledge": {
                    "type": "integer",
                    "description": "Maximum number of knowledge base entries to include (default 5)",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "language": {
                    "type": "string",
                    "description": ("Language for the prompt template: en, zh, or ja " "(default en)"),
                    "default": "en",
                    "enum": ["en", "zh", "ja"],
                },
            },
        },
    },
    {
        "name": "summarize_and_store",
        "description": (
            "Request the host AI to summarize conversation content, then store "
            "the summary as a session_summary memory. This implements the "
            "'borrow host LLM' pattern: CarryMem returns the content that "
            "needs summarizing, the host AI generates a concise summary "
            "focusing on user preferences, decisions, and key facts, then "
            "calls classify_and_remember or declare_preference to store it. "
            "No external LLM API key needed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "The session ID to summarize"},
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens of content to return for summarization (default 2000)",
                    "default": 2000,
                    "minimum": 100,
                    "maximum": 8000,
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace for the stored summary (default 'default')",
                    "default": "default",
                },
            },
            "required": ["session_id"],
        },
    },
]

CONSOLIDATION_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "consolidate_memories",
        "description": (
            "Run memory consolidation: deduplicate similar memories, apply "
            "time-based decay, clean up low-value entries, and detect "
            "patterns for rule promotion. Preferences are always preserved. "
            "P0 handles dedup+decay, P1 detects repeated patterns and "
            "generates rule candidates. Run periodically (e.g., daily) to "
            "keep memory store healthy. Use dry_run=true first to preview "
            "changes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only report what would be done without making changes (default true)",
                    "default": True,
                },
                "run_p1": {
                    "type": "boolean",
                    "description": (
                        "If true, also run P1 pattern recognition and " "rule candidate generation (default true)"
                    ),
                    "default": True,
                },
                "run_p2": {
                    "type": "boolean",
                    "description": "If true, also run P2 semantic consolidation via host LLM (default true)",
                    "default": True,
                },
            },
        },
    },
    {
        "name": "schedule_consolidation",
        "description": "Schedule periodic memory consolidation (dedup, decay, cleanup) at a fixed interval",
        "inputSchema": {
            "type": "object",
            "properties": {
                "interval_hours": {
                    "type": "number",
                    "description": "Hours between consolidation runs (minimum 0.1 = 6 minutes)",
                    "default": 1.0,
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, only report what would be done without making changes",
                    "default": False,
                },
                "run_p1": {
                    "type": "boolean",
                    "description": "If true, also run P1 pattern recognition",
                    "default": True,
                },
                "run_p2": {
                    "type": "boolean",
                    "description": "If true, also run P2 semantic consolidation",
                    "default": False,
                },
            },
            "required": [],
        },
    },
    {
        "name": "stop_consolidation",
        "description": "Stop the scheduled periodic memory consolidation",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

RULE_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "add_rule",
        "description": (
            "Add a behavioral rule to CarryMem's rule engine. Rules guide "
            "AI behavior for specific topics. Use 'company' scope for "
            "organization-mandated rules (highest priority), 'negotiated' "
            "for team-adapted rules, or 'personal' for individual "
            "preferences (lowest priority)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "trigger": {
                    "type": "string",
                    "description": "Topic/scene that activates this rule (e.g., 'database', 'code review', 'security')",
                },
                "action": {
                    "type": "string",
                    "description": "What to do when triggered (e.g., 'Always use SSL', 'Never commit secrets')",
                },
                "scope": {
                    "type": "string",
                    "enum": ["personal", "company", "negotiated"],
                    "default": "personal",
                    "description": (
                        "Rule scope: company (org-mandated, cannot be "
                        "overridden), negotiated (team-adapted), personal "
                        "(individual preference)"
                    ),
                },
                "rule_type": {
                    "type": "string",
                    "enum": ["always", "avoid", "forbid", "prefer", "recommend"],
                    "default": "always",
                    "description": (
                        "Rule type: always (mandatory), avoid (discouraged), "
                        "forbid (prohibited), prefer (recommended), "
                        "recommend (suggested)"
                    ),
                },
                "override": {
                    "type": "boolean",
                    "default": False,
                    "description": "Whether this rule overrides conflicting lower-scope rules",
                },
            },
            "required": ["trigger", "action"],
        },
    },
    {
        "name": "list_rules",
        "description": "List all rules in CarryMem's rule engine, optionally filtered by scope or trigger topic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["personal", "company", "negotiated"],
                    "description": "Filter by scope (optional)",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "paused", "deprecated"],
                    "default": "active",
                    "description": "Filter by status",
                },
                "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
            },
        },
    },
    {
        "name": "match_rules",
        "description": (
            "Match rules against a scene/topic and return applicable rules "
            "with scores. Use this to find which rules apply to a given "
            "context before generating a response."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scene": {
                    "type": "string",
                    "description": (
                        "The scene/topic to match rules against (e.g., " "'database design', 'code review process')"
                    ),
                },
                "scopes": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["personal", "company", "negotiated"]},
                    "description": "Filter by scopes (optional, defaults to all)",
                },
            },
            "required": ["scene"],
        },
    },
    {
        "name": "inject_rules",
        "description": (
            "Generate a formatted rules section for injection into AI "
            "prompts. Returns structured text with applicable rules for a "
            "given context, including scope labels and priority markers."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Context/topic to filter relevant rules",
                },
                "format": {
                    "type": "string",
                    "enum": ["structured", "compact", "json", "anchored"],
                    "default": "structured",
                    "description": (
                        "Output format: structured (markdown), compact " "(single line), json, anchored (by type)"
                    ),
                },
                "max_rules": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            },
            "required": ["context"],
        },
    },
    {
        "name": "my_rules",
        "description": (
            "View all your saved rules in a readable summary format. Shows "
            "rule triggers, actions, scope, type, and override status. Use "
            "this to review what CarryMem remembers about your preferences "
            "and behavioral rules."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["personal", "company", "negotiated"],
                    "description": "Filter by scope (optional)",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "paused", "deprecated"],
                    "default": "active",
                    "description": "Filter by status",
                },
            },
        },
    },
    {
        "name": "delete_rule",
        "description": (
            "Delete a rule by its ID. Use my_rules first to find the "
            "rule ID you want to remove. Returns confirmation with the "
            "deleted rule's details."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {
                    "type": "string",
                    "description": "The ID of the rule to delete (find it using my_rules)",
                }
            },
            "required": ["rule_id"],
        },
    },
    {
        "name": "suggest_rules",
        "description": (
            "Analyze your stored memories and suggest rule candidates "
            "based on detected patterns. Useful for discovering preferences "
            "you've expressed multiple times that could become formal rules."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": [
                        "user_preference",
                        "correction",
                        "decision",
                        "task_pattern",
                        "sentiment_marker",
                    ],
                    "description": "Filter analysis to a specific memory type (optional)",
                },
                "max_candidates": {"type": "integer", "default": 5, "minimum": 1, "maximum": 10},
            },
        },
    },
    {
        "name": "promote_rules",
        "description": (
            "Run the full promotion pipeline: analyze memories, detect "
            "patterns, generate rule candidates, and optionally auto-accept "
            "them. Use this to convert accumulated preferences into active "
            "rules."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": [
                        "user_preference",
                        "correction",
                        "decision",
                        "task_pattern",
                        "sentiment_marker",
                    ],
                    "description": "Filter to a specific memory type (optional)",
                },
                "auto_accept": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "If true, automatically accept all suggested rules. "
                        "If false, rules are queued for your review."
                    ),
                },
            },
        },
    },
    {
        "name": "update_rule",
        "description": (
            "Update an existing rule's trigger, action, scope, or type. "
            "Use my_rules first to find the rule ID. Returns the updated "
            "rule details."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "rule_id": {"type": "string", "description": "The ID of the rule to update"},
                "trigger": {"type": "string", "description": "New trigger (topic/scene), optional"},
                "action": {"type": "string", "description": "New action (what to do), optional"},
                "scope": {
                    "type": "string",
                    "enum": ["personal", "company", "negotiated"],
                    "description": "New scope, optional",
                },
                "rule_type": {
                    "type": "string",
                    "enum": ["always", "avoid", "forbid", "prefer", "recommend"],
                    "description": "New rule type, optional",
                },
                "override": {"type": "boolean", "description": "New override flag, optional"},
            },
            "required": ["rule_id"],
        },
    },
    {
        "name": "my_profile",
        "description": (
            "Get a complete view of your CarryMem identity: memory "
            "statistics, rule summary, recent activity, and preference "
            "distribution. Use this to understand what CarryMem knows "
            "about you."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_memories": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include memory statistics and recent memories",
                },
                "include_rules": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include rule summary and distribution",
                },
            },
        },
    },
    {
        "name": "onboard",
        "description": (
            "First-time user onboarding. Returns a welcome message and asks "
            "key preference questions to initialize your CarryMem profile. "
            "Call this when a new user starts their first conversation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["en", "zh", "ja"],
                    "default": "en",
                    "description": "Language for the onboarding message",
                }
            },
        },
    },
]

HEALTH_CHECK_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "health_check",
        "description": (
            "Check CarryMem system health. Returns adapter health, audit "
            "logger stats, memory count, and uptime. Lightweight check "
            "that does not start any HTTP service — use this from MCP "
            "clients to verify CarryMem is operational."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]

GRAPH_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "query_graph",
        "description": (
            "Multi-hop graph traversal from an entity. Performs BFS "
            "traversal of the knowledge graph starting from the given "
            "entity, collecting all connected entities and memories "
            "within max_hops hops. Requires storage adapter with graph "
            "capability."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_text": {
                    "type": "string",
                    "description": "The starting entity text to traverse from",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Maximum traversal depth (default 2, max 5)",
                    "default": 2,
                    "minimum": 1,
                    "maximum": 5,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum memories to return (default 20, max 100)",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": ["entity_text"],
        },
    },
    {
        "name": "shortest_path",
        "description": (
            "Find the shortest path between two entities in the knowledge "
            "graph using bidirectional BFS. Returns the path as a list of "
            "entity texts from source to destination. Useful for "
            "understanding how concepts are connected. Requires storage "
            "adapter with graph capability."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "src_entity": {
                    "type": "string",
                    "description": "The source entity text",
                },
                "dst_entity": {
                    "type": "string",
                    "description": "The destination entity text",
                },
                "max_hops": {
                    "type": "integer",
                    "description": "Maximum path length to search (default 4, max 10)",
                    "default": 4,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["src_entity", "dst_entity"],
        },
    },
    {
        "name": "get_memory_impact",
        "description": (
            "Compute the graph impact of a memory. Returns the number of "
            "entities linked to the memory, the number of relations it "
            "evidences, whether it spans multiple namespaces, and an "
            "impact_score (entity_count*0.4 + relation_count*0.4 + "
            "cross_namespace*0.2). Requires storage adapter with graph "
            "capability."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "string",
                    "description": "The memory's storage_key (memory_id) to evaluate",
                },
            },
            "required": ["memory_id"],
        },
    },
]

TOOLS = (
    CORE_TOOLS
    + OPTIONAL_TOOLS
    + KNOWLEDGE_TOOLS
    + PROFILE_TOOLS
    + PROMPT_TOOLS
    + CONSOLIDATION_TOOLS
    + RULE_TOOLS
    + HEALTH_CHECK_TOOLS
    + GRAPH_TOOLS
)
TOOL_NAMES = {tool["name"] for tool in TOOLS}
CORE_TOOL_NAMES = {tool["name"] for tool in CORE_TOOLS}
OPTIONAL_TOOL_NAMES = {tool["name"] for tool in OPTIONAL_TOOLS}
KNOWLEDGE_TOOL_NAMES = {tool["name"] for tool in KNOWLEDGE_TOOLS}
PROFILE_TOOL_NAMES = {tool["name"] for tool in PROFILE_TOOLS}
PROMPT_TOOL_NAMES = {tool["name"] for tool in PROMPT_TOOLS}
CONSOLIDATION_TOOL_NAMES = {tool["name"] for tool in CONSOLIDATION_TOOLS}
RULE_TOOL_NAMES = {tool["name"] for tool in RULE_TOOLS}
HEALTH_CHECK_TOOL_NAMES = {tool["name"] for tool in HEALTH_CHECK_TOOLS}
GRAPH_TOOL_NAMES = {tool["name"] for tool in GRAPH_TOOLS}

CLASSIFICATION_SCHEMA = {
    "schema_version": "1.0.0",
    "engine_version": _version,
    "mode": "classification_only",
    "memory_types": [
        {
            "id": "user_preference",
            "label_en": "User Preference",
            "label_zh": "用户偏好",
            "description": "User habits, preferences, style choices that affect future behavior",
            "examples": ["I prefer double quotes", "Use camelCase naming", "Dark mode please"],
            "default_tier": 2,
            "persistence_hint": "short_term_to_long_term",
            "downstream_mapping": {
                "supermemory": "preference",
                "mem0": "user_profile",
                "obsidian": "# Preferences",
                "custom_field": "category",
            },
        },
        {
            "id": "correction",
            "label_en": "Correction",
            "label_zh": "纠正信号",
            "description": "Corrections, clarifications, or negations of previous information",
            "examples": ["No, that's wrong", "Actually use X not Y", "Let me correct that"],
            "default_tier": 2,
            "persistence_hint": "immediate",
            "downstream_mapping": {
                "supermemory": "correction",
                "mem0": "correction",
                "obsidian": "# Corrections",
                "custom_field": "category",
            },
        },
        {
            "id": "fact_declaration",
            "label_en": "Fact Declaration",
            "label_zh": "事实声明",
            "description": "Factual statements, verifiable truths about the world or project",
            "examples": ["We have 100 employees", "Python 3.9 required", "Deployed on AWS"],
            "default_tier": 3,
            "persistence_hint": "long_term",
            "downstream_mapping": {
                "supermemory": "fact",
                "mem0": "fact",
                "obsidian": "# Facts",
                "custom_field": "category",
            },
        },
        {
            "id": "decision",
            "label_en": "Decision Record",
            "label_zh": "决策记录",
            "description": "Decisions made, choices selected, with reasoning context",
            "examples": [
                "We chose Redis for caching",
                "Go with PostgreSQL",
                "Use REST not GraphQL",
            ],
            "default_tier": 3,
            "persistence_hint": "long_term",
            "downstream_mapping": {
                "supermemory": "decision",
                "mem0": "decision",
                "obsidian": "# Decisions",
                "custom_field": "category",
            },
        },
        {
            "id": "relationship",
            "label_en": "Relationship Mapping",
            "label_zh": "关系映射",
            "description": "Relationships between entities, roles, ownerships, or connections",
            "examples": ["Alice owns backend", "Bob reports to Carol", "Module X depends on Y"],
            "default_tier": 4,
            "persistence_hint": "archive",
            "downstream_mapping": {
                "supermemory": "relation",
                "mem0": "relationship",
                "obsidian": "# Relationships",
                "custom_field": "category",
            },
        },
        {
            "id": "task_pattern",
            "label_en": "Task Pattern",
            "label_zh": "任务模式",
            "description": "Recurring workflows, automation rules, procedural patterns",
            "examples": ["Always test before deploy", "Run lint on every PR", "Review on Fridays"],
            "default_tier": 2,
            "persistence_hint": "short_term_to_long_term",
            "downstream_mapping": {
                "supermemory": "pattern",
                "mem0": "workflow",
                "obsidian": "# Patterns",
                "custom_field": "category",
            },
        },
        {
            "id": "sentiment_marker",
            "label_en": "Sentiment Marker",
            "label_zh": "情感标记",
            "description": "Emotional signals, pain points, satisfaction indicators",
            "examples": ["This workflow is frustrating", "Love this approach", "Too many meetings"],
            "default_tier": 3,
            "persistence_hint": "medium_term",
            "downstream_mapping": {
                "supermemory": "sentiment",
                "mem0": "emotion",
                "obsidian": "# Sentiments",
                "custom_field": "category",
            },
        },
    ],
    "storage_tiers": [
        {"id": 1, "name": "Sensory", "zh_name": "感觉记忆", "duration": "<1s", "action": "ignore"},
        {
            "id": 2,
            "name": "Procedural/Working",
            "zh_name": "程序性记忆",
            "duration": "hours-days",
            "action": "cache",
        },
        {
            "id": 3,
            "name": "Episodic",
            "zh_name": "情节记忆",
            "duration": "days-months",
            "action": "persist",
        },
        {
            "id": 4,
            "name": "Semantic",
            "zh_name": "语义记忆",
            "duration": "months-years",
            "action": "archive",
        },
    ],
    "confidence_thresholds": {"high": 0.85, "medium": 0.60, "low": 0.30},
    "suggested_actions": {
        "store": "High-confidence memory, should be persisted to downstream storage",
        "defer": "Medium-confidence, may be worth storing after more context accumulates",
        "ignore": "Low-confidence or no memorable content, safe to discard",
    },
    "output_format": {
        "root_keys": ["schema_version", "should_remember", "entries", "summary", "engine_info"],
        "entry_keys": [
            "id",
            "type",
            "content",
            "confidence",
            "tier",
            "source_layer",
            "reasoning",
            "suggested_action",
            "metadata",
        ],
    },
}
