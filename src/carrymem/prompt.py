"""Prompt building — construct AI system prompts from memories and knowledge.

Extracted from context.py for modularity.
"""

from typing import Any, Dict, List

from carrymem.format import _build_superseded_notes, format_knowledge_entry, format_memory_entry

PROMPT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "en": {
        "header": "You are an AI assistant with access to the user's memory and knowledge base.",
        "priority": [
            (
                "1. **User Memories** (highest priority) — Personal "
                "preferences, corrections, and decisions the user has shared."
            ),
            "2. **Knowledge Base** — Notes and documents from the user's personal vault.",
            (
                "3. **General Knowledge** (lowest priority) — Use only when "
                "memories and knowledge base don't cover the topic."
            ),
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
            "1. Answer with ONLY the specific fact or detail asked for "
            "— no explanations, no context, no full sentences unless "
            "necessary.",
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
        "answer_conflict_rule": (
            "3. If memories conflict, prefer [MANDATORY] over others, " "and non-[OUTDATED] over [OUTDATED]."
        ),
        "answer_preference_rule": (
            "8. For preference/recommendation questions (what does the user "
            "prefer, can you recommend, what would the user like), describe "
            "the user's preferences AND aversions based on their memories. "
            "Include what they prefer and what they might NOT prefer. Write a "
            "descriptive sentence, not just a keyword."
        ),
        "answer_temporal_rule": (
            "5. For temporal questions (which happened first, how many days "
            "between), use the dates in memories to determine order and "
            "calculate intervals."
        ),
        "answer_aggregation_rule": (
            "6. For counting questions (how many, total), carefully count ALL "
            "matching items across all memories before answering."
        ),
        "answer_cot_rule": (
            "7. For reasoning questions, think step-by-step internally, then " "output ONLY the final answer."
        ),
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
        "answer_conflict_rule": (
            "3. 記憶が矛盾する場合、[MANDATORY]を優先し、[OUTDATED]以外を" "[OUTDATED]より優先する。"
        ),
        "answer_preference_rule": (
            "8. 好み/推奨の質問（ユーザーの好み、推奨できるもの）について"
            "は、記憶に基づいてユーザーの好みと嫌いなことを説明する。"
            "好みと好まないものの両方を含める。キーワードだけでなく説明的"
            "な文で書く。"
        ),
        "answer_temporal_rule": "5. 時系列の質問（どちらが先、何日間隔）については、記憶内の日付を使用して順序を決定し間隔を計算する。",
        "answer_aggregation_rule": "6. カウントの質問（いくつ、合計）については、すべての記憶にわたって一致する項目を慎重に数えてから回答する。",
        "answer_fallback": "4. 記憶に答えが見つからない場合、次のように返答する：情報は利用できません。",
    },
}


def build_prompt(
    memories: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    language: str = "en",
    progressive: bool = False,
) -> str:
    """Build a system prompt from memories and knowledge entries.

    Args:
        memories: List of memory dicts to inject.
        knowledge: List of knowledge entry dicts.
        language: Language code ("en"/"zh"/"ja").
        progressive: v0.5.2 — enable progressive disclosure. When True, memories
            are rendered at bucket-specific depths: Mandatory=3 (full),
            Important=2 (short summary), Context=2 (short summary),
            Outdated=1 (keywords). When False (default), all memories render
            at depth=3 (v0.5.1 behavior).
    """
    t = PROMPT_TEMPLATES.get(language, PROMPT_TEMPLATES["en"])
    parts = [t["header"], "Follow these retrieval priorities when responding:"]
    parts.extend(t["priority"])

    if memories:
        active = [m for m in memories if not m.get("superseded_at")]
        outdated = [m for m in memories if m.get("superseded_at")]

        mandatory = [m for m in active if m.get("type") in ("correction", "decision", "user_preference")]
        important = [
            m
            for m in active
            if m.get("type") not in ("correction", "decision", "user_preference") and m.get("confidence", 0) >= 0.8
        ]
        optional = [m for m in active if m not in mandatory and m not in important]

        # v0.5.2: Bucket → depth mapping for progressive disclosure.
        # Mandatory always renders at full depth (never sacrifice key directives).
        depth_mandatory = 3
        depth_important = 2 if progressive else 3
        depth_context = 2 if progressive else 3
        depth_outdated = 1 if progressive else 3

        if mandatory:
            parts.append("\n### Mandatory (must follow)")
            for m in mandatory:
                parts.append(format_memory_entry(m, language, depth=depth_mandatory))

        if important:
            parts.append("\n### Important (high confidence)")
            for m in important:
                parts.append(format_memory_entry(m, language, depth=depth_important))

        if optional:
            parts.append("\n### Context (for reference)")
            for m in optional:
                parts.append(format_memory_entry(m, language, depth=depth_context))

        if outdated:
            parts.append("\n### Outdated (superseded, do NOT use)")
            for m in outdated[:3]:
                parts.append(format_memory_entry(m, language, depth=depth_outdated))

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


def _format_preference_line(m: Dict[str, Any]) -> str:
    """Format a single preference memory as a bullet line."""
    content = m.get("content", "")
    if m.get("auto_rule", "") == "avoid":
        return f"- Avoid: {content}"
    return f"- Preference: {content}"


def _build_preferences_section(pref_memories: List[Dict[str, Any]]) -> List[str]:
    """Build the '### User Preferences' section lines."""
    lines = ["### User Preferences"]
    for m in pref_memories:
        lines.append(_format_preference_line(m))
    return lines


def _apply_qa_preference_header(
    parts: List[str],
    t: Dict[str, Any],
    pref_memories: List[Dict[str, Any]],
) -> None:
    """Apply preference header, guidelines, and section to ``parts`` in-place."""
    pref_header = t.get("preference_qa_header", "")
    if pref_header:
        parts[0] = pref_header
    pref_guidelines = t.get("preference_qa_guidelines", [])
    if pref_guidelines:
        parts.extend(pref_guidelines)
    parts.extend(_build_preferences_section(pref_memories))


def _build_qa_short_path(
    t: Dict[str, Any],
    pref_memories: List[Dict[str, Any]],
    rules: str,
    question: str,
    include_question: bool,
) -> str:
    """Build the short QA prompt when only preference memories exist."""
    parts = [t.get("preference_qa_header", "") or t["header"]]
    pref_guidelines = t.get("preference_qa_guidelines", [])
    if pref_guidelines:
        parts.extend(pref_guidelines)
    parts.extend(_build_preferences_section(pref_memories))
    if rules:
        parts.append("")
        parts.append(rules)
    if include_question:
        parts.append("")
        parts.append(f"Question: {question}")
        parts.append("Answer:")
    return "\n".join(parts)


def _build_outdated_corrections_section(
    outdated: List[Dict[str, Any]],
    language: str,
) -> List[str]:
    """Build the '### Updated preferences' section from outdated corrections."""
    corrections = [m for m in outdated if m.get("type") in ("correction", "decision")]
    if not corrections:
        return []
    lines = ["### Updated preferences"]
    for m in corrections[:2]:
        lines.append(format_memory_entry(m, language))
    return lines


def _build_qa_standard_path(
    t: Dict[str, Any],
    pref_memories: List[Dict[str, Any]],
    non_pref_active: List[Dict[str, Any]],
    outdated: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    rules: str,
    question: str,
    include_question: bool,
    language: str,
) -> str:
    """Build the standard QA prompt with full context (non-short-path)."""
    parts = [t.get("preference_qa_header", "") or t["header"]]

    if pref_memories:
        _apply_qa_preference_header(parts, t, pref_memories)

    if non_pref_active:
        parts.append("")
        parts.append("### Additional context")
        for m in non_pref_active:
            parts.append(format_memory_entry(m, language))

    parts.append("")
    parts.extend(_build_outdated_corrections_section(outdated, language))

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


def build_qa_prompt(
    memories: List[Dict[str, Any]],
    knowledge: List[Dict[str, Any]],
    question: str,
    language: str = "en",
    include_question: bool = True,
    rules: str = "",
) -> str:
    """Build a QA prompt with relevant memories for answering a question."""
    t = PROMPT_TEMPLATES.get(language, PROMPT_TEMPLATES["en"])

    active = [m for m in memories if not m.get("superseded_at")]
    outdated = [m for m in memories if m.get("superseded_at")]
    pref_memories = [m for m in active if m.get("type") == "user_preference"]
    non_pref_active = [m for m in active if m.get("type") != "user_preference"]

    # Short path: only preferences, no other context
    if pref_memories and not non_pref_active and not knowledge and not outdated:
        return _build_qa_short_path(t, pref_memories, rules, question, include_question)

    return _build_qa_standard_path(
        t,
        pref_memories,
        non_pref_active,
        outdated,
        knowledge,
        rules,
        question,
        include_question,
        language,
    )
