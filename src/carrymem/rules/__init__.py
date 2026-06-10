"""
CarryMem Rules Engine — Public API

High-level facade for the rules system. Provides simple interface
for creating, managing, and using behavioral rules.

Usage:
    from carrymem.rules import RuleEngine, Rule

    engine = RuleEngine(db_path="~/.carrymem/memories.db")

    # Create rule
    rule = engine.add_rule(
        trigger="写报告",
        action="控制在3页以内",
        rule_type="format"
    )

    # Match rules to scene
    matches = engine.match("帮我做竞品分析")

    # Inject into prompt
    prompt_section = engine.inject("帮我做Q2销售报告")
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

_logger = logging.getLogger(__name__)

from ..__version__ import __version__
from .candidate_rule_generator import CandidateRuleGenerator, RuleCandidate
from .conflict_detector import ConflictSeverity, ConflictType, RuleConflict, RuleConflictDetector
from .experience_bridge import (
    EXPERIENCE_STATUS_ACCEPTED,
    EXPERIENCE_STATUS_EXPIRED,
    EXPERIENCE_STATUS_PENDING,
    EXPERIENCE_STATUS_REJECTED,
    ExperienceAuditEntry,
    ExperienceRuleBridge,
)
from .failure_experience import (
    ExtractedLesson,
    FailureConfidence,
    FailureExperienceExtractor,
    FailureSignal,
)
from .injector import RuleInjector
from .limiter import RuleLimiter
from .matcher import MatchResult, RuleMatcher
from .merge_protocol import MergeConflict, MergeDecision, MergeResult, MergeStrategy
from .models import (
    SCOPE_PRIORITY,
    VALID_DERIVATION_SOURCES,
    VALID_RULE_SCOPES,
    VALID_RULE_STATUSES,
    VALID_RULE_TYPES,
    Rule,
    RuleScope,
)
from .pattern_detector import MemoryPattern, PatternConfidence, PatternDetector, PatternType
from .promotion_pipeline import (
    PROMOTION_STATUS_ACCEPTED,
    PROMOTION_STATUS_EXPIRED,
    PROMOTION_STATUS_PENDING,
    PROMOTION_STATUS_REJECTED,
    PromotionAuditEntry,
    PromotionPipeline,
)
from .refinement_session import (
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_CANCELLED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_EXPIRED,
    RefinementSessionManager,
    SessionEntry,
)
from .rule_refiner import (
    QuestionType,
    RefinedRuleDraft,
    RefinementAnswer,
    RefinementPhase,
    RefinementQuestion,
    RuleRefiner,
)
from .sanitizer import RuleSanitizer
from .skill import skill_install, skill_pack, skill_verify
from .storage import RuleStorage


class ImportModeError(ValueError):
    """Raised when an invalid import mode is specified."""


class RuleEngine:
    """
    High-level facade for rules operations.

    Provides a unified interface for all rules functionality:
    - CRUD operations (create/read/update/delete)
    - Scene matching (find applicable rules)
    - Prompt injection (format rules for AI)
    - Usage statistics and monitoring

    This is the main entry point for external consumers.

    Usage:
        engine = RuleEngine(db_path="~/.carrymem/memories.db")

        # Create a new rule
        rule = engine.add_rule(
            trigger="写报告",
            action="控制在3页以内",
            rule_type="format",
            override=True
        )

        # Find matching rules for a scene
        matches = engine.match("帮我做季度销售报告")

        # Get formatted prompt section
        prompt_text = engine.inject("写技术方案文档")
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the rules engine.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.carrymem/memories.db
        """
        if db_path is None:
            from ..constants import DB_PATH, DEFAULT_CONFIG_DIR

            DEFAULT_CONFIG_DIR.mkdir(exist_ok=True)
            db_path = str(DB_PATH)
        self.storage = RuleStorage(db_path)
        self.matcher = RuleMatcher(self.storage)
        self.injector = RuleInjector(self.matcher)
        self.pattern_detector = PatternDetector()
        self.candidate_generator = CandidateRuleGenerator()
        self.promotion_pipeline = PromotionPipeline(self.storage)
        self.experience_bridge = ExperienceRuleBridge(self.storage)
        self.failure_extractor = FailureExperienceExtractor()
        self.rule_refiner = RuleRefiner()
        self.refinement_session = RefinementSessionManager(self.storage)

    def add_rule(
        self,
        trigger: str,
        action: str,
        rule_type: str = "avoid",
        override: bool = True,
        derived_from: str = "manual",
        source_memories: Optional[list] = None,
        scope: str = "personal",
        expires_at: str = "",
        condition: str = "",
        **kwargs,
    ) -> Rule:
        """
        Create and store a new rule with full validation.

        This is the primary method for creating rules. It performs:
        1. Input validation via RuleSanitizer
        2. Limit checking via RuleLimiter
        3. Storage via RuleStorage

        Args:
            trigger: Scene description that activates this rule
            action: Behavioral instruction to execute when triggered
            rule_type: Type of rule (avoid/always/prefer/forbid/format)
            override: If True, AI cannot ignore this rule (hard rule)
            derived_from: How this rule was created (manual/auto/failure/refined)
            source_memories: IDs of memories this rule was derived from
            scope: Rule scope (personal/company/negotiated)
            **kwargs: Additional fields (confidence, metadata)

        Returns:
            Created Rule object

        Raises:
            ValueError: If validation fails or limits exceeded

        Examples:
            >>> engine.add_rule("写报告", "控制在3页以内", "format")
            Rule(id='rule_abc123', trigger='写报告', ...)
            >>> engine.add_rule("security", "Use SSL", scope="company")
        """
        from .models import VALID_RULE_SCOPES

        if scope not in VALID_RULE_SCOPES:
            raise ValueError(f"Invalid scope '{scope}'. Must be one of {VALID_RULE_SCOPES}")

        # Validate through sanitizer
        trigger = RuleSanitizer.validate_trigger(trigger)
        action = RuleSanitizer.validate_action(action)
        RuleSanitizer.validate_rule_type(rule_type)

        # Check limits before creating
        temp_rule = Rule(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=override,
            derived_from=derived_from,
            source_memories=source_memories or [],
            scope=scope,
        )
        RuleLimiter.validate_new_rule(self.storage, temp_rule)

        conflict_warnings = []
        try:
            existing_rules = self.storage.list_all(status="active", limit=500)
            for er in existing_rules:
                if er.trigger == trigger and er.scope == scope:
                    if er.rule_type != rule_type or er.action != action:
                        conflict_warnings.append(
                            {
                                "conflicting_rule_id": er.id,
                                "conflicting_trigger": er.trigger,
                                "conflicting_action": er.action,
                                "conflicting_type": er.rule_type,
                                "conflict_type": "same_trigger_different_action",
                                "suggestion": "Consider updating the existing rule instead of creating a new one",
                            }
                        )
        except (ValueError, KeyError, TypeError):
            pass

        created = self.storage._create_validated(
            trigger=trigger,
            action=action,
            rule_type=rule_type,
            override=override,
            derived_from=derived_from,
            source_memories=source_memories,
            scope=scope,
            expires_at=expires_at,
            condition=condition,
            **kwargs,
        )
        if conflict_warnings:
            created._conflict_warnings = conflict_warnings

        return created

    def get_rule(self, rule_id: str):
        """
        Retrieve a rule by ID.

        Args:
            rule_id: Unique rule identifier

        Returns:
            Rule object or None if not found
        """
        return self.storage.get(rule_id)

    def list_rules(
        self,
        status: Optional[str] = None,
        rule_type: Optional[str] = None,
        scope: Optional[str] = None,
        limit: int = 50,
    ) -> list:
        """
        List rules with optional filtering.

        Args:
            status: Filter by status (active/paused/deprecated)
            rule_type: Filter by type
            scope: Filter by scope (personal/company/negotiated)
            limit: Maximum number to return

        Returns:
            List of Rule objects
        """
        return self.storage.list_all(status=status, rule_type=rule_type, scope=scope, limit=limit)

    def match(
        self,
        scene_description: str,
        limit: int = 10,
        increment_count: bool = True,
        scopes: Optional[list] = None,
    ) -> list:
        """
        Find rules matching a given scene.

        Uses multi-strategy matching (global > exact > FTS5 > partial).
        By default, increments trigger_count for matched rules.

        Args:
            scene_description: Natural language description of current context
            limit: Maximum results
            increment_count: If True, increment trigger_count for matched rules
            scopes: Optional list of scopes to filter (e.g., ["company", "personal"])

        Returns:
            List of MatchResult objects sorted by relevance
        """
        results = self.matcher.match(scene_description, limit=limit, scopes=scopes)

        if increment_count and results:
            rule_ids = [r.rule.id for r in results]
            self.storage.batch_increment_trigger_counts(rule_ids)

        return results

    def inject(
        self,
        scene_description: str,
        format: str = "structured",
        max_rules: int = 10,
        context_budget_tokens: Optional[int] = None,
    ) -> str:
        """
        Generate formatted rules section for prompt injection.

        Args:
            scene_description: Current scene/context
            format: Output format (structured/compact/json/anchored/ddd)
            max_rules: Maximum rules to include
            context_budget_tokens: Token budget for compression (None=no limit)

        Returns:
            Formatted string ready for injection into AI prompts
        """
        return self.injector.inject(
            scene_description,
            format=format,
            max_rules=max_rules,
            context_budget_tokens=context_budget_tokens,
        )

    def update_rule(self, rule_id: str, **updates) -> Optional[Rule]:
        """
        Update an existing rule.

        Args:
            rule_id: ID of rule to update
            **updates: Fields to update

        Returns:
            Updated Rule or None if not found
        """
        if "trigger" in updates:
            updates["trigger"] = RuleSanitizer.validate_trigger(updates["trigger"])
        if "action" in updates:
            updates["action"] = RuleSanitizer.validate_action(updates["action"])
        if "rule_type" in updates:
            RuleSanitizer.validate_rule_type(updates["rule_type"])
        return self.storage.update(rule_id, **updates)

    def delete_rule(self, rule_id: str) -> bool:
        """
        Delete a rule by ID.

        Args:
            rule_id: ID of rule to delete

        Returns:
            True if deleted, False if not found
        """
        return self.storage.delete(rule_id)

    def search_rules(self, query: str, limit: int = 20) -> list:
        """
        Full-text search across rules.

        Args:
            query: Search query text
            limit: Maximum results

        Returns:
            List of matching Rule objects
        """
        return self.storage.search(query, limit=limit)

    def get_stats(self) -> dict:
        """
        Get usage statistics for monitoring.

        Returns:
            Dictionary with usage metrics
        """
        return RuleLimiter.get_usage_stats(self.storage)

    def get_effectiveness_report(self) -> dict:
        """
        Get comprehensive rule effectiveness report.

        Aggregates trigger counts, confidence distribution, override usage,
        and type breakdown for monitoring rule quality.

        Returns:
            Dictionary with effectiveness metrics
        """
        all_rules = self.storage.list_all(limit=10000)

        total = len(all_rules)
        active = [r for r in all_rules if r.status == "active"]
        paused = [r for r in all_rules if r.status == "paused"]
        deprecated = [r for r in all_rules if r.status == "deprecated"]

        triggered = [r for r in active if r.trigger_count > 0]
        never_triggered = [r for r in active if r.trigger_count == 0]

        override_rules = [r for r in active if r.override]
        soft_rules = [r for r in active if not r.override]

        type_counts = {}
        type_trigger_counts = {}
        for r in active:
            rt = r.rule_type
            type_counts[rt] = type_counts.get(rt, 0) + 1
            type_trigger_counts[rt] = type_trigger_counts.get(rt, 0) + r.trigger_count

        confidence_buckets = {"high": 0, "medium": 0, "low": 0}
        for r in active:
            if r.confidence >= 0.8:
                confidence_buckets["high"] += 1
            elif r.confidence >= 0.5:
                confidence_buckets["medium"] += 1
            else:
                confidence_buckets["low"] += 1

        top_triggered = sorted(active, key=lambda r: r.trigger_count, reverse=True)[:10]
        never_triggered_list = [
            {"id": r.id, "trigger": r.trigger, "action": r.action, "rule_type": r.rule_type}
            for r in never_triggered[:20]
        ]

        derivation_counts = {}
        for r in all_rules:
            d = r.derived_from
            derivation_counts[d] = derivation_counts.get(d, 0) + 1

        scope_counts = {}
        scope_trigger_counts = {}
        for r in active:
            s = r.scope
            scope_counts[s] = scope_counts.get(s, 0) + 1
            scope_trigger_counts[s] = scope_trigger_counts.get(s, 0) + r.trigger_count

        return {
            "total_rules": total,
            "active": len(active),
            "paused": len(paused),
            "deprecated": len(deprecated),
            "triggered": len(triggered),
            "never_triggered": len(never_triggered),
            "trigger_rate": len(triggered) / max(len(active), 1),
            "override_rules": len(override_rules),
            "soft_rules": len(soft_rules),
            "type_breakdown": type_counts,
            "type_trigger_totals": type_trigger_counts,
            "scope_breakdown": scope_counts,
            "scope_trigger_totals": scope_trigger_counts,
            "confidence_distribution": confidence_buckets,
            "top_triggered": [
                {
                    "id": r.id,
                    "trigger": r.trigger,
                    "action": r.action,
                    "rule_type": r.rule_type,
                    "trigger_count": r.trigger_count,
                    "override": r.override,
                }
                for r in top_triggered
            ],
            "never_triggered_sample": never_triggered_list,
            "derivation_sources": derivation_counts,
        }

    def validate_source_memories(self, rule_id: str) -> dict:
        """
        Check the status of a rule's source memories.

        Verifies whether source memories still exist and determines
        their status (active/deleted/superseded).

        Args:
            rule_id: ID of the rule to validate

        Returns:
            Dictionary with validation results per source memory
        """
        rule = self.storage.get(rule_id)
        if rule is None:
            return {"rule_id": rule_id, "error": "Rule not found"}

        if not rule.source_memories:
            return {
                "rule_id": rule_id,
                "source_memories": [],
                "total": 0,
                "active": 0,
                "deleted": 0,
                "superseded": 0,
                "confidence_adjustment": 0.0,
            }

        active_ids = set()
        try:
            all_active = self.storage.list_all(status="active", limit=10000)
            active_ids = {r.id for r in all_active}
        except Exception as e:
            _logger.warning(f"Failed to list active rules: {e}")

        superseded_ids = set()
        try:
            all_deprecated = self.storage.list_all(status="deprecated", limit=10000)
            superseded_ids = {r.id for r in all_deprecated}
        except Exception as e:
            _logger.warning(f"Failed to list deprecated rules: {e}")

        results = []
        active_count = 0
        deleted_count = 0
        superseded_count = 0

        for sm_id in rule.source_memories:
            if sm_id in active_ids:
                status = "active"
                active_count += 1
            elif sm_id in superseded_ids:
                status = "superseded"
                superseded_count += 1
            else:
                status = "deleted"
                deleted_count += 1

            results.append({"source_memory_id": sm_id, "status": status})

        confidence_penalty = deleted_count * 0.1 + superseded_count * 0.05

        return {
            "rule_id": rule_id,
            "source_memories": results,
            "total": len(rule.source_memories),
            "active": active_count,
            "deleted": deleted_count,
            "superseded": superseded_count,
            "confidence_adjustment": -confidence_penalty,
        }

    def skill_pack(
        self,
        name: str,
        version: str = "1.0.0",
        author: str = "",
        description: str = "",
        scope: str = "personal",
        status: Optional[str] = None,
        dependencies: Optional[list] = None,
        tags: Optional[list] = None,
        config: Optional[dict] = None,
    ) -> dict:
        """
        Pack rules into a portable Skill bundle.

        Args:
            name: Skill name (alphanumeric + hyphens)
            version: Semantic version
            author: Author name
            description: Human-readable description
            scope: Default scope for installed rules
            status: Optional status filter for rules to include
            dependencies: List of Skill names this depends on
            tags: Categorization tags
            config: Arbitrary configuration data

        Returns:
            Skill bundle dictionary (carrymem-skill-v1 format)
        """
        from .skill import skill_pack

        rules = self.storage.list_all(status=status, limit=10000)
        return skill_pack(
            rules=rules,
            name=name,
            version=version,
            author=author,
            description=description,
            scope=scope,
            dependencies=dependencies,
            tags=tags,
            config=config,
        )

    @staticmethod
    def skill_verify(data: dict) -> dict:
        """
        Verify Skill bundle integrity.

        Args:
            data: Skill bundle dictionary

        Returns:
            Verification result
        """
        from .skill import skill_verify

        return skill_verify(data)

    def skill_install(
        self,
        data: dict,
        scope_override: Optional[str] = None,
        mode: str = "skip",
    ) -> dict:
        """
        Install a Skill bundle into this engine's storage.

        Args:
            data: Skill bundle dictionary
            scope_override: Override the Skill's default scope
            mode: Conflict resolution mode (skip/overwrite/rename)

        Returns:
            Installation result with statistics
        """
        from .skill import skill_install

        return skill_install(
            data=data,
            storage=self.storage,
            scope_override=scope_override,
            mode=mode,
        )

    def review_incoming_rules(
        self,
        incoming: List[Rule],
        target_scope: Optional[str] = None,
    ) -> dict:
        """
        Preview what would happen if incoming rules are merged.

        This is the "customs review" step — detect conflicts and suggest
        resolutions without actually modifying anything.

        Args:
            incoming: Rules to review for merge
            target_scope: Override scope for incoming rules

        Returns:
            Preview dictionary with conflicts, severity, strategy previews
        """
        from .merge_protocol import review_incoming_rules

        existing = self.storage.list_all(limit=10000)
        return review_incoming_rules(incoming, existing, target_scope=target_scope)

    def accept_rules(
        self,
        incoming: List[Rule],
        strategy: str = "negotiate",
        target_scope: Optional[str] = None,
    ) -> dict:
        """
        Accept incoming rules with merge protocol.

        Applies the merge strategy, resolves conflicts, and stores
        accepted rules. All decisions are audit-logged.

        Args:
            incoming: Rules to merge in
            strategy: Merge strategy (company_overrides/negotiate/keep_both)
            target_scope: Override scope for incoming rules

        Returns:
            MergeResult dictionary with accepted/skipped/modified + audit trail
        """
        from .merge_protocol import MergeStrategy, merge_rules

        strategy_enum = MergeStrategy(strategy)
        existing = self.storage.list_all(limit=10000)
        result = merge_rules(incoming, existing, strategy=strategy_enum, target_scope=target_scope)

        errors: List[str] = []

        for rule in result.accepted:
            try:
                self.storage._create_validated(
                    trigger=rule.trigger,
                    action=rule.action,
                    rule_type=rule.rule_type,
                    override=rule.override,
                    derived_from=rule.derived_from,
                    source_memories=rule.source_memories,
                    confidence=rule.confidence,
                    scope=rule.scope,
                )
            except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
                errors.append(f"create rule '{rule.trigger}': {e}")

        for rule_id in result.replaced_ids:
            try:
                self.storage.delete(rule_id)
            except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
                errors.append(f"delete rule '{rule_id}': {e}")

        for rule_id in result.downgrade_override_ids:
            try:
                self.storage.update(rule_id, override=False)
            except (sqlite3.IntegrityError, sqlite3.OperationalError) as e:
                errors.append(f"downgrade rule '{rule_id}': {e}")

        result_dict = result.to_dict()
        if errors:
            result_dict["errors"] = errors
        return result_dict

    def pause_rule(self, rule_id: str) -> Optional[Rule]:
        """
        Pause a rule (set status to 'paused').

        Args:
            rule_id: ID of rule to pause

        Returns:
            Updated Rule or None if not found
        """
        return self.storage.update(rule_id, status="paused")

    def resume_rule(self, rule_id: str) -> Optional[Rule]:
        """
        Resume a paused rule (set status to 'active').

        Args:
            rule_id: ID of rule to resume

        Returns:
            Updated Rule or None if not found
        """
        return self.storage.update(rule_id, status="active")

    def count_rules(self, status: Optional[str] = None) -> int:
        """
        Count total rules.

        Args:
            status: Optional status filter

        Returns:
            Count of rules
        """
        return self.storage.count(status=status)

    def check_conflicts(self, new_rule: Optional[Rule] = None) -> list:
        """
        Detect conflicts among rules.

        Args:
            new_rule: Optional new rule to check against existing

        Returns:
            List of RuleConflict objects
        """
        active_rules = self.list_rules(status="active", limit=1000)
        return RuleConflictDetector.detect(active_rules, new_rule=new_rule)

    def check_health(self) -> dict:
        """
        Comprehensive health check for rules.

        Returns:
            Dictionary with health metrics and conflict details
        """
        return RuleConflictDetector.check_health(self.storage)

    def export_rules(self, status: Optional[str] = None) -> dict:
        """
        Export all rules as a portable dictionary.

        Args:
            status: Optional status filter (export only matching rules)

        Returns:
            Dictionary with version info and list of rule dicts
        """
        rules = self.storage.list_all(status=status, limit=10000)
        return {
            "format": "carrymem-rules-v1",
            "version": __version__,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_rules": len(rules),
            "rules": [r.to_dict() for r in rules],
        }

    def import_rules(
        self,
        data: dict,
        mode: str = "skip",
    ) -> dict:
        """
        Import rules from a dictionary.

        Args:
            data: Dictionary from export_rules()
            mode: Conflict resolution mode
                - "skip": Skip rules with duplicate triggers+actions (default)
                - "overwrite": Replace existing rules with same trigger+action
                - "rename": Import with new ID even if duplicate

        Returns:
            Dictionary with import statistics
        """
        if data.get("format") != "carrymem-rules-v1":
            raise ValueError(f"Unsupported format: {data.get('format')}. " f"Expected 'carrymem-rules-v1'")

        imported_rules = data.get("rules", [])
        if len(imported_rules) > 500:
            raise ValueError(
                f"Import file contains {len(imported_rules)} rules, "
                f"maximum allowed is 500 per import. "
                f"Please split into smaller files."
            )
        stats = {"imported": 0, "skipped": 0, "overwritten": 0, "errors": []}

        existing_rules = self.storage.list_all(limit=10000)
        existing_keys = {(r.trigger, r.action, r.rule_type, r.scope): r for r in existing_rules}

        for rule_data in imported_rules:
            try:
                rule = Rule.from_dict(rule_data)
                sanitized_trigger = RuleSanitizer.validate_trigger(rule.trigger)
                sanitized_action = RuleSanitizer.validate_action(rule.action)
                RuleSanitizer.validate_rule_type(rule.rule_type)
                key = (sanitized_trigger, sanitized_action, rule.rule_type, rule.scope)

                if key in existing_keys:
                    if mode == "skip":
                        stats["skipped"] += 1
                        continue
                    elif mode == "overwrite":
                        existing_rule = existing_keys[key]
                        self.storage.update(
                            existing_rule.id,
                            trigger=sanitized_trigger,
                            action=sanitized_action,
                            rule_type=rule.rule_type,
                            override=rule.override,
                            derived_from=rule.derived_from,
                            source_memories=rule.source_memories,
                            confidence=rule.confidence,
                            scope=rule.scope,
                        )
                        stats["overwritten"] += 1
                        stats["imported"] += 1
                        continue
                    elif mode == "rename":
                        pass
                    else:
                        raise ImportModeError(f"Unknown import mode: {mode}")

                self.storage._create_validated(
                    trigger=sanitized_trigger,
                    action=sanitized_action,
                    rule_type=rule.rule_type,
                    override=rule.override,
                    derived_from=rule.derived_from,
                    source_memories=rule.source_memories,
                    confidence=rule.confidence,
                    scope=rule.scope,
                )
                stats["imported"] += 1

            except ImportModeError:
                raise
            except Exception as e:
                stats["errors"].append(str(e))

        return stats

    def suggest_rules(
        self,
        memories: list,
        memory_type: Optional[str] = None,
        max_candidates: int = 10,
    ) -> list:
        """
        Analyze memories and suggest rule candidates.

        Args:
            memories: List of memory dicts (from CarryMem.recall_memories)
            memory_type: Optional filter for specific memory type
            max_candidates: Maximum number of suggestions

        Returns:
            List of RuleCandidate objects
        """
        patterns = self.pattern_detector.detect_patterns(memories, memory_type=memory_type)
        candidates = self.candidate_generator.generate(patterns, max_candidates=max_candidates)
        return candidates

    def run_promotion(
        self,
        memories: list,
        memory_type: Optional[str] = None,
        max_candidates: int = 10,
        auto_accept: bool = False,
    ) -> dict:
        """
        Run the full promotion pipeline on memories.

        Args:
            memories: List of memory dicts from CarryMem.recall_memories
            memory_type: Optional filter for specific memory type
            max_candidates: Maximum candidates to generate
            auto_accept: If True, automatically accept all candidates

        Returns:
            Dictionary with pipeline results
        """
        return self.promotion_pipeline.run_pipeline(
            memories,
            memory_type=memory_type,
            max_candidates=max_candidates,
            auto_accept=auto_accept,
        )

    def list_pending_promotions(self, limit: int = 20) -> list:
        """List all pending promotion candidates."""
        return self.promotion_pipeline.list_pending(limit=limit)

    def accept_promotion(self, audit_id: str, note: Optional[str] = None) -> Optional[str]:
        """Accept a pending promotion candidate and create a rule."""
        return self.promotion_pipeline.accept_candidate(audit_id, note=note)

    def reject_promotion(self, audit_id: str, note: Optional[str] = None) -> bool:
        """Reject a pending promotion candidate."""
        return self.promotion_pipeline.reject_candidate(audit_id, note=note)

    def get_promotion_log(self, limit: int = 50) -> list:
        """Get full audit log of all promotion actions."""
        return self.promotion_pipeline.get_audit_log(limit=limit)

    def get_promotion_stats(self) -> dict:
        """Get promotion pipeline statistics."""
        return self.promotion_pipeline.get_stats()

    def extract_failure_lessons(
        self,
        memories: list,
        memory_type: Optional[str] = None,
    ) -> dict:
        """
        Extract failure lessons from memories and queue for review.

        Args:
            memories: List of memory dicts from CarryMem.recall_memories
            memory_type: Optional filter for specific memory type

        Returns:
            Dictionary with extraction results
        """
        return self.experience_bridge.extract_lessons(memories, memory_type=memory_type)

    def list_pending_lessons(self, limit: int = 20) -> list:
        """List all pending failure lessons awaiting review."""
        return self.experience_bridge.list_pending(limit=limit)

    def accept_lesson(
        self,
        audit_id: str,
        note: Optional[str] = None,
        trigger_override: Optional[str] = None,
        action_override: Optional[str] = None,
    ) -> Optional[str]:
        """
        Accept a pending lesson and create an avoidance rule.

        Args:
            audit_id: ID of the pending experience entry
            note: Optional review note
            trigger_override: Custom trigger (overrides extracted hint)
            action_override: Custom action (overrides extracted hint)

        Returns:
            Created rule ID, or None on failure
        """
        return self.experience_bridge.accept_lesson(
            audit_id,
            note=note,
            trigger_override=trigger_override,
            action_override=action_override,
        )

    def reject_lesson(self, audit_id: str, note: Optional[str] = None) -> bool:
        """Reject a pending failure lesson."""
        return self.experience_bridge.reject_lesson(audit_id, note=note)

    def get_lesson_log(self, limit: int = 50) -> list:
        """Get full audit log of experience→rule actions."""
        return self.experience_bridge.get_audit_log(limit=limit)

    def get_lesson_stats(self) -> dict:
        """Get experience bridge statistics."""
        return self.experience_bridge.get_stats()

    def start_refinement(
        self,
        trigger: str,
        action: str,
        rule_type: str = "avoid",
        source_rule_id: Optional[str] = None,
        source_memory_id: Optional[str] = None,
    ) -> dict:
        """Start a multi-turn rule refinement session."""
        return self.refinement_session.start_session(
            trigger,
            action,
            rule_type=rule_type,
            source_rule_id=source_rule_id,
            source_memory_id=source_memory_id,
        )

    def answer_refinement(self, session_id: str, answer: str, selected_option: Optional[str] = None) -> dict:
        """Answer a refinement question and advance the session."""
        return self.refinement_session.answer_question(session_id, answer, selected_option=selected_option)

    def confirm_refinement(self, session_id: str) -> dict:
        """Confirm a refinement session and create the refined rule."""
        return self.refinement_session.confirm_session(session_id)

    def cancel_refinement(self, session_id: str) -> bool:
        """Cancel an active refinement session."""
        return self.refinement_session.cancel_session(session_id)

    def list_refinement_sessions(self, limit: int = 20) -> list:
        """List all active refinement sessions."""
        return self.refinement_session.list_active_sessions(limit=limit)

    def get_refinement_detail(self, session_id: str) -> Optional[dict]:
        """Get full detail of a refinement session."""
        return self.refinement_session.get_session_detail(session_id)

    def get_refinement_stats(self) -> dict:
        """Get refinement session statistics."""
        return self.refinement_session.get_stats()


# Convenience exports for common patterns
__all__ = [
    "RuleEngine",
    "Rule",
    "RuleType",
    "RuleStatus",
    "DerivationSource",
    "RuleScope",
    "VALID_RULE_TYPES",
    "VALID_RULE_STATUSES",
    "VALID_DERIVATION_SOURCES",
    "VALID_RULE_SCOPES",
    "SCOPE_PRIORITY",
    "RuleSanitizer",
    "RuleLimiter",
    "RuleStorage",
    "RuleMatcher",
    "MatchResult",
    "RuleInjector",
    "RuleConflictDetector",
    "RuleConflict",
    "ConflictType",
    "ConflictSeverity",
    "ImportModeError",
    "PatternDetector",
    "MemoryPattern",
    "PatternType",
    "PatternConfidence",
    "CandidateRuleGenerator",
    "RuleCandidate",
    "PromotionPipeline",
    "PromotionAuditEntry",
    "PROMOTION_STATUS_PENDING",
    "PROMOTION_STATUS_ACCEPTED",
    "PROMOTION_STATUS_REJECTED",
    "PROMOTION_STATUS_EXPIRED",
    "FailureExperienceExtractor",
    "ExtractedLesson",
    "FailureSignal",
    "FailureConfidence",
    "ExperienceRuleBridge",
    "ExperienceAuditEntry",
    "EXPERIENCE_STATUS_PENDING",
    "EXPERIENCE_STATUS_ACCEPTED",
    "EXPERIENCE_STATUS_REJECTED",
    "EXPERIENCE_STATUS_EXPIRED",
    "RuleRefiner",
    "RefinementPhase",
    "RefinementQuestion",
    "RefinementAnswer",
    "RefinedRuleDraft",
    "QuestionType",
    "RefinementSessionManager",
    "SessionEntry",
    "SESSION_STATUS_ACTIVE",
    "SESSION_STATUS_COMPLETED",
    "SESSION_STATUS_CANCELLED",
    "SESSION_STATUS_EXPIRED",
    "MergeStrategy",
    "MergeDecision",
    "MergeConflict",
    "MergeResult",
    "skill_pack",
    "skill_verify",
    "skill_install",
]
