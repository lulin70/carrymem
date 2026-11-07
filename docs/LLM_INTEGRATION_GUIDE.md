# CarryMem LLM Integration Guide

**Version**: v0.12.0-alpha  
**Last Updated**: 2026-11-07  
**Status**: Phase 4.0 Complete

---

## Overview

Phase 4 introduces **optional LLM integration** to enhance CarryMem's memory analysis capabilities while maintaining its core zero-dependency promise. The system uses a **tiered architecture** that gracefully degrades when LLMs are unavailable.

### Key Design Principles

✅ **Zero Mandatory Dependencies**: Core features work without LLM  
✅ **Host LLM First**: Leverages MCP client's LLM (Claude Desktop, Cursor) with zero configuration  
✅ **Graceful Degradation**: Automatic fallback to rule-based implementations  
✅ **Privacy by Default**: No external API calls unless explicitly configured  
✅ **Offline Capable**: Tier 1 and Tier 2 work without internet

---

## Architecture: 4-Tier LLM Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Tier 4: Host LLM (MCP Sampling)                            │
│  • Uses Claude Desktop / Cursor's LLM                       │
│  • Zero configuration required                              │
│  • Best quality, no API keys needed                         │
│  • Availability: When running as MCP server                 │
└─────────────────────────────────────────────────────────────┘
                        ↓ Degrades on failure
┌─────────────────────────────────────────────────────────────┐
│  Tier 3: Cloud API (OpenAI-compatible)                      │
│  • Requires API key (explicit opt-in)                       │
│  • High quality responses                                   │
│  • Network dependency                                       │
│  • Status: Available (needs the openai package)             │
└─────────────────────────────────────────────────────────────┘
                        ↓ Degrades on failure
┌─────────────────────────────────────────────────────────────┐
│  Tier 2: Local LLM (OpenAI-compatible endpoint)             │
│  • No cloud key required                                    │
│  • Fully offline capable                                    │
│  • Lower quality than Tier 3/4                              │
│  • Status: Available (loopback CARRYMEM_LLM_BASE_URL)       │
└─────────────────────────────────────────────────────────────┘
                        ↓ Always available fallback
┌─────────────────────────────────────────────────────────────┐
│  Tier 1: Rule-based (Zero Dependencies)                     │
│  • Pattern matching and heuristics                          │
│  • Always available (guaranteed)                            │
│  • No LLM required                                          │
│  • Baseline quality                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## Enhanced Features

### 1. Intelligent Rule Suggestion

**Tier 4 (Host LLM)**:
```python
# Analyzes memories with host LLM
suggest_rules(memory_type="preference", max_candidates=5)

# Example output:
{
  "tier": "llm_enhanced",
  "suggestions": [
    {
      "trigger": "when writing Python code",
      "action": "use type hints and pytest",
      "confidence": 0.9,
      "reasoning": "User consistently mentions type hints in Python contexts"
    }
  ]
}
```

**Tier 1 (Rule-based Fallback)**:
```python
# Pattern matching on keyword frequency
# Detects "always"/"never"/"prefer" patterns
# No LLM required
{
  "tier": "rule_based",
  "suggestions": [
    {
      "trigger": "when working with python",
      "action": "follow established python patterns",
      "confidence": 0.6,
      "reasoning": "Keyword 'python' appears frequently"
    }
  ]
}
```

### 2. Session Summarization

**Tier 4 (Host LLM)**:
```python
summarize_and_store(session_id="session_123", max_tokens=500)

# Example output:
{
  "action": "llm_summary",
  "tier": "llm_enhanced",
  "summary": "User explored Python packaging best practices...",
  "key_themes": ["python", "packaging", "best-practices"],
  "decisions": ["Use pyproject.toml", "Adopt semantic versioning"],
  "patterns": ["Prefers modern Python tooling"]
}
```

**Tier 1 (Template-based Fallback)**:
```python
# Template-based summary
{
  "action": "summarize",
  "tier": "rule_based",
  "content": "- [preference] Use type hints\n- [decision] Adopt pytest",
  "memory_count": 15
}
```

---

## Usage

### As MCP Server (Recommended)

**Tier 4 Host LLM** is automatically enabled when running as MCP server:

```bash
# Run MCP server (Tier 4 auto-enabled)
carrymem mcp

# Or via CLI wrapper
python -m carrymem.integration.layer2_mcp
```

**How it works**:
1. CarryMem detects it's running as MCP server
2. `LLMClient` initializes with `mcp_server=self`
3. When `suggest_rules()` is called, it tries Tier 4 first
4. On failure (e.g., client doesn't support sampling), falls back to Tier 1

### As Python Library

```python
from carrymem import CarryMem
from carrymem.llm import LLMClient

# Tier 1 only (no LLM)
cm = CarryMem()
rules = cm.rule_engine.suggest_rules(memories, max_candidates=5)

# With explicit LLM client
llm_client = LLMClient(mcp_server=None)  # Tier 1 only
# To enable Tier 4, pass MCP server instance

# Check active tier
status = llm_client.get_status()
print(f"Active tier: {status['active_tier']}")
print(f"Available tiers: {status['available_tiers']}")
```

---

## Configuration

### Tier 4: Host LLM (Zero Config)

No configuration needed! If running as MCP server under Claude Desktop/Cursor, Tier 4 is automatically available.

**Check availability**:
```python
from carrymem.llm import LLMClient

client = LLMClient(mcp_server=mcp_server_instance)
status = client.get_status()

if 4 in status['available_tiers']:
    print("✓ Host LLM available (Tier 4)")
else:
    print("○ Host LLM unavailable, using Tier 1")
```

### Tier 3: Cloud API

Tier 3 uses an OpenAI-compatible client. It needs explicit configuration.

```bash
export CARRYMEM_LLM_ENABLED=true
export CARRYMEM_LLM_API_KEY=sk-...
export CARRYMEM_LLM_BASE_URL=https://api.openai.com/v1
export CARRYMEM_LLM_MODEL=gpt-4o-mini
```

```python
from carrymem.llm import LLMClient

client = LLMClient()  # reads CARRYMEM_LLM_* variables
print(client.get_status())  # {"active_tier": 3, ...}
```

### Tier 2: Local LLM

Tier 2 uses the same client with a loopback endpoint. The provider reports
Tier 2 when the endpoint host is `localhost`, `127.0.0.1`, `::1` or `0.0.0.0`.

```bash
export CARRYMEM_LLM_ENABLED=true
export CARRYMEM_LLM_API_KEY=local
export CARRYMEM_LLM_BASE_URL=http://localhost:11434/v1
export CARRYMEM_LLM_MODEL=qwen3:8b
```

The `openai` package is required for Tier 2 and Tier 3. It is not a core
dependency.

---

## Graceful Degradation

### Automatic Fallback

The system automatically tries tiers in order (4 → 3 → 2 → 1) until one succeeds:

```python
# Example: every LLM tier fails -> the caller falls back to rule-based output
import logging
logging.basicConfig(level=logging.INFO)

llm_client = LLMClient(mcp_server=broken_server)
try:
    result = await llm_client.generate("Suggest rules...")
except LLMUnavailableError:
    result = suggest_rules_pattern_based(memories)

# Log output:
# WARNING - LLM tier 4 failed: Sampling request timed out
# WARNING - LLM tier 3 failed: ...
```

### Manual Tier Selection

```python
# Force specific tier (advanced use)
from carrymem.llm import RuleBasedProvider

provider = RuleBasedProvider()  # Tier 1 only
result = await provider.generate("prompt...")
```

---

## Performance

### Latency by Tier

| Tier | Typical Latency | Quality |
|------|-----------------|---------|
| Tier 4 (Host LLM) | 2-5s | ★★★★★ |
| Tier 3 (Cloud API) | 1-3s | ★★★★★ |
| Tier 2 (Local LLM) | 3-10s | ★★★☆☆ |
| Tier 1 (Rule-based) | <1ms | ★★☆☆☆ |

### Resource Usage

- **Tier 4**: No local compute (uses host LLM)
- **Tier 3**: Network only
- **Tier 2**: Local GPU/CPU (model-dependent)
- **Tier 1**: Negligible (<1MB RAM)

---

## Troubleshooting

### Tier 4 Not Available

**Symptom**: `LLMClient.tier == 1` when expecting Tier 4

**Causes**:
1. Not running as MCP server → Start with `carrymem mcp`
2. MCP client doesn't support sampling → Update client
3. `mcp_server=None` in `LLMClient()` → Pass server instance

**Verify**:
```python
status = llm_client.get_status()
for p in status['provider_status']:
    print(f"Tier {p['tier']}: {p['type']} - available={p['is_available']}")
```

### Tier 4 Times Out

**Symptom**: `Tier 4 failed: Sampling request timed out`

**Causes**:
1. Host LLM is slow → Increase timeout (default 30s)
2. Network issues → Check connectivity
3. MCP client overloaded → Restart client

**Workaround**: System auto-degrades to Tier 1

### All Tiers Fail

**Symptom**: `[Error: all providers failed]`

**This should never happen** — Tier 1 is guaranteed to work. If you see this:
1. Check Python version (requires 3.12+)
2. Verify CarryMem installation: `pip show carrymem`
3. Report bug with stack trace

---

## Roadmap

### Phase 4.1: Local LLM Integration (Next)
- Ollama auto-detection
- LM Studio support
- llama.cpp integration

### Phase 4.2: Cloud API Integration
- OpenAI GPT-4 support
- Anthropic Claude API
- Explicit API key management

### Phase 4.3: Advanced Features
- Streaming responses
- Token usage tracking
- Custom prompts
- Multi-modal support

---

## FAQ

**Q: Do I need an API key to use LLM features?**  
A: No. Tier 4 (host LLM) needs no key. Tier 3 and Tier 2 need `CARRYMEM_LLM_API_KEY`; Tier 2 also needs a loopback base URL.

**Q: Can I use CarryMem offline?**  
A: Yes. Tier 1 works offline with no dependencies. Tier 2 works with a local OpenAI-compatible endpoint.

**Q: What happens if Tier 4 fails?**  
A: The client tries Tier 3, then Tier 2. If all tiers fail, `generate()` raises `LLMUnavailableError`. The caller then uses the rule-based path.

**Q: How do I force Tier 1 (no LLM)?**  
A: Initialize with `LLMClient(mcp_server=None)` or use MCP handlers without `_llm_client` injection.

**Q: Can I customize prompts for Tier 4?**  
A: Not yet. Custom prompts are planned for Phase 4.3.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

**Contact**: lulin70@gmail.com  
**Repo**: https://github.com/lulin70/carrymem
