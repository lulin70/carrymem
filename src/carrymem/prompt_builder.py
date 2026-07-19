"""PromptBuilder — Extracted prompt construction logic from CarryMem.

Separates the "what memories to retrieve and how to assemble them" concern
from the CarryMem core class, reducing god-module bloat.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from carrymem.context import (
    build_prompt,
)
from carrymem.context import build_qa_prompt as _build_qa_prompt
from carrymem.context import (
    context_relevance,
    preference_matches_scope,
    select_knowledge,
    select_memories,
)
from carrymem.scoring import RecallBudget, recalculate_confidence
from carrymem.selection import (
    _estimate_tokens,
    _has_aggregation_signal,
)

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds system prompts and QA prompts from stored memories.

    This class encapsulates the memory retrieval, filtering, and prompt
    assembly logic that was previously inline in CarryMem.build_context()
    and CarryMem.build_qa_prompt().
    """

    def __init__(self, carrymem_instance):
        """Initialize with a reference to the CarryMem instance.

        Args:
            carrymem_instance: The CarryMem instance to read memories from.
        """
        self._cm = carrymem_instance

    # ------------------------------------------------------------------
    # Internal: memory retrieval helpers
    # ------------------------------------------------------------------

    def _recall_base_memories(
        self,
        query: str,
        limit: int,
    ) -> tuple[List[Dict[str, Any]], Set[str]]:
        """Main recall + superseded + summaries + preferences.

        Returns (all_memories, seen_keys, pref_keys).
        """
        all_memories = self._cm.recall_memories(
            query=query,
            limit=limit,
            update_access=False,
        )
        seen_keys: Set[str] = {m.get("storage_key") for m in all_memories}

        # Superseded memories
        superseded = self._cm.recall_memories(
            query=query,
            limit=5,
            filters={"include_superseded": True},
            update_access=False,
        )
        for m in superseded:
            if m.get("superseded_at") and m.get("storage_key") not in seen_keys:
                all_memories.append(m)
                seen_keys.add(m.get("storage_key"))

        # Session summaries (excluded from main recall by default)
        summaries = self._cm.recall_memories(
            query=query,
            limit=10,
            filters={"type": "session_summary"},
            update_access=False,
        )
        for m in summaries:
            if m.get("storage_key") not in seen_keys:
                if not query or context_relevance(m.get("content", ""), query) > 0.05:
                    all_memories.append(m)
                    seen_keys.add(m.get("storage_key"))

        # Aggregation signal: include all session summaries
        if _has_aggregation_signal(query):
            session_memories = self._cm.recall_memories(
                query="",
                limit=50,
                filters={"include_session_summary": True},
                update_access=False,
            )
            for m in session_memories:
                if m.get("storage_key") not in seen_keys:
                    all_memories.append(m)
                    seen_keys.add(m.get("storage_key"))

        return all_memories, seen_keys

    def _fetch_extra_core_prefs(
        self,
        core_prefs: List[Dict[str, Any]],
        seen_keys: Set[str],
        all_memories: List[Dict[str, Any]],
        ensure_core: bool,
    ) -> None:
        """Fetch additional high-confidence core prefs not in main recall. Mutates inputs in-place."""
        if not (ensure_core and len(core_prefs) < 5):
            return
        core_prefs_extra = self._cm.recall_memories(
            query="",
            limit=5 - len(core_prefs),
            filters={"type": "user_preference", "confidence_min": 0.9},
            update_access=False,
        )
        for m in core_prefs_extra:
            if m.get("storage_key") not in seen_keys:
                core_prefs.append(m)
                seen_keys.add(m.get("storage_key"))
                all_memories.append(m)

    def _collect_context_prefs(
        self,
        all_memories: List[Dict[str, Any]],
        context: str,
    ) -> List[Dict[str, Any]]:
        """Collect contextual prefs (mid-confidence, scope-matched) from existing memories."""
        return [
            m
            for m in all_memories
            if m.get("type") == "user_preference"
            and m.get("confidence", 0) < 0.9
            and m.get("confidence", 0) >= 0.5
            and preference_matches_scope(m, context)
        ]

    def _fetch_extra_context_prefs(
        self,
        context_prefs: List[Dict[str, Any]],
        core_keys: Set[Any],
        seen_keys: Set[str],
        all_memories: List[Dict[str, Any]],
        context: str,
        ensure_core: bool,
    ) -> None:
        """Actively fetch mid-confidence prefs/corrections that FTS may have missed. Mutates inputs in-place."""
        if not ensure_core:
            return
        for mem_type in ("user_preference", "correction"):
            contextual_extra = self._cm.recall_memories(
                query="",
                limit=10,
                filters={
                    "type": mem_type,
                    "confidence_min": 0.5,
                },
                update_access=False,
            )
            for m in contextual_extra:
                sk = m.get("storage_key")
                conf = m.get("confidence", 0)
                if (
                    sk not in seen_keys
                    and sk not in core_keys
                    and conf < 0.9
                    and preference_matches_scope(m, context)
                ):
                    context_prefs.append(m)
                    seen_keys.add(sk)
                    all_memories.append(m)

    def _merge_preferences(
        self,
        core_prefs: List[Dict[str, Any]],
        context_prefs: List[Dict[str, Any]],
        core_keys: Set[Any],
    ) -> tuple:
        """Merge core and contextual prefs (dedup by core_keys). Returns (pref_memories, pref_keys)."""
        pref_memories = list(core_prefs)
        for m in context_prefs:
            if m.get("storage_key") not in core_keys:
                pref_memories.append(m)
        pref_keys = {m.get("storage_key") for m in pref_memories}
        return pref_memories, pref_keys

    def _identify_preferences(
        self,
        all_memories: List[Dict[str, Any]],
        seen_keys: Set[str],
        context: str,
        ensure_core: bool = True,
    ) -> tuple:
        """Identify and filter preference memories.

        Returns (pref_memories, pref_keys, all_memories_updated).

        Two-tier injection:
        - Core prefs (conf >= 0.9): auto-injected everywhere (global)
        - Contextual prefs (0.5 <= conf < 0.9): injected only when scope matches
          the current question context via preference_matches_scope().

        The contextual fetch actively pulls preferences that FTS recall may
        have missed (FTS searches the user's question, not preference content).
        """
        # Core prefs: high-confidence preferences (auto-injected everywhere)
        core_prefs = [m for m in all_memories if m.get("type") == "user_preference" and m.get("confidence", 0) >= 0.9]

        # If core prefs not in main recall, fetch them
        self._fetch_extra_core_prefs(core_prefs, seen_keys, all_memories, ensure_core)

        # Contextual prefs from FTS recall (scope-filtered)
        context_prefs = self._collect_context_prefs(all_memories, context)

        # Active fetch: pull mid-confidence prefs/corrections that FTS may have missed.
        # FTS searches the user's question, not stored preference content,
        # so many valid preferences never appear in all_memories.
        core_keys = {m.get("storage_key") for m in core_prefs}
        self._fetch_extra_context_prefs(context_prefs, core_keys, seen_keys, all_memories, context, ensure_core)

        # Merge: core first, then contextual (dedup by core_keys)
        pref_memories, pref_keys = self._merge_preferences(core_prefs, context_prefs, core_keys)
        return pref_memories, pref_keys, all_memories

    def _compute_recalc_scores(
        self,
        all_memories: List[Dict[str, Any]],
    ) -> Dict[str, tuple]:
        """Compute recalculated confidence/importance without mutating dicts."""
        _recalc_scores: Dict[str, tuple] = {}
        for m in all_memories:
            base_conf = m.get("confidence", 0.0)
            if base_conf > 0:
                try:
                    new_conf = recalculate_confidence(
                        base_confidence=base_conf,
                        access_count=m.get("access_count", 0),
                        created_at=m.get("created_at"),
                    )
                    key = m.get("storage_key", "")
                    new_imp = (
                        new_conf * m.get("importance_score", 0) / max(base_conf, 0.001)
                        if "importance_score" in m
                        else m.get("importance_score", 0)
                    )
                    _recalc_scores[key] = (new_conf, new_imp)
                except (KeyError, ValueError, TypeError, ZeroDivisionError) as e:
                    logger.warning("Confidence recalculation failed: %s", e)
        return _recalc_scores

    def _budget_filter(
        self,
        all_memories: List[Dict[str, Any]],
        pref_keys: Set[str],
        budget: RecallBudget,
        memories_budget: int,
        _recalc_scores: Dict[str, tuple],
    ) -> List[Dict[str, Any]]:
        """Filter memories by budget constraints."""
        budget_filtered = []
        type_counts: Dict[str, int] = {}
        pref_token_total = 0
        pref_token_budget = int(memories_budget * 0.6)

        for m in all_memories:
            mtype = m.get("type", "unknown")
            if m.get("storage_key") in pref_keys:
                tok = _estimate_tokens(m.get("content", ""))
                if pref_token_total + tok <= pref_token_budget:
                    budget_filtered.append(m)
                    pref_token_total += tok
                continue
            _key = m.get("storage_key", "")
            _conf, _imp = _recalc_scores.get(_key, (m.get("confidence", 0.0), m.get("importance_score", 0.0)))
            if not budget.allows(mtype, _conf, _imp):
                continue
            quota = budget.quota_for(mtype)
            type_counts[mtype] = type_counts.get(mtype, 0) + 1
            if type_counts[mtype] <= quota:
                budget_filtered.append(m)

        return budget_filtered

    def _inject_rules(
        self,
        context: Optional[str],
        max_rules: int,
        rules_budget: int,
        override_only: bool = False,
    ) -> str:
        """Inject rules into prompt section."""
        try:
            rule_engine = getattr(self._cm, "rule_engine", None) or getattr(self._cm, "_rule_engine", None)
            if not rule_engine:
                return ""

            if not override_only and context:
                return rule_engine.inject(  # type: ignore[no-any-return]
                    context,
                    format="anchored",
                    max_rules=max_rules,
                    context_budget_tokens=rules_budget,
                )

            # Override-only mode (for QA prompts)
            all_rules = rule_engine.list_rules(status="active", limit=max_rules)
            if override_only:
                override_rules = [r for r in all_rules if getattr(r, "override", False)]
                rules_to_inject = override_rules[:3]
            else:
                override_rules = [r for r in all_rules if getattr(r, "override", False)]
                rules_to_inject = override_rules[:max_rules]

            if not rules_to_inject:
                return ""

            from carrymem.rules.injector import RuleInjector
            from carrymem.rules.matcher import MatchResult

            injector = RuleInjector(rule_engine.matcher)
            matches = [
                MatchResult(rule=r, score=0.8, match_type="override", matched_text=r.trigger) for r in rules_to_inject
            ]
            return injector._format_structured(matches, include_metadata=False)
        except (ImportError, KeyError, ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning("Rule injection failed: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Public: build_context
    # ------------------------------------------------------------------

    def _build_context_memories_section(
        self,
        context: Optional[str],
        max_memories: int,
        memories_budget: int,
    ) -> List[Dict]:
        """Build the memories section for build_context."""
        memories_section: List[Dict] = []
        if not self._cm._adapter:
            return memories_section
        try:
            query = context or ""
            all_memories, seen_keys = self._recall_base_memories(query, max_memories * 3)

            # Preferences (tiered injection)
            pref_memories, pref_keys, all_memories = self._identify_preferences(
                all_memories,
                seen_keys,
                context or "",
            )
            # Add pref memories not already in all_memories
            for m in pref_memories:
                if m.get("storage_key") not in seen_keys:
                    all_memories.append(m)
                    seen_keys.add(m.get("storage_key"))

            memories_section = select_memories(
                memories=all_memories,
                context=context,
                max_count=max_memories,
                max_tokens=memories_budget,
            )

            # Respect select_memories ordering (corrections/decisions before preferences)
            pref_in_selected = [m for m in memories_section if m.get("storage_key") in pref_keys]
            non_pref_selected = [m for m in memories_section if m.get("storage_key") not in pref_keys]
            pref_in_all = [
                m
                for m in all_memories
                if m.get("storage_key") in pref_keys
                and m.get("storage_key") not in {s.get("storage_key") for s in memories_section}
            ]
            memories_section = non_pref_selected + pref_in_selected + pref_in_all
        except (KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.warning("Failed to select memories for context: %s", e)
        return memories_section

    def _build_knowledge_section(
        self,
        context: Optional[str],
        max_knowledge: int,
        knowledge_budget: int,
    ) -> List[Dict]:
        """Build the knowledge section. Returns empty list if no knowledge adapter or context."""
        knowledge_section: List[Dict] = []
        if not (getattr(self._cm, "_knowledge_adapter", None) and context):
            return knowledge_section
        try:
            all_knowledge = self._cm.recall_from_knowledge(query=context, limit=max_knowledge * 2)
            knowledge_section = select_knowledge(
                knowledge=all_knowledge,
                context=context,
                max_count=max_knowledge,
                max_tokens=knowledge_budget,
            )
        except (KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.warning("Failed to select knowledge for context: %s", e)
        return knowledge_section

    def _collect_applied_rules_info(
        self,
        context: Optional[str],
        max_rules: int,
    ) -> List[Dict[str, Any]]:
        """Collect applied rules info for the context."""
        applied_rules_info: List[Dict[str, Any]] = []
        try:
            _re = getattr(self._cm, "rule_engine", None) or getattr(self._cm, "_rule_engine", None)
            if _re:
                _matched = _re.matcher.match(context if context else "*", limit=max_rules)
                for m in _matched:
                    applied_rules_info.append(
                        {
                            "trigger": m.rule.trigger,
                            "action": m.rule.action,
                            "rule_type": m.rule.rule_type,
                            "scope": m.rule.scope,
                            "override": m.rule.override,
                        }
                    )
        except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.warning("Rule matching in system prompt failed: %s", e)
        return applied_rules_info

    def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
        progressive: bool = False,
    ) -> Dict[str, Any]:
        """Build a full context dict with system_prompt, memories, knowledge, rules.

        Args:
            progressive: v0.5.2 — enable progressive disclosure in the generated
                system_prompt. When True, lower-priority memory buckets render
                as summaries instead of full raw_text, reducing token consumption.
        """
        rules_budget = int(max_tokens * 0.2)
        memories_budget = int(max_tokens * 0.6)
        knowledge_budget = int(max_tokens * 0.2)

        # Rules
        rules_section = self._inject_rules(context, max_rules, rules_budget, override_only=False)

        # Memories
        memories_section = self._build_context_memories_section(context, max_memories, memories_budget)

        # Knowledge
        knowledge_section = self._build_knowledge_section(context, max_knowledge, knowledge_budget)

        # Build prompt
        system_prompt = build_prompt(
            memories=memories_section,
            knowledge=knowledge_section,
            language=language,
            progressive=progressive,
        )
        if rules_section:
            system_prompt = rules_section + "\n\n" + system_prompt

        # Applied rules info
        applied_rules_info = self._collect_applied_rules_info(context, max_rules)

        total = len(applied_rules_info) + len(memories_section) + len(knowledge_section)
        return {
            "system_prompt": system_prompt,
            "rules": rules_section if isinstance(rules_section, str) else rules_section,
            "memories": memories_section,
            "knowledge": knowledge_section,
            "applied_rules": applied_rules_info,
            "rule_count": len(applied_rules_info),
            "memory_count": len(memories_section),
            "knowledge_count": len(knowledge_section),
            "total_count": total,
            "token_estimate": _estimate_tokens(system_prompt),
            "language": language,
        }

    # ------------------------------------------------------------------
    # Public: build_system_prompt
    # ------------------------------------------------------------------

    def build_system_prompt(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 4000,
        language: str = "en",
        progressive: bool = False,
    ) -> str:
        """Build a system prompt string (convenience wrapper).

        Args:
            progressive: v0.5.2 — enable progressive disclosure. See build_context().
        """
        result = self.build_context(
            context=context,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_rules=max_rules,
            max_tokens=max_tokens,
            language=language,
            progressive=progressive,
        )
        return result["system_prompt"]  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Public: build_qa_prompt
    # ------------------------------------------------------------------

    def _select_qa_memories_aggregation(
        self,
        budget_filtered: List[Dict[str, Any]],
        all_memories: List[Dict[str, Any]],
        _recalc_scores: Dict[str, tuple],
        budget: RecallBudget,
        memories_budget: int,
    ) -> List[Dict]:
        """Select memories for QA prompt when aggregation signal is detected."""
        sorted_mems = sorted(
            budget_filtered or all_memories,
            key=lambda m: _recalc_scores.get(
                m.get("storage_key", ""),
                (0, m.get("importance_score", 0.0)),
            )[1],
            reverse=True,
        )
        memories_section: List[Dict] = []
        total_tok = 0
        for m in sorted_mems:
            if len(memories_section) >= budget.max_results:
                break
            tok = _estimate_tokens(m.get("content", ""))
            if total_tok + tok > memories_budget:
                continue
            memories_section.append(m)
            total_tok += tok
        return memories_section

    def _select_qa_memories_standard(
        self,
        budget_filtered: List[Dict[str, Any]],
        all_memories: List[Dict[str, Any]],
        pref_keys: Set[str],
        question: str,
        budget: RecallBudget,
        memories_budget: int,
    ) -> List[Dict]:
        """Select memories for QA prompt in standard (non-aggregation) mode."""
        pref_in_filtered = [m for m in budget_filtered if m.get("storage_key") in pref_keys]
        non_pref_filtered = [m for m in budget_filtered if m.get("storage_key") not in pref_keys]
        selected = select_memories(
            memories=non_pref_filtered or all_memories,
            context=question,
            max_count=budget.max_results,
            max_tokens=memories_budget,
        )
        return pref_in_filtered + [m for m in selected if m.get("storage_key") not in pref_keys]

    def _build_qa_memories_section(
        self,
        question: str,
        budget: RecallBudget,
        memories_budget: int,
    ) -> List[Dict]:
        """Build the memories section for the QA prompt."""
        memories_section: List[Dict] = []
        if not self._cm._adapter:
            return memories_section
        try:
            all_memories, seen_keys = self._recall_base_memories(question, budget.max_results * 3)

            # Preferences
            pref_memories, pref_keys, all_memories = self._identify_preferences(
                all_memories,
                seen_keys,
                question,
            )

            # Remove scope-mismatched preferences from all_memories
            # so they don't get selected as non-preference memories
            all_prefs_in_all = {m.get("storage_key") for m in all_memories if m.get("type") == "user_preference"}
            mismatched_pref_keys = all_prefs_in_all - pref_keys
            if mismatched_pref_keys:
                all_memories = [m for m in all_memories if m.get("storage_key") not in mismatched_pref_keys]

            # Recalculate confidence for sorting (no mutation)
            _recalc_scores = self._compute_recalc_scores(all_memories)

            # Budget filtering
            budget_filtered = self._budget_filter(
                all_memories,
                pref_keys,
                budget,
                memories_budget,
                _recalc_scores,
            )

            # Select memories
            if _has_aggregation_signal(question):
                memories_section = self._select_qa_memories_aggregation(
                    budget_filtered, all_memories, _recalc_scores, budget, memories_budget
                )
            else:
                memories_section = self._select_qa_memories_standard(
                    budget_filtered, all_memories, pref_keys, question, budget, memories_budget
                )
        except (KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.warning("Failed to select memories for QA prompt: %s", e)
        return memories_section

    def _build_qa_knowledge_section(
        self,
        question: str,
        max_knowledge: int,
        knowledge_budget: int,
    ) -> List[Dict]:
        """Build the knowledge section for the QA prompt."""
        knowledge_section: List[Dict] = []
        if not getattr(self._cm, "_knowledge_adapter", None):
            return knowledge_section
        try:
            all_knowledge = self._cm.recall_from_knowledge(query=question, limit=max_knowledge * 2)
            knowledge_section = select_knowledge(
                knowledge=all_knowledge,
                context=question,
                max_count=max_knowledge,
                max_tokens=knowledge_budget,
            )
        except (KeyError, ValueError, TypeError, RuntimeError) as e:
            logger.warning("Failed to select knowledge for QA prompt: %s", e)
        return knowledge_section

    def build_qa_prompt(
        self,
        question: str,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
        budget: Optional[RecallBudget] = None,
        include_question: bool = True,
    ) -> str:
        """Build a QA prompt with memories, knowledge, and rules."""
        if budget is None:
            budget = RecallBudget(
                max_results=max_memories,
                max_tokens=max_tokens,
            )

        memories_budget = int(budget.max_tokens * 0.65)
        knowledge_budget = int(budget.max_tokens * 0.2)

        # Rules (override-only for QA)
        rules_section = self._inject_rules(question, 3, int(budget.max_tokens * 0.1), override_only=True)

        # Memories
        memories_section = self._build_qa_memories_section(question, budget, memories_budget)

        # Knowledge
        knowledge_section = self._build_qa_knowledge_section(question, max_knowledge, knowledge_budget)

        return _build_qa_prompt(
            memories=memories_section,
            knowledge=knowledge_section,
            question=question,
            language=language,
            include_question=include_question,
            rules=rules_section,
        )
