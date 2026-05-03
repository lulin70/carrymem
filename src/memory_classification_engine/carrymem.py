"""CarryMem — Main entry point for the portable AI memory layer.

Usage:
    # Mode 1: Classify + Store (default SQLite)
    from memory_classification_engine import CarryMem
    cm = CarryMem()
    result = cm.classify_and_remember("I prefer dark mode")

    # Mode 2: Pure classification (no storage)
    cm = CarryMem(storage=None)
    result = cm.classify_message("I prefer dark mode")

    # Mode 3: Custom storage adapter
    from carrymem.adapters import SQLiteAdapter
    cm = CarryMem(storage=SQLiteAdapter("/path/to/custom.db"))

    # Mode 4: With knowledge base (Obsidian)
    from carrymem.adapters import ObsidianAdapter
    cm = CarryMem(knowledge_adapter=ObsidianAdapter("/path/to/vault"))
    cm.index_knowledge()
    results = cm.recall_from_knowledge("Python design patterns")
"""

from typing import Any, Dict, List, Optional
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from memory_classification_engine.engine import MemoryClassificationEngine
from memory_classification_engine.adapters.base import MemoryEntry, StorageAdapter, StoredMemory
from memory_classification_engine.adapters.sqlite_adapter import SQLiteAdapter
from memory_classification_engine.adapters.obsidian_adapter import ObsidianAdapter


def _validate_file_path(path: str, allowed_base: str = None) -> str:
    resolved = os.path.realpath(os.path.expanduser(path))
    if allowed_base:
        allowed = os.path.realpath(allowed_base)
        if not resolved.startswith(allowed + os.sep) and resolved != allowed:
            raise ValueError(f"Path escapes allowed directory: {path}")
    else:
        if ".." in path:
            raise ValueError(f"Path traversal not allowed: {path}")
    return resolved


from memory_classification_engine.adapters.loader import load_adapter
from memory_classification_engine.utils.logger import logger
from memory_classification_engine.utils.validators import (
    validate_message, validate_context, validate_language,
    validate_limit, validate_storage_key, validate_query,
)
from memory_classification_engine.__version__ import __version__ as _version
from memory_classification_engine.exceptions import (
    StorageNotConfiguredError as _StorageNotConfiguredError,
    KnowledgeNotConfiguredError as _KnowledgeNotConfiguredError,
    ValidationError,
)

try:
    from memory_classification_engine.security.input_validator import InputValidator
    _import_validator = InputValidator(strict_mode=False)
except ImportError:
    _import_validator = None


class StorageNotConfiguredError(_StorageNotConfiguredError):
    def __init__(self):
        super().__init__(
            "Storage adapter not configured. "
            "Use CarryMem(storage='sqlite') or CarryMem(storage=YourAdapter()) "
            "to enable storage features."
        )


class KnowledgeNotConfiguredError(_KnowledgeNotConfiguredError):
    def __init__(self):
        super().__init__(
            "Knowledge adapter not configured. "
            "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path/to/vault')) "
            "to enable knowledge base features."
        )


class CarryMem:
    """CarryMem — Portable AI Memory Layer.

    Makes AI agents remember users. Classification is core, storage is swappable,
    works out of the box. Knowledge base is read-only, memories are read-write.
    Recall priority: memories > knowledge base.
    """

    def __init__(
        self,
        storage: Optional[Any] = "sqlite",
        db_path: Optional[str] = None,
        knowledge_adapter: Optional[StorageAdapter] = None,
        namespace: str = "default",
        config: Optional[Dict] = None,
        encryption_key: Optional[str] = None,
    ):
        self._engine = MemoryClassificationEngine()
        self._namespace = namespace

        if db_path is None:
            db_path = os.environ.get("MCE_DATA_PATH") or os.environ.get("CARRYMEM_DB_PATH")

        if storage is None:
            self._adapter = None
        elif storage == "sqlite":
            self._adapter = SQLiteAdapter(
                db_path=db_path, namespace=namespace,
                encryption_key=encryption_key,
            )
        elif isinstance(storage, StorageAdapter):
            self._adapter = storage
        elif isinstance(storage, str):
            adapter_cls = load_adapter(storage)
            if adapter_cls is None:
                raise ValueError(
                    f"Unknown adapter: {storage!r}. "
                    "Use 'sqlite', 'obsidian', a StorageAdapter instance, "
                    "or install a plugin that registers this adapter name."
                )
            if storage == "obsidian":
                raise ValueError(
                    "ObsidianAdapter requires a vault_path. "
                    "Use CarryMem(knowledge_adapter=ObsidianAdapter('/path/to/vault')) instead."
                )
            else:
                self._adapter = adapter_cls()
        else:
            raise ValueError(
                f"Invalid storage type: {storage!r}. "
                "Use None, 'sqlite', or a StorageAdapter instance."
            )

        self._knowledge_adapter = knowledge_adapter
        self._rule_engine = None

    @property
    def rule_engine(self):
        if self._rule_engine is None:
            from .rules import RuleEngine
            db_path = self._adapter.db_path if hasattr(self._adapter, 'db_path') else None
            self._rule_engine = RuleEngine(db_path=db_path)
        return self._rule_engine

    def close(self):
        if self._rule_engine:
            self._rule_engine = None
        if self._adapter and hasattr(self._adapter, 'close'):
            self._adapter.close()
        if self._knowledge_adapter and hasattr(self._knowledge_adapter, 'close'):
            self._knowledge_adapter.close()

    def clear_cache(self) -> None:
        if self._adapter and hasattr(self._adapter, '_cache') and self._adapter._cache:
            self._adapter._cache.clear()

    def backup(self, backup_dir: Optional[str] = None) -> Dict[str, Any]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Backup only supported with SQLiteAdapter"}

        from memory_classification_engine.backup import BackupManager
        db_path = self._adapter._db_path
        if db_path == ":memory:":
            return {"error": "Cannot backup in-memory database"}

        manager = BackupManager(db_path, backup_dir=backup_dir)
        try:
            path = manager.create_backup()
            return {"backed_up": True, "path": path}
        except Exception as e:
            return {"backed_up": False, "error": str(e)}

    def list_backups(self, backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return []

        from memory_classification_engine.backup import BackupManager
        db_path = self._adapter._db_path
        manager = BackupManager(db_path, backup_dir=backup_dir)
        return manager.list_backups()

    def restore_backup(self, backup_path: str) -> Dict[str, Any]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Restore only supported with SQLiteAdapter"}

        from memory_classification_engine.backup import BackupManager
        db_path = self._adapter._db_path
        if db_path == ":memory:":
            return {"error": "Cannot restore to in-memory database"}

        manager = BackupManager(db_path)
        try:
            manager.restore_backup(backup_path)
            return {"restored": True, "backup_path": backup_path}
        except Exception as e:
            return {"restored": False, "error": str(e)}

    def get_audit_log(
        self,
        operation: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if not self._adapter or not isinstance(self._adapter, SQLiteAdapter):
            return []

        if not self._adapter._audit:
            return []

        return self._adapter._audit.query(
            operation=operation,
            namespace=self._namespace,
            since=since,
            until=until,
            source=source,
            limit=limit,
        )

    def merge_memories(
        self,
        namespaces: Optional[List[str]] = None,
        strategy: str = "latest_wins",
        conflict_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        from memory_classification_engine.merge import merge_memories as _merge

        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            return {"error": "Merge only supported with SQLiteAdapter"}

        ns_list = namespaces or [self._namespace]
        all_memories = []
        for ns in ns_list:
            results = self._adapter.recall("", limit=10000, namespaces=[ns])
            all_memories.extend([r.to_dict() for r in results])

        conflicts_before = len(all_memories)
        merged = _merge(
            memories=all_memories,
            strategy=strategy,
            conflict_callback=conflict_callback,
        )
        duplicates_removed = conflicts_before - len(merged)

        return {
            "total_input": conflicts_before,
            "total_output": len(merged),
            "duplicates_removed": duplicates_removed,
            "strategy": strategy,
            "namespaces": ns_list,
            "memories": merged,
        }

    def update_memory(
        self,
        storage_key: str,
        new_content: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        result = self._adapter.update_memory(storage_key, new_content, reason)
        if result is None:
            return {"updated": False, "error": f"Memory not found: {storage_key}"}

        if self._adapter._cache:
            self._adapter._cache.invalidate()

        return {
            "updated": True,
            "storage_key": result.storage_key,
            "version": result.version,
            "content": result.content,
        }

    def get_memory_history(
        self,
        storage_key: str,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        return self._adapter.get_memory_history(storage_key)

    def rollback_memory(
        self,
        storage_key: str,
        version: int,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            raise ValueError("Memory versioning only supported with SQLiteAdapter")

        result = self._adapter.rollback_memory(storage_key, version)
        if result is None:
            return {"rolled_back": False, "error": f"Memory or version not found"}

        if self._adapter._cache:
            self._adapter._cache.invalidate()

        return {
            "rolled_back": True,
            "storage_key": result.storage_key,
            "version": result.version,
            "content": result.content,
        }

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @property
    def namespace(self) -> str:
        return self._namespace

    @property
    def engine(self) -> MemoryClassificationEngine:
        return self._engine

    @property
    def adapter(self) -> Optional[StorageAdapter]:
        return self._adapter

    @property
    def storage(self) -> Optional[StorageAdapter]:
        return self._adapter

    @property
    def knowledge_adapter(self) -> Optional[StorageAdapter]:
        return self._knowledge_adapter

    def index_knowledge(self) -> Dict[str, Any]:
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        if isinstance(self._knowledge_adapter, ObsidianAdapter):
            return self._knowledge_adapter.index_vault()

        return {"error": "Knowledge adapter does not support indexing"}

    def recall_from_knowledge(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self._knowledge_adapter:
            raise KnowledgeNotConfiguredError()

        results = self._knowledge_adapter.recall(query, filters=filters, limit=limit)
        if isinstance(results, list) and results and isinstance(results[0], dict):
            return results
        return [r.to_dict() if hasattr(r, 'to_dict') else r for r in results]

    def recall_all(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        namespaces: Optional[List[str]] = None,
        include_rules: bool = True,
    ) -> Dict[str, Any]:
        memory_results = []
        knowledge_results = []
        rule_results = []

        if include_rules:
            try:
                rule_engine = self.rule_engine
                matches = rule_engine.match(query, limit=min(limit, 5), increment_count=False)
                rule_results = [
                    {
                        "rule_id": m.rule.id,
                        "trigger": m.rule.trigger,
                        "action": m.rule.action,
                        "rule_type": m.rule.rule_type,
                        "override": m.rule.override,
                        "score": m.score,
                        "match_type": m.match_type,
                    }
                    for m in matches
                ]
            except Exception as e:
                logger.warning(f"Rule engine failed for recall_all: {e}")
                rule_results = []

        if self._adapter:
            try:
                if isinstance(self._adapter, SQLiteAdapter) and namespaces:
                    stored = self._adapter.recall(
                        query or "", filters=filters, limit=limit, namespaces=namespaces,
                    )
                    memory_results = [r.to_dict() for r in stored]
                else:
                    memory_results = self.recall_memories(query=query, filters=filters, limit=limit)
            except Exception as e:
                logger.warning(f"Failed to recall memories for prompt: {e}")
                memory_results = []

        if self._knowledge_adapter:
            try:
                knowledge_results = self.recall_from_knowledge(query=query, filters=filters, limit=limit)
            except Exception as e:
                logger.warning(f"Failed to recall from knowledge base: {e}")
                knowledge_results = []

        return {
            "rules": rule_results,
            "memories": memory_results,
            "knowledge": knowledge_results,
            "rule_count": len(rule_results),
            "memory_count": len(memory_results),
            "knowledge_count": len(knowledge_results),
            "total_count": len(rule_results) + len(memory_results) + len(knowledge_results),
            "namespace": self._namespace,
            "priority": "rules > memory > knowledge",
        }

    def classify_message(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        validate_message(message)
        validate_context(context)
        validate_language(language)
        result = self._engine.process_message(message, context=context, language=language)

        matches = result.get("matches", [])
        entries = []
        for m in matches:
            entry = MemoryEntry(
                id=m.get("id", ""),
                type=m.get("memory_type") or m.get("type", "unknown"),
                content=m.get("content", ""),
                confidence=m.get("confidence", 0.0),
                tier=m.get("tier", 2),
                source_layer=m.get("source_layer", "unknown"),
                reasoning=m.get("reasoning", ""),
                suggested_action=m.get("suggested_action", "store"),
                recall_hint=m.get("recall_hint"),
                metadata=m.get("metadata", {}),
            )
            entries.append(entry)

        return {
            "should_remember": len(entries) > 0,
            "entries": [e.to_dict() for e in entries],
            "summary": {
                "total_entries": len(entries),
                "by_type": self._count_by_type(entries),
            },
        }

    def classify_and_remember(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not message or not message.strip():
            raise ValueError("Message cannot be empty")

        if len(message) > 50000:
            raise ValueError(f"Message too long: {len(message)} chars (max 50000)")

        classify_result = self.classify_message(message, context=context, language=language)

        if not classify_result["should_remember"]:
            return {
                **classify_result,
                "stored": False,
                "storage_keys": [],
            }

        stored_memories = []
        storage_keys = []
        updated_memories = []
        for entry_dict in classify_result["entries"]:
            entry = MemoryEntry.from_dict(entry_dict)
            if entry.suggested_action == "store":
                try:
                    if entry.type == "correction":
                        updated = self._handle_correction(entry)
                        if updated:
                            updated_memories.append(updated)

                    stored = self._adapter.remember(entry)
                    stored_memories.append(stored.to_dict())
                    storage_keys.append(stored.storage_key)
                except Exception as e:
                    from memory_classification_engine.utils.logger import logger
                    logger.warning(f"Failed to store memory: {e}")
                    continue

        auto_rules = []
        try:
            auto_rules = self._auto_suggest_rules(stored_memories)
        except Exception as e:
            logger.debug(f"Auto rule suggestion skipped: {e}")

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
                        if storage_key and hasattr(self._adapter, 'update_memory'):
                            try:
                                reason = f"Corrected by: {content[:100]}"
                                self._adapter.update_memory(storage_key, content, reason)
                                updated_info = {
                                    "storage_key": storage_key,
                                    "old_content": mem.get("content", "")[:100],
                                    "new_content": content[:100],
                                    "reason": reason,
                                }
                            except Exception:
                                pass
                        break
        except Exception:
            pass

        try:
            engine = self.rule_engine
            rules = engine.list_rules(status="active", limit=50)
            for rule in rules:
                rule_content = (rule.trigger + " " + rule.action).lower()
                overlap = sum(1 for kw in keywords if kw in rule_content and len(kw) > 1)
                if overlap >= 2:
                    try:
                        engine.update_rule(rule.id, action=content[:200])
                        if updated_info is None:
                            updated_info = {"rule_updated": rule.id, "new_action": content[:100]}
                        else:
                            updated_info["rule_updated"] = rule.id
                    except Exception:
                        pass
                    break
        except Exception:
            pass

        return updated_info

    def _auto_suggest_rules(self, stored_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not stored_memories:
            return []

        rule_worthy_types = {"user_preference", "correction", "decision", "task_pattern", "sentiment_marker", "fact_declaration"}
        candidates = []

        try:
            engine = self.rule_engine

            for mem in stored_memories:
                mem_type = mem.get("type", "")
                if mem_type not in rule_worthy_types:
                    continue

                content = mem.get("content", "")
                if not content or len(content.strip()) < 3:
                    continue

                trigger = self._extract_trigger(content, mem_type)
                action = self._extract_action(content, mem_type)
                rule_type = self._infer_rule_type(mem_type)

                if trigger and action:
                    condition = self._extract_condition(content)
                    candidate = {
                        "trigger": trigger,
                        "action": action,
                        "rule_type": rule_type,
                        "scope": "personal",
                        "override": mem_type in ("correction", "decision"),
                        "confidence": mem.get("confidence", 0.7),
                        "source_memory_type": mem_type,
                        "source_memory_content": content[:200],
                    }
                    if condition:
                        candidate["condition"] = condition
                    candidates.append(candidate)

            existing_memories = self.recall_memories(limit=100)
            if len(existing_memories) >= 5:
                try:
                    suggested = engine.suggest_rules(existing_memories, max_candidates=2)
                    for s in suggested[:2]:
                        if not s.trigger or not s.action:
                            continue
                        if s.action == s.trigger:
                            continue
                        if len(s.action.split()) <= 2 and any(c in s.action for c in (',', '，')):
                            continue
                        if s.trigger in ("related scenarios", "tech selection or solution design",
                                         "general context", "偏好选择", "通用场景"):
                            continue
                        candidate_dict = {
                            "trigger": s.trigger,
                            "action": s.action,
                            "rule_type": s.rule_type if hasattr(s, 'rule_type') else "prefer",
                            "scope": "personal",
                            "override": False,
                            "confidence": min(s.confidence if hasattr(s, 'confidence') else 0.6, 0.85),
                            "source": "pattern_detection",
                        }
                        if candidate_dict not in candidates:
                            candidates.append(candidate_dict)
                except Exception:
                    pass

            try:
                implicit = self._detect_implicit_preferences()
                for imp in implicit:
                    if not any(c.get("trigger") == imp["trigger"] for c in candidates):
                        candidates.append(imp)
            except Exception:
                pass

        except Exception as e:
            logger.debug(f"Rule suggestion engine unavailable: {e}")

        return candidates[:3]

    def _detect_implicit_preferences(self) -> List[Dict[str, Any]]:
        try:
            memories = self.recall_memories(limit=50)
        except Exception:
            return []

        if len(memories) < 3:
            return []

        import re
        tech_pattern = re.compile(
            r'\b(?:javascript|typescript|python|java|react|vue|angular|postgresql|mysql|sqlite|'
            r'mongodb|redis|docker|kubernetes|aws|gcp|azure|node\.js|go|rust|swift|kotlin)\b',
            re.IGNORECASE,
        )

        tech_counts = {}
        for mem in memories:
            content = mem.get("content", "").lower()
            for match in tech_pattern.finditer(content):
                tech = match.group(0).lower()
                tech_counts[tech] = tech_counts.get(tech, 0) + 1

        domain_groups = {
            "language": {"python", "java", "javascript", "typescript", "go", "rust", "swift", "kotlin", "node.js"},
            "frontend": {"react", "vue", "angular"},
            "database": {"postgresql", "mysql", "sqlite", "mongodb", "redis"},
            "cloud": {"aws", "gcp", "azure"},
            "container": {"docker", "kubernetes"},
        }

        trigger_map = {
            "language": "programming language selection",
            "frontend": "frontend framework selection",
            "database": "database selection",
            "cloud": "cloud platform selection",
            "container": "containerization strategy",
        }

        implicit = []
        for domain, techs in domain_groups.items():
            domain_total = sum(tech_counts.get(t, 0) for t in techs)
            if domain_total < 3:
                continue

            top_tech = max(techs, key=lambda t: tech_counts.get(t, 0))
            top_count = tech_counts.get(top_tech, 0)

            if top_count >= 3:
                ratio = top_count / domain_total
                if ratio >= 0.5:
                    implicit.append({
                        "trigger": trigger_map.get(domain, domain),
                        "action": f"prefer {top_tech}",
                        "rule_type": "prefer",
                        "scope": "personal",
                        "override": False,
                        "confidence": min(0.5 + ratio * 0.3, 0.9),
                        "source": "implicit_preference",
                        "domain": domain,
                        "top_tech": top_tech,
                        "ratio": round(ratio, 2),
                    })

        return implicit

    def _extract_trigger(self, content: str, mem_type: str) -> str:
        import re
        content_lower = content.lower()

        trigger_map = [
            (r'\b(?:javascript|typescript|python|java|go|rust|swift|kotlin|c\+\+|ruby|php)\b',
             lambda m: "programming language selection"),
            (r'\b(?:react|vue|angular|svelte|next\.js|nuxt)\b',
             lambda m: "frontend framework selection"),
            (r'\b(?:postgresql|mysql|sqlite|mongodb|redis|dynamodb|cassandra|elasticsearch)\b',
             lambda m: "database selection"),
            (r'\b(?:docker|kubernetes|terraform|ansible|puppet|chef)\b',
             lambda m: "infrastructure and deployment"),
            (r'\b(?:aws|gcp|azure|digitalocean|heroku)\b',
             lambda m: "cloud platform selection"),
            (r'(?:dark\s*mode|light\s*mode|theme|ui\s*theme)',
             lambda m: "UI theme and appearance"),
            (r'\b(?:vim|emacs|vscode|intellij|pycharm|sublime|neovim)\b',
             lambda m: "editor and IDE selection"),
            (r'\b(?:terminal|gui|cli|command\s*line|tui)\b',
             lambda m: "interface preference"),
            (r'\b(?:ssl|tls|https|oauth|jwt|encryption|authentication|security)\b',
             lambda m: "security and authentication"),
            (r'\b(?:rest|graphql|grpc|websocket|api\s*design)\b',
             lambda m: "API design and protocol"),
            (r'\b(?:microservice|monolith|serverless|soa)\b',
             lambda m: "architecture pattern selection"),
            (r'\b(?:test|testing|unit\s*test|integration\s*test|tdd|bdd)\b',
             lambda m: "testing strategy"),
            (r'\b(?:git|github|gitlab|bitbucket|version\s*control)\b',
             lambda m: "version control workflow"),
            (r'\b(?:ci|cd|pipeline|continuous\s*integration|continuous\s*deployment)\b',
             lambda m: "CI/CD pipeline configuration"),
        ]

        for pattern, resolver in trigger_map:
            if re.search(pattern, content_lower):
                return resolver(None)

        if mem_type == "correction":
            return "error prevention and code review"
        if mem_type == "decision":
            return "project decision making"
        if mem_type == "task_pattern":
            return "workflow and task execution"
        if mem_type == "sentiment_marker":
            return "user sentiment and feedback"
        if mem_type == "fact_declaration":
            return "factual reference"

        return "general context"

    def _extract_condition(self, content: str) -> str:
        import re
        condition_patterns = [
            (r'如果.{0,5}?([^.，！？\n]+?)(?:的话|就|则|时|的时候)', 1),
            (r'当.{0,5}?([^.，！？\n]+?)(?:的时候|时|则)', 1),
            (r'(?:要是|假如|若).{0,5}?([^.，！？\n]+?)(?:的话|就|则)', 1),
            (r'if\s+(.+?)(?:\s+then|\s*,|\s*$)', 1),
            (r'when\s+(.+?)(?:\s+then|\s*,|\s*$)', 1),
            (r'(?:小项目|大项目|小团队|大团队|小规模|大规模)', 0),
        ]

        for pattern, group in condition_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                if group == 0:
                    return match.group(0)
                return match.group(group).strip()

        return ""

    def _extract_action(self, content: str, mem_type: str) -> str:
        import re
        content_lower = content.lower()

        prefer_match = re.search(
            r'(?:prefer|like|love|favor|favour|want|choose|use|prefer\s+to\s+use)\s+(.+?)(?:\.|,|;|$)',
            content_lower,
        )
        if prefer_match and mem_type == "user_preference":
            action_text = prefer_match.group(1).strip()
            if len(action_text) > 3:
                return f"use {action_text}"

        avoid_match = re.search(
            r'(?:avoid|don\'t|do not|never|hate|dislike|stop)\s+(.+?)(?:\.|,|;|$)',
            content_lower,
        )
        if avoid_match:
            action_text = avoid_match.group(1).strip()
            if len(action_text) > 3:
                return f"avoid {action_text}"

        always_match = re.search(
            r'(?:always|must|should|need\s+to|make\s+sure)\s+(.+?)(?:\.|,|;|$)',
            content_lower,
        )
        if always_match:
            action_text = always_match.group(1).strip()
            if len(action_text) > 3:
                return f"always {action_text}"

        tech_preference = re.search(
            r'\b(?:javascript|typescript|python|java|react|vue|angular|postgresql|mysql|'
            r'sqlite|mongodb|redis|docker|kubernetes|aws|gcp|azure|go|rust|swift|kotlin)\b',
            content_lower,
        )
        if tech_preference and mem_type == "user_preference":
            tech = tech_preference.group(0)
            over_match = re.search(
                r'(?:over|instead\s+of|rather\s+than|vs\.?|compared\s+to)\s+(\w+)',
                content_lower,
            )
            if over_match:
                return f"prefer {tech} over {over_match.group(1)}"
            return f"prefer {tech}"

        if mem_type == "correction":
            fix_match = re.search(
                r'(?:should\s+(?:be|use)|fix|correct|change|replace)\s+(.+?)(?:\.|,|;|$)',
                content_lower,
            )
            if fix_match:
                return f"avoid {fix_match.group(1).strip()}"
            return f"avoid repeating this mistake"

        if mem_type == "decision":
            dec_match = re.search(
                r'(?:decided|decision|chose|chosen|will\s+use|going\s+with)\s+(.+?)(?:\.|,|;|$)',
                content_lower,
            )
            if dec_match:
                return f"follow decision: {dec_match.group(1).strip()}"
            return f"follow established decision"

        if mem_type == "task_pattern":
            return f"apply this workflow pattern"

        if mem_type == "sentiment_marker":
            return f"consider this feedback"

        if mem_type == "fact_declaration":
            return f"reference this fact"

        return f"apply this preference"

    def _infer_rule_type(self, mem_type: str) -> str:
        mapping = {
            "user_preference": "prefer",
            "correction": "avoid",
            "decision": "always",
            "task_pattern": "prefer",
            "sentiment_marker": "avoid",
            "fact_declaration": "prefer",
        }
        return mapping.get(mem_type, "prefer")

    def recall_memories(
        self,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_query(query)
        validate_limit(limit)
        results = self._adapter.recall(query or "", filters=filters, limit=limit)
        return [r.to_dict() for r in results]

    def forget_memory(self, memory_id: str) -> bool:
        if not self._adapter:
            raise StorageNotConfiguredError()

        validate_storage_key(memory_id)
        return self._adapter.forget(memory_id)

    def get_stats(self) -> Dict[str, Any]:
        if not self._adapter:
            return {"adapter": None, "total_count": 0}

        return self._adapter.get_stats()

    def declare(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        result = self._engine.process_message(message, context=context)
        matches = result.get("matches", [])

        if not matches:
            entry = MemoryEntry(
                id="",
                type="user_preference",
                content=message,
                confidence=1.0,
                tier=2,
                source_layer="declaration",
                reasoning="User explicit declaration",
                suggested_action="store",
                metadata={"original_message": message, "source": "declaration"},
            )
            matches = [entry]
        else:
            entries = []
            for m in matches:
                entry = MemoryEntry(
                    id=m.get("id", ""),
                    type=m.get("memory_type") or m.get("type", "unknown"),
                    content=m.get("content", ""),
                    confidence=1.0,
                    tier=m.get("tier", 2),
                    source_layer="declaration",
                    reasoning=(m.get("reasoning") or "") + " (explicit declaration)",
                    suggested_action="store",
                    recall_hint=m.get("recall_hint"),
                    metadata={**m.get("metadata", {}), "source": "declaration"},
                )
                entries.append(entry)
            matches = entries

        stored_memories = []
        storage_keys = []
        for entry in matches:
            stored = self._adapter.remember(entry)
            stored_memories.append(stored.to_dict())
            storage_keys.append(stored.storage_key)

        return {
            "declared": True,
            "entries": stored_memories,
            "storage_keys": storage_keys,
            "source": "declaration",
            "summary": {
                "total_entries": len(stored_memories),
                "by_type": self._count_by_type(matches),
            },
        }

    def declare_preference(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.declare(message, context)

    def get_memory_profile(self) -> Dict[str, Any]:
        if not self._adapter:
            return {
                "summary": "No storage configured",
                "total_memories": 0,
                "highlights": {},
                "stats": {},
            }

        profile = self._adapter.get_profile()
        return profile

    def whoami(self) -> Dict[str, Any]:
        if not self._adapter:
            return {"identity": "unknown", "summary": "No storage configured"}

        stats = self._adapter.get_stats()
        profile = self._adapter.get_profile()
        total = stats.get("total_count", 0) if isinstance(stats, dict) else 0

        if total == 0:
            return {
                "identity": "new_user",
                "summary": "No memories yet. Start by telling me about yourself.",
                "total_memories": 0,
            }

        by_type = stats.get("by_type", {}) if isinstance(stats, dict) else {}
        profile_stats = profile.get("stats", {}) if isinstance(profile, dict) else {}

        preferences = self.recall_memories(query="", filters={"type": "user_preference"}, limit=10)
        decisions = self.recall_memories(query="", filters={"type": "decision"}, limit=5)
        corrections = self.recall_memories(query="", filters={"type": "correction"}, limit=5)

        pref_list = [m.get("content", "") for m in preferences[:5]]
        decision_list = [m.get("content", "") for m in decisions[:3]]
        correction_list = [m.get("content", "") for m in corrections[:3]]

        top_type = max(by_type, key=by_type.get) if by_type else "unknown"
        conf_avg = profile_stats.get("confidence_avg", 0)

        identity_parts = []
        if pref_list:
            identity_parts.append("Preferences: " + "; ".join(pref_list[:3]))
        if decision_list:
            identity_parts.append("Decisions: " + "; ".join(decision_list[:2]))
        if correction_list:
            identity_parts.append("Corrections: " + "; ".join(correction_list[:2]))

        summary = " | ".join(identity_parts) if identity_parts else f"User with {total} memories"

        return {
            "identity": "known_user",
            "summary": summary,
            "total_memories": total,
            "top_type": top_type,
            "confidence_avg": conf_avg,
            "preferences": pref_list,
            "decisions": decision_list,
            "corrections": correction_list,
            "by_type": by_type,
        }

    def export_profile(self, output_path: Optional[str] = None) -> Dict[str, Any]:
        whoami = self.whoami()
        profile = self.get_memory_profile()

        export = {
            "schema_version": "1.0.0",
            "format": "carrymem_identity",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "identity": whoami.get("identity", "unknown"),
            "summary": whoami.get("summary", ""),
            "preferences": whoami.get("preferences", []),
            "decisions": whoami.get("decisions", []),
            "corrections": whoami.get("corrections", []),
            "stats": {
                "total_memories": whoami.get("total_memories", 0),
                "top_type": whoami.get("top_type", ""),
                "confidence_avg": whoami.get("confidence_avg", 0),
                "by_type": whoami.get("by_type", {}),
            },
            "profile": profile,
        }

        if output_path:
            output_path = _validate_file_path(output_path)
            p = Path(output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(export, f, ensure_ascii=False, indent=2)

        return export

    def export_memories(
        self,
        output_path: Optional[str] = None,
        format: str = "json",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Export memories to a portable format.

        Args:
            output_path: File path to write. If None, returns dict without writing.
            format: Export format ('json' or 'markdown').
            namespace: Export only this namespace. If None, export current namespace.

        Returns:
            Dict with export metadata and data.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()

        if output_path:
            output_path = _validate_file_path(output_path)

        ns = namespace or self._namespace
        stats = self._adapter.get_stats()
        total_count = stats.get("total_count", 0) if isinstance(stats, dict) else 0
        export_limit = max(total_count, 1)

        all_memories = self._adapter.recall("", limit=export_limit)

        if ns != "default" and isinstance(self._adapter, SQLiteAdapter):
            all_memories = self._adapter.recall("", limit=export_limit, namespaces=[ns])

        export_data = {
            "schema_version": "1.0.0",
            "export_format": "carrymem_portable",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "source": {
                "version": _version,
                "namespace": ns,
                "total_memories": len(all_memories),
            },
            "memories": [m.to_dict() for m in all_memories],
        }

        if format == "markdown":
            md_lines = [
                f"# CarryMem Memory Export",
                f"",
                f"- **Exported**: {export_data['exported_at']}",
                f"- **Namespace**: {ns}",
                f"- **Total memories**: {len(all_memories)}",
                f"",
            ]
            by_type: Dict[str, list] = {}
            for m in all_memories:
                d = m.to_dict()
                t = d.get("type", "unknown")
                by_type.setdefault(t, []).append(d)

            for mem_type, items in sorted(by_type.items()):
                md_lines.append(f"## {mem_type}")
                md_lines.append("")
                for item in items:
                    content = item.get("content", "")
                    conf = item.get("confidence", 0)
                    tier = item.get("tier", "?")
                    md_lines.append(f"- [{tier}] {content} (confidence: {conf:.0%})")
                md_lines.append("")

            md_content = "\n".join(md_lines)
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
            return {
                "exported": True,
                "format": "markdown",
                "path": output_path,
                "total_memories": len(all_memories),
                "namespace": ns,
                "content": md_content if not output_path else None,
            }

        json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(json_content)

        return {
            "exported": True,
            "format": "json",
            "path": output_path,
            "total_memories": len(all_memories),
            "namespace": ns,
            "data": export_data if not output_path else None,
        }

    def import_memories(
        self,
        input_path: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
        merge_strategy: str = "skip_existing",
    ) -> Dict[str, Any]:
        """Import memories from a portable format.

        Args:
            input_path: File path to read. If None, uses data parameter.
            data: Direct dict data (alternative to file).
            namespace: Import into this namespace. If None, uses current.
            merge_strategy: 'skip_existing' or 'overwrite'.

        Returns:
            Dict with import results.
        """
        if not self._adapter:
            raise StorageNotConfiguredError()

        if input_path:
            input_path = _validate_file_path(input_path)

        if input_path:
            with open(input_path, "r", encoding="utf-8") as f:
                import_data = json.load(f)
        elif data:
            import_data = data
        else:
            raise ValueError("Either input_path or data must be provided")

        target_ns = namespace or self._namespace
        memories = import_data.get("memories", [])

        imported = 0
        skipped = 0
        errors = 0

        for mem_dict in memories:
            try:
                content = mem_dict.get("content", "")
                if _import_validator and content:
                    try:
                        content = _import_validator.validate_content(content, "imported_content")
                    except Exception:
                        errors += 1
                        continue
                content_hash = mem_dict.get("content_hash", "")
                if merge_strategy == "skip_existing" and content_hash:
                    existing = self._adapter.recall(
                        mem_dict.get("content", "")[:50], limit=5
                    )
                    if any(
                        (getattr(e, 'content_hash', None) == content_hash
                         or (isinstance(e, dict) and e.get("content_hash") == content_hash)
                         or (hasattr(e, 'metadata') and isinstance(e.metadata, dict)
                             and e.metadata.get("content_hash") == content_hash))
                        for e in existing
                    ):
                        skipped += 1
                        continue

                entry = MemoryEntry(
                    id=mem_dict.get("id", ""),
                    type=mem_dict.get("type", "unknown"),
                    content=content,
                    confidence=mem_dict.get("confidence", 0.5),
                    tier=mem_dict.get("tier", 2),
                    source_layer=mem_dict.get("source_layer", "import"),
                    reasoning=mem_dict.get("reasoning", ""),
                    suggested_action="store",
                    recall_hint=mem_dict.get("recall_hint"),
                    metadata={
                        **mem_dict.get("metadata", {}),
                        "imported_from": import_data.get("source", {}).get("namespace", "unknown"),
                        "imported_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                self._adapter.remember(entry)
                imported += 1
            except Exception as e:
                logger.warning(f"Failed to import memory entry: {e}")
                errors += 1

        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
            "total_processed": len(memories),
            "namespace": target_ns,
            "merge_strategy": merge_strategy,
        }

    def build_context(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> Dict[str, Any]:
        from memory_classification_engine.context import (
            select_memories, select_knowledge, build_prompt, _estimate_tokens,
        )

        memories_section = []
        knowledge_section = []
        rules_section = []

        rules_budget = int(max_tokens * 0.3)
        memories_budget = int(max_tokens * 0.45)
        knowledge_budget = int(max_tokens * 0.25)

        try:
            rule_engine = self.rule_engine
            if context:
                rules_section = rule_engine.inject(
                    context, format="anchored", max_rules=max_rules,
                    context_budget_tokens=rules_budget,
                )
            else:
                all_rules = rule_engine.list_rules(status="active", limit=max_rules)
                if all_rules:
                    from .rules.injector import RuleInjector
                    injector = RuleInjector(rule_engine.matcher)
                    matches = []
                    from .rules.matcher import MatchResult
                    for r in all_rules:
                        matches.append(MatchResult(
                            rule=r, score=0.6, match_type="global", matched_text=r.trigger,
                        ))
                    rules_section = injector._format_structured(matches, include_metadata=False)
                else:
                    rules_section = ""
        except Exception as e:
            logger.warning(f"Rule injection failed for build_context: {e}")
            rules_section = ""

        if self._adapter:
            try:
                query = context or ""
                if query:
                    all_memories = self.recall_memories(query=query, limit=max_memories * 3)
                else:
                    all_memories = self.recall_memories(limit=max_memories * 3)

                memories_section = select_memories(
                    memories=all_memories,
                    context=context,
                    max_count=max_memories,
                    max_tokens=memories_budget,
                )
            except Exception as e:
                logger.warning(f"Failed to select memories for context: {e}")

        if self._knowledge_adapter and context:
            try:
                all_knowledge = self.recall_from_knowledge(query=context, limit=max_knowledge * 2)
                knowledge_section = select_knowledge(
                    knowledge=all_knowledge,
                    context=context,
                    max_count=max_knowledge,
                    max_tokens=knowledge_budget,
                )
            except Exception as e:
                logger.warning(f"Failed to select knowledge for context: {e}")

        system_prompt = build_prompt(
            memories=memories_section,
            knowledge=knowledge_section,
            language=language,
        )

        if rules_section:
            system_prompt = rules_section + "\n\n" + system_prompt

        applied_rules_info = []
        try:
            _re = self.rule_engine
            _matched = _re.matcher.match(context if context else "*", limit=max_rules)
            for m in _matched:
                applied_rules_info.append({
                    "trigger": m.rule.trigger,
                    "action": m.rule.action,
                    "rule_type": m.rule.rule_type,
                    "scope": m.rule.scope,
                    "override": m.rule.override,
                })
        except Exception:
            pass

        return {
            "system_prompt": system_prompt,
            "rules": rules_section if isinstance(rules_section, str) else rules_section,
            "memories": memories_section,
            "knowledge": knowledge_section,
            "applied_rules": applied_rules_info,
            "rule_count": len(applied_rules_info),
            "memory_count": len(memories_section),
            "knowledge_count": len(knowledge_section),
            "token_estimate": _estimate_tokens(system_prompt),
            "language": language,
        }

    def build_system_prompt(
        self,
        context: Optional[str] = None,
        max_memories: int = 10,
        max_knowledge: int = 5,
        max_rules: int = 5,
        max_tokens: int = 2000,
        language: str = "en",
    ) -> str:
        result = self.build_context(
            context=context,
            max_memories=max_memories,
            max_knowledge=max_knowledge,
            max_rules=max_rules,
            max_tokens=max_tokens,
            language=language,
        )
        return result["system_prompt"]

    def check_conflicts(self) -> List[Dict[str, Any]]:
        from memory_classification_engine.conflict_detector import ConflictDetector

        if not self._adapter:
            raise StorageNotConfiguredError()

        all_memories = self._adapter.recall("", limit=10000)
        if not all_memories:
            return []

        detector = ConflictDetector()
        conflicts = detector.detect_conflicts(all_memories)
        return [c.to_dict() for c in conflicts]

    def check_quality(self, min_score: float = 0.3) -> List[Dict[str, Any]]:
        from memory_classification_engine.quality_scorer import MemoryQualityScorer, QualityAnalyzer

        if not self._adapter:
            raise StorageNotConfiguredError()

        all_memories = self._adapter.recall("", limit=10000)
        if not all_memories:
            return []

        analyzer = QualityAnalyzer()
        low_quality = analyzer.identify_low_quality(all_memories, threshold=min_score)
        result = []
        for item in low_quality:
            result.append({
                "storage_key": item["storage_key"],
                "score": item["score"],
                "reasons": item["reasons"],
                "content": item["memory"].content[:80],
                "type": item["memory"].type,
            })
        return result

    def list_expired(self) -> List[Dict[str, Any]]:
        if not self._adapter:
            raise StorageNotConfiguredError()

        if not isinstance(self._adapter, SQLiteAdapter):
            return []

        from datetime import datetime, timezone
        conn = self._adapter._get_connection()
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = conn.execute(
            "SELECT storage_key, content, type, expires_at FROM memories "
            "WHERE namespace = ? AND expires_at IS NOT NULL AND expires_at < ?",
            (self._namespace, now_iso),
        ).fetchall()

        result = []
        for row in rows:
            content = row["content"]
            if self._adapter._encryption and self._adapter._encryption.is_active:
                content = self._adapter._decrypt_field(content)
            result.append({
                "storage_key": row["storage_key"],
                "content": (content or "")[:80],
                "type": row["type"],
                "expires_at": row["expires_at"],
            })
        return result

    def _count_by_type(self, entries: List[MemoryEntry]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in entries:
            counts[e.type] = counts.get(e.type, 0) + 1
        return counts
