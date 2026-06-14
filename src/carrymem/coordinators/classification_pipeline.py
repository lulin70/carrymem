"""Classification pipeline for coordinating classification layers."""

import re
from typing import Any, Dict, List, Optional

from carrymem.layers.pattern_analyzer import PatternAnalyzer
from carrymem.layers.rule_matcher import RuleMatcher
from carrymem.layers.semantic_classifier import SemanticClassifier
from carrymem.utils.confirmation import is_confirmation, summarize_context
from carrymem.utils.logger import logger


class ClassificationPipeline:
    """Coordinates the classification layers in order."""

    MIN_DEFAULT_CONFIDENCE = 0.6
    MIN_SENTIMENT_DEFAULT_CONFIDENCE = 0.7
    ASSISTANT_PREFIXES = ("[assistant said]", "[ai said]", "[bot said]")

    def __init__(self, config: Dict[str, Any], noise_filter_mode: str = "strict"):
        """Initialize classification pipeline.

        Args:
            config: Configuration manager instance.
            noise_filter_mode: "strict" or "soft" - controls how aggressively noise is filtered.
        """
        self.config = config

        rules = config.get_rules().get("rules", [])
        self.rule_matcher = RuleMatcher(rules)
        self.pattern_analyzer = PatternAnalyzer(noise_filter_mode=noise_filter_mode)

        self.semantic_classifier = SemanticClassifier(self.config)

        self._filter_counts = {"noise": 0, "low_info_assistant": 0, "fail_closed": 0}

        if noise_filter_mode == "soft":
            self.MIN_DEFAULT_CONFIDENCE = 0.5
            self.MIN_SENTIMENT_DEFAULT_CONFIDENCE = 0.4

    def classify(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Classify a message through the pipeline.

        Args:
            message: The message to classify.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.

        Returns:
            List of classification matches.
        """
        rule_matches = self.rule_matcher.match(message, context, execution_context)

        if rule_matches:
            logger.debug("Rule matching found %d matches", len(rule_matches))
            return rule_matches

        pattern_matches = self.pattern_analyzer.analyze(message, context, execution_context)

        if pattern_matches:
            logger.debug("Pattern analysis found %d matches", len(pattern_matches))
            pattern_matches = self._resolve_type_priority(pattern_matches)
            return pattern_matches

        semantic_matches = self.semantic_classifier.classify(message, context, execution_context)

        if semantic_matches:
            logger.debug("Semantic classification found %d matches", len(semantic_matches))
            return semantic_matches

        logger.debug("No classification matches found")
        return []

    def classify_with_defaults(
        self,
        message: str,
        language: str,
        context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Classify a message with default fallback.

        Phase A Fix #1 (Critical): Noise filtering at pipeline level to prevent
        _get_default_classification() from generating false positives on noise.
        P0-C: Filter low-information assistant replies.
        P0-D: Fail-closed default - unclassifiable content is NOT stored.

        Args:
            message: The message to classify.
            language: The detected language code.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.

        Returns:
            List of classification matches, with default if no matches found.
        """
        # Phase A Fix #1: Pipeline-level noise filtering (P0-3d)
        # This prevents _get_default_classification from matching noise messages
        ai_reply = None
        if context and isinstance(context, dict):
            ai_reply = context.get("ai_reply", "")

        is_confirmation_with_context = bool(ai_reply and is_confirmation(message))

        if self.pattern_analyzer._is_noise(message) and not is_confirmation_with_context:
            self._filter_counts["noise"] += 1
            if self._filter_counts["noise"] % 100 == 1:
                logger.info("Noise filter: %d messages filtered total", self._filter_counts['noise'])
            return []

        # P0-C: Filter low-information assistant replies
        # Check both explicit role context and "[Assistant said]" prefix convention
        is_assistant_msg = False
        if context and isinstance(context, dict):
            role = context.get("role", "")
            if role == "assistant":
                is_assistant_msg = True
        if message and isinstance(message, str):
            msg_stripped_lower = message.strip().lower()
            if any(msg_stripped_lower.startswith(prefix) for prefix in self.ASSISTANT_PREFIXES):
                is_assistant_msg = True
        if is_assistant_msg:
            if self._is_low_info_assistant_reply(message):
                self._filter_counts["low_info_assistant"] += 1
                if self._filter_counts["low_info_assistant"] % 100 == 1:
                    logger.info(
                        f"Low-info assistant filter: "
                        f"{self._filter_counts['low_info_assistant']} messages filtered total"
                    )
                return []

        matches = self.classify(message, context, execution_context)

        # P0-D: Fail-closed default - if no classification matches, do NOT store
        # Previously: unclassifiable content defaulted to fact_declaration(0.5)
        # Now: return empty list (fail-closed behavior)
        if not matches:
            default_match = self._get_default_classification(message, language)
            if default_match:
                if default_match.get("confidence", 0) < self.MIN_DEFAULT_CONFIDENCE:
                    self._filter_counts["fail_closed"] += 1
                    if self._filter_counts["fail_closed"] % 100 == 1:
                        logger.info(
                            f"Fail-closed filter: "
                            f"{self._filter_counts['fail_closed']} low-confidence defaults filtered total"
                        )
                    if self.pattern_analyzer.noise_filter_mode == "soft":
                        default_match["confidence"] = self.MIN_DEFAULT_CONFIDENCE
                        default_match["source"] = "default:soft_fallback"
                        matches = [default_match]
                    else:
                        return []
                if (
                    default_match.get("memory_type") == "sentiment_marker"
                    and default_match.get("confidence", 0) < self.MIN_SENTIMENT_DEFAULT_CONFIDENCE
                ):
                    self._filter_counts["fail_closed"] += 1
                    if self.pattern_analyzer.noise_filter_mode == "soft":
                        default_match["confidence"] = self.MIN_SENTIMENT_DEFAULT_CONFIDENCE
                        default_match["source"] = "default:soft_fallback"
                        matches = [default_match]
                    else:
                        return []
                if not matches:
                    matches = [default_match]
            elif self.pattern_analyzer.noise_filter_mode == "soft":
                matches = [
                    {
                        "memory_type": "fact_declaration",
                        "tier": 2,
                        "content": message,
                        "confidence": 0.3,
                        "source": "default:soft_catchall",
                        "description": "Soft-mode catchall: store everything",
                    }
                ]

        if matches and context and isinstance(context, dict):
            ai_reply = context.get("ai_reply", "")
            if ai_reply and is_confirmation(message):
                for match in matches:
                    match_type = match.get("memory_type") or match.get("type", "")
                    if match_type in ("decision", "correction"):
                        if not match.get("context_source"):
                            ai_summary = summarize_context(ai_reply)
                            original_content = match.get("content", "")
                            if original_content and len(original_content) > 5:
                                match["content"] = f"{original_content}: {ai_summary}"
                            else:
                                match["content"] = f"Confirmed: {ai_summary}"
                            match["context_source"] = "ai_reply"
                            match["original_user_message"] = message

        return matches

    @staticmethod
    def _is_low_info_assistant_reply(message: str) -> bool:
        """P0-C: Check if an assistant reply has low information density.

        Filters:
        1. Generic confirmation replies ("I understand", "Got it", "Sure")
        2. Short replies (<10 words) without factual content
        3. Replies without information markers (code, URL, number, CamelCase)
        4. Conversational/emotional replies without factual substance

        Args:
            message: The assistant reply message.

        Returns:
            True if the reply should be filtered (low info), False if it may contain useful info.
        """
        if not message or not message.strip():
            return True

        msg = message.strip()
        for prefix in ClassificationPipeline.ASSISTANT_PREFIXES:
            if msg.lower().startswith(prefix):
                msg = msg[len(prefix) :].strip()
                break
        if msg.startswith("]"):
            msg = msg[1:].strip()
        msg_lower = msg.lower()

        # 1. Generic confirmation patterns
        generic_confirmations = [
            r"^(i\s+)?(understand|see|got\s+it|gotcha|sure|ok|okay"
            r"|alright|right|exactly|absolutely|correct|indeed|of\s+course"
            r"|certainly|definitely|surely)\b",
            r"^(that\'?s?\s+)?(right|correct|true|accurate|makes?\s+sense" r"|sounds?\s+good|looks?\s+good)",
            r"^(yes|yeah|yep|no\s+problem|not\s+at\s+all|not\s+really)",
            r"^(let\s+me\s+)?(help|assist|check|look|try|work\s+on)\s+(you|that|this|it)",
            r"^(here\'?s?\s+)?(what|i\s+can|the\s+result|the\s+answer)",
        ]
        for pat in generic_confirmations:
            if re.match(pat, msg_lower):
                return True

        # 2. Check for factual information markers (strong signal to KEEP)
        factual_markers = [
            r"\b\d+(\.\d+)+\b",  # Version numbers (3.11, 14.2)
            r"\bv?\d+(\.\d+)+\b",  # Version with v prefix
            r"https?://",  # URLs
            r"`[^`]+`",  # Code snippets
            r"\b[A-Z][a-z]+[A-Z]\w*\b",  # CamelCase terms (PostgreSQL, etc.)
            r"\b(api|sdk|http|sql|python|java|docker|redis|nginx|server|database|endpoint|port|config)\b",
            r"\$\d+",  # Dollar amounts
            r"\b\d+\s*(%|mb|gb|tb|ms|sec|min|hour|day|week|month|year|employees?|users?|members?|people|teams?)\b",
            r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b",  # Dates
            r"\b\d{4}\b",  # Years
        ]
        has_factual = any(re.search(marker, msg) for marker in factual_markers)

        # 3. Short replies without factual content
        word_count = len(msg.split())
        if word_count < 10 and not has_factual:
            return True

        # 4. Conversational/emotional replies without factual substance
        # These are long enough to pass the word count check but contain no facts
        conversational_patterns = [
            r"^(i\s+)?(think|believe|feel|agree|love|hate|enjoy|appreciate)\s+(that|this|it|you|we)\b",
            r"^(that\'?s?\s+)?(great|wonderful|amazing|fantastic|terrible|awful|beautiful|nice|cool|interesting)\b",
            r"\b(i\'?m\s+)?(glad|happy|sorry|excited|worried|proud)\s+(to|that|about|for)\b",
            r"\b(you\'?re?\s+welcome|good\s+luck|keep\s+up|well\s+done|great\s+job)\b",
            r"\b(i\s+)?(hope|wish|suggest|recommend)\s+(you|that|this|we)\b",
            r"\b(active\s+listening|communication|teamwork|collaboration)\b",
        ]
        is_conversational = any(re.search(pat, msg_lower) for pat in conversational_patterns)

        if is_conversational and not has_factual:
            return True

        return False

    @staticmethod
    def _resolve_type_priority(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Resolve type priority when multiple types match the same message.

        Priority: correction > decision > preference > task > fact > others

        Args:
            matches: List of pattern matches.

        Returns:
            Resolved list with highest-priority type first.
        """
        if len(matches) <= 1:
            return matches

        type_priority = {
            "correction": 1,
            "decision": 2,
            "user_preference": 3,
            "task_pattern": 4,
            "fact_declaration": 5,
            "sentiment_marker": 6,
            "relationship": 7,
            "location": 8,
        }

        def sort_key(m):
            return type_priority.get(m.get("memory_type", ""), 99)

        matches.sort(key=sort_key)
        return matches

    def _get_default_classification(self, message: str, language: str) -> Optional[Dict[str, Any]]:
        """Get default classification for a message when no other matches found.

        V4-03 Fix: Added quality gates to reduce FP from 18 to <10.
        - Minimum length requirement (skip ultra-short messages)
        - Chitchat/blacklist keyword filtering
        - Content substance check (require meaningful keywords)

        Args:
            message: The message to classify.
            language: The detected language code.

        Returns:
            A default classification match if found, None otherwise.
        """
        from carrymem.utils.language import language_manager

        # Handle None message - P0-D: fail-closed, do not store
        if message is None:
            return None

        message_lower = message.lower()
        msg_stripped = message.strip()

        # === V4-03 Quality Gate 1: Minimum length (ultra-short = likely noise) ===
        if len(msg_stripped) < 8:
            return None

        # === V4-03 Quality Gate 2: Chitchat/Noise blacklist ===
        chitchat_blacklist = [
            # Weather/small talk
            "sunny",
            "rainy",
            "weather",
            "beautiful day",
            "pretty",
            # Acknowledgments that slipped through
            "sounds good",
            "oh really",
            "interesting",
            "hmm",
            "cool",
            # Filler responses
            "see you",
            "okay",
            "ok then",
            "alright",
            "sure thing",
            # Emojis/short reactions
            "😎",
            "😊",
            "👍",
            "🎉",
            "❤️",
            "💪",
            "🔥",
            # Question-like but not real questions
            "really?",
            "right?",
            "yes?",
            "no?",
        ]
        if any(black in message_lower for black in chitchat_blacklist):
            return None

        # === V4-03 Quality Gate 3: Require substantive content ===
        # Messages with only 1-2 words are likely noise/chitchat
        word_count = len(msg_stripped.split())
        if word_count <= 2 and len(msg_stripped) < 20:
            return None

        preference_keywords = language_manager.get_keywords("user_preference", language)
        correction_keywords = language_manager.get_keywords("correction", language)
        fact_keywords = language_manager.get_keywords("fact_declaration", language)
        decision_keywords = language_manager.get_keywords("decision", language)
        relationship_keywords = language_manager.get_keywords("relationship", language)
        task_keywords = language_manager.get_keywords("task_pattern", language)
        sentiment_keywords = language_manager.get_keywords("sentiment_marker", language)

        if any(keyword in message_lower for keyword in preference_keywords):
            return {
                "memory_type": "user_preference",
                "tier": 2,
                "content": message,
                "confidence": 0.9,
                "source": "default:preference",
                "description": "User preference detected",
                "language": language,
            }
        elif any(keyword in message_lower for keyword in correction_keywords):
            return {
                "memory_type": "correction",
                "tier": 3,
                "content": message,
                "confidence": 0.8,
                "source": "default:correction",
                "description": "Correction detected",
                "language": language,
            }
        elif any(keyword in message_lower for keyword in fact_keywords):
            return {
                "memory_type": "fact_declaration",
                "tier": 3,
                "content": message,
                "confidence": 0.7,
                "source": "default:fact",
                "description": "Fact declaration detected",
                "language": language,
            }
        elif any(keyword in message_lower for keyword in decision_keywords):
            return {
                "memory_type": "decision",
                "tier": 2,
                "content": message,
                "confidence": 0.8,
                "source": "default:decision",
                "description": "Decision detected",
                "language": language,
            }
        elif any(keyword in message_lower for keyword in relationship_keywords):
            return {
                "memory_type": "relationship",
                "tier": 3,
                "content": message,
                "confidence": 0.7,
                "source": "default:relationship",
                "description": "Relationship information detected",
                "language": language,
            }
        elif any(keyword in message_lower for keyword in task_keywords):
            return {
                "memory_type": "task_pattern",
                "tier": 2,
                "content": message,
                "confidence": 0.8,
                "source": "default:task",
                "description": "Task pattern detected",
                "language": language,
            }
        elif any(keyword in message_lower for keyword in sentiment_keywords):
            return {
                "memory_type": "sentiment_marker",
                "tier": 3,
                "content": message,
                "confidence": 0.7,
                "source": "default:sentiment",
                "description": "Sentiment detected",
                "language": language,
            }
        else:
            # P0-D: Fail-closed - unclassifiable content is NOT stored as fact_declaration
            # Previously: returned fact_declaration with confidence 0.5 (fail-open)
            # Now: return None to prevent noise storage
            return None
