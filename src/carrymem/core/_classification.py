"""Classification pipeline internals + rule-delegate methods."""

from typing import Any, Dict, List, Optional

from carrymem.adapters.base import MemoryEntry
from carrymem.security.input_validator import InputValidator
from carrymem.utils.logger import logger
from carrymem.utils.validators import (
    validate_context,
    validate_language,
    validate_message,
)


class ClassificationMixin:
    """Internal classification pipeline and rule-candidate delegate methods."""

    def _validate_and_resolve(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> tuple:
        """Validate input, inject session_id, resolve coreferences, check redaction.

        Returns:
            (resolved_message, should_continue, redact_result, coreference_resolved)
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        if len(message) > 50000:
            raise ValueError(f"Message too long: {len(message)} chars (max 50000)")

        # Inject session_id into context
        if session_id and context is None:
            context = {}
        if session_id and isinstance(context, dict):
            context["session_id"] = session_id

        # Coreference resolution
        resolved_message = message
        coreference_resolved = False

        _PRONOUNS = {
            "it",
            "this",
            "that",
            "these",
            "those",
            "he",
            "she",
            "they",
            "him",
            "her",
            "them",
            "his",
            "its",
            "their",
            "my",
            "your",
            "our",
        }
        _has_pronoun = bool(
            set(message.lower().split()) & _PRONOUNS
            or any(p in message.lower() for p in ("it's", "that's", "he's", "she's"))
        )

        if _has_pronoun:
            try:
                from carrymem.coreference import resolve_coreference

                context_str = ""
                if context and isinstance(context, dict):
                    context_str = context.get("ai_reply", "") or context.get("previous_message", "")
                recent_mems = []
                try:
                    recent_mems = self.recall_memories(query="", limit=5, update_access=False)
                except (KeyError, ValueError, RuntimeError) as e:
                    logger.debug(f"Coreference recall skipped (non-critical): {e}")
                resolved_message, coreference_resolved = resolve_coreference(
                    message,
                    context=context_str,
                    recent_memories=recent_mems,
                )
                if coreference_resolved:
                    logger.debug(f"Coreference resolved: '{message}' → '{resolved_message}'")
            except (ValueError, TypeError, ImportError, RuntimeError) as e:
                logger.debug(f"Coreference resolution failed (non-critical), using original message: {e}")

        # Auto-redaction
        if not force_type:
            try:
                from carrymem.security.redaction import should_redact

                should_block, redact_reason = should_redact(resolved_message)
                if should_block:
                    logger.warning(f"Auto-redact blocked memory storage: {redact_reason}")
                    redact_result = {
                        "should_remember": False,
                        "type": "auto_redacted",
                        "content": resolved_message,
                        "entries": [],
                        "stored": False,
                        "storage_keys": [],
                        "rule_suggestions": [],
                        "auto_rules": [],
                        "updated_memories": [],
                        "summary": {
                            "total_entries": 0,
                            "by_type": {},
                            "redacted": True,
                            "redact_reason": redact_reason,
                        },
                    }
                    return (resolved_message, False, redact_result, coreference_resolved)
            except (ImportError, ValueError, TypeError, RuntimeError) as e:
                logger.warning(f"Auto-redaction check failed, allowing storage as precaution: {e}")

        return (resolved_message, True, None, coreference_resolved)

    def _classify_message(
        self,
        resolved_message: str,
        context: Optional[Dict[str, Any]],
        language: Optional[str],
        force_type: Optional[str],
        message: str,
    ) -> List[Dict[str, Any]]:
        """Classify the message and apply force_type override.

        Returns:
            entries list (may be empty for noise).
        """
        classify_result = self.classify_message(resolved_message, context=context, language=language)

        if not classify_result["should_remember"] and not force_type:
            return []  # Signal: noise

        if force_type and not classify_result["should_remember"]:
            classify_result["should_remember"] = True
            if not classify_result["entries"]:
                classify_result["entries"] = [
                    {
                        "content": message,
                        "type": force_type,
                        "suggested_action": "store",
                        "confidence": 0.8,
                    }
                ]

        return classify_result

    def _store_entries(
        self,
        classify_result: Dict[str, Any],
        resolved_message: str,
        message: str,
        context: Optional[Dict[str, Any]],
        coreference_resolved: bool,
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> Dict[str, Any]:
        """Store classified entries, handle corrections, suggest rules, backup."""
        stored_memories = []
        storage_keys = []
        updated_memories = []
        for entry_dict in classify_result["entries"]:
            entry = MemoryEntry.from_dict(entry_dict)
            if force_type:
                entry.type = force_type
            if coreference_resolved:
                entry.raw_text = message
            if session_id and isinstance(entry.metadata, dict):
                entry.metadata["session_id"] = session_id
            elif session_id and not entry.metadata:
                entry.metadata = {"session_id": session_id}
            if entry.suggested_action == "store":
                try:
                    if entry.type == "correction":
                        updated = self._handle_correction(entry)
                        if updated:
                            updated_memories.append(updated)

                    stored = self._adapter.remember(entry)
                    stored_memories.append(stored.to_dict())
                    storage_keys.append(stored.storage_key)
                except (ValueError, KeyError, TypeError, RuntimeError) as e:
                    logger.warning(f"Failed to store memory: {e}")
                    continue

        auto_rules = []
        try:
            auto_rules = self._auto_suggest_rules(stored_memories)
        except (ImportError, KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.debug(f"Auto rule suggestion skipped: {e}")

        self._auto_backup()

        return {
            "should_remember": True,
            "type": stored_memories[0].get("type", "unknown") if stored_memories else "unknown",
            "content": stored_memories[0].get("content", message) if stored_memories else message,
            "entries": stored_memories,
            "stored": len(stored_memories) > 0,
            "storage_keys": storage_keys,
            "rule_suggestions": auto_rules,
            "auto_rules": auto_rules,
            "updated_memories": updated_memories,
            "summary": classify_result["summary"],
        }

    def _handle_correction(self, correction_entry: MemoryEntry) -> Optional[Dict[str, Any]]:
        if not self._adapter:
            return None

        content = correction_entry.content
        if not content or len(content.strip()) < 3:
            return None

        updated_info = None

        try:
            keywords = content.lower().split()
            related = self.recall_memories(limit=10)
            for mem in related:
                mem_content = mem.get("content", "").lower()
                mem_type = mem.get("type", "")
                if mem_type in ("user_preference", "decision", "fact_declaration"):
                    overlap = sum(1 for kw in keywords if kw in mem_content and len(kw) > 1)
                    if overlap >= 2:
                        storage_key = mem.get("storage_key", "")
                        if storage_key and hasattr(self._adapter, "update_memory"):
                            try:
                                reason = f"Corrected by: {content[:100]}"
                                self._adapter.update_memory(storage_key, content, reason)
                                updated_info = {
                                    "storage_key": storage_key,
                                    "old_content": mem.get("content", "")[:100],
                                    "new_content": content[:100],
                                    "reason": reason,
                                }
                            except (ValueError, KeyError, TypeError) as e:
                                logger.warning(f"Correction update failed: {e}")
                        break
        except (ValueError, KeyError, TypeError, RuntimeError) as e:
            logger.warning(f"Correction handling failed: {e}")

        try:
            engine = self.rule_engine
            rules = engine.list_rules(status="active", limit=50)
            for rule in rules:
                rule_content = (rule.trigger + " " + rule.action).lower()
                overlap = sum(1 for kw in keywords if kw in rule_content and len(kw) > 1)
                if overlap >= 2:
                    try:
                        safe_action = self._sanitize_rule_content(content[:200])
                        engine.update_rule(rule.id, action=safe_action)
                        if updated_info is None:
                            updated_info = {
                                "rule_updated": rule.id,
                                "new_action": safe_action[:100],
                            }
                        else:
                            updated_info["rule_updated"] = rule.id
                    except (ValueError, KeyError, TypeError) as e:
                        logger.warning(f"Rule update in correction handling failed: {e}")
                    break
        except (ImportError, ValueError, KeyError, TypeError, RuntimeError) as e:
            logger.warning(f"Rule correction handling failed: {e}")

        return updated_info

    def _count_by_type(self, entries: List[MemoryEntry]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in entries:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts

    # --- Rule delegate methods (thin wrappers around RuleCandidateGenerator) ---

    def _auto_suggest_rules(self, stored_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._candidate_generator.auto_suggest_rules(stored_memories)

    def _detect_implicit_preferences(self) -> List[Dict[str, Any]]:
        return self._candidate_generator.detect_implicit_preferences()

    def _sanitize_rule_content(self, text: str) -> str:
        return self._candidate_generator.sanitize_rule_content(text)

    def _extract_trigger(self, content: str, mem_type: str) -> str:
        return self._candidate_generator.extract_trigger(content, mem_type)

    def _extract_condition(self, content: str) -> str:
        return self._candidate_generator.extract_condition(content)

    def _extract_action(self, content: str, mem_type: str) -> str:
        return self._candidate_generator.extract_action(content, mem_type)

    def _infer_rule_type(self, mem_type: str, content: str = "") -> str:
        return self._candidate_generator.infer_rule_type(mem_type, content)
