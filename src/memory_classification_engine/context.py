"""Smart context injection — select and rank memories for AI prompts.

v0.5.0: Context-aware memory selection with token budget control.

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
    context_tokens = _tokenize_text(context)
    memory_tokens = _tokenize_text(memory_content)
    if not context_tokens or not memory_tokens:
        return 0.0
    overlap = len(context_tokens & memory_tokens)
    union = len(context_tokens | memory_tokens)
    if union == 0:
        return 0.0
    return overlap / union


def select_memories(
    memories: List[Dict[str, Any]],
    context: Optional[str] = None,
    max_count: int = 10,
    max_tokens: int = 2000,
    importance_weight: float = 0.7,
    relevance_weight: float = 0.3,
) -> List[Dict[str, Any]]:
    if not memories:
        return []

    scored = []
    for m in memories:
        imp = m.get("importance_score", 0.0)
        rel = context_relevance(m.get("content", ""), context or "")
        final = imp * importance_weight + rel * relevance_weight
        scored.append((final, m))

    scored.sort(key=lambda x: x[0], reverse=True)

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


def format_memory_entry(m: Dict[str, Any], language: str = "en") -> str:
    labels = TYPE_LABELS.get(language, TYPE_LABELS["en"])
    label = labels.get(m.get("type", ""), m.get("type", "Info"))
    content = m.get("content", "")
    conf = m.get("confidence", 0)
    source = m.get("source_layer", "")
    src_tag = f" [{source}]" if source and source != "unknown" else ""
    return f"- [{label}{src_tag}] {content} (confidence: {conf:.0%})"


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
        parts.append("\n" + t["memories_header"])
        for m in memories:
            parts.append(format_memory_entry(m, language))

    if knowledge:
        parts.append("\n" + t["knowledge_header"])
        for k in knowledge:
            parts.append(format_knowledge_entry(k))

    parts.append("\n" + t["guidelines_header"])
    parts.extend(t["guidelines"])

    return "\n".join(parts)
