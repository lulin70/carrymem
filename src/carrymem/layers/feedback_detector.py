"""Execution feedback detection extracted from PatternAnalyzer (Group D).

Detects positive/negative feedback, tool errors, retry signals,
performance issues and context-position markers from an
``execution_context`` dict.
"""

from typing import Any, Dict, Optional


class FeedbackDetector:
    """Stateless execution feedback detection.

    Owns only the positive/negative feedback keyword sets. The
    PatternAnalyzer facade delegates execution-feedback detection
    here via :meth:`detect`.
    """

    def __init__(self):
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

    def detect(
        self, message: str, execution_context: Dict[str, Any]
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
