"""Noise detection extracted from PatternAnalyzer (Group C).

Covers acknowledgment, chitchat, technical noise, question-only,
instruction, adversarial, and substantive-content checks.

The detector is stateless: shared state (registry, noise_filter_mode)
is owned by the PatternAnalyzer facade and passed to :meth:`is_noise`
as the ``analyzer`` argument.
"""

import re


class NoiseDetector:
    """Stateless noise detection helpers.

    Operates on shared state owned by the PatternAnalyzer instance
    (``registry``, ``noise_filter_mode``) which is passed in as the
    ``analyzer`` argument to :meth:`is_noise`.
    """

    def __init__(self):
        # Utility regexes (not part of the pattern groups)
        self._re_log_prefix = re.compile(r"^\[(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\]")
        self._re_log_timestamp = re.compile(r"^(DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)[:\s]")
        self._re_iso_date = re.compile(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}")
        self._re_short_msg = re.compile(r"[a-z]{3,}")

    def is_noise(self, message: str, analyzer) -> bool:
        """Detect if message is noise.

        Phase A Fix #1: Critical filtering to achieve TN > 0.
        Covers B1 (acknowledgment), B2 (chitchat), B3 (noise), B4 (question),
        B5 (instruction).
        """
        if not message or not message.strip():
            return True

        msg = message.strip()
        msg_lower = msg.lower()

        if self._is_acknowledgment(msg, msg_lower, analyzer):
            return True
        if self._is_chitchat(msg, msg_lower, analyzer):
            return True
        if self._is_technical_noise(msg, msg_lower, analyzer):
            return True
        if self._is_question_only(msg, msg_lower, analyzer):
            return True
        if self._is_instruction(msg, msg_lower, analyzer):
            return True
        if self._is_adversarial(msg_lower, analyzer):
            return True

        # Ultra-short messages (< 5 chars likely noise)
        if len(msg) < 5 and not self._re_short_msg.search(msg_lower):
            return True

        return False

    def _is_acknowledgment(self, msg: str, msg_lower: str, analyzer) -> bool:
        """B1: Detect acknowledgment patterns (EN/ZH/JA)."""
        reg = analyzer.registry
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

    def _is_chitchat(self, msg: str, msg_lower: str, analyzer) -> bool:
        """B2: Detect chitchat/social patterns (EN/ZH/JA)."""
        reg = analyzer.registry
        if reg.any_match_by_group("noise_chat", msg_lower, "en"):
            if analyzer.noise_filter_mode == "soft":
                return False
            return True
        if reg.any_match_by_group("noise_chat", msg, "zh"):
            return True
        if reg.any_match_by_group("noise_chat", msg, "ja"):
            return True
        return False

    def _is_technical_noise(self, msg: str, msg_lower: str, analyzer) -> bool:
        """B3/C5: Detect log prefixes, timestamps, and command noise."""
        if self._re_log_prefix.match(msg):
            return True
        if self._re_log_timestamp.match(msg):
            return True
        if self._re_iso_date.match(msg) and len(msg.split()) <= 4:
            return True

        reg = analyzer.registry
        # Command patterns
        if reg.any_match_by_group("noise_cmd", msg_lower, "en"):
            # If it also has fact indicators, skip
            if reg.any_match_by_group("noise_fact_indicator", msg_lower, "en"):
                pass  # has fact indicators, don't filter
            elif self._has_substantive_content(msg, msg_lower):
                pass  # has substantive content beyond command, don't filter
            else:
                return True
        return False

    def _is_question_only(self, msg: str, msg_lower: str, analyzer) -> bool:
        """B4: Detect pure question/query patterns (EN/ZH/JA)."""
        reg = analyzer.registry
        if reg.any_match_by_group("noise_question", msg_lower, "en") and len(msg) < 60:
            if analyzer.noise_filter_mode == "soft":
                return False
            return True
        if reg.any_match_by_group("noise_question", msg, "zh") and len(msg) < 60:
            return True
        if reg.any_match_by_group("noise_question", msg, "ja") and len(msg) < 60:
            return True
        return False

    def _is_instruction(self, msg: str, msg_lower: str, analyzer) -> bool:
        """B5: Detect instruction/command patterns."""
        reg = analyzer.registry
        if reg.any_match_by_group("noise_instruction", msg_lower, "en") and len(msg) < 60:
            if reg.any_match_by_group("noise_workflow", msg_lower, "en"):
                pass  # has workflow markers, don't filter
            elif self._has_substantive_content(msg, msg_lower):
                pass  # has substantive content beyond instruction, don't filter
            elif analyzer.noise_filter_mode == "soft":
                pass
            else:
                return True
        return False

    def _is_adversarial(self, msg_lower: str, analyzer) -> bool:
        """C5: Detect adversarial/anti-memory patterns."""
        return analyzer.registry.any_match_by_group("noise_adversarial", msg_lower, "en")  # type: ignore[no-any-return]

    def _has_substantive_content(self, msg: str, msg_lower: str) -> bool:
        """Check if message has substantive content beyond a command/instruction verb.

        Returns True if the message is likely a statement/fact rather than
        a pure command, based on technical content indicators. This prevents
        legitimate technical statements (e.g., "Docker for containerization",
        "Deploy to AWS") from being filtered as command/instruction noise.

        Args:
            msg: Original message (for case-sensitive checks like CamelCase).
            msg_lower: Lowercased message (for keyword checks).

        Returns:
            True if the message contains substantive technical content.
        """
        words = msg.split()
        if len(words) < 3:
            return False

        # CamelCase words (e.g., PostgreSQL, JavaScript)
        if re.search(r"\b[A-Z][a-z]+[A-Z]\w*\b", msg):
            return True

        # All-caps acronyms (2+ chars, e.g., AWS, CI, API)
        if re.search(r"\b[A-Z]{2,}\b", msg):
            return True

        # Underscore identifiers (e.g., recall_all, ns_alpha)
        if re.search(r"\b\w+_\w+\b", msg):
            return True

        # Technical keywords (lowercase check)
        tech_keywords = {
            "docker",
            "kubernetes",
            "agile",
            "methodology",
            "containerization",
            "microservices",
            "devops",
            "ci/cd",
            "continuous",
            "integration",
            "deployment",
            "monitoring",
            "observability",
            "architecture",
            "framework",
            "library",
            "runtime",
            "compiler",
            "database",
            "serverless",
            "cloud",
            "infrastructure",
            "pipeline",
            "orchestration",
            "prometheus",
            "grafana",
            "elasticsearch",
            "redis",
            "nginx",
            "python",
            "javascript",
            "typescript",
            "golang",
            "rust",
            "java",
        }
        if any(kw in msg_lower for kw in tech_keywords):
            return True

        # Prepositional phrases indicating statements ("X for Y", "X with Y")
        # with 4+ words suggest a statement, not a command
        if len(words) >= 4 and any(prep in msg_lower for prep in [" for ", " with ", " using "]):
            return True

        return False
