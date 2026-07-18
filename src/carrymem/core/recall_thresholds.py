"""Confidence threshold constants for memory recall decisions.

These thresholds determine the suggested action for a memory based on its
confidence score:

- Above STORE: memory should be stored
- Above DEFER (but below STORE): memory should be deferred for later review
- Below DEFER: memory should be ignored
"""

from enum import Enum


class ConfidenceThreshold(float, Enum):
    """Confidence thresholds for memory store/defer/ignore decisions.

    Inherits from ``float`` so members can be used directly in numeric
    comparisons (e.g. ``confidence > ConfidenceThreshold.STORE``) without
    calling ``.value``.
    """

    STORE = 0.5  # Confidence above this → store
    DEFER = 0.3  # Confidence above this (but below STORE) → defer; below → ignore


def compute_suggested_action(confidence: float) -> str:
    """Compute the suggested action for a memory based on its confidence.

    Centralises the store/defer/ignore decision so the rule is defined in
    a single location and reused by both the classification engine and the
    MCP integration layer.

    Args:
        confidence: Confidence score (typically 0.0-1.0).

    Returns:
        One of ``"store"``, ``"defer"`` or ``"ignore"``:

        * ``"store"`` — confidence above :attr:`ConfidenceThreshold.STORE`
        * ``"defer"`` — confidence above :attr:`ConfidenceThreshold.DEFER`
          but at or below :attr:`ConfidenceThreshold.STORE`
        * ``"ignore"`` — confidence at or below
          :attr:`ConfidenceThreshold.DEFER`
    """
    if confidence > ConfidenceThreshold.STORE:
        return "store"
    if confidence > ConfidenceThreshold.DEFER:
        return "defer"
    return "ignore"
