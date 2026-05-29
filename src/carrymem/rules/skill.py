"""
CarryMem Rules Engine — Skill Format

Defines the Skill manifest specification and operations:
- Skill packing: export rules as a portable Skill bundle
- Skill installation: import Skill with scope assignment
- Skill verification: integrity check via content hash
- Skill listing: enumerate installed Skills

Skill format: carrymem-skill-v1
  {
    "format": "carrymem-skill-v1",
    "manifest": {
      "name": "security-best-practices",
      "version": "1.0.0",
      "author": "CarryMem Team",
      "description": "Security rules for production systems",
      "scope": "company",
      "dependencies": [],
      "tags": ["security", "production"]
    },
    "signature": {
      "algorithm": "sha256",
      "hash": "abc123..."
    },
    "rules": [...],
    "templates": [...],
    "config": {}
  }
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import Rule, VALID_RULE_SCOPES

SKILL_FORMAT = "carrymem-skill-v1"
SKILL_MAX_RULES = 500


def _compute_signature(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def skill_pack(
    rules: List[Rule],
    name: str,
    version: str = "1.0.0",
    author: str = "",
    description: str = "",
    scope: str = "personal",
    dependencies: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Pack rules into a portable Skill bundle.

    Args:
        rules: List of Rule objects to include
        name: Skill name (alphanumeric + hyphens)
        version: Semantic version string
        author: Author name or organization
        description: Human-readable description
        scope: Default scope for installed rules
        dependencies: List of Skill names this depends on
        tags: Categorization tags
        config: Arbitrary configuration data

    Returns:
        Skill bundle dictionary

    Raises:
        ValueError: If validation fails
    """
    if not name or not name.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"Invalid skill name: '{name}'. Use alphanumeric + hyphens/underscores only.")

    if scope not in VALID_RULE_SCOPES:
        raise ValueError(f"Invalid scope '{scope}'. Must be one of {VALID_RULE_SCOPES}")

    if dependencies and name in dependencies:
        raise ValueError(f"Skill '{name}' cannot depend on itself")

    if dependencies:
        seen = set()
        for dep in dependencies:
            if dep in seen:
                raise ValueError(f"Duplicate dependency: '{dep}'")
            seen.add(dep)

    if not rules:
        raise ValueError("Cannot pack empty rules list into a Skill bundle")

    if len(rules) > SKILL_MAX_RULES:
        raise ValueError(
            f"Skill contains {len(rules)} rules, maximum is {SKILL_MAX_RULES}. " f"Split into smaller Skills."
        )

    rule_dicts = [r.to_dict() for r in rules]

    payload = {
        "format": SKILL_FORMAT,
        "manifest": {
            "name": name,
            "version": version,
            "author": author,
            "description": description,
            "scope": scope,
            "dependencies": dependencies or [],
            "tags": tags or [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rule_count": len(rules),
        },
        "rules": rule_dicts,
        "templates": [],
        "config": config or {},
    }

    payload_str = json.dumps(
        {
            "manifest": {
                "name": name,
                "version": version,
                "scope": scope,
            },
            "rules": rule_dicts,
            "templates": [],
            "config": payload["config"],
        },
        sort_keys=True,
    )
    payload_hash = _compute_signature(payload_str.encode("utf-8"))

    payload["signature"] = {
        "algorithm": "sha256",
        "hash": payload_hash,
    }

    return payload


def skill_verify(data: dict) -> dict:
    """
    Verify Skill bundle integrity.

    Recomputes the content hash and compares with the stored signature.

    Args:
        data: Skill bundle dictionary

    Returns:
        Verification result with valid/invalid status and details
    """
    if data.get("format") != SKILL_FORMAT:
        return {
            "valid": False,
            "reason": f"Unsupported format: {data.get('format')}. Expected '{SKILL_FORMAT}'",
        }

    signature = data.get("signature", {})
    stored_hash = signature.get("hash", "")
    algorithm = signature.get("algorithm", "sha256")

    if not stored_hash:
        return {"valid": False, "reason": "No signature found in Skill bundle"}

    payload_str = json.dumps(
        {
            "manifest": {
                "name": data.get("manifest", {}).get("name", ""),
                "version": data.get("manifest", {}).get("version", ""),
                "scope": data.get("manifest", {}).get("scope", "personal"),
            },
            "rules": data.get("rules", []),
            "templates": data.get("templates", []),
            "config": data.get("config", {}),
        },
        sort_keys=True,
    )

    if algorithm == "sha256":
        computed_hash = _compute_signature(payload_str.encode("utf-8"))
    else:
        return {"valid": False, "reason": f"Unsupported algorithm: {algorithm}"}

    if computed_hash != stored_hash:
        return {
            "valid": False,
            "reason": "Content hash mismatch — Skill bundle may have been tampered with",
            "stored_hash": stored_hash,
            "computed_hash": computed_hash,
        }

    manifest = data.get("manifest", {})
    return {
        "valid": True,
        "name": manifest.get("name", "unknown"),
        "version": manifest.get("version", "unknown"),
        "author": manifest.get("author", ""),
        "rule_count": manifest.get("rule_count", len(data.get("rules", []))),
        "scope": manifest.get("scope", "personal"),
        "dependencies": manifest.get("dependencies", []),
        "tags": manifest.get("tags", []),
    }


def skill_install(
    data: dict,
    storage,
    scope_override: Optional[str] = None,
    mode: str = "skip",
) -> dict:
    verification = skill_verify(data)
    if not verification["valid"]:
        return {"installed": 0, "errors": [verification["reason"]]}

    manifest = data.get("manifest", {})
    target_scope = scope_override or manifest.get("scope", "personal")

    if target_scope not in VALID_RULE_SCOPES:
        return {"installed": 0, "errors": [f"Invalid scope: {target_scope}"]}

    dependencies = manifest.get("dependencies", [])
    if dependencies:
        installed_skill_names = set()
        existing_rules = storage.list_all(limit=10000)
        for r in existing_rules:
            if hasattr(r, "metadata") and isinstance(r.metadata, dict):
                skill_name = r.metadata.get("_skill_name")
                if skill_name:
                    installed_skill_names.add(skill_name)
        missing = [d for d in dependencies if d not in installed_skill_names]
        if missing:
            return {
                "installed": 0,
                "errors": [f"Missing dependencies: {', '.join(missing)}"],
                "missing_dependencies": missing,
            }

    imported_rules = data.get("rules", [])
    if len(imported_rules) > SKILL_MAX_RULES:
        return {
            "installed": 0,
            "errors": [f"Too many rules: {len(imported_rules)} (max {SKILL_MAX_RULES})"],
        }

    if not imported_rules:
        return {"installed": 0, "errors": ["Cannot install empty Skill bundle"]}

    from .limiter import RuleLimiter

    current_count = storage.count()
    try:
        RuleLimiter.check_total_limit(current_count + len(imported_rules))
    except ValueError as e:
        return {"installed": 0, "errors": [str(e)]}

    stats = {
        "installed": 0,
        "skipped": 0,
        "overwritten": 0,
        "errors": [],
        "skill_name": manifest.get("name", "unknown"),
        "scope": target_scope,
    }

    from .sanitizer import RuleSanitizer

    existing_rules = storage.list_all(limit=10000)
    existing_keys = {(r.trigger, r.action, r.rule_type, r.scope): r for r in existing_rules}
    existing_keys_no_scope = {(r.trigger, r.action, r.rule_type): r for r in existing_rules}

    for rule_data in imported_rules:
        try:
            rule = Rule.from_dict(rule_data)
            rule.scope = target_scope

            sanitized_trigger = RuleSanitizer.validate_trigger(rule.trigger)
            sanitized_action = RuleSanitizer.validate_action(rule.action)
            RuleSanitizer.validate_rule_type(rule.rule_type)

            key = (sanitized_trigger, sanitized_action, rule.rule_type, target_scope)
            key_no_scope = (sanitized_trigger, sanitized_action, rule.rule_type)

            if key in existing_keys:
                if mode == "skip":
                    stats["skipped"] += 1
                    continue
                elif mode == "overwrite":
                    existing_rule = existing_keys[key]
                    storage.update(
                        existing_rule.id,
                        trigger=sanitized_trigger,
                        action=sanitized_action,
                        rule_type=rule.rule_type,
                        override=rule.override,
                        derived_from=rule.derived_from,
                        source_memories=rule.source_memories,
                        confidence=rule.confidence,
                        scope=target_scope,
                        metadata={"_skill_name": manifest.get("name", "unknown")},
                    )
                    stats["overwritten"] += 1
                    stats["installed"] += 1
                    continue
                elif mode == "rename":
                    pass
                else:
                    stats["errors"].append(f"Unknown import mode: {mode}")
                    break
            elif key_no_scope in existing_keys_no_scope and target_scope != existing_keys_no_scope[key_no_scope].scope:
                pass

            storage._create_validated(
                trigger=sanitized_trigger,
                action=sanitized_action,
                rule_type=rule.rule_type,
                override=rule.override,
                derived_from=rule.derived_from,
                source_memories=rule.source_memories,
                confidence=rule.confidence,
                scope=target_scope,
                metadata={"_skill_name": manifest.get("name", "unknown")},
            )
            stats["installed"] += 1
        except Exception as e:
            stats["errors"].append(f"Rule '{rule_data.get('trigger', '?')}': {e}")

    return stats
