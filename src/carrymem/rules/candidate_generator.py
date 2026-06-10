"""
RuleCandidateGenerator — Extract rule candidates from stored memories.

Generates rule suggestions by analyzing memory content for triggers,
actions, conditions, and implicit preferences. Used by CarryMem to
auto-suggest rules when new memories are stored.
"""

import re
from typing import Any, Callable, Dict, List

from carrymem.utils.logger import logger


class RuleCandidateGenerator:
    """Generate rule candidates from stored memories.

    Extracts triggers, actions, conditions, and rule types from memory
    content using pattern matching and heuristics.

    Args:
        rule_engine_getter: Callable that returns the RuleEngine instance.
        recall_memories: Callable that recalls memories (same signature as
            CarryMem.recall_memories).
    """

    def __init__(
        self,
        rule_engine_getter: Callable,
        recall_memories: Callable,
    ):
        self._rule_engine_getter = rule_engine_getter
        self._recall_memories = recall_memories

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def auto_suggest_rules(self, stored_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not stored_memories:
            return []

        rule_worthy_types = {
            "user_preference",
            "correction",
            "decision",
            "task_pattern",
            "sentiment_marker",
            "fact_declaration",
        }
        candidates = []

        try:
            engine = self._rule_engine_getter()

            for mem in stored_memories:
                mem_type = mem.get("type", "")
                if mem_type not in rule_worthy_types:
                    continue

                content = mem.get("content", "")
                if not content or len(content.strip()) < 3:
                    continue

                trigger = self.extract_trigger(content, mem_type)
                action = self.extract_action(content, mem_type)
                rule_type = self.infer_rule_type(mem_type, content)

                if trigger and action:
                    condition = self.extract_condition(content)
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

            existing_memories = self._recall_memories(limit=100)
            if len(existing_memories) >= 5:
                try:
                    suggested = engine.suggest_rules(existing_memories, max_candidates=2)
                    for s in suggested[:2]:
                        if not s.trigger or not s.action:
                            continue
                        if s.action == s.trigger:
                            continue
                        if len(s.action.split()) <= 2 and any(c in s.action for c in (",", "，")):
                            continue
                        if s.trigger in (
                            "related scenarios",
                            "tech selection or solution design",
                            "general context",
                            "偏好选择",
                            "通用场景",
                        ):
                            continue
                        candidate_dict = {
                            "trigger": s.trigger,
                            "action": s.action,
                            "rule_type": s.rule_type if hasattr(s, "rule_type") else "prefer",
                            "scope": "personal",
                            "override": False,
                            "confidence": min(s.confidence if hasattr(s, "confidence") else 0.6, 0.85),
                            "source": "pattern_detection",
                        }
                        if candidate_dict not in candidates:
                            candidates.append(candidate_dict)
                except (ValueError, KeyError, TypeError, RuntimeError) as e:
                    logger.warning(f"Pattern detection candidate generation failed: {e}")

            try:
                implicit = self.detect_implicit_preferences()
                for imp in implicit:
                    if not any(c.get("trigger") == imp["trigger"] for c in candidates):
                        candidates.append(imp)
            except (ValueError, KeyError, TypeError) as e:
                logger.warning(f"Implicit preference detection failed: {e}")

        except (ImportError, ValueError, KeyError, RuntimeError) as e:
            logger.debug(f"Rule suggestion engine unavailable: {e}")

        return candidates[:3]

    # ------------------------------------------------------------------
    # Implicit preference detection
    # ------------------------------------------------------------------

    def detect_implicit_preferences(self) -> List[Dict[str, Any]]:
        try:
            memories = self._recall_memories(limit=50)
        except (KeyError, ValueError, RuntimeError):
            return []

        if len(memories) < 3:
            return []

        tech_pattern = re.compile(
            r"\b(?:javascript|typescript|python|java|react|vue|angular|postgresql|mysql|sqlite|"
            r"mongodb|redis|docker|kubernetes|aws|gcp|azure|node\.js|go|rust|swift|kotlin)\b",
            re.IGNORECASE,
        )

        tech_counts = {}
        for mem in memories:
            content = mem.get("content", "").lower()
            for match in tech_pattern.finditer(content):
                tech = match.group(0).lower()
                tech_counts[tech] = tech_counts.get(tech, 0) + 1

        domain_groups = {
            "language": {
                "python",
                "java",
                "javascript",
                "typescript",
                "go",
                "rust",
                "swift",
                "kotlin",
                "node.js",
            },
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
                    implicit.append(
                        {
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
                        }
                    )

        return implicit

    # ------------------------------------------------------------------
    # Pure helper methods (no external dependencies)
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize_rule_content(text: str) -> str:
        danger_pattern = re.compile(
            r"(?:ignore\s+(?:previous|above|all)\s+(?:instructions?|rules?)|"
            r"system\s*[:：]\s*|"
            r"forget\s+(?:all\s+)?(?:rules?|instructions?)|"
            r"you\s+are\s+now|"
            r"(?:DAN|jailbreak|developer)\s+mode|"
            r"bypass\s+(?:all\s+)?(?:restrictions?|filters?|safety)|"
            r"\$\{.*?\}|\{\{.*?\}\}|"
            r"eval\(|exec\(|__import__)",
            re.IGNORECASE,
        )
        if danger_pattern.search(text):
            return "[filtered: potentially unsafe content]"
        return text

    @staticmethod
    def extract_trigger(content: str, mem_type: str) -> str:
        content_lower = content.lower()

        trigger_map = [
            (
                r"\b(?:javascript|typescript|python|java|go|rust|swift|kotlin|c\+\+|ruby|php)\b",
                lambda m: "programming language selection",
            ),
            (
                r"\b(?:react|vue|angular|svelte|next\.js|nuxt)\b",
                lambda m: "frontend framework selection",
            ),
            (
                r"\b(?:postgresql|mysql|sqlite|mongodb|redis|dynamodb|cassandra|elasticsearch)\b",
                lambda m: "database selection",
            ),
            (
                r"\b(?:docker|kubernetes|terraform|ansible|puppet|chef)\b",
                lambda m: "infrastructure and deployment",
            ),
            (r"\b(?:aws|gcp|azure|digitalocean|heroku)\b", lambda m: "cloud platform selection"),
            (r"(?:dark\s*mode|light\s*mode|theme|ui\s*theme)", lambda m: "UI theme and appearance"),
            (
                r"\b(?:vim|emacs|vscode|intellij|pycharm|sublime|neovim)\b",
                lambda m: "editor and IDE selection",
            ),
            (r"\b(?:terminal|gui|cli|command\s*line|tui)\b", lambda m: "interface preference"),
            (
                r"\b(?:ssl|tls|https|oauth|jwt|encryption|authentication|security)\b",
                lambda m: "security and authentication",
            ),
            (
                r"\b(?:rest|graphql|grpc|websocket|api\s*design)\b",
                lambda m: "API design and protocol",
            ),
            (
                r"\b(?:microservice|monolith|serverless|soa)\b",
                lambda m: "architecture pattern selection",
            ),
            (
                r"\b(?:test|testing|unit\s*test|integration\s*test|tdd|bdd)\b",
                lambda m: "testing strategy",
            ),
            (
                r"\b(?:git|github|gitlab|bitbucket|version\s*control)\b",
                lambda m: "version control workflow",
            ),
            (
                r"\b(?:ci|cd|pipeline|continuous\s*integration|continuous\s*deployment)\b",
                lambda m: "CI/CD pipeline configuration",
            ),
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

    @staticmethod
    def extract_condition(content: str) -> str:
        condition_patterns = [
            (r"如果.{0,5}?([^.，！？\n]+?)(?:的话|就|则|时|的时候)", 1),
            (r"当.{0,5}?([^.，！？\n]+?)(?:的时候|时|则)", 1),
            (r"(?:要是|假如|若).{0,5}?([^.，！？\n]+?)(?:的话|就|则)", 1),
            (r"if\s+(.+?)(?:\s+then|\s*,|\s*$)", 1),
            (r"when\s+(.+?)(?:\s+then|\s*,|\s*$)", 1),
            (r"(?:小项目|大项目|小团队|大团队|小规模|大规模)", 0),
        ]

        for pattern, group in condition_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                if group == 0:
                    return match.group(0)
                return match.group(group).strip()

        return ""

    @staticmethod
    def extract_action(content: str, mem_type: str) -> str:
        content_lower = content.lower()

        prefer_match = re.search(
            r"(?:prefer|like|love|favor|favour|want|choose|use|prefer\s+to\s+use)\s+(.+?)(?:\.|,|;|$)",
            content_lower,
        )
        if prefer_match and mem_type == "user_preference":
            action_text = prefer_match.group(1).strip()
            if len(action_text) > 3:
                return f"use {action_text}"

        avoid_match = re.search(
            r"(?:avoid|don\'t|do not|never|hate|dislike|stop)\s+(.+?)(?:\.|,|;|$)",
            content_lower,
        )
        if avoid_match:
            action_text = avoid_match.group(1).strip()
            if len(action_text) > 3:
                return f"avoid {action_text}"

        always_match = re.search(
            r"(?:always|must|should|need\s+to|make\s+sure)\s+(.+?)(?:\.|,|;|$)",
            content_lower,
        )
        if always_match:
            action_text = always_match.group(1).strip()
            if len(action_text) > 3:
                return f"always {action_text}"

        tech_preference = re.search(
            r"\b(?:javascript|typescript|python|java|react|vue|angular|postgresql|mysql|"
            r"sqlite|mongodb|redis|docker|kubernetes|aws|gcp|azure|go|rust|swift|kotlin)\b",
            content_lower,
        )
        if tech_preference and mem_type == "user_preference":
            tech = tech_preference.group(0)
            over_match = re.search(
                r"(?:over|instead\s+of|rather\s+than|vs\.?|compared\s+to)\s+(\w+)",
                content_lower,
            )
            if over_match:
                return f"prefer {tech} over {over_match.group(1)}"
            return f"prefer {tech}"

        if mem_type == "correction":
            fix_match = re.search(
                r"(?:should\s+(?:be|use)|fix|correct|change|replace)\s+(.+?)(?:\.|,|;|$)",
                content_lower,
            )
            if fix_match:
                return f"avoid {fix_match.group(1).strip()}"
            return "avoid repeating this mistake"

        if mem_type == "decision":
            dec_match = re.search(
                r"(?:decided|decision|chose|chosen|will\s+use|going\s+with)\s+(.+?)(?:\.|,|;|$)",
                content_lower,
            )
            if dec_match:
                return f"follow decision: {dec_match.group(1).strip()}"
            return "follow established decision"

        if mem_type == "task_pattern":
            return "apply this workflow pattern"

        if mem_type == "sentiment_marker":
            return "consider this feedback"

        if mem_type == "fact_declaration":
            return "reference this fact"

        return "apply this preference"

    @staticmethod
    def infer_rule_type(mem_type: str, content: str = "") -> str:
        if mem_type == "user_preference" and content:
            negation_patterns = [
                r"别用",
                r"不要用",
                r"下次别",
                r"不喜欢",
                r"讨厌",
                r"don't",
                r"do not",
                r"never",
                r"hate",
                r"dislike",
                r"avoid",
                r"stop",
                r"no more",
            ]
            if any(re.search(p, content.lower()) for p in negation_patterns):
                return "avoid"
        mapping = {
            "user_preference": "prefer",
            "correction": "avoid",
            "decision": "always",
            "task_pattern": "prefer",
            "sentiment_marker": "avoid",
            "fact_declaration": "prefer",
        }
        return mapping.get(mem_type, "prefer")
