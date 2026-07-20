"""Classification pipeline internals + rule-delegate methods."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union, cast

from carrymem.adapters.base import MemoryEntry
from carrymem.constants import (
    ACTIVE_RULES_LIST_LIMIT,
    CONTENT_PREVIEW_LENGTH,
    COREFERENCE_RECALL_LIMIT,
    CORRECTION_KEYWORD_OVERLAP,
    CORRECTION_RECALL_LIMIT,
    DEFAULT_FORCE_TYPE_CONFIDENCE,
    MAX_MESSAGE_LENGTH,
    MIN_CORRECTION_CONTENT_LENGTH,
    RULE_CONTENT_MAX_LENGTH,
)
from carrymem.layers.entity_normalizer import is_entity_normalization_enabled
from carrymem.types import (
    ClassificationResult,
    CorrectionUpdateInfo,
    ValidateAndResolveResult,
)

if TYPE_CHECKING:
    from carrymem.adapters.base import StorageAdapter
    from carrymem.rules import RuleEngine
    from carrymem.rules.candidate_generator import RuleCandidateGenerator

logger = logging.getLogger(__name__)


class ClassificationMixin:
    """Internal classification pipeline and rule-candidate delegate methods."""

    # Shared instance state provided by LifecycleMixin.__init__.
    _adapter: Optional[StorageAdapter]
    _candidate_generator: RuleCandidateGenerator
    # Lazy-init entity normalizer + input validator (v0.5.1)
    _entity_normalizer: Optional[Any]
    _input_validator: Optional[Any]
    _namespace: str  # provided by LifecycleMixin.__init__ (trusted adapter source, C18)

    # ── Cross-Mixin dependencies (TD-037: explicit Protocol contract) ──
    if TYPE_CHECKING:
        # From RecallMixin
        def recall_memories(
            self,
            query: Optional[str] = None,
            filters: Optional[Dict[str, Any]] = None,
            limit: int = 20,
            namespaces: Optional[List[str]] = None,
            update_access: bool = True,
        ) -> List[Dict[str, Any]]: ...

        # From MemoryCRUDMixin
        def classify_message(
            self,
            message: str,
            context: Optional[Dict[str, Any]] = None,
            language: Optional[str] = None,
        ) -> ClassificationResult: ...

        # From BackupMixin
        def _auto_backup(self) -> None: ...

        # From LifecycleMixin (property)
        @property
        def rule_engine(self) -> RuleEngine: ...

    def _validate_and_resolve(
        self,
        message: str,
        context: Optional[Dict[str, Any]],
        force_type: Optional[str],
        session_id: Optional[str],
    ) -> ValidateAndResolveResult:
        """Validate input, inject session_id, resolve coreferences, check redaction.

        Returns:
            (resolved_message, should_continue, redact_result, coreference_resolved)
        """
        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Message too long: {len(message)} chars (max {MAX_MESSAGE_LENGTH})")

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
                    recent_mems = self.recall_memories(query="", limit=COREFERENCE_RECALL_LIMIT, update_access=False)
                except (KeyError, ValueError, RuntimeError) as e:
                    logger.debug("Coreference recall skipped (non-critical): %s", e)
                resolved_message, coreference_resolved = resolve_coreference(
                    message,
                    context=context_str,
                    recent_memories=recent_mems,
                )
                if coreference_resolved:
                    logger.debug("Coreference resolved: '%s' → '%s'", message, resolved_message)
            except (ValueError, TypeError, ImportError, RuntimeError) as e:
                logger.debug("Coreference resolution failed (non-critical), using original message: %s", e)

        # Auto-redaction: block storage of sensitive content
        if not force_type:
            try:
                from carrymem.security.redaction import should_redact

                should_block, redact_reason = should_redact(resolved_message)
                if should_block:
                    logger.warning("Memory storage blocked by auto-redaction: %s", redact_reason)
                    return (resolved_message, False, redact_reason, coreference_resolved)  # type: ignore[return-value]
            except (ImportError, ValueError, TypeError, RuntimeError) as e:
                logger.warning("Auto-redaction check failed, allowing storage as precaution: %s", e)

        return (resolved_message, True, None, coreference_resolved)

    def _classify_message(
        self,
        resolved_message: str,
        context: Optional[Dict[str, Any]],
        language: Optional[str],
        force_type: Optional[str],
        message: str,
    ) -> Union[List[Dict[str, Any]], ClassificationResult]:
        """Classify the message and apply force_type override.

        Returns:
            entries list (may be empty for noise) or ClassificationResult dict.
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
                        "confidence": DEFAULT_FORCE_TYPE_CONFIDENCE,
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
    ) -> ClassificationResult:
        """Store classified entries, handle corrections, suggest rules, backup."""
        stored_memories = []
        storage_keys = []
        updated_memories = []

        # v0.5.1: Entity normalization (Ontology-lite). Runs as post-classification
        # enrichment. Namespace from self._namespace (adapter-sourced, C18).
        entity_meta = self._normalize_entities_safe(resolved_message)

        for entry_dict in classify_result["entries"]:
            entry = MemoryEntry.from_dict(entry_dict)
            self._apply_entry_overrides(entry, force_type, coreference_resolved, message, session_id, entity_meta)
            if entry.suggested_action == "store":
                stored_dict, storage_key, updated = self._store_single_entry(entry, resolved_message)
                if updated:
                    updated_memories.append(updated)
                if stored_dict is not None:
                    stored_memories.append(stored_dict)
                    storage_keys.append(cast(str, storage_key))

        auto_rules = []
        try:
            auto_rules = self._auto_suggest_rules(stored_memories)
        except (ImportError, KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.debug("Auto rule suggestion skipped: %s", e)

        self._auto_backup()

        return {
            "should_remember": True,
            "type": stored_memories[0].get("type", "unknown") if stored_memories else "unknown",
            "content": stored_memories[0].get("content", message) if stored_memories else message,
            "entries": stored_memories,  # type: ignore[typeddict-item]
            "stored": len(stored_memories) > 0,
            "storage_keys": storage_keys,
            "rule_suggestions": auto_rules,
            "auto_rules": auto_rules,
            "updated_memories": updated_memories,  # type: ignore[typeddict-item]
            "summary": classify_result["summary"],
        }

    @staticmethod
    def _apply_entry_overrides(
        entry: MemoryEntry,
        force_type: Optional[str],
        coreference_resolved: bool,
        message: str,
        session_id: Optional[str],
        entity_meta: List[Dict[str, Any]],
    ) -> None:
        """Apply force_type, coreference, session_id, and entity metadata overrides in-place."""
        if force_type:
            entry.type = force_type
            entry.confidence = DEFAULT_FORCE_TYPE_CONFIDENCE
        if coreference_resolved:
            entry.raw_text = message
        if session_id and isinstance(entry.metadata, dict):
            entry.metadata["session_id"] = session_id
        elif session_id and not entry.metadata:
            entry.metadata = {"session_id": session_id}
        if entity_meta:
            if not entry.metadata:
                entry.metadata = {}
            if isinstance(entry.metadata, dict):
                entry.metadata["entities"] = entity_meta

    def _store_single_entry(
        self,
        entry: MemoryEntry,
        resolved_message: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[CorrectionUpdateInfo]]:
        """Store a single entry, returning (stored_dict, storage_key, updated_info).

        On storage failure, returns (None, None, updated_info) where updated_info
        may still be populated from a successful correction-handling step.
        """
        updated: Optional[CorrectionUpdateInfo] = None
        try:
            if entry.type == "correction":
                updated = self._handle_correction(entry)
            stored = self._adapter.store_entry(entry)  # type: ignore[union-attr]
            storage_key = stored.storage_key
            # v0.7.0: Populate knowledge graph entities
            adapter = self._adapter
            if adapter and adapter.capabilities.get("graph", False):
                try:
                    adapter.store_graph_entities(storage_key, resolved_message, self._namespace)
                except (ValueError, RuntimeError, AttributeError) as e:
                    logger.debug("Knowledge graph entity extraction skipped: %s", e)
            return stored.to_dict(), storage_key, updated
        except (ValueError, KeyError, TypeError) as e:
            logger.warning("Failed to store memory: %s", e)
            return None, None, updated

    def _handle_correction(self, correction_entry: MemoryEntry) -> Optional[CorrectionUpdateInfo]:
        if not self._adapter:
            return None

        content = correction_entry.content
        if not content or len(content.strip()) < MIN_CORRECTION_CONTENT_LENGTH:
            return None

        keywords = content.lower().split()
        updated_info = self._find_correctable_memory(content, keywords)
        updated_info = self._find_correctable_rule(content, keywords, updated_info)

        return updated_info

    def _find_correctable_memory(
        self,
        content: str,
        keywords: List[str],
    ) -> Optional[CorrectionUpdateInfo]:
        """Find and update a memory matching correction keywords."""
        try:
            related = self.recall_memories(limit=CORRECTION_RECALL_LIMIT)
            for mem in related:
                mem_content = mem.get("content", "").lower()
                mem_type = mem.get("type", "")
                if mem_type in ("user_preference", "decision", "fact_declaration"):
                    overlap = sum(1 for kw in keywords if kw in mem_content and len(kw) > 1)
                    if overlap >= CORRECTION_KEYWORD_OVERLAP:
                        return self._try_update_correctable_memory(mem, content)
        except (ValueError, KeyError, TypeError, RuntimeError) as e:
            logger.warning("Correction handling failed: %s", e)
        return None

    def _try_update_correctable_memory(
        self,
        mem: Dict[str, Any],
        content: str,
    ) -> Optional[CorrectionUpdateInfo]:
        """Attempt to update a single memory; returns the update info or None."""
        storage_key = mem.get("storage_key", "")
        if storage_key and hasattr(self._adapter, "update_memory"):
            try:
                reason = f"Corrected by: {content[:CONTENT_PREVIEW_LENGTH]}"
                self._adapter.update_memory(storage_key, content, reason)  # type: ignore[union-attr]
                return {
                    "storage_key": storage_key,
                    "old_content": mem.get("content", "")[:CONTENT_PREVIEW_LENGTH],
                    "new_content": content[:CONTENT_PREVIEW_LENGTH],
                    "reason": reason,
                }
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("Correction update failed: %s", e)
        return None

    def _find_correctable_rule(
        self,
        content: str,
        keywords: List[str],
        updated_info: Optional[CorrectionUpdateInfo],
    ) -> Optional[CorrectionUpdateInfo]:
        """Find and update an active rule matching correction keywords."""
        try:
            engine = self.rule_engine
            rules = engine.list_rules(status="active", limit=ACTIVE_RULES_LIST_LIMIT)
            for rule in rules:
                rule_content = (rule.trigger + " " + rule.action).lower()
                overlap = sum(1 for kw in keywords if kw in rule_content and len(kw) > 1)
                if overlap >= CORRECTION_KEYWORD_OVERLAP:
                    return self._try_update_correctable_rule(rule, content, updated_info)
        except (ImportError, ValueError, KeyError, TypeError, RuntimeError) as e:
            logger.warning("Rule correction handling failed: %s", e)
        return updated_info

    def _try_update_correctable_rule(
        self,
        rule: Any,
        content: str,
        updated_info: Optional[CorrectionUpdateInfo],
    ) -> Optional[CorrectionUpdateInfo]:
        """Attempt to update a single rule; returns the (possibly updated) info."""
        try:
            safe_action = self._sanitize_rule_content(content[:RULE_CONTENT_MAX_LENGTH])
            self.rule_engine.update_rule(rule.id, action=safe_action)
            if updated_info is None:
                return {
                    "rule_updated": rule.id,
                    "new_action": safe_action[:CONTENT_PREVIEW_LENGTH],
                }
            updated_info["rule_updated"] = rule.id
            return updated_info
        except (ValueError, KeyError, TypeError) as e:
            logger.warning("Rule update in correction handling failed: %s", e)
            return updated_info

    def _count_by_type(self, entries: List[MemoryEntry]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in entries:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts

    # ── v0.5.1: Entity normalization (Ontology-lite) ──────────────────

    def _get_entity_normalizer(self) -> Optional[Any]:
        """Lazily initialize EntityNormalizer bound to the storage backend.

        Returns None if entity normalization is disabled, adapter is missing,
        or adapter lacks ConnectionManager (non-SQLite backends).
        """
        if not is_entity_normalization_enabled():
            return None
        if self._entity_normalizer is not None:
            return self._entity_normalizer
        if self._adapter is None:
            return None
        conn_mgr = getattr(self._adapter, "_conn_mgr", None)
        if conn_mgr is None:
            return None
        if self._input_validator is None:
            try:
                from carrymem.security.input_validator import InputValidator

                self._input_validator = InputValidator(strict_mode=False)
            except (ImportError, TypeError) as e:
                logger.debug("InputValidator init failed: %s", e)
                self._input_validator = None
        try:
            from carrymem.layers.entity_normalizer import EntityNormalizer

            self._entity_normalizer = EntityNormalizer(
                conn_mgr=conn_mgr,
                input_validator=self._input_validator,
            )
        except (ImportError, TypeError) as e:
            logger.debug("EntityNormalizer init failed: %s", e)
            self._entity_normalizer = None
        return self._entity_normalizer

    def _normalize_entities_safe(self, resolved_message: str) -> List[Dict[str, Any]]:
        """Run entity normalization with graceful degradation.

        Returns a list of entity metadata dicts (empty on any failure).
        Namespace comes from self._namespace (adapter-sourced, C18).
        """
        normalizer = self._get_entity_normalizer()
        if normalizer is None:
            return []
        try:
            result = normalizer.normalize(resolved_message, self._namespace)
            return cast(List[Dict[str, Any]], result.to_metadata()["entities"])
        except (ValueError, RuntimeError, AttributeError) as e:
            logger.debug("Entity normalization skipped: %s", e)
            return []

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
