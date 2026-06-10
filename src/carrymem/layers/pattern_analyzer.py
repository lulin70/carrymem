import re
from typing import Any, Dict, List, Optional

from carrymem.patterns.definitions import build_registry
from carrymem.utils.language import language_manager
from carrymem.utils.logger import logger


class PatternAnalyzer:
    """Pattern-based memory analyzer.

    Uses a PatternRegistry for structured, language-aware pattern matching
    instead of a flat _RE_PATTERNS dictionary.
    """

    def __init__(self, noise_filter_mode: str = "strict"):
        """Initialize the pattern analyzer with pre-compiled regex patterns.

        Args:
            noise_filter_mode: "strict" (hard discard noise) or "soft" (downgrade confidence instead of discarding)
        """
        self.noise_filter_mode = noise_filter_mode
        self.message_history = []
        self.task_patterns = {}
        self.preference_patterns = {}
        self.correction_patterns = {}
        self.fact_patterns = {}
        self.relationship_patterns = {}
        self.location_patterns = {}

        # Build the pattern registry from all definition modules
        self.registry = build_registry()

        # Utility regexes (not part of the pattern groups)
        self._re_log_prefix = re.compile(r"^\[(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\]")
        self._re_log_timestamp = re.compile(r"^(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)[:\s]")
        self._re_iso_date = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}")
        self._re_short_msg = re.compile(r"[a-z]{3,}")

        # Pre-compiled keyword sets for O(1) lookup
        self._feedback_positive_keywords = {
            "对了",
            "正确",
            "好的",
            "成功",
            "完成",
            "不错",
            "great",
            "correct",
            "good",
            "success",
            "done",
        }
        self._feedback_negative_keywords = {
            "不对",
            "错误",
            "重做",
            "失败",
            "不行",
            "重新",
            "wrong",
            "error",
            "redo",
            "fail",
            "no",
            "again",
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Analyze a message for patterns.

        Args:
            message: The message to analyze.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.

        Returns:
            A list of detected patterns.
        """
        patterns = []

        if message is None:
            return patterns

        from carrymem.utils.confirmation import has_confirmation_context, is_confirmation, summarize_context

        confirmation_with_context = has_confirmation_context(context) and is_confirmation(message)

        if self._is_noise(message) and not confirmation_with_context:
            return patterns

        # Append to message history
        self.message_history.append(message)
        if len(self.message_history) > 10:
            self.message_history.pop(0)

        # Detect language (with fallback)
        try:
            language, _ = language_manager.detect_language(message)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Failed to detect language, defaulting to 'en': {e}")
            language = "en"

        # Run all detectors (Phase B Fix #4: task/decision BEFORE fact)
        if execution_context:
            feedback = self._detect_execution_feedback_pattern(message, execution_context, language)
            if feedback:
                feedback["language"] = language
                patterns.append(feedback)

        if has_confirmation_context(context) and is_confirmation(message):
            ai_reply = context.get("ai_reply", "")

            ai_summary = summarize_context(ai_reply)
            patterns.append(
                {
                    "memory_type": "decision",
                    "type": "decision",
                    "content": ai_summary,
                    "confidence": 0.85,
                    "tier": 3,
                    "source_layer": "pattern_analyzer",
                    "reasoning": "User confirmation of AI suggestion",
                    "suggested_action": "store",
                    "context_source": "ai_reply",
                    "original_user_message": message,
                    "language": language,
                }
            )
            return patterns

        for detector_name, detector_func in [
            ("correction", self._detect_correction_pattern),
            ("fact", self._detect_fact_pattern),
            ("decision", self._detect_decision_pattern),
            ("task", self._detect_task_pattern),
            ("preference", self._detect_preference_pattern),
            ("relationship", self._detect_relationship_pattern),
            ("location", self._detect_location_pattern),
            ("sentiment", self._detect_sentiment_pattern),
        ]:
            result = detector_func(message, language)
            if result:
                result["language"] = language
                patterns.append(result)

        return patterns

    # ------------------------------------------------------------------
    # Noise detection (uses registry)
    # ------------------------------------------------------------------

    def _is_acknowledgment(self, msg: str, msg_lower: str) -> bool:
        """B1: Detect acknowledgment patterns (EN/ZH/JA)."""
        reg = self.registry
        # EN patterns match on lowercase
        if reg.any_match_by_group("noise_ack", msg_lower, "en"):
            return True
        # Extended acknowledgment with context (e.g., "OK, let me check that")
        ext_group = reg.get_group("noise_ack")
        if ext_group:
            for p in ext_group.get_patterns("en"):
                if p.name == "ext_with_context" and p.match(msg_lower) and len(msg) < 40:
                    return True
        # ZH patterns match on original message
        if reg.any_match_by_group("noise_ack", msg, "zh"):
            return True
        # JA patterns match on original message
        if reg.any_match_by_group("noise_ack", msg, "ja"):
            return True
        return False

    def _is_chitchat(self, msg: str, msg_lower: str) -> bool:
        """B2: Detect chitchat/social patterns (EN/ZH/JA)."""
        reg = self.registry
        if reg.any_match_by_group("noise_chat", msg_lower, "en"):
            if self.noise_filter_mode == "soft":
                return False
            return True
        if reg.any_match_by_group("noise_chat", msg, "zh"):
            return True
        if reg.any_match_by_group("noise_chat", msg, "ja"):
            return True
        return False

    def _is_technical_noise(self, msg: str, msg_lower: str) -> bool:
        """B3/C5: Detect log prefixes, timestamps, and command noise."""
        if self._re_log_prefix.match(msg):
            return True
        if self._re_log_timestamp.match(msg):
            return True
        if self._re_iso_date.match(msg) and len(msg.split()) <= 4:
            return True

        reg = self.registry
        # Command patterns
        if reg.any_match_by_group("noise_cmd", msg_lower, "en"):
            # If it also has fact indicators, skip
            if reg.any_match_by_group("noise_fact_indicator", msg_lower, "en"):
                pass  # has fact indicators, don't filter
            else:
                return True
        return False

    def _is_question_only(self, msg: str, msg_lower: str) -> bool:
        """B4: Detect pure question/query patterns (EN/ZH/JA)."""
        reg = self.registry
        if reg.any_match_by_group("noise_question", msg_lower, "en") and len(msg) < 60:
            if self.noise_filter_mode == "soft":
                return False
            return True
        if reg.any_match_by_group("noise_question", msg, "zh") and len(msg) < 60:
            return True
        if reg.any_match_by_group("noise_question", msg, "ja") and len(msg) < 60:
            return True
        return False

    def _is_instruction(self, msg: str, msg_lower: str) -> bool:
        """B5: Detect instruction/command patterns."""
        reg = self.registry
        if reg.any_match_by_group("noise_instruction", msg_lower, "en") and len(msg) < 60:
            if reg.any_match_by_group("noise_workflow", msg_lower, "en"):
                pass  # has workflow markers, don't filter
            elif self.noise_filter_mode == "soft":
                pass
            else:
                return True
        return False

    def _is_adversarial(self, msg_lower: str) -> bool:
        """C5: Detect adversarial/anti-memory patterns."""
        return self.registry.any_match_by_group("noise_adversarial", msg_lower, "en")

    def _is_noise(self, message: str) -> bool:
        """Detect if message is noise.

        Phase A Fix #1: Critical filtering to achieve TN > 0.
        Covers B1 (acknowledgment), B2 (chitchat), B3 (noise), B4 (question), B5 (instruction).
        """
        if not message or not message.strip():
            return True

        msg = message.strip()
        msg_lower = msg.lower()

        if self._is_acknowledgment(msg, msg_lower):
            return True
        if self._is_chitchat(msg, msg_lower):
            return True
        if self._is_technical_noise(msg, msg_lower):
            return True
        if self._is_question_only(msg, msg_lower):
            return True
        if self._is_instruction(msg, msg_lower):
            return True
        if self._is_adversarial(msg_lower):
            return True

        # Ultra-short messages (< 5 chars likely noise)
        if len(msg) < 5 and not self._re_short_msg.search(msg_lower):
            return True

        return False

    # ------------------------------------------------------------------
    # Execution feedback detection (unchanged logic)
    # ------------------------------------------------------------------

    def _detect_execution_feedback_pattern(
        self, message: str, execution_context: Dict[str, Any], language: str
    ) -> Optional[Dict[str, Any]]:
        """Detect execution feedback patterns."""
        user_feedback = execution_context.get("user_feedback", "").lower()

        tool_error = execution_context.get("tool_error", False)
        retry_count = execution_context.get("retry_count", 0)
        execution_time = execution_context.get("execution_time", 0)

        context_position = execution_context.get("context_position", "")

        if self._feedback_positive_keywords & set(user_feedback.split()):
            return {
                "memory_type": "positive_feedback",
                "tier": 2,
                "content": f"Positive feedback: {message}",
                "confidence": 0.85,
                "source": "pattern:execution_feedback",
                "feedback_type": "positive",
                "execution_context": execution_context,
            }

        if self._feedback_negative_keywords & set(user_feedback.split()):
            return {
                "memory_type": "negative_feedback",
                "tier": 3,
                "content": f"Negative feedback: {message}",
                "confidence": 0.85,
                "source": "pattern:execution_feedback",
                "feedback_type": "negative",
                "execution_context": execution_context,
            }

        if tool_error:
            return {
                "memory_type": "tool_error",
                "tier": 3,
                "content": f"Tool error detected: {message}",
                "confidence": 0.90,
                "source": "pattern:execution_feedback",
                "feedback_type": "error",
                "execution_context": execution_context,
            }

        if retry_count > 0:
            return {
                "memory_type": "retry_needed",
                "tier": 3,
                "content": f"Retry needed: {message}",
                "confidence": 0.80,
                "source": "pattern:execution_feedback",
                "feedback_type": "retry",
                "execution_context": execution_context,
            }
        elif execution_time and execution_time > 30:
            return {
                "tier": 3,
                "content": f"Performance issue: {message} (executed in {execution_time}s)",
                "confidence": 0.75,
                "source": "pattern:execution_feedback",
                "feedback_type": "performance",
                "execution_context": execution_context,
            }

        if context_position == "correction_followup":
            return {
                "memory_type": "correction_followup",
                "tier": 3,
                "content": f"Correction followup: {message}",
                "confidence": 0.80,
                "source": "pattern:execution_feedback",
                "feedback_type": "context",
                "execution_context": execution_context,
            }

        if context_position == "confirmation_pending":
            return {
                "memory_type": "confirmation_pending",
                "tier": 2,
                "content": f"Confirmation pending: {message}",
                "confidence": 0.75,
                "source": "pattern:execution_feedback",
                "feedback_type": "context",
                "execution_context": execution_context,
            }

        return None

    # ------------------------------------------------------------------
    # Preference detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_preference_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect preference patterns.

        Phase B-3 Fix: Enhanced preference detection.
        Target: Recall from 33% to >=60%.
        """
        reg = self.registry
        message_lower = message.lower()

        # Strong preference patterns via registry
        if reg.any_match_by_group("preference_strong", message_lower, "en"):
            return {
                "memory_type": "user_preference",
                "tier": 2,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:preference_strong",
                "description": "Explicit preference pattern",
            }
        if language.startswith("zh") and reg.any_match_by_group("preference_strong", message, "zh"):
            return {
                "memory_type": "user_preference",
                "tier": 2,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:preference_strong",
                "description": "Explicit preference pattern",
            }
        if language == "ja" and reg.any_match_by_group("preference_strong", message, "ja"):
            return {
                "memory_type": "user_preference",
                "tier": 2,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:preference_strong",
                "description": "Explicit preference pattern",
            }

        # Keyword-based fallback
        preference_keywords = language_manager.get_keywords("user_preference", language)

        if language == "en":
            preference_keywords.extend(
                [
                    "prefer",
                    "preference",
                    "favorite",
                    "favourite",
                    "preferred",
                    "hate",
                    "dislike",
                    "adore",
                    "default",
                    "standard",
                    "convention",
                    "style",
                    "approach",
                    "choice",
                    "habit",
                    "practice",
                    "routine",
                    "ritual",
                    "rule",
                    "policy",
                    "always",
                    "never",
                    "usually",
                    "typically",
                    "normally",
                    "consistently",
                    "over",
                    "instead of",
                    "rather than",
                    "better than",
                    "worse than",
                    "i love",
                    "i like",
                    "i hate",
                    "i enjoy",
                    "i prefer",
                    "i always",
                    "i never",
                    "i usually",
                    "i typically",
                ]
            )
        elif language.startswith("zh"):
            preference_keywords.extend(
                [
                    "爱好",
                    "喜好",
                    "偏爱",
                    "最爱的",
                    "喜欢的",
                    "偏好",
                    "喜欢",
                    "爱",
                    "讨厌",
                    "不喜欢",
                    "习惯",
                    "通常",
                    "总是",
                    "从不",
                    "默认",
                    "标准",
                    "风格",
                    "选择",
                    "觉得",
                    "认为",
                    "看法",
                    "观点",
                    "意见",
                    "倾向于",
                    "倾向于用",
                    "习惯用",
                    "喜欢用",
                    "别用",
                    "不要用",
                    "避免",
                ]
            )
        elif language == "ja":
            preference_keywords.extend(
                [
                    "好き",
                    "嫌い",
                    "好む",
                    "欲しい",
                    "嫌う",
                    "好きです",
                    "好きではありません",
                    "いいです",
                    "ほしい",
                    "いつも",
                    "常に",
                    "通常",
                    "習慣",
                    "デフォルト",
                    "標準",
                    "スタイル",
                    "選択",
                    "好み",
                    "傾向",
                    "使いたい",
                    "使ってください",
                    "お願いします",
                    "避けて",
                    "使わず",
                ]
            )

        message_lower = message.lower()
        for keyword in preference_keywords:
            if keyword in message_lower:
                preference_content = message

                preference_hash = hash(preference_content)
                if preference_hash in self.preference_patterns:
                    self.preference_patterns[preference_hash] += 1
                    if self.preference_patterns[preference_hash] >= 2:
                        return {
                            "memory_type": "user_preference",
                            "tier": 2,
                            "content": preference_content,
                            "confidence": 0.8,
                            "source": "pattern:preference_repeat",
                            "description": "Repeated preference pattern",
                        }
                else:
                    self.preference_patterns[preference_hash] = 1
                    return {
                        "memory_type": "user_preference",
                        "tier": 2,
                        "content": preference_content,
                        "confidence": 0.6,
                        "source": "pattern:preference",
                        "description": "Preference pattern",
                    }

        return None

    # ------------------------------------------------------------------
    # Correction detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_correction_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect correction patterns.

        V4-02 Enhanced: Comprehensive correction detection with 3-tier strategy.
        Tier 1: Explicit correction markers (highest confidence)
        Tier 2: Structural patterns (grammar-based)
        Tier 3: Keyword-based (broadest coverage)
        """
        reg = self.registry
        message_lower = message.lower()

        # === TIER 1: Explicit correction markers (confidence 0.85) ===
        if reg.any_match_by_group("correction_explicit", message_lower, "en"):
            return self._build_correction_result(message, language, "pattern:correction_explicit", 0.85)
        if language.startswith("zh") and reg.any_match_by_group("correction_explicit", message, "zh"):
            return self._build_correction_result(message, language, "pattern:correction_explicit", 0.85)
        if language == "ja" and reg.any_match_by_group("correction_explicit", message, "ja"):
            return self._build_correction_result(message, language, "pattern:correction_explicit", 0.85)

        # === TIER 2: Structural patterns (confidence 0.75) ===
        if reg.any_match_by_group("correction_structural", message_lower, "en"):
            return self._build_correction_result(message, language, "pattern:correction_structural", 0.75)
        if language.startswith("zh") and reg.any_match_by_group("correction_structural", message, "zh"):
            return self._build_correction_result(message, language, "pattern:correction_structural", 0.75)
        if language == "ja" and reg.any_match_by_group("correction_structural", message, "ja"):
            return self._build_correction_result(message, language, "pattern:correction_structural", 0.75)

        # === TIER 3: Keyword-based detection (confidence 0.65) ===
        strong_correction_keywords = [
            "wrong",
            "incorrect",
            "mistake",
            "error",
            "fix it",
            "bug in",
            "change our",
            "change strategy",
            "different approach",
            "should be",
            "needs to be",
            "actually is",
            "supposed to be",
        ]
        if any(kw in message_lower for kw in strong_correction_keywords):
            return self._build_correction_result(message, language, "pattern:correction_keyword", 0.65)

        return None

    def _build_correction_result(self, message: str, language: str, source: str, confidence: float) -> Dict[str, Any]:
        """Build a standardized correction result."""
        correction_content = message

        if len(self.message_history) >= 2:
            correction_content = message

        correction_hash = hash(correction_content)
        if correction_hash in self.correction_patterns:
            self.correction_patterns[correction_hash] += 1
        else:
            self.correction_patterns[correction_hash] = 1

        return {
            "memory_type": "correction",
            "tier": 3,
            "content": correction_content,
            "confidence": confidence,
            "source": source,
            "description": "Correction pattern",
        }

    # ------------------------------------------------------------------
    # Fact detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_fact_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect fact declaration patterns.

        V4-04 Enhanced: Balanced 3-tier fact detection.
        Tier 1: Tech terms + structural patterns -> conf 0.8
        Tier 2: Quantifiable facts (numbers/dates/locations) -> conf 0.7
        Tier 3: General declarative statements -> conf 0.6
        """
        reg = self.registry
        if len(message.strip()) < 10:
            return None

        msg_lower = message.lower().strip()

        noise_indicators = [
            "ok",
            "yeah",
            "sure",
            "thanks",
            "nice",
            "cool",
            "great",
            "got it",
            "sounds good",
            "alright",
            "understood",
            "noted",
            "interesting",
            "hmm",
            "oh really",
            "pretty",
        ]
        if any(indicator in msg_lower for indicator in noise_indicators):
            return None

        if language.startswith("zh"):
            if reg.any_match_by_group("fact_zh", message, "zh"):
                return self._build_fact_result(message)
        elif language == "ja":
            if reg.any_match_by_group("fact_zh", message, "ja"):
                return self._build_fact_result(message)
        else:
            # === TIER 1: Strong technical facts (conf 0.8) ===
            has_tech = reg.any_match_by_group("fact_tech_term", msg_lower, "en")

            if has_tech:
                if reg.any_match_by_group("fact_tech_struct", msg_lower, "en"):
                    return self._build_fact_result(message, 0.8, "pattern:fact_tech")

                if has_tech:
                    return self._build_fact_result(message, 0.75, "pattern:fact_tech_fallback")

            # === TIER 2: Quantifiable facts (conf 0.7) ===
            has_quant = reg.any_match_by_group("fact_quantifiable", msg_lower, "en")

            if has_quant:
                if reg.any_match_by_group("fact_quant_struct", msg_lower, "en"):
                    return self._build_fact_result(message, 0.7, "pattern:fact_quant")

            # === TIER 3: General declarative (conf 0.6), only longer messages ===
            if len(msg_lower) > 25:
                if reg.any_match_by_group("fact_general", msg_lower, "en"):
                    return self._build_fact_result(message, 0.6, "pattern:fact_general")

        return None

    def _build_fact_result(self, message: str, confidence: float = 0.7, source: str = "pattern:fact") -> Dict[str, Any]:
        """Build a standardized fact result."""
        fact_content = message
        fact_hash = hash(fact_content)
        if fact_hash in self.fact_patterns:
            self.fact_patterns[fact_hash] += 1
            if self.fact_patterns[fact_hash] >= 2:
                return {
                    "memory_type": "fact_declaration",
                    "tier": 4,
                    "content": fact_content,
                    "confidence": 0.8,
                    "source": "pattern:fact_repeat",
                    "description": "Repeated fact pattern",
                }
        else:
            self.fact_patterns[fact_hash] = 1
        return {
            "memory_type": "fact_declaration",
            "tier": 4,
            "content": fact_content,
            "confidence": confidence,
            "source": source,
            "description": "Fact declaration pattern",
        }

    # ------------------------------------------------------------------
    # Relationship detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_relationship_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect relationship patterns.

        V4-05 Enhanced: 3-tier relationship detection.
        Tier 1: Structural role/dependency patterns (conf 0.8)
        Tier 2: Keyword-based (original, conf 0.7)
        """
        reg = self.registry
        msg_lower = message.lower().strip()

        min_len = 12
        if language.startswith("zh") or language == "ja":
            min_len = 6
        if len(msg_lower) < min_len:
            return None

        # === TIER 1: Structural patterns ===
        if not language.startswith("zh") and language != "ja":
            if reg.any_match_by_group("relationship_role", msg_lower, "en"):
                return self._build_rel_result(message)
            if reg.any_match_by_group("relationship_dep", msg_lower, "en"):
                return self._build_rel_result(message)

        if language.startswith("zh") and reg.any_match_by_group("relationship_role", message, "zh"):
            return self._build_rel_result(message)
        if language == "ja" and reg.any_match_by_group("relationship_role", message, "ja"):
            return self._build_rel_result(message)

        # === TIER 2: Keyword-based (original) ===
        relationship_keywords = language_manager.get_keywords("relationship", language)
        for keyword in relationship_keywords:
            if keyword in msg_lower:
                return self._build_rel_result(message)

        return None

    def _build_rel_result(self, message: str) -> Dict[str, Any]:
        """Build a standardized relationship result."""
        rel_hash = hash(message)
        if rel_hash in self.relationship_patterns:
            self.relationship_patterns[rel_hash] += 1
            if self.relationship_patterns[rel_hash] >= 2:
                return {
                    "memory_type": "relationship",
                    "tier": 4,
                    "content": message,
                    "confidence": 0.8,
                    "source": "pattern:relationship_repeat",
                    "description": "Repeated relationship pattern",
                }
        else:
            self.relationship_patterns[rel_hash] = 1
        return {
            "memory_type": "relationship",
            "tier": 4,
            "content": message,
            "confidence": 0.75,
            "source": "pattern:relationship",
            "description": "Relationship pattern",
        }

    # ------------------------------------------------------------------
    # Task detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_task_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect task patterns.

        Phase A Fix #3: Enhanced with technical action verbs and structured patterns.
        Target: F1 from 0% to >=50%.
        """
        reg = self.registry
        message_lower = message.lower()
        decision_guard = re.compile(
            r"\b(decided?|agreed?|chose|chosen|going\s+with|settled?\s+on|opted?\s+for|"
            r"we\s+('ll|will)\s+(use|adopt|go\s+with|move\s+to|switch\s+to))\b",
            re.IGNORECASE,
        )
        if decision_guard.search(message_lower):
            return None

        task_keywords = language_manager.get_keywords("task_pattern", language)

        if language == "en":
            task_keywords.extend(
                [
                    "implement",
                    "refactor",
                    "optimize",
                    "fix",
                    "debug",
                    "resolve",
                    "add",
                    "create",
                    "build",
                    "make",
                    "generate",
                    "develop",
                    "write",
                    "update",
                    "upgrade",
                    "migrate",
                    "integrate",
                    "deploy",
                    "release",
                    "plan",
                    "design",
                    "architect",
                    "research",
                    "investigate",
                    "analyze",
                    "review",
                    "test",
                    "validate",
                    "verify",
                    "check",
                    "monitor",
                    "need to",
                    "should",
                    "must",
                    "have to",
                    "require",
                    "going to",
                    "todo",
                    "task",
                    "action item",
                    "follow up",
                    "next step",
                ]
            )
        elif language.startswith("zh"):
            task_keywords.extend(
                [
                    "实现",
                    "重构",
                    "优化",
                    "修复",
                    "调试",
                    "解决",
                    "添加",
                    "创建",
                    "构建",
                    "制作",
                    "生成",
                    "开发",
                    "编写",
                    "更新",
                    "升级",
                    "迁移",
                    "集成",
                    "部署",
                    "发布",
                    "计划",
                    "设计",
                    "研究",
                    "调查",
                    "分析",
                    "审查",
                    "测试",
                    "验证",
                    "检查",
                    "监控",
                    "需要",
                    "应该",
                    "必须",
                    "要",
                    "待办",
                    "下一步",
                    "每次",
                    "每周",
                    "每天",
                    "定期",
                    "例行",
                    "站会",
                    "冒烟测试",
                    "代码审查",
                ]
            )
        elif language == "ja":
            task_keywords.extend(
                [
                    "実装",
                    "リファクタ",
                    "最適化",
                    "修正",
                    "デバッグ",
                    "解決",
                    "追加",
                    "作成",
                    "構築",
                    "生成",
                    "開発",
                    "記述",
                    "更新",
                    "アップグレード",
                    "移行",
                    "統合",
                    "デプロイ",
                    "リリース",
                    "計画",
                    "設計",
                    "研究",
                    "調査",
                    "分析",
                    "レビュー",
                    "テスト",
                    "検証",
                    "確認",
                    "監視",
                    "必要",
                    "すべき",
                    "必須",
                    "やるべき",
                    "次のステップ",
                    "毎回",
                    "毎週",
                    "毎日",
                    "定期的",
                    "ルーティン",
                    "スタンドアップ",
                    "スモークテスト",
                    "コードレビュー",
                ]
            )

        message_lower = message.lower()

        # 1. Structured task patterns
        if reg.any_match_by_group("task_structured", message_lower, "en"):
            return {
                "memory_type": "task_pattern",
                "tier": 3,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:task_structured",
                "description": "Structured task pattern",
            }

        # 2. Workflow rules & recurring patterns
        if reg.any_match_by_group("task_workflow", message_lower, "en"):
            return {
                "memory_type": "task_pattern",
                "tier": 3,
                "content": message,
                "confidence": 0.72,
                "source": "pattern:task_workflow",
                "description": "Workflow/recurring task pattern",
            }

        # 3. Personal habit patterns
        if reg.any_match_by_group("task_habit", message_lower, "en"):
            return {
                "memory_type": "task_pattern",
                "tier": 3,
                "content": message,
                "confidence": 0.70,
                "source": "pattern:task_habit",
                "description": "Personal habit/routine pattern",
            }

        # 4. Keyword-based fallback
        for keyword in task_keywords:
            if keyword in message_lower:
                task_content = message

                task_hash = hash(task_content)
                if task_hash in self.task_patterns:
                    self.task_patterns[task_hash] += 1
                    if self.task_patterns[task_hash] >= 2:
                        return {
                            "memory_type": "task_pattern",
                            "tier": 3,
                            "content": task_content,
                            "confidence": 0.8,
                            "source": "pattern:task_repeat",
                            "description": "Repeated task pattern",
                        }
                else:
                    self.task_patterns[task_hash] = 1
                    return {
                        "memory_type": "task_pattern",
                        "tier": 3,
                        "content": task_content,
                        "confidence": 0.6,
                        "source": "pattern:task",
                        "description": "Task pattern",
                    }

        return None

    # ------------------------------------------------------------------
    # Decision detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_decision_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect decision patterns.

        Phase B-2 Fix: Complete rewrite of decision detection.
        Target: Recall from 10% to >=50%.
        """
        reg = self.registry
        message_lower = message.lower()

        # Strong decision indicators via registry
        if reg.any_match_by_group("decision_strong", message_lower, "en"):
            return {
                "memory_type": "decision",
                "tier": 2,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:decision_strong",
                "description": "Explicit decision pattern",
            }
        if language.startswith("zh") and reg.any_match_by_group("decision_strong", message, "zh"):
            return {
                "memory_type": "decision",
                "tier": 2,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:decision_strong",
                "description": "Explicit decision pattern",
            }
        if language == "ja" and reg.any_match_by_group("decision_strong", message, "ja"):
            return {
                "memory_type": "decision",
                "tier": 2,
                "content": message,
                "confidence": 0.75,
                "source": "pattern:decision_strong",
                "description": "Explicit decision pattern",
            }

        # Weaker decision indicators (require context length > 15)
        weak_decision_keywords = [
            "let's use",
            "let's go with",
            "let's adopt",
            "let's choose",
            "we should use",
            "we could use",
            "we might use",
            "i think we should",
            "i propose we",
            "i suggest we",
            "best option is",
            "better to go",
            "makes sense to",
            "our approach",
            "the plan is",
            "the strategy is",
        ]

        if len(message.strip()) > 15:
            for keyword in weak_decision_keywords:
                if keyword in message_lower:
                    return {
                        "memory_type": "decision",
                        "tier": 3,
                        "content": message,
                        "confidence": 0.65,
                        "source": "pattern:decision_weak",
                        "description": "Weak decision pattern",
                    }

        # Legacy support (language-specific keywords - filtered for noise)
        decision_keywords = language_manager.get_keywords("decision", language)

        if language == "en":
            decision_keywords.extend(
                [
                    "decide",
                    "determine",
                    "conclude",
                    "resolve",
                    "finalize",
                    "preference",
                    "verdict",
                    "ruling",
                    "judgment",
                ]
            )
        elif language.startswith("zh"):
            decision_keywords.extend(
                [
                    "决定",
                    "选定",
                    "确定",
                    "采用",
                    "选用",
                    "敲定",
                    "方案",
                    "策略",
                    "架构",
                    "共识",
                    "一致同意",
                    "我们用",
                    "选了",
                    "就用",
                ]
            )
        elif language == "ja":
            decision_keywords.extend(
                [
                    "決める",
                    "決定",
                    "選ぶ",
                    "選択",
                    "確認",
                    "合意",
                    "使いましょう",
                    "行きましょう",
                    "に決めました",
                    "選びました",
                    "採用",
                    "採用しました",
                ]
            )

        message_lower = message.lower()
        for keyword in decision_keywords:
            if keyword in message_lower:
                if len(self.message_history) >= 2:
                    return {
                        "memory_type": "decision",
                        "tier": 3,
                        "content": message,
                        "confidence": 0.7,
                        "source": "pattern:decision",
                        "description": "Decision pattern",
                    }
                else:
                    return {
                        "memory_type": "decision",
                        "tier": 3,
                        "content": message,
                        "confidence": 0.6,
                        "source": "pattern:decision",
                        "description": "Decision pattern",
                    }

        return None

    # ------------------------------------------------------------------
    # Sentiment detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_sentiment_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect sentiment patterns.

        V4-05 Enhanced: Structural + keyword hybrid detection.
        Tier 1: Strong emotion patterns with intensifiers (conf 0.8)
        Tier 2: Keyword-based (narrowed per P0-B, conf 0.65)
        """
        reg = self.registry
        msg_lower = message.lower().strip()

        min_len = 10
        if language.startswith("zh") or language == "ja":
            min_len = 5
        if len(msg_lower) < min_len:
            return None

        # === TIER 1: Structural patterns ===
        if not language.startswith("zh") and language != "ja":
            if reg.any_match_by_group("sentiment_emotion", msg_lower, "en"):
                return self._build_sent_result(message, 0.8)

            # Intensifier + adjective patterns
            if any(
                intensifier in msg_lower
                for intensifier in [
                    "so ",
                    "really ",
                    "very ",
                    "super ",
                    "absolutely ",
                    "extremely ",
                ]
            ):
                if reg.any_match_by_group("sentiment_adj", msg_lower, "en"):
                    return self._build_sent_result(message, 0.75)

        # ZH sentiment structural patterns
        if language.startswith("zh"):
            if reg.any_match_by_group("sentiment_zh", message, "zh"):
                return self._build_sent_result(message, 0.8)

        # JA sentiment structural patterns
        if language == "ja":
            if reg.any_match_by_group("sentiment_ja", message, "ja"):
                return self._build_sent_result(message, 0.8)

        # === TIER 2: Keyword-based (narrowed per P0-B) ===
        sentiment_keywords = language_manager.get_keywords("sentiment_marker", language)
        if language == "en":
            sentiment_keywords.extend(
                [
                    "love",
                    "hate",
                    "dislike",
                    "enjoy",
                    "happy",
                    "sad",
                    "angry",
                    "excited",
                    "frustrated",
                    "upset",
                    "annoyed",
                    "bored",
                    "tired",
                    "exhausted",
                    "inspired",
                    "proud",
                    "confident",
                    "worried",
                    "scared",
                    "relaxed",
                    "loathe",
                    "detest",
                    "disappoint",
                    "delighted",
                    "thrilled",
                    "depressed",
                    "irritated",
                    "panic",
                    "frighten",
                    "motivated",
                    "too slow",
                    "too fast",
                    "too hard",
                    "too easy",
                    "painful",
                    "annoying",
                    "clunky",
                    "laggy",
                    "awesome",
                    "fantastic",
                    "wonderful",
                    "amazing",
                    "terrible",
                    "horrible",
                    "awful",
                    "brilliant",
                    "superb",
                    "outstanding",
                ]
            )
        elif language.startswith("zh"):
            sentiment_keywords.extend(
                [
                    "棒",
                    "很棒",
                    "真好",
                    "太好了",
                    "优秀",
                    "惊人",
                    "可怕",
                    "糟糕",
                    "恶心",
                    "恐怖",
                    "喜欢",
                    "讨厌",
                    "烦",
                    "崩溃",
                    "心碎",
                    "开心",
                    "难过",
                    "生气",
                    "激动",
                    "不满",
                    "超赞",
                    "无语",
                    "无语了",
                    "太赞了",
                    "绝了",
                    "牛",
                    "牛逼",
                    "累",
                    "疲惫",
                    "无聊",
                    "焦虑",
                    "担心",
                    "害怕",
                    "自豪",
                    "自信",
                    "放松",
                    "失望",
                    "郁闷",
                    "不爽",
                    "太慢",
                    "太烦",
                    "很担心",
                    "棒极了",
                ]
            )
        elif language == "ja":
            sentiment_keywords.extend(
                [
                    "嬉しい",
                    "悲しい",
                    "怒っている",
                    "興奮",
                    "失望",
                    "満足",
                    "素晴らしい",
                    "最高",
                    "ひどい",
                    "最悪",
                    "好き",
                    "嫌い",
                    "楽しい",
                    "面白い",
                    "つまらない",
                    "感動",
                    "驚き",
                    "不安",
                    "心配",
                    "怖い",
                    "イライラ",
                    "ストレス",
                    "疲れた",
                    "うんざり",
                    "すごい",
                    "やばい",
                    "素敵",
                    "残念",
                    "遅い",
                    "不便",
                    "迷惑",
                ]
            )

        for keyword in sentiment_keywords:
            if keyword in msg_lower:
                # P0-B: Fact exclusion - if text contains factual markers, skip sentiment
                if reg.any_match_by_group("sentiment_fact_exclusion", msg_lower, "en"):
                    continue
                return self._build_sent_result(message, 0.65)

        return None

    def _build_sent_result(self, message: str, confidence: float = 0.7) -> Dict[str, Any]:
        """Build a standardized sentiment result."""
        return {
            "memory_type": "sentiment_marker",
            "tier": 3,
            "content": message,
            "confidence": confidence,
            "source": "pattern:sentiment",
            "description": "Sentiment pattern",
        }

    # ------------------------------------------------------------------
    # Location detection (uses registry)
    # ------------------------------------------------------------------

    def _detect_location_pattern(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Detect location patterns.

        V4-08: Restricted to pure location info, not facts containing locations.
        """
        reg = self.registry
        msg_lower = message.lower()

        # V4-08: Skip if this looks like a fact/decision/task
        if reg.any_match_by_group("location_fact_exclusion", msg_lower, "en"):
            return None

        # Location keywords
        location_keywords = {
            "en": ["at", "in", "on", "located", "place", "location", "address"],
            "zh-cn": ["在", "位于", "地址", "地方", "位置"],
        }

        keywords = location_keywords.get(language, location_keywords.get("en", []))

        for keyword in keywords:
            if keyword in msg_lower:
                common_locations = {
                    "en": [
                        "park",
                        "station",
                        "airport",
                        "hotel",
                        "restaurant",
                        "office",
                        "building",
                        "street",
                        "avenue",
                        "road",
                    ],
                    "zh-cn": [
                        "公园",
                        "车站",
                        "机场",
                        "酒店",
                        "餐厅",
                        "办公室",
                        "大楼",
                        "街道",
                        "大道",
                        "路",
                    ],
                }

                location_terms = common_locations.get(language, common_locations.get("en", []))
                for term in location_terms:
                    if term in msg_lower:
                        location_content = message
                        location_hash = hash(location_content)
                        if location_hash in self.location_patterns:
                            self.location_patterns[location_hash] += 1
                        else:
                            self.location_patterns[location_hash] = 1

                        return {
                            "memory_type": "location",
                            "tier": 3,
                            "content": location_content,
                            "confidence": 0.7,
                            "source": "pattern:location",
                            "description": "Location pattern",
                        }

        return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def clear_history(self):
        """Clear the message history."""
        self.message_history = []
        self.task_patterns = {}
        self.preference_patterns = {}
        self.correction_patterns = {}
        self.fact_patterns = {}
        self.relationship_patterns = {}
        self.location_patterns = {}
