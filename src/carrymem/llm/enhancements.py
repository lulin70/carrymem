"""LLM-enhanced rule suggestion via host LLM (Tier 4)."""

import json
from collections import Counter
from typing import Any, Dict, List, Optional

from carrymem.utils.logger import logger


async def suggest_rules_via_host_llm(
    llm_client, memories: List[Dict[str, Any]], context: Optional[str] = None, limit: int = 5
) -> List[Dict[str, Any]]:
    """Suggest behavioral rules using host LLM.

    Args:
        llm_client: LLMClient instance (Tier 4 preferred).
        memories: List of memory dicts to analyze.
        context: Optional context hint for rule generation.
        limit: Maximum number of rules to suggest.

    Returns:
        List of suggested rules in format:
        [{"trigger": "when X", "action": "do Y", "confidence": 0.8}, ...]
    """
    # Format memories for LLM
    memory_texts = []
    for mem in memories[:50]:  # Limit to 50 most relevant
        text = mem.get("raw_text") or mem.get("content", "")
        mem_type = mem.get("type", "unknown")
        memory_texts.append(f"[{mem_type}] {text}")

    memories_str = "\n".join(memory_texts)

    # Construct prompt
    prompt = f"""Analyze the following user memories and extract behavioral rules.

Context: {context or "general usage patterns"}

Memories:
{memories_str}

Task: Identify {limit} actionable behavioral rules from these memories.

Output JSON array with this exact format:
[
  {{
    "trigger": "when working on Python projects",
    "action": "use type hints and pytest",
    "confidence": 0.9,
    "reasoning": "User consistently mentions type hints in Python contexts"
  }}
]

Rules should be:
- Specific and actionable
- Based on recurring patterns
- Confidence 0.0-1.0 based on evidence strength

Output only the JSON array, no explanation."""

    # Generate via host LLM (with fallback)
    try:
        response = await llm_client.generate(prompt=prompt, max_tokens=1500, temperature=0.7)
    except Exception as exc:  # noqa: BLE001 - NOTE: any LLM failure must degrade, not break
        logger.warning("LLM generation unavailable (%s), falling back to rule-based", exc)
        return suggest_rules_pattern_based(memories, limit)

    if not response or not response.strip():
        return suggest_rules_pattern_based(memories, limit)

    # Parse response
    try:
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response.strip()

        rules = json.loads(json_str)

        # Validate format
        validated_rules = []
        for rule in rules[:limit]:
            if isinstance(rule, dict) and "trigger" in rule and "action" in rule:
                validated_rules.append(
                    {
                        "trigger": rule["trigger"],
                        "action": rule["action"],
                        "confidence": rule.get("confidence", 0.5),
                        "reasoning": rule.get("reasoning", ""),
                        "source": "llm",
                    }
                )

        return validated_rules

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        # Fallback to rule-based if LLM output unparseable
        logger.warning("LLM response parse error: %s, falling back to rule-based", e)
        return suggest_rules_pattern_based(memories, limit)


def suggest_rules_pattern_based(memories: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """Tier 1 fallback: Pattern-based rule suggestion (no LLM).

    Uses frequency analysis and keyword extraction.
    """
    import re

    # Extract keywords and patterns
    keyword_freq: Counter[str] = Counter()
    patterns = []

    for mem in memories:
        text = mem.get("raw_text") or mem.get("content", "")

        # Extract keywords (simple tokenization)
        words = re.findall(r"\b\w+\b", text.lower())
        keyword_freq.update(words)

        # Detect "always" / "never" patterns
        if "always" in text.lower():
            patterns.append(("always", text))
        if "never" in text.lower():
            patterns.append(("never", text))
        if "prefer" in text.lower():
            patterns.append(("prefer", text))

    # Generate rules from top keywords
    suggested = []
    top_keywords = [k for k, v in keyword_freq.most_common(10) if v >= 2]

    for keyword in top_keywords[:limit]:
        suggested.append(
            {
                "trigger": f"when working with {keyword}",
                "action": f"follow established {keyword} patterns",
                "confidence": 0.6,
                "reasoning": f"Keyword '{keyword}' appears frequently in memories",
                "source": "pattern",
            }
        )

    # Add pattern-based rules
    for pattern_type, text in patterns[: limit - len(suggested)]:
        suggested.append(
            {
                "trigger": f"in contexts similar to: {text[:50]}...",
                "action": f"{pattern_type} follow this pattern",
                "confidence": 0.7,
                "reasoning": f"Explicit {pattern_type} pattern detected",
                "source": "pattern",
            }
        )

    return suggested[:limit]


async def summarize_session_via_host_llm(
    llm_client, memories: List[Dict[str, Any]], session_id: str, max_tokens: int = 500
) -> Dict[str, Any]:
    """Summarize a session's memories using host LLM.

    Args:
        llm_client: LLMClient instance.
        memories: Session memories to summarize.
        session_id: Session identifier.
        max_tokens: Maximum summary length.

    Returns:
        Dict with summary and metadata.
    """
    # Format memories
    memory_texts = []
    for mem in memories:
        text = mem.get("raw_text") or mem.get("content", "")
        mem_type = mem.get("type", "unknown")
        memory_texts.append(f"[{mem_type}] {text}")

    memories_str = "\n".join(memory_texts)

    # Construct prompt
    prompt = f"""Summarize the following session's memories concisely.

Session ID: {session_id}
Memory Count: {len(memories)}

Memories:
{memories_str}

Task: Create a structured summary covering:
1. Key themes and topics
2. Important decisions made
3. User preferences expressed
4. Notable patterns

Output as JSON:
{{
  "summary": "concise 2-3 sentence summary",
  "key_themes": ["theme1", "theme2"],
  "decisions": ["decision1", "decision2"],
  "patterns": ["pattern1"]
}}

Output only the JSON, no explanation."""

    # Generate summary
    try:
        response = await llm_client.generate(prompt=prompt, max_tokens=max_tokens, temperature=0.5)
    except Exception as exc:  # noqa: BLE001 - NOTE: any LLM failure must degrade, not break
        logger.warning("LLM summary unavailable (%s), using template", exc)
        return summarize_session_template(memories, session_id)

    if not response or not response.strip():
        return summarize_session_template(memories, session_id)

    # Parse response
    try:
        if "```json" in response:
            json_str = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            json_str = response.split("```")[1].split("```")[0].strip()
        else:
            json_str = response.strip()

        summary = json.loads(json_str)
        return {"session_id": session_id, "memory_count": len(memories), "source": "llm", **summary}

    except (json.JSONDecodeError, KeyError) as e:
        # Fallback to template-based summary
        logger.warning("LLM summary parse error: %s, using template", e)
        return summarize_session_template(memories, session_id)


def summarize_session_template(memories: List[Dict[str, Any]], session_id: str) -> Dict[str, Any]:
    """Tier 1 fallback: Template-based session summary (no LLM)."""
    from collections import Counter

    # Group by type
    type_counts = Counter(mem.get("type", "unknown") for mem in memories)

    # Extract keywords
    all_text = " ".join(mem.get("raw_text") or mem.get("content", "") for mem in memories)
    words = all_text.lower().split()
    top_keywords = [k for k, v in Counter(words).most_common(5)]

    return {
        "session_id": session_id,
        "memory_count": len(memories),
        "source": "template",
        "summary": f"Session with {len(memories)} memories covering {', '.join(top_keywords[:3])}",
        "key_themes": top_keywords,
        "decisions": [mem.get("content") for mem in memories if mem.get("type") == "decision"][:3],
        "patterns": [f"{k}: {v} occurrences" for k, v in type_counts.most_common(3)],
    }


__all__ = [
    "suggest_rules_via_host_llm",
    "suggest_rules_pattern_based",
    "summarize_session_via_host_llm",
    "summarize_session_template",
]
