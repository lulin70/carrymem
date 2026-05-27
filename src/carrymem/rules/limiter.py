"""
CarryMem Rules Engine — Usage Limiter

Enforces usage limits to prevent:
- Global rule hijacking (too many trigger="*" rules)
- Database bloat (too many total rules)
- Per-scene rule overload
- Rule creation rate limiting
"""

from typing import List, Optional
from datetime import datetime, timezone


class RuleLimiter:
    """
    Enforces usage limits on rules to maintain system health.

    This class implements multiple limit checks to prevent abuse:
    1. Global rule limits (prevent behavior hijacking)
    2. Total rule limits (prevent database bloat)
    3. Per-type limits (balanced rule distribution)
    4. Rate limiting (prevent spam)

    Usage:
        limiter = RuleLimiter()
        limiter.check_before_create(storage, new_rule_trigger)
    """

    # Hard limits (cannot be exceeded)
    MAX_GLOBAL_RULES = 3  # Maximum trigger="*" rules
    MAX_TOTAL_RULES = 200  # Maximum total rules in database

    # Soft limits (warnings but not blocking)
    SOFT_LIMIT_TOTAL_RULES = 150  # Warning threshold for total rules
    SOFT_LIMIT_PER_TYPE = 50  # Warning threshold per rule type

    # Rate limiting
    MAX_RULES_PER_HOUR = 20  # Maximum rules created in 1 hour window
    MAX_RULES_PER_DAY = 50  # Maximum rules created in 24 hour window

    @classmethod
    def check_global_limit(cls, active_rules: List) -> None:
        """
        Check if global rule limit has been reached.

        Global rules (trigger="*") apply to ALL scenes and can hijack
        AI behavior. We strictly limit these to prevent abuse.

        Args:
            active_rules: List of currently active rules

        Raises:
            ValueError: If global rule limit is reached or exceeded

        Examples:
            >>> # If there are already 3 global rules:
            >>> RuleLimiter.check_global_limit(active_rules)
            ValueError: Maximum number of global rules (3) reached
        """
        global_rules = [
            r for r in active_rules if r.trigger == "*" and r.status == "active"
        ]

        if len(global_rules) >= cls.MAX_GLOBAL_RULES:
            raise ValueError(
                f"Maximum number of global rules ({cls.MAX_GLOBAL_RULES}) reached. "
                f"Global rules apply to all scenes and should be used sparingly. "
                f"Consider using more specific triggers instead."
            )

    @classmethod
    def check_total_limit(cls, total_count: int) -> None:
        """
        Check if total rule count exceeds limits.

        Args:
            total_count: Current total number of rules in database

        Raises:
            ValueError: If hard limit exceeded
            UserWarning: If soft limit exceeded (logged but not raised)
        """
        import warnings

        if total_count >= cls.MAX_TOTAL_RULES:
            raise ValueError(
                f"Maximum total rules ({cls.MAX_TOTAL_RULES}) reached. "
                f"Cannot create additional rules. Consider deprecating unused rules."
            )

        if total_count >= cls.SOFT_LIMIT_TOTAL_RULES:
            warnings.warn(
                f"Warning: You have {total_count} rules (soft limit: {
    cls.SOFT_LIMIT_TOTAL_RULES}). "
                f"Consider reviewing and cleaning up old rules.",
                UserWarning,
                stacklevel=2,
            )

    @classmethod
    def check_per_type_limit(
        cls, rules_by_type: dict, new_rule_type: str
    ) -> None:
        """
        Check if adding a rule would exceed per-type limits.

        Ensures balanced distribution across rule types to prevent
        over-reliance on a single type.

        Args:
            rules_by_type: Dictionary mapping rule_type → count
            new_rule_type: Type of the rule being created

        Raises:
            ValueError: If per-type hard limit would be exceeded
        """
        current_count = rules_by_type.get(new_rule_type, 0)

        if current_count >= cls.SOFT_LIMIT_PER_TYPE:
            import warnings

            warnings.warn(
                f"Warning: You have {current_count} '{new_rule_type}' rules. "
                f"Consider diversifying your rule types for better coverage.",
                UserWarning,
                stacklevel=2,
            )

    @classmethod
    def check_rate_limit(
        cls,
        recent_rules: List,
        time_window_hours: float = 1.0,
    ) -> None:
        """
        Check if user is creating rules too quickly.

        Prevents accidental spam or automated abuse of the rule system.

        Args:
            recent_rules: Rules created within the time window
            time_window_hours: Time window to check (default: 1 hour)

        Raises:
            ValueError: If rate limit exceeded
        """
        now = datetime.now(timezone.utc)

        # Filter rules within time window
        cutoff = now.timestamp() - (time_window_hours * 3600)
        rules_in_window = []
        for r in recent_rules:
            try:
                rule_time = datetime.fromisoformat(r.created_at).timestamp()
                if rule_time > cutoff:
                    rules_in_window.append(r)
            except (ValueError, TypeError):
                continue

        # Check hourly limit
        if time_window_hours <= 1.0 and len(rules_in_window) >= cls.MAX_RULES_PER_HOUR:
            raise ValueError(
                f"Rate limit exceeded: {cls.MAX_RULES_PER_HOUR} rules per hour maximum. "
                f"Please wait before creating more rules."
            )

        # Check daily limit (if checking 24h window)
        if time_window_hours >= 24.0 and len(rules_in_window) >= cls.MAX_RULES_PER_DAY:
            raise ValueError(
                f"Rate limit exceeded: {cls.MAX_RULES_PER_DAY} rules per day maximum. "
                f"Please wait until tomorrow to create more rules."
            )

    @classmethod
    def validate_new_rule(
        cls,
        storage,
        new_rule,
        recent_rules: Optional[List] = None,
    ) -> bool:
        """
        Comprehensive validation before creating a new rule.

        Runs all limit checks in sequence and returns True only if
        all checks pass.

        Args:
            storage: RuleStorage instance for querying existing rules
            new_rule: The Rule object being created
            recent_rules: Optionally provide recently created rules for rate limiting

        Returns:
            True if validation passes

        Raises:
            ValueError: If any limit check fails
        """
        active_rules = storage.list_all(status="active", limit=1000)
        total_count = storage.count()
        cls.check_total_limit(total_count)

        if new_rule.trigger == "*":
            cls.check_global_limit(active_rules)

        rules_by_type = {}
        for r in active_rules:
            rules_by_type[r.rule_type] = rules_by_type.get(r.rule_type, 0) + 1

        cls.check_per_type_limit(rules_by_type, new_rule.rule_type)

        # Rate limiting (if recent rules provided)
        if recent_rules is not None:
            cls.check_rate_limit(recent_rules)

        return True

    @classmethod
    def get_usage_stats(cls, storage) -> dict:
        """
        Generate usage statistics for monitoring.

        Args:
            storage: RuleStorage instance

        Returns:
            Dictionary with usage statistics
        """
        all_rules = storage.list_all()
        active_rules = [r for r in all_rules if r.status == "active"]
        global_rules = [r for r in active_rules if r.trigger == "*"]

        # Count by type
        type_counts = {}
        for r in active_rules:
            type_counts[r.rule_type] = type_counts.get(r.rule_type, 0) + 1

        # Count by status
        status_counts = {}
        for r in all_rules:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        return {
            "total_rules": len(all_rules),
            "active_rules": len(active_rules),
            "global_rules": len(global_rules),
            "global_limit": f"{len(global_rules)}/{cls.MAX_GLOBAL_RULES}",
            "total_limit": f"{len(all_rules)}/{cls.MAX_TOTAL_RULES}",
            "rules_by_type": type_counts,
            "rules_by_status": status_counts,
            "utilization_percent": round(
                (len(all_rules) / cls.MAX_TOTAL_RULES) * 100, 1
            ),
        }
