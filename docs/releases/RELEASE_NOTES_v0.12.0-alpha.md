# CarryMem v0.12.0-alpha Release Notes

**Release Date**: 2026-11-07  
**Code Name**: Phase 4.0 - Intelligent Enhancement Layer  
**Status**: Alpha Release (source only; not on PyPI)

> **Correction (2026-11-07)**: The first `v0.12.0-alpha` tag failed CI and
> Release preflight. That commit removed the legacy synchronous LLM API and
> broke 31 tests. This revision restores the legacy contract, adds the async
> tier API, and fixes sampling response routing. CI run `42387757587` on commit
> `51277fd` passed every job. Prefer tag `v0.12.0a1` when it becomes available.

---

## 🎉 What's New: Host LLM Integration

CarryMem v0.12.0-alpha introduces **optional LLM enhancement** while maintaining its core zero-dependency promise. The highlight feature is **Tier 4 Host LLM** integration, which leverages your MCP client's built-in LLM (Claude Desktop, Cursor) with **zero configuration**.

### Key Features

#### 🧠 Intelligent Rule Suggestion
```python
# Analyzes your memories with host LLM
result = carrymem.rule_engine.suggest_rules(memories, max_candidates=5)

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

#### 📝 Session Summarization
```python
# Summarize session with LLM
result = summarize_and_store(session_id="session_123", max_tokens=500)

# Example output:
{
  "tier": "llm_enhanced",
  "summary": "User explored Python packaging best practices...",
  "key_themes": ["python", "packaging", "best-practices"],
  "decisions": ["Use pyproject.toml", "Adopt semantic versioning"]
}
```

#### 🏗️ Four-Tier Architecture

```
Tier 4: Host LLM (MCP Sampling)     ← NEW! No API key
         ↓ degrades on failure
Tier 3: Cloud API (OpenAI-compatible) ← requires CARRYMEM_LLM_API_KEY
         ↓ degrades on failure
Tier 2: Local LLM (OpenAI-compatible) ← local CARRYMEM_LLM_BASE_URL
         ↓ always available fallback
Tier 1: Rule-based (Zero Dependencies) ← Guaranteed to work
```

Tier 2 and Tier 3 share one provider. The provider reports Tier 2 when the
endpoint host is a loopback address. It reports Tier 3 for all other hosts.

### Design Guarantees

✅ **Zero Configuration**: Tier 4 needs no key. The client must support sampling
✅ **Zero Dependencies**: Core features work without LLM
✅ **Privacy First**: No external API calls by default
✅ **Graceful Degradation**: The response `tier` field reports the tier that
   actually answered
✅ **Stable API**: The synchronous `chat`, `is_available` and `count_tokens`
   contract is preserved

---

## 📦 Installation

### Upgrade from v0.11.x

```bash
# Existing installation
pip install --upgrade carrymem

# Or from source
cd carrymem
git pull origin main
git checkout v0.12.0-alpha
pip install -e .
```

### Fresh Installation

This alpha is a source release. It is not on PyPI.

```bash
git clone https://github.com/lulin70/carrymem.git
cd carrymem
git checkout v0.12.0-alpha
pip install -e .
```

---

## 🚀 Quick Start

### As MCP Server (Recommended)

Host LLM (Tier 4) is automatically enabled:

```bash
# Run MCP server
carrymem mcp

# Or
python -m carrymem.integration.layer2_mcp
```

### As Python Library

```python
from carrymem import CarryMem
from carrymem.llm import LLMClient

# Without LLM (Tier 1 only, backward compatible)
cm = CarryMem()
rules = cm.rule_engine.suggest_rules(memories)

# With LLM client
llm_client = LLMClient(mcp_server=mcp_server_instance)
status = llm_client.get_status()
print(f"Active tier: {status['active_tier']}")  # Should be 4 if in MCP mode
```

---

## 📖 Documentation

- **[LLM Integration Guide](../LLM_INTEGRATION_GUIDE.md)**: Complete technical documentation
- **[Design Principles](../DESIGN_PRINCIPLES.md)**: Core philosophy and decision framework
- **[Phase 4 Plan](../design/PHASE_4_INTELLIGENT_ENHANCEMENT_PLAN.md)**: Detailed roadmap

---

## ✅ Testing

Phase 4.0 includes comprehensive test coverage:

- **15+ Unit Tests**: `tests/test_llm_phase4.py`
  - HostLLMProvider initialization and sampling
  - RuleBasedProvider always-available guarantee
  - LLMClient tier selection and graceful degradation
  - LLM enhancement functions

- **8 E2E Tests**: `tests/e2e/test_phase4_mcp_integration.py`
  - Full MCP server integration
  - Graceful degradation scenarios
  - Backward compatibility verification
  - Zero-dependency guarantee validation

**Test status**: The full non-slow regression on the corrected tree reports
`5167 passed, 1 skipped, 77 deselected`. The first alpha tag did not report
this: 31 tests failed, because the legacy synchronous LLM API was removed.
The corrected tree restores that API and adds 4 tests for the Tier 2/3
provider. The CI result on the pushed commit is the release evidence.

---

## 🧪 Alpha Release Status

### Testing Coverage

✅ **Validated**:
- Unit tests (15+ test cases) - All passing
- E2E integration tests (8 scenarios) - All passing
- Smoke tests - Module imports and initialization verified
- Backward compatibility - Existing code continues to work
- Zero-dependency guarantee - Tier 1 always available

⚠️ **Community Testing Needed**:
- **Real MCP Client Integration**: Only simulated via mocks, not tested in actual Claude Desktop/Cursor
- **Host LLM Sampling API**: Protocol implemented but needs real-world validation
- **Tier 4 Degradation**: Tested in mock scenarios, real failure scenarios need validation
- **Cross-platform**: Tested on macOS only

### Expected Issues

As an alpha release, you may encounter:

1. **MCP Sampling Protocol Compatibility**: Different MCP clients may have varying sampling API implementations
2. **Response Parsing**: LLM output formats may vary, current parsing is conservative
3. **Performance**: Tier 4 latency depends on host LLM, not yet benchmarked in production
4. **Error Messages**: May need refinement based on real usage patterns

### How to Report Issues

Please report issues with:
- MCP client name and version (Claude Desktop x.x.x, Cursor x.x.x)
- Operating system
- Error messages or unexpected behavior
- Whether Tier 1 fallback worked correctly

**GitHub Issues**: https://github.com/lulin70/carrymem/issues

---

## 🐛 Known Limitations

### Alpha Release Constraints

1. **Tier 2/3 Need the `openai` Package**: Each uses an OpenAI-compatible endpoint. Install `openai` and set the `CARRYMEM_LLM_*` variables.
2. **MCP Sampling Protocol**: Requires MCP client with sampling support (Claude Desktop 2024-11+, Cursor 0.40+)
3. **Limited Prompt Customization**: Custom prompts planned for Phase 4.3
4. **Real-world Integration Untested**: Mock-based testing only, community validation needed

### Workarounds

- If Tier 4 unavailable: System auto-degrades to Tier 3, Tier 2 or Tier 1
- If you encounter sampling errors: Check MCP client version and logs
- If you need offline LLM: Use a local OpenAI-compatible endpoint (Tier 2)
- If you need custom prompts: Use Tier 1 or wait for Phase 4.3

---

## 🛣️ Roadmap

### Phase 4.1 (Q4 2026)
- ✨ Local LLM provider: shipped in this alpha as Tier 2 (OpenAI-compatible)
- 🔧 Auto-detection of local models
- 📊 Offline semantic analysis

### Phase 4.2 (Q1 2027)
- ☁️ Provider auto-detection and failover tuning
- 🔐 Explicit API key management
- 💰 Token usage tracking

### Phase 4.3 (Q2 2027)
- 🎨 Custom prompt templates
- 📡 Streaming responses
- 🖼️ Multi-modal support (image analysis)

---

## 💬 Feedback & Support

This is an **alpha release** — community testing and feedback actively sought!

### What We Need from You

**Priority Testing Areas**:
1. ✨ Real MCP client integration (Claude Desktop, Cursor)
2. 🔄 Tier 4→1 degradation in production scenarios
3. 📊 Host LLM response quality and parsing edge cases
4. ⚡ Performance benchmarks in real usage

**Especially Valuable Feedback**:
- First-time setup experience in Claude Desktop/Cursor
- Actual Tier 4 suggestion quality vs expectations
- Any scenarios where Tier 1 fallback triggers unexpectedly
- Performance issues or latency concerns

### Contact Channels

- 🐛 **Report bugs**: [GitHub Issues](https://github.com/lulin70/carrymem/issues)
- 💡 **Feature requests**: [GitHub Discussions](https://github.com/lulin70/carrymem/discussions)
- 📧 **Email**: lulin70@gmail.com
- 📚 **Docs**: [README.md](../../README.md), [LLM_INTEGRATION_GUIDE.md](../LLM_INTEGRATION_GUIDE.md)

**When reporting issues, please include**:
- MCP client name and version
- OS and Python version
- Whether Tier 1 fallback worked
- Expected vs actual behavior

---

## 🙏 Credits

**Maintainer**: lulin70  
**Contributors**: Kiro AI (implementation assistant)

Special thanks to:
- Claude Desktop team for MCP sampling API
- Anthropic for Claude 3.5 Sonnet
- CarryMem community for feedback and testing

---

## 📜 License

MIT License - see [LICENSE](LICENSE)

---

## 🔗 Links

- **GitHub**: https://github.com/lulin70/carrymem
- **PyPI**: https://pypi.org/project/carrymem/
- **Documentation**: [LLM_INTEGRATION_GUIDE.md](../LLM_INTEGRATION_GUIDE.md)
- **Changelog**: [CHANGELOG_PHASE4.md](../archive/CHANGELOG_PHASE4.md)

---

**Happy Memory Managing! 🎯**
