"""Pattern-based memory analyzer (thin facade).

Originally a 1547-line God Class, now a backward-compatible facade that
delegates to three focused modules:

* :class:`carrymem.layers.noise_detector.NoiseDetector` - noise detection
* :class:`carrymem.layers.feedback_detector.FeedbackDetector` - execution feedback
* :class:`carrymem.layers.memory_pattern_detectors.MemoryPatternDetectors` - the
  8 memory-type detectors (preference, correction, fact, relationship, task,
  decision, sentiment, location)

The facade owns the shared mutable state (``message_history``, the per-type
pattern caches, ``registry``, ``noise_filter_mode``) and passes itself to the
stateless detectors during delegation. ``PatternAnalyzer``, ``analyze``,
``_is_noise``, ``clear_history`` and all public attributes remain unchanged.
"""

from typing import Any, Dict, List, Optional

from carrymem.layers.feedback_detector import FeedbackDetector
from carrymem.layers.memory_pattern_detectors import MemoryPatternDetectors
from carrymem.layers.noise_detector import NoiseDetector
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
        self.message_history: List[str] = []
        self.task_patterns: Dict[str, Any] = {}
        self.preference_patterns: Dict[str, Any] = {}
        self.correction_patterns: Dict[str, Any] = {}
        self.fact_patterns: Dict[str, Any] = {}
        self.relationship_patterns: Dict[str, Any] = {}
        self.location_patterns: Dict[str, Any] = {}

        # Build the pattern registry from all definition modules
        self.registry = build_registry()

        # Stateless detector collaborators
        self._noise_detector = NoiseDetector()
        self._feedback_detector = FeedbackDetector()
        self._memory_detectors = MemoryPatternDetectors()

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
        patterns: List[Dict[str, Any]] = []

        if message is None:
            return patterns  # type: ignore[unreachable]

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
            logger.warning("Failed to detect language, defaulting to 'en': %s", e)
            language = "en"

        # Run all detectors (Phase B Fix #4: task/decision BEFORE fact)
        if execution_context:
            feedback = self._feedback_detector.detect(message, execution_context)
            if feedback:
                feedback["language"] = language
                patterns.append(feedback)

        if has_confirmation_context(context) and is_confirmation(message):
            ai_reply = context.get("ai_reply", "")  # type: ignore[union-attr]

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

        for detector_func in [
            self._memory_detectors.detect_correction,
            self._memory_detectors.detect_fact,
            self._memory_detectors.detect_decision,
            self._memory_detectors.detect_task,
            self._memory_detectors.detect_preference,
            self._memory_detectors.detect_relationship,
            self._memory_detectors.detect_location,
            self._memory_detectors.detect_sentiment,
        ]:
            result = detector_func(message, language, self)
            if result:
                result["language"] = language
                patterns.append(result)

        return patterns

    # ------------------------------------------------------------------
    # Noise detection (delegates to NoiseDetector)
    # ------------------------------------------------------------------

    def _is_noise(self, message: str) -> bool:
        """Detect if message is noise.

        Phase A Fix #1: Critical filtering to achieve TN > 0.
        Covers B1 (acknowledgment), B2 (chitchat), B3 (noise), B4 (question), B5 (instruction).
        """
        return self._noise_detector.is_noise(message, self)

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
