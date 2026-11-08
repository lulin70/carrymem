# CarryMem v0.12.0-alpha1 - Community Testing Guide

**For Alpha Testers**  
**Target**: Early adopters, MCP client users, LLM integration enthusiasts

---

## 🎯 Testing Goals

Phase 4.0 introduces **Host LLM integration** via MCP sampling. As an alpha release, we need community validation of:

1. **Real MCP client integration** (Claude Desktop, Cursor)
2. **Tier 4 host LLM functionality** in production
3. **Graceful degradation** when Tier 4 unavailable
4. **Edge cases** we haven't anticipated

---

## 📋 Test Scenarios

### Scenario 1: Basic Setup (5 minutes)

**Goal**: Verify MCP server starts and connects

1. Install CarryMem alpha:
   ```bash
   pip install --pre carrymem==0.12.0a1
   ```

2. Configure in Claude Desktop:
   ```json
   {
     "mcpServers": {
       "carrymem": {
         "command": "python3",
         "args": ["-m", "carrymem.integration.layer2_mcp"],
         "env": {
           "CARRYMEM_DATA_PATH": "/tmp/carrymem_alpha_test.db"
         }
       }
     }
   }
   ```

3. Restart Claude Desktop

4. Check logs for errors

**Expected**: Server starts without errors

**Report if**: Connection fails, timeout, or error messages

---

### Scenario 2: Tier 4 Host LLM - Suggest Rules (10 minutes)

**Goal**: Test LLM-enhanced rule suggestion

1. In Claude Desktop, have a conversation with some preferences:
   ```
   User: "I prefer using pytest for testing"
   User: "Always use type hints in Python"
   User: "Never commit .env files"
   ```

2. Ask CarryMem to suggest rules:
   ```
   Can you use CarryMem to suggest behavioral rules based on this conversation?
   ```

3. Observe the response

**Expected**:
- Returns structured rules with triggers, actions, confidence
- Response indicates `tier: "llm_enhanced"` (Tier 4)
- Rules are contextually relevant

**Report if**:
- Returns `tier: "rule_based"` (degraded to Tier 1)
- Rules are generic or off-topic
- JSON parsing errors
- Timeout or errors

---

### Scenario 3: Tier 4 - Session Summarization (10 minutes)

**Goal**: Test LLM-powered session summary

1. Have a longer conversation about a specific topic (e.g., Python packaging)

2. Ask for a summary:
   ```
   Use CarryMem to summarize this conversation session
   ```

3. Check the summary quality

**Expected**:
- Structured summary with key themes, decisions, patterns
- `tier: "llm_enhanced"`
- Captures main conversation points

**Report if**:
- Summary too generic or template-like
- Missing key conversation points
- Tier 1 fallback triggered unexpectedly

---

### Scenario 4: Graceful Degradation (5 minutes)

**Goal**: Verify Tier 1 fallback works

1. Temporarily break MCP sampling (e.g., disconnect network)

2. Try suggest_rules or summarize again

3. Verify you still get results (even if lower quality)

**Expected**:
- Response with `tier: "rule_based"`
- Still functional, just pattern-based
- No crashes or hard errors

**Report if**:
- Complete failure with no fallback
- Confusing error messages
- Tier 1 results unusable

---

### Scenario 5: Backward Compatibility (5 minutes)

**Goal**: Ensure existing features still work

1. Test basic CarryMem functions:
   ```python
   from carrymem import CarryMem
   
   cm = CarryMem()
   result = cm.classify_message("I prefer pytest over unittest")
   print(result)
   ```

2. Verify classification still works

**Expected**: No breaking changes to existing API

**Report if**: Existing code breaks after upgrade

---

## 📊 What to Report

### Priority 1: Blockers
- Server won't start
- MCP client can't connect
- Tier 4 never works (always degrades to Tier 1)
- Data corruption or crashes

### Priority 2: Integration Issues
- Tier 4 works intermittently
- Response parsing errors
- Poor LLM suggestion quality
- Performance problems (>10s latency)

### Priority 3: UX/Polish
- Confusing error messages
- Missing documentation
- Setup friction
- Feature requests

---

## 📝 Issue Report Template

```markdown
**Environment**:
- OS: macOS 14.2 / Windows 11 / Linux
- Python: 3.12.x
- MCP Client: Claude Desktop x.x.x / Cursor x.x.x
- CarryMem: 0.12.0a1

**Scenario**: [Scenario number from above]

**Expected**: [What should happen]

**Actual**: [What actually happened]

**Logs**: [Error messages, stack traces]

**Tier Status**: [Did Tier 1 fallback work? Y/N]

**Reproducible**: [Always / Sometimes / Once]
```

---

## 🎁 Tester Recognition

Alpha testers who contribute valuable feedback will be:
- Acknowledged in v0.12.0 final release notes
- Get early access to Phase 4.1 (Local LLM) beta
- Invited to Phase 4 design discussions

---

## 🔗 Resources

- **Installation**: See [RELEASE_NOTES_v0.12.0-alpha.md](../releases/RELEASE_NOTES_v0.12.0-alpha.md)
- **Technical Docs**: [LLM_INTEGRATION_GUIDE.md](../LLM_INTEGRATION_GUIDE.md)
- **Report Issues**: https://github.com/lulin70/carrymem/issues
- **Discussions**: https://github.com/lulin70/carrymem/discussions

---

**Thank you for helping test CarryMem Phase 4.0! 🚀**
