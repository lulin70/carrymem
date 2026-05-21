"""CarryMem DevSquad Integration Adapter.

Provides MemoryProvider and CarryMemAdapter Protocol implementations
for DevSquad multi-agent orchestration.

Usage:
    from carrymem.integration.devsquad import DevSquadAdapter

    adapter = DevSquadAdapter(db_path="carrymem.db")
    if adapter.is_available():
        rules = adapter.match_rules("Design REST API", "user1", role="architect")
        prompt = adapter.format_rules_as_prompt(rules)
"""

from .adapter import DevSquadAdapter
from .protocol import CarryMemAdapter, MemoryProvider
from .type_mapping import (
    CARRYMEM_TO_DEVOPSQUAD_RULE_TYPE,
    DEVSQUAD_TO_CARRYMEM_RULE_TYPE,
    carrymem_rule_to_devsquad_dict,
    carrymem_to_devsquad_type,
    devsquad_rule_to_carrymem_params,
    devsquad_to_carrymem_type,
)

__all__ = [
    "DevSquadAdapter",
    "MemoryProvider",
    "CarryMemAdapter",
    "DEVSQUAD_TO_CARRYMEM_RULE_TYPE",
    "CARRYMEM_TO_DEVOPSQUAD_RULE_TYPE",
    "devsquad_to_carrymem_type",
    "carrymem_to_devsquad_type",
    "carrymem_rule_to_devsquad_dict",
    "devsquad_rule_to_carrymem_params",
]
