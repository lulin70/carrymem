"""Memory Classification Engine — classification core.

Slim refactored version: only the classification pipeline that CarryMem needs.
Enterprise features (tenants, access control, encryption, distributed, etc.)
have been removed. CarryMem handles storage via its own adapter system.

v0.4.2: Fixed memory leak by using deque with maxlen for message_history.
"""

import time
from collections import deque
from typing import Dict, List, Optional, Any
from memory_classification_engine.utils.config import ConfigManager
from memory_classification_engine.__version__ import __version__ as _version
from memory_classification_engine.utils.helpers import generate_memory_id, get_current_time
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.language import language_manager
from memory_classification_engine.coordinators.classification_pipeline import ClassificationPipeline


class MemoryClassificationEngine:
    """Memory Classification Engine — classification core only.

    This engine runs the three-layer classification funnel:
      Rule Matcher → Pattern Analyzer → Semantic Classifier

    Storage, encryption, access control, and other enterprise features
    are handled by CarryMem's adapter system, not here.
    """

    def __init__(self, config_path: str = None):
        self.config = ConfigManager(config_path)
        self.classification_pipeline = ClassificationPipeline(self.config)
        self.working_memory = []
        self.max_work_memory_size = self.config.get(
            'storage.max_work_memory_size', 100
        )
        # v0.4.2: Use deque with maxlen to prevent unbounded growth
        self.max_message_history_size = self.config.get(
            'storage.max_message_history_size', 1000
        )
        self.message_history = deque(maxlen=self.max_message_history_size)

    def process_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a message and classify memory.

        Args:
            message: The message to process.
            context: Optional context for the message.
            execution_context: Optional execution context containing feedback signals.
            language: Optional language hint to override auto-detection ("en", "zh", "ja").

        Returns:
            A dictionary containing the classification results.
        """
        start_time = time.time()

        if not message or not message.strip():
            duration = time.time() - start_time
            return {
                'message': message,
                'matches': [],
                'working_memory_size': len(self.working_memory),
                'processing_time': duration,
                'language': language or 'unknown',
                'language_confidence': 1.0 if language else 0.0,
            }

        self._add_to_working_memory(message)

        if language:
            detected_lang = language
            lang_confidence = 1.0
        else:
            detected_lang, lang_confidence = language_manager.detect_language(message)

        matches = self.classification_pipeline.classify_with_defaults(
            message, detected_lang, context, execution_context
        )

        unique_matches = self._deduplicate(matches)

        stored_memories = []
        for match in unique_matches:
            memory_id = generate_memory_id()
            match['id'] = memory_id
            match['language'] = detected_lang
            match['language_confidence'] = lang_confidence
            if 'memory_type' in match:
                match['type'] = match['memory_type']
            if 'type' in match and 'memory_type' not in match:
                match['memory_type'] = match['type']
            stored_memories.append(match)

        duration = time.time() - start_time

        return {
            'message': message,
            'matches': stored_memories,
            'working_memory_size': len(self.working_memory),
            'processing_time': duration,
            'language': detected_lang,
            'language_confidence': lang_confidence,
        }

    def _deduplicate(self, matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Simple deduplication by content similarity."""
        seen_content = set()
        unique = []
        for m in matches:
            content = m.get('content', '')
            content_key = content.strip().lower()[:100]
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique.append(m)
        return unique

    def _add_to_working_memory(self, message: str):
        self.working_memory.append({
            'message': message,
            'timestamp': get_current_time(),
        })
        self.message_history.append({
            'message': message,
            'timestamp': time.time(),
        })
        if len(self.working_memory) > self.max_work_memory_size:
            self.working_memory.pop(0)
        if len(self.message_history) > 1000:
            self.message_history.pop(0)

    def clear_working_memory(self):
        self.working_memory = []

    def to_memory_entry(self, message: str, context: str = None) -> Dict[str, Any]:
        """Convert process_message result to MemoryEntry Schema v1.0.

        This is the core method for Pure Upstream mode (v0.3.0).
        Output follows the standard MemoryEntry JSON format that any downstream
        storage system can consume directly.
        """
        from datetime import datetime as dt
        from uuid import uuid4

        result = self.process_message(message, context)
        matches = result.get("matches", [])

        entries = []
        for match in matches:
            mem_type = match.get("memory_type") or match.get("type", "unknown")
            confidence = match.get("confidence", 0.0)
            entries.append({
                "id": f"mce_{dt.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}",
                "type": mem_type,
                "content": match.get("content") or message[:200],
                "confidence": round(confidence, 4),
                "tier": match.get("tier", 2),
                "source_layer": match.get("source", "unknown"),
                "reasoning": match.get("reasoning", ""),
                "suggested_action": "store" if confidence > 0.5 else ("defer" if confidence > 0.3 else "ignore"),
                "metadata": {
                    "original_message": message,
                    "timestamp_utc": dt.utcnow().isoformat() + "Z",
                },
            })

        by_type: Dict[str, int] = {}
        by_tier: Dict[int, int] = {}
        total_conf = 0.0
        for e in entries:
            by_type[e["type"]] = by_type.get(e["type"], 0) + 1
            by_tier[e["tier"]] = by_tier.get(e["tier"], 0) + 1
            total_conf += e["confidence"]

        return {
            "schema_version": "1.0.0",
            "should_remember": len(entries) > 0,
            "entries": entries,
            "summary": {
                "total_entries": len(entries),
                "by_type": by_type,
                "by_tier": by_tier,
                "avg_confidence": round(total_conf / max(len(entries), 1), 4),
            },
            "engine_info": {
                "mode": "classification_only",
                "version": _version,
            },
        }
