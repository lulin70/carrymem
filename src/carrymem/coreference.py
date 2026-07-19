"""Coreference Resolution — Resolve pronouns to entities before memory storage.

Inspired by M-Flow's coreference resolution that resolves pronouns
(he/she/it/that/the company) to specific entities before indexing,
improving memory retrievability.

Example:
    Context: "My mom is from Sichuan"
    Message: "She likes spicy food"
    Resolved: "User's mom likes spicy food"

Strategy:
    1. Rule-based resolution (zero LLM dependency): pronoun → nearest entity
    2. LLM-based resolution (borrow host LLM): complex cases via MCP tool
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Pronoun patterns
# ---------------------------------------------------------------------------

# English pronouns that need resolution
EN_SUBJECT_PRONOUNS = {"he", "she", "it", "they"}
EN_OBJECT_PRONOUNS = {"him", "her", "it", "them"}
EN_POSSESSIVE_PRONOUNS = {"his", "her", "its", "their"}
EN_DEMONSTRATIVE = {"this", "that", "these", "those"}

# Chinese pronouns that need resolution
ZH_PRONOUNS = {"他", "她", "它", "他们", "她们", "它们"}
ZH_DEMONSTRATIVE = {"这个", "那个", "这", "那", "该公司", "该组织", "该项目", "该产品"}

# All pronouns to detect
ALL_PRONOUNS = (
    EN_SUBJECT_PRONOUNS
    | EN_OBJECT_PRONOUNS
    | EN_POSSESSIVE_PRONOUNS
    | EN_DEMONSTRATIVE
    | ZH_PRONOUNS
    | ZH_DEMONSTRATIVE
)

# Gender mapping for English pronouns
PRONOUN_GENDER = {
    "he": "male",
    "him": "male",
    "his": "male",
    "she": "female",
    "her": "female",
    "it": "neuter",
    "its": "neuter",
    "they": "plural",
    "them": "plural",
    "their": "plural",
    "他": "male",
    "她": "female",
    "它": "neuter",
    "他们": "plural",
    "她们": "female_plural",
    "它们": "neuter_plural",
}


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def has_pronoun(text: str) -> bool:
    """Check if text contains any pronoun that needs resolution."""
    if not text:
        return False
    # Check English pronouns with word boundaries
    words = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
    if words & ALL_PRONOUNS:
        return True
    # Check Chinese pronouns (no word boundary)
    for p in ZH_PRONOUNS | ZH_DEMONSTRATIVE:
        if p in text:
            return True
    return False


# ---------------------------------------------------------------------------
# Entity extraction from context
# ---------------------------------------------------------------------------


def _extract_entities_en(text: str) -> List[Tuple[str, str]]:
    """Extract entities from English text. Returns list of (entity, gender_hint)."""
    entities = []
    seen = set()

    # Pattern: my/our + relationship noun
    for m in re.finditer(
        r"(?:my|our)\s+(mom|mother|dad|father|sister|brother|wife"
        r"|husband|son|daughter|friend|boss|colleague|teacher|student"
        r"|project|team|company|app|product)",
        text,
        re.IGNORECASE,
    ):
        entity = m.group(0).lower()
        if entity not in seen:
            gender = _relationship_gender(m.group(1).lower())
            entities.append((entity, gender))
            seen.add(entity)

    # Pattern: "User" or "I" as entity
    if "i " in text.lower() or text.lower().startswith("i "):
        entities.append(("user", "neutral"))

    return entities


def _extract_entities_zh(text: str) -> List[Tuple[str, str]]:
    """Extract entities from Chinese text. Returns list of (entity, gender_hint)."""
    entities = []
    seen = set()

    # Pattern: 我的/我们的/我 + noun (with or without 的)
    for m in re.finditer(
        r"(?:我的|我们的|我)(妈妈|爸爸|姐姐|妹妹|哥哥|弟弟|老婆|丈夫|儿子|女儿|朋友|老板|同事|老师|学生|项目|公司|产品|团队)",
        text,
    ):
        entity = "用户的" + m.group(1)
        if entity not in seen:
            gender = _zh_relationship_gender(m.group(1))
            entities.append((entity, gender))
            seen.add(entity)

    # Pattern: project/company names (Chinese prefix + type suffix)
    for m in re.finditer(r"([\u4e00-\u9fffA-Za-z]{2,8}(?:项目|公司|产品|团队|应用|系统|方案))", text):
        entity = m.group(1)
        if entity not in seen:
            entities.append((entity, "neuter"))
            seen.add(entity)

    return entities


def _relationship_gender(rel: str) -> str:
    """Map English relationship noun to gender hint."""
    male = {"dad", "father", "brother", "husband", "son"}
    female = {"mom", "mother", "sister", "wife", "daughter"}
    if rel in male:
        return "male"
    if rel in female:
        return "female"
    return "neuter"


def _zh_relationship_gender(rel: str) -> str:
    """Map Chinese relationship noun to gender hint."""
    male = {"爸爸", "哥哥", "弟弟", "丈夫", "儿子", "老板"}
    female = {"妈妈", "姐姐", "妹妹", "老婆", "女儿"}
    if rel in male:
        return "male"
    if rel in female:
        return "female"
    return "neutral"


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _collect_entities(
    context: Optional[str],
    recent_memories: Optional[List[Dict[str, Any]]],
) -> List[Tuple[str, str]]:
    """Collect entities from the context string and recent memories."""
    entities: List[Tuple[str, str]] = []
    if context:
        entities.extend(_extract_entities_en(context))
        entities.extend(_extract_entities_zh(context))
    if recent_memories:
        for mem in recent_memories[:10]:
            content = mem.get("content", "") or mem.get("raw_text", "")
            if content:
                entities.extend(_extract_entities_en(content))
                entities.extend(_extract_entities_zh(content))
    return entities


def _resolve_english_pronouns(
    resolved: str,
    entities: List[Tuple[str, str]],
) -> Tuple[str, bool]:
    """Resolve English subject/object/possessive pronouns. Returns (resolved, any_resolved)."""
    any_resolved = False
    for pronoun in EN_SUBJECT_PRONOUNS | EN_OBJECT_PRONOUNS | EN_POSSESSIVE_PRONOUNS:
        if pronoun in resolved.lower():
            target = _find_matching_entity(pronoun, entities)
            if target:
                resolved = _replace_pronoun(resolved, pronoun, target)
                any_resolved = True
    return resolved, any_resolved


def _resolve_english_demonstratives(
    resolved: str,
    entities: List[Tuple[str, str]],
) -> Tuple[str, bool]:
    """Resolve English demonstrative pronouns (this/that/these/those). Returns (resolved, any_resolved)."""
    any_resolved = False
    for pronoun in EN_DEMONSTRATIVE:
        if re.search(r"\b" + re.escape(pronoun) + r"\b", resolved, re.IGNORECASE):
            target = _find_matching_entity(pronoun, entities)
            if target:
                resolved = _replace_pronoun(resolved, pronoun, target)
                any_resolved = True
    return resolved, any_resolved


def _resolve_chinese_pronoun_set(
    resolved: str,
    pronouns: Set[str],
    entities: List[Tuple[str, str]],
) -> Tuple[str, bool]:
    """Resolve a set of Chinese pronouns in text. Returns (resolved, any_resolved)."""
    any_resolved = False
    for pronoun in pronouns:
        if pronoun in resolved:
            target = _find_matching_entity(pronoun, entities)
            if target:
                target = _sanitize_replacement(target)
                if target:
                    resolved = resolved.replace(pronoun, target, 1)
                    any_resolved = True
    return resolved, any_resolved


def resolve_coreference(
    message: str,
    context: Optional[str] = None,
    recent_memories: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, bool]:
    """Resolve pronouns in message to entities from context.

    Args:
        message: The message containing pronouns.
        context: Recent conversation context (previous messages).
        recent_memories: Recently stored memories for entity extraction.

    Returns:
        Tuple of (resolved_message, was_resolved).
        If no resolution possible, returns (message, False).
    """
    if not has_pronoun(message):
        return message, False

    entities = _collect_entities(context, recent_memories)
    if not entities:
        return message, False

    resolved = message
    any_resolved = False

    resolved, en_resolved = _resolve_english_pronouns(resolved, entities)
    any_resolved = any_resolved or en_resolved

    resolved, en_dem_resolved = _resolve_english_demonstratives(resolved, entities)
    any_resolved = any_resolved or en_dem_resolved

    resolved, zh_resolved = _resolve_chinese_pronoun_set(resolved, ZH_PRONOUNS, entities)
    any_resolved = any_resolved or zh_resolved

    resolved, zh_dem_resolved = _resolve_chinese_pronoun_set(resolved, ZH_DEMONSTRATIVE, entities)
    any_resolved = any_resolved or zh_dem_resolved

    return resolved, any_resolved


def _find_matching_entity(
    pronoun: str,
    entities: List[Tuple[str, str]],
) -> Optional[str]:
    """Find the best matching entity for a pronoun based on gender/number.

    Strategy: Use the most recent entity that matches the pronoun's gender/number.
    If no gender match, use the most recent entity of any type.
    """
    if not entities:
        return None

    pronoun_gender = PRONOUN_GENDER.get(pronoun, "neutral")

    # Try gender-matched entity first
    for entity, gender in reversed(entities):
        if gender == pronoun_gender:
            return entity

    # Fallback: most recent entity of any type (for "it", "that", etc.)
    if pronoun_gender in ("neuter", "neutral"):
        for entity, gender in reversed(entities):
            if gender in ("neuter", "neutral"):
                return entity

    # Last resort: most recent entity
    if entities:
        return entities[-1][0]

    return None


def _sanitize_replacement(text: str) -> str:
    """Sanitize replacement text to prevent prompt injection.

    If injection patterns are detected, returns '[filtered]' instead of
    attempting to strip them (stripping can leave behind manipulative content).
    Otherwise strips control characters and limits length.
    """
    if not text:
        return text
    # Remove control characters (except space)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Check for injection patterns — if found, block entirely
    injection_patterns = [
        r"(?i)ignore\s+(all\s+)?previous\s+instructions",
        r"(?i)system\s*:",
        r"(?i)assistant\s*:",
        r"(?i)user\s*:",
        r"(?i)<\s*/?\s*(system|instruction|prompt)\s*>",
        r"(?i)you\s+are\s+now",
        r"(?i)forget\s+(everything|all)",
        r"(?i)new\s+instructions?\s*:",
        r"(?i)<\|im_start\|>",
        r"(?i)<\|im_end\|>",
        r"(?i)role\s*:",
    ]
    for pattern in injection_patterns:
        if re.search(pattern, text):
            return "[filtered]"
    # Limit length to prevent abuse
    if len(text) > 100:
        text = text[:100]
    return text.strip()


def _replace_pronoun(text: str, pronoun: str, replacement: str) -> str:
    """Replace a pronoun in text with the replacement, preserving case."""
    # Sanitize replacement to prevent injection
    replacement = _sanitize_replacement(replacement)
    if not replacement:
        return text
    # Handle possessive pronouns specially
    if pronoun in EN_POSSESSIVE_PRONOUNS:
        # "her preference" → "user's preference" (not "user preference")
        pattern = r"\b" + re.escape(pronoun) + r"\b"

        def replacer(m):
            """Replace possessive pronoun match with the user-possessive form."""
            result = replacement + "'s"
            if m.group(0)[0].isupper():
                result = result[0].upper() + result[1:]
            return result

        return re.sub(pattern, replacer, text, count=1, flags=re.IGNORECASE)

    # Subject/object pronouns
    pattern = r"\b" + re.escape(pronoun) + r"\b"

    def replacer(m):  # type: ignore[no-redef]
        """Replace subject/object pronoun match with the configured replacement."""
        result = replacement
        if m.group(0)[0].isupper():
            result = result[0].upper() + result[1:]
        return result

    return re.sub(pattern, replacer, text, count=1, flags=re.IGNORECASE)
