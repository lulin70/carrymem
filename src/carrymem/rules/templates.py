"""
CarryMem Rules Engine — Rule Templates

Pre-defined rule patterns for common use cases.
Users can instantiate these templates via CLI:
    carrymem add-rule --template code-review
"""

from typing import Dict, Any

RULE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "code-review": {
        "trigger": "代码评审",
        "action": "必须检查安全漏洞、代码规范、性能问题",
        "rule_type": "always",
        "override": True,
        "description": "Code review checklist: security, style, performance",
    },
    "report-format": {
        "trigger": "写报告",
        "action": "控制在3页以内，包含摘要和结论",
        "rule_type": "format",
        "override": True,
        "description": "Report format: ≤3 pages, with summary and conclusion",
    },
    "tech-selection": {
        "trigger": "技术选型",
        "action": "优先考虑团队熟悉度和社区支持",
        "rule_type": "prefer",
        "override": False,
        "description": "Tech selection: prefer team familiarity and community support",
    },
    "no-java": {
        "trigger": "技术选型",
        "action": "不使用Java/Spring，优先Python/Go",
        "rule_type": "avoid",
        "override": True,
        "description": "Avoid Java/Spring, prefer Python/Go",
    },
    "security-first": {
        "trigger": "系统设计",
        "action": "必须包含安全评审和威胁建模",
        "rule_type": "always",
        "override": True,
        "description": "System design: must include security review and threat modeling",
    },
    "no-shortcut": {
        "trigger": "代码编写",
        "action": "禁止使用硬编码密码、密钥和敏感信息",
        "rule_type": "forbid",
        "override": True,
        "description": "Coding: forbid hardcoded passwords, keys, and sensitive info",
    },
    "api-design": {
        "trigger": "API设计",
        "action": "遵循RESTful规范，包含错误码和文档",
        "rule_type": "format",
        "override": True,
        "description": "API design: RESTful, with error codes and documentation",
    },
    "testing-required": {
        "trigger": "功能开发",
        "action": "必须编写单元测试，覆盖率≥80%",
        "rule_type": "always",
        "override": True,
        "description": "Feature dev: must write unit tests, coverage ≥80%",
    },
    "doc-first": {
        "trigger": "项目启动",
        "action": "先写设计文档，再写代码",
        "rule_type": "always",
        "override": False,
        "description": "Project start: docs before code",
    },
    "competitor-analysis": {
        "trigger": "竞品分析",
        "action": "对手官方数据必须标注[待验证]",
        "rule_type": "always",
        "override": True,
        "description": "Competitor analysis: mark rival official data as [Unverified]",
    },
}


def get_template(name: str) -> Dict[str, Any]:
    """
    Get a rule template by name.

    Args:
        name: Template name (e.g., "code-review")

    Returns:
        Template dictionary with trigger, action, rule_type, etc.

    Raises:
        KeyError: If template name not found
    """
    if name not in RULE_TEMPLATES:
        available = ", ".join(sorted(RULE_TEMPLATES.keys()))
        raise KeyError(
            f"Template '{name}' not found. Available: {available}"
        )
    return RULE_TEMPLATES[name]


def list_templates() -> Dict[str, str]:
    """
    List all available template names and descriptions.

    Returns:
        Dictionary mapping template name → description
    """
    return {name: t["description"] for name, t in RULE_TEMPLATES.items()}
