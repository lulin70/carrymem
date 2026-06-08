"""Task pattern definitions."""

import re
from carrymem.patterns.base import PatternType
from carrymem.patterns.builder import PatternBuilder
from carrymem.patterns.registry import PatternRegistry


def register_task_patterns(registry: PatternRegistry) -> None:
    """Register all task patterns into the registry."""
    b = PatternBuilder(registry)

    # ===== Structured task (EN) =====
    b.create_group("task_structured", PatternType.TASK)
    b.set_language("en")
    b.add_task_batch(
        [
            ("need_to", r"^(i\s+|we\s+|let\'s\s+)?(need|should|must|have|got)\s+to\s+", "structured"),
            ("todo", r"^(todo|task):\s*", "structured"),
            ("implement", r"^(please\s+)?(can\s+you\s+)?(help\s+me\s+)?(implement|refactor|fix|add|create|build|write|update)\s+", "structured"),
            ("dont_forget", r"^(don(\'t)?\s+)?forget\s+to\s+", "structured"),
            ("remember_to", r"^(remember\s+to\s+|make sure to\s+)", "structured"),
            ("going_to", r"^(we\'re|we are|i\'m|i am)\s+(going to|planning to|working on)\s+", "structured"),
        ],
        flags=re.IGNORECASE,
        match_method="match",
    )
    b.register()

    # ===== Workflow/recurring task (EN) =====
    b.create_group("task_workflow", PatternType.TASK)
    b.set_language("en")
    b.add_task_batch(
        [
            ("always_verb", r"^(always|every\s+time|each\s+time|generally|typically|normally|usually)\s+(run|test|review|check|verify|update|backup|deploy|build|lint|format|document|validate)\b", "workflow"),
            ("verb_freq", r"\b(run|test|review|check|verify|update|backup|deploy|build|lint|format|document|validate|monitor|analyze|debug|refactor|optimize|migrate|integrate)\b\s+(always|every\s+\w+|weekly|monthly|daily|before\s+\w+|after\s+\w+|each\s+\w+|on\s+\w+days?|at\s+\w+)\b", "workflow"),
            ("freq_noun", r"^(weekly|monthly|daily|quarterly|annually|yearly)\s+.*\b(retro|meeting|report|sync|standup|review|check|update|deploy|release|backup)\b", "workflow"),
            ("every_period", r"\b(every\s+(morning|afternoon|evening|night|monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month|quarter|year))\b.*\b(i\s+|we\s+)?(check|review|run|test|update|verify|monitor|analyze|send|generate|create|build|deploy)\b", "workflow"),
            ("before_after", r"^(before|after|when|whenever|once)\s+\w+.*,?\s*(please\s+)?(make sure to|remember to|don\'t forget to|ensure to|verify|check|test|update|run|review)\b", "workflow"),
            ("before_every", r"\b(before|after)\s+(every|each|any|all)\s+\w+.*(run|test|check|review|update|verify|deploy|backup|build)\b", "workflow"),
        ],
        flags=re.IGNORECASE,
    )
    b.register()

    # ===== Habit task (EN) =====
    b.create_group("task_habit", PatternType.TASK)
    b.set_language("en")
    b.add_task_batch(
        [
            ("i_always", r"^(i|we)\s+(always|usually|typically|normally|generally|tend to|like to|try to)\s+(check|review|run|test|update|verify|monitor|read|write|build|deploy|start|begin|finish|complete|do)\b", "habit"),
            ("my_routine", r"^(my|our)\s+(routine|habit|practice|workflow|process|schedule|ritual|rule|policy|guideline|standard|procedure)\s+(is|includes|requires|involves|has)\b", "habit"),
        ],
        flags=re.IGNORECASE,
    )
    b.register()
