"""Memory selection — score, rank, and select memories within token budget.

Extracted from context.py for modularity.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .utils.language import has_cjk

ACCESS_BOOST_PER_ACCESS = 0.01
ACCESS_BOOST_CAP = 0.1
RECENCY_DECAY_RATE = 0.1  # Halve every ~7 days: 2^(-0.1*7) ≈ 0.616

# Type-specific confidence floors — memories below these are filtered out
_TYPE_CONFIDENCE_FLOOR = {
    "user_preference": 0.4,
    "sentiment_marker": 0.5,
}

# Type-specific score boosts applied after base score computation
_TYPE_SELECTION_BOOST = {
    "correction": 0.5,
    "decision": 0.4,
    "user_preference": 0.3,
    "fact_declaration": 0.0,
    "session_summary": -0.1,
    "sentiment_marker": -0.2,
}

# Types that must appear first in the final ordering
_MANDATORY_TYPES = {"correction", "decision"}


def _days_since_last_access(last_accessed_at: Any) -> Optional[float]:
    """Calculate days since last access from a datetime or ISO string.

    Args:
        last_accessed_at: ISO string, datetime, or None.

    Returns:
        Days as float (>=0), or None if the value cannot be parsed.
    """
    if not last_accessed_at:
        return None
    dt = last_accessed_at
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return None
    if isinstance(dt, datetime):
        now = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt).total_seconds() / 86400)
    return None


def _estimate_tokens(text: str) -> int:
    cjk_count = sum(1 for c in text if has_cjk(c))
    other_count = len(text) - cjk_count
    return max(1, cjk_count + other_count // 4)


def _tokenize_text(text: str) -> set:
    words = set(re.findall(r"[a-zA-Z]{2,}", text.lower()))
    cjk_chars = set()
    for c in text:
        if has_cjk(c):
            cjk_chars.add(c)
    return words | cjk_chars


def context_relevance(memory_content: str, context: str) -> float:
    """Return Jaccard relevance score between memory content and context."""
    if not context or not context.strip():
        return 0.0
    if not memory_content or not isinstance(memory_content, str):
        return 0.0
    context_tokens = _tokenize_text(context)
    memory_tokens = _tokenize_text(memory_content)
    if not context_tokens or not memory_tokens:
        return 0.0
    overlap = len(context_tokens & memory_tokens)
    union = len(context_tokens | memory_tokens)
    if union == 0:
        return 0.0
    return overlap / union


def _has_temporal_signal(text: str) -> bool:
    temporal_patterns = [
        r"\b(first|last|before|after|earlier|later|previous|next)\b",
        r"\bhow many days\b",
        r"\bhow (long|much time)\b",
        r"\bwhen\b",
        r"\b(days?|weeks?|months?|years?) (ago|before|after|between|passed)\b",
    ]
    for p in temporal_patterns:
        if re.search(p, text.lower()):
            return True
    return False


def _has_preference_signal(text: str) -> bool:
    pref_patterns = [
        r"\bprefer\b",
        r"\bpreference\b",
        r"\bfavorite\b",
        r"\bfavourite\b",
        r"\bdislike\b",
        r"\brecommend\b",
        r"\blike\b",
        r"\blove\b",
        r"\bhate\b",
        r"\bavoid\b",
        r"\bwant\b",
        r"\bneed\b",
        r"\bcare about\b",
        r"\bimportant to\b",
        r"\bcan\'t stand\b",
        r"\bnot a fan\b",
        r"\bnot interested\b",
        r"\baverse\b",
        r"\baversion\b",
        r"\bstrongly\b",
        r"\balways\b",
        r"\bnever\b",
        r"\bbest\b",
        r"\bworst\b",
        r"\bsuggest\b",
        r"\badvice\b",
        r"\bopinion\b",
    ]
    for p in pref_patterns:
        if re.search(p, text.lower()):
            return True
    return False


def _has_aggregation_signal(text: str) -> bool:
    agg_patterns = [
        r"\bhow many\b",
        r"\bhow much\b",
        r"\btotal\b",
        r"\ball\b",
        r"\bevery\b",
        r"\bcount\b",
        r"\blist\b",
    ]
    for p in agg_patterns:
        if re.search(p, text.lower()):
            return True
    return False


def _jaccard_sim(tokens_a: set, tokens_b: set) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _mmr_select(
    scored: List[tuple],
    query_tokens: set,
    max_count: int,
    lambda_param: float = 0.7,
) -> List[tuple]:
    if not scored:
        return []
    if len(scored) <= max_count:
        return scored

    # Pre-compute token sets for all candidates (avoid repeated tokenization)
    candidate_tokens = []
    for _, mem in scored:
        text = (mem.get("raw_text", "") or "") + " " + (mem.get("content", "") or "")
        candidate_tokens.append(_tokenize_text(text))

    selected_indices = []
    selected_tokens_list: List[set] = []
    remaining = list(range(len(scored)))

    max_score = max(s for s, _ in scored) if scored else 1.0
    if max_score <= 0:
        max_score = 1.0

    for _ in range(max_count):
        best_mmr = -float("inf")
        best_idx = -1

        for idx in remaining:
            score, mem = scored[idx]
            norm_score = score / max_score

            mem_tokens = candidate_tokens[idx]

            if selected_tokens_list:
                max_sim = max(_jaccard_sim(mem_tokens, s) for s in selected_tokens_list)
            else:
                max_sim = 0.0

            query_sim = _jaccard_sim(mem_tokens, query_tokens)
            relevance = 0.7 * norm_score + 0.3 * query_sim
            mmr = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr > best_mmr:
                best_mmr = mmr
                best_idx = idx

        if best_idx < 0:
            break

        selected_indices.append(best_idx)
        remaining.remove(best_idx)
        selected_tokens_list.append(candidate_tokens[best_idx])

    return [scored[i] for i in selected_indices]


def _compute_temporal_bonus(m: Dict[str, Any], is_temporal: bool) -> float:
    """Compute temporal signal bonus for a memory.

    Returns 0.0 if ``is_temporal`` is False or no date patterns are found.
    """
    if not is_temporal:
        return 0.0

    content_lower = (m.get("content", "") or "").lower()
    raw_lower = (m.get("raw_text", "") or "").lower()
    combined = content_lower + " " + raw_lower

    has_date = bool(
        re.search(
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}",
            combined,
        )
    ) or bool(re.search(r"\d{4}-\d{2}-\d{2}", combined))
    has_short_date = bool(
        re.search(
            r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
            combined,
        )
    )

    bonus = 0.0
    if has_date or has_short_date:
        bonus += 0.4

    date_count = (
        len(
            re.findall(
                r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}",
                combined,
            )
        )
        + len(re.findall(r"\d{4}-\d{2}-\d{2}", combined))
        + len(
            re.findall(
                r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
                combined,
            )
        )
    )
    if date_count >= 2:
        bonus += 0.15
    if m.get("type") in ("fact_declaration", "decision"):
        bonus += 0.1

    return bonus


def _compute_memory_score(
    m: Dict[str, Any],
    context: Optional[str],
    importance_weight: float,
    relevance_weight: float,
    min_confidence: float,
    is_temporal: bool,
    is_aggregation: bool,
) -> Optional[float]:
    """Compute the selection score for a single memory.

    Returns ``None`` if the memory is filtered out by the type-specific
    confidence floor.
    """
    conf = m.get("confidence", 0.0)
    mtype = m.get("type", "")
    type_floor = _TYPE_CONFIDENCE_FLOOR.get(mtype, min_confidence)
    if conf < type_floor:
        return None

    imp = m.get("importance_score", 0.0)
    rel = context_relevance(m.get("content", ""), context or "")
    final = imp * importance_weight + rel * relevance_weight

    type_boost = _TYPE_SELECTION_BOOST.get(mtype, 0.0)
    final += type_boost

    access_count = max(0, m.get("access_count", 0) or 0)
    access_boost = min(access_count * ACCESS_BOOST_PER_ACCESS, ACCESS_BOOST_CAP)
    # Recency decay: frequently accessed but long-unaccessed memories fade
    if access_count > 0:
        days_since = _days_since_last_access(m.get("last_accessed_at"))
        if days_since is not None:
            access_boost *= 2 ** (-RECENCY_DECAY_RATE * days_since)
    final += access_boost

    final += _compute_temporal_bonus(m, is_temporal)

    if is_aggregation:
        final += 0.3

    return float(final)


def _apply_aggregation_dedup(
    scored: List[tuple],
    max_count: int,
) -> List[tuple]:
    """Deduplicate scored memories by ``session_id``, keeping first per session.

    The first occurrence of each session is preserved in score order; the
    remaining items are appended afterwards. Only applied when the
    aggregation signal is present and ``len(scored) > max_count``.
    """
    seen_sessions: set = set()
    session_represented: List[tuple] = []
    remaining: List[tuple] = []
    for score, m in scored:
        meta = m.get("metadata", {})
        sid = meta.get("session_id", "") if isinstance(meta, dict) else ""
        if sid and sid not in seen_sessions:
            session_represented.append((score, m))
            seen_sessions.add(sid)
        else:
            remaining.append((score, m))
    return session_represented + remaining


def _reorder_by_type_priority(scored: List[tuple]) -> List[tuple]:
    """Reorder scored memories: mandatory types first, then preferences, then others."""
    mandatory_scored = [(s, m) for s, m in scored if m.get("type") in _MANDATORY_TYPES]
    pref_scored = [(s, m) for s, m in scored if m.get("type") == "user_preference"]
    other_scored = [
        (s, m) for s, m in scored if m.get("type") not in _MANDATORY_TYPES and m.get("type") != "user_preference"
    ]
    return mandatory_scored + pref_scored + other_scored


def _select_within_token_budget(
    scored: List[tuple],
    max_count: int,
    max_tokens: int,
    context: Optional[str],
) -> List[Dict[str, Any]]:
    """Select memories within token budget, annotating each with score metadata."""
    selected: List[Dict[str, Any]] = []
    total_tokens = 0
    for score, m in scored:
        if len(selected) >= max_count:
            break
        entry_tokens = _estimate_tokens(m.get("content", ""))
        if total_tokens + entry_tokens > max_tokens:
            break
        m_copy = dict(m)
        m_copy["_selection_score"] = round(score, 6)
        m_copy["_context_relevance"] = round(context_relevance(m.get("content", ""), context or ""), 6)
        selected.append(m_copy)
        total_tokens += entry_tokens

    return selected


def select_memories(
    memories: List[Dict[str, Any]],
    context: Optional[str] = None,
    max_count: int = 10,
    max_tokens: int = 2000,
    importance_weight: float = 0.7,
    relevance_weight: float = 0.3,
    use_mmr: bool = True,
    mmr_lambda: float = 0.7,
    min_confidence: float = 0.0,
) -> List[Dict[str, Any]]:
    """Select the most relevant memories for a context within token limits."""
    if not memories:
        return []

    is_temporal = bool(context and _has_temporal_signal(context))
    is_aggregation = bool(context and _has_aggregation_signal(context))

    scored: List[tuple] = []
    for m in memories:
        score = _compute_memory_score(
            m,
            context,
            importance_weight,
            relevance_weight,
            min_confidence,
            is_temporal,
            is_aggregation,
        )
        if score is not None:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)

    if is_aggregation and len(scored) > max_count:
        scored = _apply_aggregation_dedup(scored, max_count)

    if use_mmr and context and len(scored) > 1:
        query_tokens = _tokenize_text(context)
        select_count = min(len(scored), max_count)
        scored = _mmr_select(scored, query_tokens, select_count, mmr_lambda)

    scored = _reorder_by_type_priority(scored)

    return _select_within_token_budget(scored, max_count, max_tokens, context)


def select_knowledge(
    knowledge: List[Dict[str, Any]],
    context: Optional[str] = None,
    max_count: int = 5,
    max_tokens: int = 1000,
) -> List[Dict[str, Any]]:
    """Select the most relevant knowledge entries for a context."""
    if not knowledge:
        return []

    scored = []
    for k in knowledge:
        content = k.get("content", "")
        title = k.get("title", "")
        full_text = f"{title} {content}"
        rel = context_relevance(full_text, context or "")
        scored.append((rel, k))

    scored.sort(key=lambda x: x[0], reverse=True)

    selected: List[Dict[str, Any]] = []
    total_tokens = 0
    for score, k in scored:
        if len(selected) >= max_count:
            break
        content = k.get("content", "")[:300]
        entry_tokens = _estimate_tokens(content)
        if total_tokens + entry_tokens > max_tokens:
            break
        selected.append(k)
        total_tokens += entry_tokens

    return selected
