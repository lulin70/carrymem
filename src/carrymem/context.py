"""Smart context injection — select and rank memories for AI prompts.

Context-aware memory selection with token budget control.

Algorithm:
1. Retrieve candidate memories (by context query or global ranking)
2. Score each memory: final_score = importance_score * 0.7 + context_relevance * 0.3
3. Sort by final_score DESC
4. Select top N within token budget
5. Format for AI system prompt injection
"""

import re
from typing import Any, Dict, List, Optional


def _estimate_tokens(text: str) -> int:
    cjk_count = sum(
        1 for c in text
        if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' or '\u30a0' <= c <= '\u30ff'
    )
    other_count = len(text) - cjk_count
    return max(1, cjk_count + other_count // 4)


def _tokenize_text(text: str) -> set:
    words = set(re.findall(r'[a-zA-Z]{2,}', text.lower()))
    cjk_chars = set()
    for c in text:
        if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff':
            cjk_chars.add(c)
    return words | cjk_chars


def context_relevance(memory_content: str, context: str) -> float:
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
        r'\b(first|last|before|after|earlier|later|previous|next)\b',
        r'\bhow many days\b',
        r'\bhow (long|much time)\b',
        r'\bwhen\b',
        r'\b(days?|weeks?|months?|years?) (ago|before|after|between|passed)\b',
    ]
    for p in temporal_patterns:
        if re.search(p, text.lower()):
            return True
    return False


def _has_preference_signal(text: str) -> bool:
    pref_patterns = [
        r'\bprefer\b',
        r'\bpreference\b',
        r'\bfavorite\b',
        r'\bfavourite\b',
        r'\bdislike\b',
        r'\brecommend\b',
        r'\blike\b',
        r'\blove\b',
        r'\bhate\b',
        r'\bavoid\b',
        r'\bwant\b',
        r'\bneed\b',
        r'\bcare about\b',
        r'\bimportant to\b',
        r'\bcan\'t stand\b',
        r'\bnot a fan\b',
        r'\bnot interested\b',
        r'\baverse\b',
        r'\baversion\b',
        r'\bstrongly\b',
        r'\balways\b',
        r'\bnever\b',
        r'\bbest\b',
        r'\bworst\b',
        r'\bsuggest\b',
        r'\badvice\b',
        r'\bopinion\b',
    ]
    for p in pref_patterns:
        if re.search(p, text.lower()):
            return True
    return False


def _has_aggregation_signal(text: str) -> bool:
    agg_patterns = [
        r'\bhow many\b',
        r'\bhow much\b',
        r'\btotal\b',
        r'\ball\b',
        r'\bevery\b',
        r'\bcount\b',
        r'\blist\b',
    ]
    for p in agg_patterns:
        if re.search(p, text.lower()):
            return True
    return False


# --- Preference scope inference ---
# Maps preference content keywords to scope domains.
# Aligned with PrefEval 20 topics for benchmark consistency.

SCOPE_VOCABULARY = {
    "education": {
        "en": ["learn", "study", "school", "university", "course", "education",
               "textbook", "exam", "homework", "lecture", "teach", "student",
               "academic", "reading", "writing", "math", "science",
               # Cross-domain: learning also happens at work and via programming
               "project-based", "tutorial", "resource", "practice", "skill",
               "training", "workshop", "lesson", "curriculum",
               # Cross-domain: educational resources have payment models
               "subscription", "free", "paid", "online"],
        "zh": ["学习", "学校", "课程", "教育", "考试", "读书", "大学", "培训",
               "教程", "资源", "练习", "技能", "课程表", "订阅", "免费", "付费", "在线"],
    },
    "entertainment": {
        "en": ["game", "gaming", "movie", "film", "show", "tv", "music", "book",
               "novel", "sport", "football", "basketball", "soccer", "hobby",
               "play", "watch", "stream", "concert", "band"],
        "zh": ["游戏", "电影", "音乐", "书", "运动", "足球", "篮球", "娱乐"],
    },
    "lifestyle": {
        "en": ["diet", "food", "cooking", "recipe", "exercise", "fitness", "gym",
               "health", "medical", "doctor", "beauty", "skincare", "wellness",
               "yoga", "meditation", "sleep", "nutrition", "vegetarian", "vegan",
               "organic", "allergy", "allergic", "meal", "dinner", "lunch",
               "breakfast", "snack", "dessert"],
        "zh": ["饮食", "食物", "烹饪", "健身", "运动", "健康", "美容", "护肤",
               "素食", "过敏", "蔬菜", "水果", "早餐", "午餐", "晚餐"],
    },
    "shopping": {
        "en": ["buy", "shop", "purchase", "brand", "fashion", "clothing", "car",
               "vehicle", "motor", "home", "furniture", "appliance", "deal",
               "price", "discount", "product", "technology", "gadget", "device",
               # Cross-domain: subscription appears in education/entertainment too
               "subscription", "free", "paid", "premium", "afford", "budget"],
        "zh": ["购物", "买", "品牌", "时尚", "服装", "汽车", "家居", "电子产品",
               "订阅", "免费", "付费", "预算"],
    },
    "travel": {
        "en": ["travel", "trip", "vacation", "hotel", "flight", "restaurant",
               "dining", "transport", "airline", "destination", "tour", "visit",
               "abroad", "luggage", "booking", "resort", "boutique", "inn",
               "hostel", "airbnb", "cruise", "sightseeing", "backpack"],
        "zh": ["旅行", "旅游", "酒店", "餐厅", "航班", "出行", "度假", "旅馆", "民宿"],
    },
    "work": {
        "en": ["work", "job", "career", "office", "remote", "meeting", "project",
               "team", "manager", "company", "professional", "business", "email",
               "deadline", "productivity", "commute",
               # Cross-domain: project-based learning, professional development
               "project-based", "collaboration", "task", "schedule"],
        "zh": ["工作", "职业", "办公室", "远程", "项目", "团队", "公司", "上班",
               "协作", "任务", "排期"],
    },
    "pet": {
        "en": ["pet", "dog", "cat", "animal", "veterinary", "breed", "puppy",
               "kitten", "fish", "bird", "rabbit", "hamster"],
        "zh": ["宠物", "狗", "猫", "动物", "养宠"],
    },
    "programming": {
        "en": ["python", "java", "javascript", "code", "coding", "programming",
               "software", "developer", "database", "api", "framework", "library",
               "debug", "deploy", "algorithm", "react", "typescript", "rust",
               "golang", "sql", "postgresql", "mysql", "redis", "docker",
               "server", "web server", "backend", "frontend", "compiler",
               "function", "class", "method", "variable", "loop", "array",
               "language", "ide", "editor", "terminal", "command"],
        "zh": ["编程", "代码", "开发", "程序", "软件", "数据库", "框架"],
    },
}


def infer_scopes(text: str) -> List[str]:
    """Infer scope domains from text content using keyword matching.

    Returns a list of matching scope names (e.g., ["education", "programming"]).
    Returns empty list if no scope matches (meaning the preference is general/unscoped).
    """
    if not text or not isinstance(text, str):
        return []

    text_lower = text.lower()
    matched_scopes = []

    for scope, lang_keywords in SCOPE_VOCABULARY.items():
        for lang, keywords in lang_keywords.items():
            for kw in keywords:
                # Use word boundary for English, substring for CJK
                if lang == "en":
                    if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                        matched_scopes.append(scope)
                        break
                else:
                    if kw in text_lower:
                        matched_scopes.append(scope)
                        break
            else:
                continue
            break  # Already matched this scope

    return matched_scopes


def preference_matches_scope(preference: Dict[str, Any], question: str,
                             core_confidence_threshold: float = 0.9) -> bool:
    """Check if a preference should be injected for the given question.

    Rules:
    1. Core preferences (confidence >= threshold) always match (safety net).
    2. If preference has explicit scope in metadata, check overlap with question scopes.
    3. If no explicit scope, infer from preference content and check overlap.
    4. If neither scope nor content inference yields a match, allow injection
       (conservative: don't filter out what we can't classify).
    5. If preference has scope but question doesn't, check if question content
       is ambiguous (could belong to preference's scope).
    """
    # Core preferences always pass
    if preference.get("confidence", 0) >= core_confidence_threshold:
        return True

    # Get preference scopes
    metadata = preference.get("metadata", {})
    if isinstance(metadata, str):
        try:
            import json
            metadata = json.loads(metadata)
        except (ValueError, TypeError):
            metadata = {}

    pref_scopes = metadata.get("scopes", [])
    if not pref_scopes:
        pref_scopes = infer_scopes(
            preference.get("raw_text", "") or preference.get("content", "")
        )

    # No scopes inferred = general preference, allow
    if not pref_scopes:
        return True

    # Check if question matches any preference scope
    question_scopes = infer_scopes(question or "")
    if not question_scopes or not question:
        # Can't determine question scope — allow (conservative)
        return True

    # Overlap check
    if set(pref_scopes) & set(question_scopes):
        return True

    # No overlap but preference scope keywords appear in question
    for scope in pref_scopes:
        if scope in SCOPE_VOCABULARY:
            for lang, keywords in SCOPE_VOCABULARY[scope].items():
                for kw in keywords:
                    if lang == "en":
                        import re
                        if re.search(r'\b' + re.escape(kw) + r'\b', question.lower()):
                            return True
                    else:
                        if kw in question.lower():
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

    selected_indices = []
    selected_tokens_list = []
    remaining = list(range(len(scored)))

    max_score = max(s for s, _ in scored) if scored else 1.0
    if max_score <= 0:
        max_score = 1.0

    for _ in range(max_count):
        best_mmr = -float('inf')
        best_idx = -1

        for idx in remaining:
            score, mem = scored[idx]
            norm_score = score / max_score

            mem_tokens = _tokenize_text(
                (mem.get("raw_text", "") or "") + " " + (mem.get("content", "") or "")
            )

            if selected_tokens_list:
                max_sim = max(
                    _jaccard_sim(mem_tokens, s) for s in selected_tokens_list
                )
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
        _, best_mem = scored[best_idx]
        selected_tokens_list.append(
            _tokenize_text(
                (best_mem.get("raw_text", "") or "") + " " + (best_mem.get("content", "") or "")
            )
        )

    return [scored[i] for i in selected_indices]


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
    if not memories:
        return []

    is_temporal = context and _has_temporal_signal(context)
    is_aggregation = context and _has_aggregation_signal(context)

    TYPE_CONFIDENCE_FLOOR = {
        "user_preference": 0.4,
        "sentiment_marker": 0.5,
    }

    # Type-based selection boost: behavioral constraints must survive budget pressure
    TYPE_SELECTION_BOOST = {
        "correction": 0.5,      # Must-always-include (e.g., "Do NOT use tabs")
        "decision": 0.4,        # Strong preference to include (e.g., "Project uses React")
        "user_preference": 0.3, # Already partially handled by positional sort
        "fact_declaration": 0.0,
        "session_summary": -0.1, # Penalize unless highly relevant
        "sentiment_marker": -0.2, # Rarely critical for context injection
    }

    scored = []
    for m in memories:
        conf = m.get("confidence", 0.0)
        mtype = m.get("type", "")
        type_floor = TYPE_CONFIDENCE_FLOOR.get(mtype, min_confidence)
        if conf < type_floor:
            continue

        imp = m.get("importance_score", 0.0)
        rel = context_relevance(m.get("content", ""), context or "")
        final = imp * importance_weight + rel * relevance_weight

        # Apply type-based selection boost
        type_boost = TYPE_SELECTION_BOOST.get(mtype, 0.0)
        final += type_boost

        if is_temporal:
            content_lower = (m.get("content", "") or "").lower()
            raw_lower = (m.get("raw_text", "") or "").lower()
            combined = content_lower + " " + raw_lower
            has_date = bool(re.search(
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}',
                combined,
            )) or bool(re.search(r'\d{4}-\d{2}-\d{2}', combined))
            has_short_date = bool(re.search(
                r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b',
                combined,
            ))
            if has_date or has_short_date:
                final += 0.4
            date_count = len(re.findall(
                r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\.?\s+\d{1,2}',
                combined,
            )) + len(re.findall(r'\d{4}-\d{2}-\d{2}', combined)) + len(re.findall(
                r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b', combined,
            ))
            if date_count >= 2:
                final += 0.15
            if m.get("type") in ("fact_declaration", "decision"):
                final += 0.1

        if is_aggregation:
            final += 0.3

        scored.append((final, m))

    scored.sort(key=lambda x: x[0], reverse=True)

    if is_aggregation and len(scored) > max_count:
        seen_sessions = set()
        session_represented = []
        remaining = []
        for score, m in scored:
            meta = m.get("metadata", {})
            sid = meta.get("session_id", "") if isinstance(meta, dict) else ""
            if sid and sid not in seen_sessions:
                session_represented.append((score, m))
                seen_sessions.add(sid)
            else:
                remaining.append((score, m))
        scored = session_represented + remaining

    if use_mmr and context and len(scored) > 1:
        query_tokens = _tokenize_text(context)
        select_count = min(len(scored), max_count)
        scored = _mmr_select(scored, query_tokens, select_count, mmr_lambda)

    # Mandatory types always come first, then preferences, then others
    mandatory_types = {"correction", "decision"}
    mandatory_scored = [(s, m) for s, m in scored if m.get("type") in mandatory_types]
    pref_scored = [(s, m) for s, m in scored if m.get("type") == "user_preference"]
    other_scored = [(s, m) for s, m in scored if m.get("type") not in mandatory_types and m.get("type") != "user_preference"]
    scored = mandatory_scored + pref_scored + other_scored

    selected = []
    total_tokens = 0
    for score, m in scored:
        if len(selected) >= max_count:
            break
        entry_tokens = _estimate_tokens(m.get("content", ""))
        if total_tokens + entry_tokens > max_tokens:
            break
        m_copy = dict(m)
        m_copy["_selection_score"] = round(score, 6)
        m_copy["_context_relevance"] = round(
            context_relevance(m.get("content", ""), context or ""), 6
        )
        selected.append(m_copy)
        total_tokens += entry_tokens

    return selected


def select_knowledge(
    knowledge: List[Dict[str, Any]],
    context: Optional[str] = None,
    max_count: int = 5,
    max_tokens: int = 1000,
) -> List[Dict[str, Any]]:
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

    selected = []
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


TYPE_LABELS = {
    "en": {
        "user_preference": "Preference",
        "correction": "Correction",
        "decision": "Decision",
        "fact_declaration": "Fact",
        "relationship": "Relationship",
        "task_pattern": "Pattern",
        "sentiment_marker": "Sentiment",
    },
    "zh": {
        "user_preference": "偏好",
        "correction": "纠正",
        "decision": "决策",
        "fact_declaration": "事实",
        "relationship": "关系",
        "task_pattern": "模式",
        "sentiment_marker": "情感",
    },
    "ja": {
        "user_preference": "好み",
        "correction": "訂正",
        "decision": "決定",
        "fact_declaration": "事実",
        "relationship": "関係",
        "task_pattern": "パターン",
        "sentiment_marker": "感情",
    },
}


def _extract_event_dates(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s*\d{4})?)\b',
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}(?:,?\s*\d{4})?)\b',
        r'\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b',
    ]
    found = []
    for p in patterns:
        for match in re.finditer(p, text, re.IGNORECASE):
            date_str = match.group(1)
            if date_str not in found:
                found.append(date_str)
    return ", ".join(found) if found else ""


def format_memory_entry(m: Dict[str, Any], language: str = "en") -> str:
    labels = TYPE_LABELS.get(language, TYPE_LABELS["en"])
    label = labels.get(m.get("type", ""), m.get("type", "Info"))
    content = m.get("raw_text", "") or m.get("content", "")
    superseded_at = m.get("superseded_at")
    supersedes = m.get("superseded")
    mtype = m.get("type", "")
    auto_rule = m.get("auto_rule", "")
    confidence = m.get("confidence", 0)

    time_tag = ""
    event_dates = _extract_event_dates(content)
    if event_dates:
        time_tag = f" (event: {event_dates})"
    else:
        created = m.get("created_at", "")
        if created:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(created)
                time_tag = f" ({dt.strftime('%Y-%m-%d')})"
            except (ValueError, TypeError):
                pass

    if superseded_at:
        return f"- NOTE: \"{content[:80]}\" is outdated{time_tag}"

    if mtype == "user_preference" and auto_rule == "avoid":
        return f"- [IMPORTANT] The user does NOT want: {content}"
    if mtype == "user_preference" and auto_rule == "prefer":
        return f"- [IMPORTANT] The user prefers: {content}"
    if mtype == "user_preference":
        return f"- [IMPORTANT] The user prefers: {content}"
    if mtype == "correction":
        return f"- Do NOT repeat: {content} — the user has corrected this before{time_tag}"
    if mtype == "decision":
        return f"- Always follow: {content} — this is the user's confirmed decision{time_tag}"
    if mtype == "session_summary":
        return f"- Based on previous conversations: {content}{time_tag}"

    tag = ""
    if mtype in ("correction", "decision"):
        tag = " [MANDATORY]"
    elif mtype == "user_preference" and confidence >= 0.8:
        tag = " [IMPORTANT]"

    return f"- [{label}{tag}] {content}{time_tag}"


def _build_superseded_notes(memories: List[Dict[str, Any]], language: str = "en") -> List[str]:
    notes = []
    seen_pairs = set()
    for m in memories:
        supersedes = m.get("supersedes")
        if not supersedes:
            continue
        old_content = m.get("raw_text", "") or m.get("content", "")
        for new_m in memories:
            if new_m.get("storage_key") == supersedes or new_m.get("id") == supersedes:
                new_content = new_m.get("raw_text", "") or new_m.get("content", "")
                pair_key = (m.get("storage_key", ""), new_m.get("storage_key", ""))
                if pair_key in seen_pairs:
                    break
                seen_pairs.add(pair_key)
                if language == "zh":
                    notes.append(f"- 更新：\"{old_content[:60]}\" → \"{new_content[:60]}\"")
                else:
                    notes.append(f"- Updated: \"{old_content[:60]}\" → \"{new_content[:60]}\"")
                break
    return notes


def format_knowledge_entry(k: Dict[str, Any]) -> str:
    title = k.get("title", "Untitled")
    content = k.get("content", "")[:200]
    tags = k.get("tags", [])
    tag_str = f" [{', '.join(tags[:3])}]" if tags else ""
    return f"- {title}{tag_str}: {content}"


PROMPT_TEMPLATES = {
    "en": {
        "header": "You are an AI assistant with access to the user's memory and knowledge base.",
        "priority": [
            "1. **User Memories** (highest priority) — Personal preferences, corrections, and decisions the user has shared.",
            "2. **Knowledge Base** — Notes and documents from the user's personal vault.",
            "3. **General Knowledge** (lowest priority) — Use only when memories and knowledge base don't cover the topic.",
        ],
        "memories_header": "## User Memories",
        "knowledge_header": "## Knowledge Base",
        "guidelines_header": "## Guidelines",
        "guidelines": [
            "- Always respect user preferences and corrections, even if they contradict general best practices.",
            "- If a user previously corrected something, the correction overrides the original.",
            "- Reference specific memories when relevant: 'Based on your preference for...'",
        ],
        "answer_guidelines": [
            "When answering questions about the user based on their memories:",
            "1. Answer with ONLY the specific fact or detail asked for — no explanations, no context, no full sentences unless necessary.",
            "2. Match the brevity of these examples:",
        ],
        "answer_examples": [
            ("What car does the user drive?", "Toyota Camry"),
            ("When did the user start their new job?", "March 2024"),
            ("What was the first issue with the car?", "GPS system not functioning correctly"),
            ("Which event happened first, the workshop or the webinar?", "The webinar"),
            ("How many days passed between the two events?", "7 days"),
            ("How many projects has the user led?", "2"),
        ],
        "answer_conflict_rule": "3. If memories conflict, prefer [MANDATORY] over others, and non-[OUTDATED] over [OUTDATED].",
        "answer_preference_rule": "8. For preference/recommendation questions (what does the user prefer, can you recommend, what would the user like), describe the user's preferences AND aversions based on their memories. Include what they prefer and what they might NOT prefer. Write a descriptive sentence, not just a keyword.",
        "answer_temporal_rule": "5. For temporal questions (which happened first, how many days between), use the dates in memories to determine order and calculate intervals.",
        "answer_aggregation_rule": "6. For counting questions (how many, total), carefully count ALL matching items across all memories before answering.",
        "answer_cot_rule": "7. For reasoning questions, think step-by-step internally, then output ONLY the final answer.",
        "answer_fallback": "4. If you cannot find the answer in the memories, respond with: Information not available.",
        "preference_qa_header": "You are a helpful assistant.",
        "preference_qa_guidelines": [],
    },
    "zh": {
        "header": "你是一个拥有用户记忆和知识库访问权限的AI助手。",
        "priority": [
            "1. **用户记忆**（最高优先级）— 用户的个人偏好、纠正和决策。",
            "2. **知识库** — 来自用户个人笔记库的文档。",
            "3. **通用知识**（最低优先级）— 仅在记忆和知识库未覆盖时使用。",
        ],
        "memories_header": "## 用户记忆",
        "knowledge_header": "## 知识库",
        "guidelines_header": "## 指导原则",
        "guidelines": [
            "- 始终尊重用户的偏好和纠正，即使与通用最佳实践矛盾。",
            "- 如果用户之前纠正过某事，纠正内容覆盖原始内容。",
            "- 相关时引用具体记忆：'根据你对...的偏好...'",
        ],
        "answer_guidelines": [
            "根据记忆回答关于用户的问题时：",
            "1. 只回答被问到的具体事实或细节——不要解释、不要上下文、除非必要不要用完整句子。",
            "2. 参照以下示例的简洁程度：",
        ],
        "answer_examples": [
            ("用户开什么车？", "丰田凯美瑞"),
            ("用户什么时候开始新工作的？", "2024年3月"),
            ("车的第一个问题是什么？", "GPS系统无法正常工作"),
            ("哪个事件先发生，研讨会还是网络研讨会？", "网络研讨会"),
            ("两个事件之间过了多少天？", "7天"),
            ("用户领导了多少个项目？", "2"),
        ],
        "answer_conflict_rule": "3. 如果记忆冲突，优先使用[MANDATORY]，非[OUTDATED]优先于[OUTDATED]。",
        "answer_preference_rule": "8. 对于偏好/推荐问题（用户偏好什么、能否推荐、用户可能喜欢什么），根据记忆描述用户的偏好和回避。包括用户偏好什么和可能不偏好什么。写描述性句子，不要只写关键词。",
        "answer_temporal_rule": "5. 对于时序问题（哪个先发生、之间隔了多少天），使用记忆中的日期来确定顺序和计算间隔。",
        "answer_aggregation_rule": "6. 对于计数问题（多少个、总计），仔细统计所有记忆中的匹配项后再回答。",
        "answer_fallback": "4. 如果在记忆中找不到答案，回复：信息不可用。",
        "preference_qa_header": "你是一个有帮助的助手。",
        "preference_qa_guidelines": [],
    },
    "ja": {
        "header": "あなたはユーザーの記憶とナレッジベースにアクセスできるAIアシスタントです。",
        "priority": [
            "1. **ユーザー記憶**（最優先）— ユーザーの個人的な好み、訂正、決定。",
            "2. **ナレッジベース** — ユーザーの個人vaultのドキュメント。",
            "3. **一般知識**（最低優先）— 記憶とナレッジベースでカバーされていない場合のみ使用。",
        ],
        "memories_header": "## ユーザー記憶",
        "knowledge_header": "## ナレッジベース",
        "guidelines_header": "## ガイドライン",
        "guidelines": [
            "- 一般的なベストプラクティスと矛盾しても、ユーザーの好みと訂正を常に尊重してください。",
            "- ユーザーが以前何かを訂正した場合、訂正が元の内容を上書きします。",
            "- 関連する場合は具体的な記憶を参照：'...の好みに基づいて...'",
        ],
        "answer_guidelines": [
            "記憶に基づいてユーザーについての質問に答える場合：",
            "1. 尋ねられた具体的な事実や詳細のみを答える——説明なし、文脈なし、必要な場合を除き完全な文は避ける。",
            "2. 以下の例の簡潔さに合わせる：",
        ],
        "answer_examples": [
            ("ユーザーはどんな車に乗っていますか？", "トヨタ カムリ"),
            ("ユーザーはいつ新しい仕事を始めましたか？", "2024年3月"),
            ("車の最初の問題は何でしたか？", "GPSシステムが正常に機能しない"),
            ("どちらのイベントが先に発生しましたか、ワークショップ还是ウェビナー？", "ウェビナー"),
            ("2つのイベントの間は何日ありましたか？", "7日"),
            ("ユーザーはいくつのプロジェクトを主導しましたか？", "2"),
        ],
        "answer_conflict_rule": "3. 記憶が矛盾する場合、[MANDATORY]を優先し、[OUTDATED]以外を[OUTDATED]より優先する。",
        "answer_preference_rule": "8. 好み/推奨の質問（ユーザーの好み、推奨できるもの）については、記憶に基づいてユーザーの好みと嫌いなことを説明する。好みと好まないものの両方を含める。キーワードだけでなく説明的な文で書く。",
        "answer_temporal_rule": "5. 時系列の質問（どちらが先、何日間隔）については、記憶内の日付を使用して順序を決定し間隔を計算する。",
        "answer_aggregation_rule": "6. カウントの質問（いくつ、合計）については、すべての記憶にわたって一致する項目を慎重に数えてから回答する。",
        "answer_fallback": "4. 記憶に答えが見つからない場合、次のように返答する：情報は利用できません。",
    },
}


def build_prompt(
    memories: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    language: str = "en",
) -> str:
    t = PROMPT_TEMPLATES.get(language, PROMPT_TEMPLATES["en"])
    parts = [t["header"], "Follow these retrieval priorities when responding:"]
    parts.extend(t["priority"])

    if memories:
        active = [m for m in memories if not m.get("superseded_at")]
        outdated = [m for m in memories if m.get("superseded_at")]

        mandatory = [m for m in active if m.get("type") in ("correction", "decision", "user_preference")]
        important = [m for m in active if m.get("type") not in ("correction", "decision", "user_preference") and m.get("confidence", 0) >= 0.8]
        optional = [m for m in active if m not in mandatory and m not in important]

        if mandatory:
            parts.append("\n### Mandatory (must follow)")
            for m in mandatory:
                parts.append(format_memory_entry(m, language))

        if important:
            parts.append("\n### Important (high confidence)")
            for m in important:
                parts.append(format_memory_entry(m, language))

        if optional:
            parts.append("\n### Context (for reference)")
            for m in optional:
                parts.append(format_memory_entry(m, language))

        if outdated:
            parts.append("\n### Outdated (superseded, do NOT use)")
            for m in outdated[:3]:
                parts.append(format_memory_entry(m, language))

        update_notes = _build_superseded_notes(memories, language)
        if update_notes:
            if language == "zh":
                parts.append("\n### 知识更新记录")
            else:
                parts.append("\n### Knowledge Updates")
            parts.extend(update_notes)

    if knowledge:
        parts.append("\n" + t["knowledge_header"])
        for k in knowledge:
            parts.append(format_knowledge_entry(k))

    parts.append("\n" + t["guidelines_header"])
    parts.extend(t["guidelines"])

    return "\n".join(parts)


def build_qa_prompt(
    memories: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    question: str,
    language: str = "en",
    include_question: bool = True,
    rules: str = "",
) -> str:
    t = PROMPT_TEMPLATES.get(language, PROMPT_TEMPLATES["en"])

    active = [m for m in memories if not m.get("superseded_at")]
    outdated = [m for m in memories if m.get("superseded_at")]
    pref_memories = [m for m in active if m.get("type") == "user_preference"]
    non_pref_active = [m for m in active if m.get("type") != "user_preference"]

    if pref_memories and not non_pref_active and not knowledge and not outdated:
        # Fast Path: only preferences, no other memories.
        # Scope filtering is NOT applied here because in Fast Path all preferences
        # are relevant (there's nothing else to compete with for prompt space).
        parts = [t.get("preference_qa_header", "") or t["header"]]
        pref_guidelines = t.get("preference_qa_guidelines", [])
        if pref_guidelines:
            parts.extend(pref_guidelines)
        parts.append("### User Preferences")
        for m in pref_memories:
            content = m.get("content", "")
            auto_rule = m.get("auto_rule", "")
            if auto_rule == "avoid":
                parts.append(f"- Avoid: {content}")
            else:
                parts.append(f"- Preference: {content}")
        parts.append("You must respect these preferences in your response.")
        if rules:
            parts.append("")
            parts.append(rules)
        if include_question:
            parts.append("")
            parts.append(f"Question: {question}")
            parts.append("Answer:")
        return "\n".join(parts)

    has_preference = bool(pref_memories)

    parts = [t.get("preference_qa_header", "") or t["header"]]

    if has_preference:
        pref_header = t.get("preference_qa_header", "")
        if pref_header:
            parts[0] = pref_header
        pref_guidelines = t.get("preference_qa_guidelines", [])
        if pref_guidelines:
            parts.extend(pref_guidelines)

        if pref_memories:
            parts.append("### User Preferences")
            for m in pref_memories:
                content = m.get("content", "")
                auto_rule = m.get("auto_rule", "")
                if auto_rule == "avoid":
                    parts.append(f"- Avoid: {content}")
                else:
                    parts.append(f"- Preference: {content}")
            parts.append("You must respect these preferences in your response.")

        if non_pref_active:
            parts.append("")
            parts.append("### Additional context")
            for m in non_pref_active:
                parts.append(format_memory_entry(m, language))
    else:
        # No preferences — just list memories without memory-query instructions
        # (answer_guidelines/answer_fallback/temporal/aggregation are for memory queries, not QA)
        if non_pref_active:
            parts.append("")
            parts.append("### Additional context")
            for m in non_pref_active:
                parts.append(format_memory_entry(m, language))

    parts.append("")

    if outdated:
        # Only show outdated if there are corrections (user explicitly changed preference)
        corrections = [m for m in outdated if m.get("type") in ("correction", "decision")]
        if corrections:
            parts.append("### Updated preferences")
            for m in corrections[:2]:
                parts.append(format_memory_entry(m, language))

        # Knowledge updates omitted for QA prompts (not needed for answering questions)

    if knowledge:
        parts.append("")
        parts.append(t["knowledge_header"])
        for k in knowledge:
            parts.append(format_knowledge_entry(k))

    if rules:
        parts.append("")
        parts.append(rules)

    if include_question:
        parts.append("")
        parts.append(f"Question: {question}")
        parts.append("Always provide a specific, helpful answer to the question above.")
        parts.append("Answer:")

    return "\n".join(parts)
