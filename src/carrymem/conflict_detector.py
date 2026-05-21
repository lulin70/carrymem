"""Memory Conflict Detection Module for CarryMem.

Detects and resolves conflicts between stored memories, such as:
- Contradictory preferences
- Outdated corrections
- Conflicting decisions
- Duplicate memories

Initial implementation
"""

from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum

from .adapters.base import StoredMemory


class ConflictType(Enum):
    """Types of memory conflicts."""
    CONTRADICTION = "contradiction"
    OUTDATED = "outdated"
    DUPLICATE = "duplicate"
    PREFERENCE_CHANGE = "preference_change"
    OVERLAP = "overlap"


class ConflictSeverity(Enum):
    """Severity levels for conflicts."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MemoryConflict:
    """Represents a detected conflict between memories."""
    
    def __init__(
        self,
        conflict_type: ConflictType,
        severity: ConflictSeverity,
        memories: List[StoredMemory],
        reason: str,
        suggested_resolution: Optional[str] = None,
    ):
        self.conflict_type = conflict_type
        self.severity = severity
        self.memories = memories
        self.reason = reason
        self.suggested_resolution = suggested_resolution
        self.detected_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict to dictionary representation."""
        return {
            'conflict_type': self.conflict_type.value,
            'severity': self.severity.value,
            'memory_keys': [m.storage_key for m in self.memories],
            'reason': self.reason,
            'suggested_resolution': self.suggested_resolution,
            'detected_at': self.detected_at.isoformat(),
        }


class ConflictDetector:
    """Detect conflicts between stored memories."""
    
    def __init__(
        self,
        similarity_threshold: float = 0.85,
        time_window_days: int = 30,
    ):
        self.similarity_threshold = similarity_threshold
        self.time_window_days = time_window_days
    
    def detect_conflicts(
        self,
        memories: List[StoredMemory],
        namespace: Optional[str] = None,
    ) -> List[MemoryConflict]:
        """Detect all conflicts in a set of memories."""
        if namespace:
            memories = [m for m in memories if m.namespace == namespace]
        
        conflicts = []
        conflicts.extend(self._detect_contradictions(memories))
        conflicts.extend(self._detect_outdated(memories))
        conflicts.extend(self._detect_duplicates(memories))
        conflicts.extend(self._detect_preference_changes(memories))
        
        return conflicts
    
    def _detect_contradictions(
        self,
        memories: List[StoredMemory],
    ) -> List[MemoryConflict]:
        conflicts = []

        by_type: Dict[str, List[StoredMemory]] = {}
        for memory in memories:
            if memory.type not in by_type:
                by_type[memory.type] = []
            by_type[memory.type].append(memory)

        for mem_type, type_memories in by_type.items():
            if len(type_memories) < 2:
                continue
            severity = ConflictSeverity.HIGH if mem_type == 'correction' else ConflictSeverity.MEDIUM
            for i, mem1 in enumerate(type_memories):
                for mem2 in type_memories[i+1:]:
                    if self._are_contradictory(mem1, mem2):
                        conflicts.append(MemoryConflict(
                            conflict_type=ConflictType.CONTRADICTION,
                            severity=severity,
                            memories=[mem1, mem2],
                            reason=f"Contradictory {mem_type} memories",
                            suggested_resolution="Keep the most recent memory",
                        ))

        return conflicts
    
    def _normalize_dt(self, dt_val) -> datetime:
        if dt_val is None:
            return datetime.min.replace(tzinfo=timezone.utc)
        if isinstance(dt_val, datetime):
            if dt_val.tzinfo is None:
                return dt_val.replace(tzinfo=timezone.utc)
            return dt_val
        if isinstance(dt_val, str):
            try:
                parsed = datetime.fromisoformat(dt_val)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed
            except (ValueError, TypeError):
                return datetime.min.replace(tzinfo=timezone.utc)
        return datetime.min.replace(tzinfo=timezone.utc)

    def _detect_outdated(
        self,
        memories: List[StoredMemory],
    ) -> List[MemoryConflict]:
        conflicts = []

        by_type_ns: Dict[str, List[StoredMemory]] = {}
        for mem in memories:
            key = f"{getattr(mem, 'namespace', '')}:{mem.type}"
            by_type_ns.setdefault(key, []).append(mem)

        for group_key, group in by_type_ns.items():
            if len(group) < 2:
                continue
            sorted_group = sorted(
                group,
                key=lambda m: self._normalize_dt(m.created_at),
            )
            for i, old_memory in enumerate(sorted_group):
                for new_memory in sorted_group[i+1:]:
                    if self._supersedes(new_memory, old_memory):
                        conflicts.append(MemoryConflict(
                            conflict_type=ConflictType.OUTDATED,
                            severity=ConflictSeverity.MEDIUM,
                            memories=[old_memory, new_memory],
                            reason=f"Memory superseded by newer version",
                            suggested_resolution="Archive or delete older memory",
                        ))

        return conflicts
    
    def _detect_duplicates(
        self,
        memories: List[StoredMemory],
    ) -> List[MemoryConflict]:
        conflicts = []

        by_type_ns: Dict[str, List[StoredMemory]] = {}
        for mem in memories:
            key = f"{getattr(mem, 'namespace', '')}:{mem.type}"
            by_type_ns.setdefault(key, []).append(mem)

        for group_key, group in by_type_ns.items():
            if len(group) < 2:
                continue
            for i, mem1 in enumerate(group):
                for mem2 in group[i+1:]:
                    similarity = self._calculate_similarity(mem1, mem2)
                    if similarity >= self.similarity_threshold:
                        conflicts.append(MemoryConflict(
                            conflict_type=ConflictType.DUPLICATE,
                            severity=ConflictSeverity.LOW,
                            memories=[mem1, mem2],
                            reason=f"Near-duplicate memories (similarity: {similarity:.2f})",
                            suggested_resolution="Merge or keep the higher quality one",
                        ))

        return conflicts
    
    def _detect_preference_changes(
        self,
        memories: List[StoredMemory],
    ) -> List[MemoryConflict]:
        """Detect preference changes over time."""
        conflicts = []
        
        preferences = [m for m in memories if m.type == 'user_preference']
        groups = self._group_similar_preferences(preferences)
        
        for group in groups:
            if len(group) > 1:
                group.sort(key=lambda m: self._normalize_dt(m.created_at))
                oldest = group[0]
                newest = group[-1]
                
                conflicts.append(MemoryConflict(
                    conflict_type=ConflictType.PREFERENCE_CHANGE,
                    severity=ConflictSeverity.LOW,
                    memories=group,
                    reason=f"Preference changed over time",
                    suggested_resolution="Keep only the most recent preference",
                ))
        
        return conflicts
    
    def _are_contradictory(
        self,
        mem1: StoredMemory,
        mem2: StoredMemory,
    ) -> bool:
        """Check if two memories contradict each other."""
        if getattr(mem1, 'namespace', None) != getattr(mem2, 'namespace', None) or mem1.type != mem2.type:
            return False
        
        negation_pairs = [
            ('like', 'dislike'),
            ('prefer', 'avoid'),
            ('use', 'dont'),
            ('always', 'never'),
            ('yes', 'no'),
        ]
        
        content1_lower = mem1.content.lower()
        content2_lower = mem2.content.lower()
        
        for pos, neg in negation_pairs:
            if pos in content1_lower and neg in content2_lower:
                return True
            if neg in content1_lower and pos in content2_lower:
                return True
        
        return False
    
    def _supersedes(
        self,
        new_memory: StoredMemory,
        old_memory: StoredMemory,
    ) -> bool:
        """Check if a new memory supersedes an old one."""
        if getattr(new_memory, 'namespace', None) != getattr(old_memory, 'namespace', None):
            return False
        if new_memory.type != old_memory.type:
            return False
        
        if not new_memory.created_at or not old_memory.created_at:
            return False
        new_dt = self._normalize_dt(new_memory.created_at)
        old_dt = self._normalize_dt(old_memory.created_at)
        if new_dt <= old_dt:
            return False
        
        update_keywords = ['actually', 'correction', 'update', 'changed', 'now']
        content_lower = new_memory.content.lower()
        
        for keyword in update_keywords:
            if keyword in content_lower:
                similarity = self._calculate_similarity(new_memory, old_memory)
                if similarity >= 0.5:
                    return True
        
        return False
    
    def _calculate_similarity(
        self,
        mem1: StoredMemory,
        mem2: StoredMemory,
    ) -> float:
        """Calculate similarity between two memories."""
        words1 = set(mem1.content.lower().split())
        words2 = set(mem2.content.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union)
    
    def _group_similar_preferences(
        self,
        preferences: List[StoredMemory],
    ) -> List[List[StoredMemory]]:
        """Group similar preferences together."""
        groups: List[List[StoredMemory]] = []
        used = set()
        
        for i, pref1 in enumerate(preferences):
            if i in used:
                continue
            
            group = [pref1]
            used.add(i)
            
            for j, pref2 in enumerate(preferences[i+1:], start=i+1):
                if j in used:
                    continue
                
                similarity = self._calculate_similarity(pref1, pref2)
                if similarity >= 0.4:
                    group.append(pref2)
                    used.add(j)
            
            if len(group) > 1:
                groups.append(group)
        
        return groups


