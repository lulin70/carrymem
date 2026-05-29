DEVSQUAD_TO_CARRYMEM_RULE_TYPE = {
    "forbid": "forbid",
    "avoid": "avoid",
    "always": "always",
}

CARRYMEM_TO_DEVOPSQUAD_RULE_TYPE = {
    "forbid": "forbid",
    "avoid": "avoid",
    "always": "always",
    "format": "avoid",
    "prefer": "avoid",
}


def devsquad_to_carrymem_type(rule_type: str) -> str:
    return DEVSQUAD_TO_CARRYMEM_RULE_TYPE.get(rule_type, "avoid")


def carrymem_to_devsquad_type(rule_type: str) -> str:
    return CARRYMEM_TO_DEVOPSQUAD_RULE_TYPE.get(rule_type, "avoid")


def carrymem_rule_to_devsquad_dict(rule) -> dict:
    return {
        "rule_id": rule.id,
        "trigger": rule.trigger,
        "action": rule.action,
        "rule_type": carrymem_to_devsquad_type(rule.rule_type),
        "override": rule.override,
        "relevance_score": getattr(rule, "relevance_score", 0.5),
    }


def devsquad_rule_to_carrymem_params(rule: str, metadata: dict = None) -> dict:
    params = {
        "trigger": metadata.get("trigger", "") if metadata else "",
        "action": rule,
        "rule_type": (devsquad_to_carrymem_type(metadata.get("rule_type", "avoid")) if metadata else "avoid"),
        "override": metadata.get("override", True) if metadata else True,
    }
    if metadata and metadata.get("source"):
        params["derived_from"] = metadata["source"]
    return params
