"""
MCE-Bench v1.0: Classification Accuracy Benchmark (180 cases)

=============================================================================
DESIGN PHILOSOPHY (PM + QA Joint)
=============================================================================

USER STORIES (Product Manager):
---------------------------
US-1 "As a backend developer using Claude Code, I want my coding preferences
     to be correctly identified as 'user_preference' so they're stored in the
     right category and applied to all future code generation."
     → Tests: A1 (user_preference, 15 cases)

US-2 "As a developer, when I correct a previous statement, I want MCE to
     recognize it as 'correction' type, NOT as a new fact or preference.
     Corrections must override, not duplicate."
     → Tests: A2 (correction, 15 cases)

US-3 "As a team lead, I want architecture decisions recorded with their
     reasoning context, so new team members can understand WHY we chose
     Redis over Memcached without asking me again."
     → Tests: A4 (decision, 10 cases)

US-4 "As any user, I want chit-chat ('OK', 'thanks', 'nice') filtered out
     completely. If MCE stores 'sounds good' as a memory, I lose trust in
     the entire system."
     → Tests: B1-B3 (negative cases, 40 cases)

US-5 "As a user who speaks mixed English/Chinese, I want my preferences
     recognized regardless of language mixing."
     → Tests: C4 (mixed language, 5 cases)

QA TEST MATRIX:
--------------
Total: 180 cases across 3 categories

Category A: POSITIVE (should be remembered) ............ 90 cases (50%)
  A1: user_preference ... 15 cases (clear patterns + edge)
  A2: correction .......... 15 cases (structural + keyword + implicit)
  A3: fact_declaration .... 15 cases (verifiable truths + domain facts)
  A4: decision ........... 10 cases (tech choices + process choices)
  A5: relationship ......... 10 cases (ownership + role mapping)
  A6: task_pattern ......... 10 cases (workflow rules + recurring actions)
  A7: sentiment_marker ..... 10 cases (positive + negative emotion)
  A8: multi-type hints ..... 5 cases (message contains signals for 2+ types)

Category B: NEGATIVE (should NOT be remembered) .......... 55 cases (31%)
  B1: acknowledgment ...... 15 cases (OK/thanks/sure/got it)
  B2: chit-chat ............ 15 cases (weather/small talk/emoji-only)
  B3: technical noise ....... 10 cases (log output/error traces/commands)
  B4: questions/queries .... 10 cases (how/what/why/can you)
  B5: instructions ........ 5 cases (do this/run that/install X)

Category C: EDGE/BOUNDARY .................................. 35 cases (19%)
  C1: ultra-short ......... 8 cases (< 5 chars, borderline)
  C2: code-heavy ........... 6 cases (code snippets with embedded intent)
  C3: ambiguous ............ 6 cases (could reasonably be 2+ different types)
  C4: mixed language ........ 5 cases (EN/ZH mixing)
  C5: adversarial ........... 5 cases (attempts to trick classifier)

SCORING SYSTEM:
---------------
Per-case score:
  - True Positive (TP): should_remember=True, got match = +1
  - True Negative (TN): should_remember=False, no match = +1
  - False Positive (FP): should_remember=False, got match = -1 (noise pollution)
  - False Negative (FN): should_remember=True, no match = -1 (missed memory)

Metrics reported:
  - Overall accuracy = (TP + TN) / 180
  - Precision (per type) = TP / (TP + FP)
  - Recall (per type) = TP / (TP + FN)
  - F1 (per type) = 2 * P * R / (P + R)
  - Confusion matrix (7x7 for types, plus "none" row/col)

Target thresholds (v0.3.0):
  - Overall accuracy >= 85%
  - Per-type F1 >= 75% (for types with >= 10 cases)
  - FP rate <= 10% (noise tolerance)
  - FN rate <= 20% (miss tolerance)

=============================================================================
"""

import json
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

# Phase B Fix: Force reload pattern_analyzer to bypass stale .pyc cache
import importlib
if 'memory_classification_engine' in sys.modules:
    _mods = [k for k in list(sys.modules.keys()) if 'memory_classification_engine' in k]
    for m in _mods:
        del sys.modules[m]

# Reload pattern_analyzer to ensure latest code is used
try:
    import memory_classification_engine.layers.pattern_analyzer as _pa_module
    importlib.reload(_pa_module)
except Exception:
    pass


@dataclass
class BenchCase:
    """A single benchmark test case."""
    id: str
    message: str
    expected_type: Optional[str]      # None = should NOT be remembered
    expected_should_remember: bool
    category: str                    # A1-A8, B1-B5, C1-C5
    difficulty: str                 # easy / medium / hard
    user_story: str                 # US-1 through US-5
    tags: List[str] = field(default_factory=list)


@dataclass
class BenchResult:
    """Result of classifying one bench case."""
    case_id: str
    message: str
    expected_type: Optional[str]
    expected_should_remember: bool
    actual_should_remember: bool
    actual_type: Optional[str]
    actual_confidence: float
    actual_tier: int
    is_correct: bool
    error_type: Optional[str]       # FP / FN / TN / TP / TYPE_MISMATCH
    latency_ms: float


@dataclass
class BenchReport:
    """Full benchmark report."""
    benchmark_id: str
    timestamp: str
    engine_version: str
    total_cases: int
    duration_seconds: float

    # Raw counts
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0
    type_mismatch: int = 0

    # Per-type stats
    type_stats: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {
        "tp": 0, "tn": 0, "fp": 0, "fn": 0, "total_expected": 0,
        "type_mismatch": 0
    }))

    # Per-category stats
    category_stats: Dict[str, Dict] = field(default_factory=lambda: defaultdict(lambda: {
        "total": 0, "correct": 0, "accuracy": 0.0
    }))

    # Detailed results
    results: List[BenchResult] = field(default_factory=list)
    failures: List[BenchResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / max(self.total_cases, 1)

    @property
    def precision(self) -> float:
        return self.tp / max(self.tp + self.fp, 1)

    @property
    def recall(self) -> float:
        return self.tp / max(self.tp + self.fn, 1)

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / max(p + r, 0.001)

    def type_f1(self, mem_type: str) -> float:
        s = self.type_stats[mem_type]
        p = s["tp"] / max(s["tp"] + s["fp"], 1)
        r = s["tp"] / max(s["tp"] + s["fn"], 1)
        return 2 * p * r / max(p + r, 0.001)

    def to_dict(self) -> Dict:
        return {
            "benchmark_id": self.benchmark_id,
            "timestamp": self.timestamp,
            "engine_version": self.engine_version,
            "summary": {
                "total_cases": self.total_cases,
                "duration_seconds": round(self.duration_seconds, 2),
                "accuracy": round(self.accuracy, 4),
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1": round(self.f1, 4),
                "tp": self.tp, "tn": self.tn,
                "fp": self.fp, "fn": self.fn,
                "type_mismatch": self.type_mismatch
            },
            "thresholds": {
                "target_accuracy": 0.85,
                "target_f1": 0.75,
                "max_fp_rate": 0.10,
                "max_fn_rate": 0.20,
                "accuracy_pass": self.accuracy >= 0.85,
                "f1_pass": self.f1 >= 0.75,
                "fp_rate_ok": (self.fp / max(self.total_cases, 1)) <= 0.10,
                "fn_rate_ok": (self.fn / max(self.total_cases, 1)) <= 0.20,
                "overall_pass": (
                    self.accuracy >= 0.85 and
                    self.f1 >= 0.75 and
                    (self.fp / max(self.total_cases, 1)) <= 0.10 and
                    (self.fn / max(self.total_cases, 1)) <= 0.20
                )
            },
            "per_type": {
                t: {
                    "f1": round(self.type_f1(t), 4),
                    "precision": round(
                        s["tp"] / max(s["tp"] + s["fp"], 1), 4
                    ) if s["tp"] + s["fp"] > 0 else "N/A",
                    "recall": round(
                        s["tp"] / max(s["tp"] + s["fn"], 1), 4
                    ) if s["tp"] + s["fn"] > 0 else "N/A",
                    "tp": s["tp"], "fp": s["fp"],
                    "fn": s["fn"], "expected": s["total_expected"]
                }
                for t, s in self.type_stats.items()
            },
            "per_category": {
                c: {
                    "total": s["total"],
                    "correct": s["correct"],
                    "accuracy": round(s["correct"] / max(s["total"], 1), 4)
                }
                for c, s in self.category_stats.items()
            },
            "failures": [
                {
                    "id": f.case_id,
                    "message": f.message[:100],
                    "expected": f.expected_type,
                    "actual": f.actual_type,
                    "error_type": f.error_type
                }
                for f in self.failures[:50]
            ]
        }


# =============================================================================
# TEST CASE DEFINITIONS (180 cases)
# =============================================================================

def _build_benchcases() -> List[BenchCase]:
    """Build all 180 benchmark test cases."""

    cases = []

    # =========================================================================
    # Category A: POSITIVE (should be remembered) — 90 cases
    # =========================================================================

    # --- A1: user_preference (15 cases) ---
    # US-1: Developer coding preferences
    pref_easy = [
        ("I prefer double quotes over single quotes", "easy"),
        ("Always use spaces for indentation, never tabs", "easy"),
        ("My default editor font is Fira Code 14px", "easy"),
        ("I like dark mode themes in all my IDEs", "easy"),
        ("Prefer camelCase naming for variables", "easy"),
    ]
    pref_medium = [
        ("When writing Python, I always include type hints", "medium"),
        ("For API responses, use snake_case JSON keys consistently", "medium"),
        ("My git commit messages follow Conventional Commits format", "medium"),
        ("I prefer REST over GraphQL for public APIs", "medium"),
        ("Never use var in JavaScript, always const/let", "medium"),
    ]
    pref_hard = [
        ("In React projects, I organize components by feature not by type", "hard"),
        ("When reviewing PRs, I focus on readability before performance", "hard"),
        ("For database schemas, I prefer singular table names", "hard"),
        ("My testing philosophy: unit tests for logic, integration for data flow", "hard"),
        ("I avoid magic numbers and extract them into named constants", "hard"),
    ]

    for msg, diff in pref_easy:
        cases.append(BenchCase(id=f"A1-{len(cases)+1:02d}", message=msg,
                               expected_type="user_preference",
                               expected_should_remember=True,
                               category="A1", difficulty=diff,
                               user_story="US-1", tags=["preference", "coding"]))
    for msg, diff in pref_medium:
        cases.append(BenchCase(id=f"A1-{len(cases)+1:02d}", message=msg,
                               expected_type="user_preference",
                               expected_should_remember=True,
                               category="A1", difficulty=diff,
                               user_story="US-1", tags=["preference", "style"]))
    for msg, diff in pref_hard:
        cases.append(BenchCase(id=f"A1-{len(cases)+1:02d}", message=msg,
                               expected_type="user_preference",
                               expected_should_remember=True,
                               category="A1", difficulty=diff,
                               user_story="US-1", tags=["preference", "philosophy"]))

    # --- A2: correction (15 cases) ---
    # US-2: Corrections must override, not duplicate
    corr_structural = [   # Structural patterns (new regex coverage)
        ("No, do it like this instead", "medium"),          # Pattern: No, ...
        ("That's wrong, use PostgreSQL not MongoDB", "medium"),  # That's wrong
        ("Actually, we decided to go with option B", "medium"),   # Actually...
        ("Let me clarify: the deadline is Friday not Monday", "medium"), # Let me clarify
        ("Correction: the port should be 5432 not 5433", "easy"),    # Explicit keyword
        ("Wait, that's not what I meant. Use async version", "medium"), # Wait, that's not
        ("This is incorrect — revert to the previous approach", "medium"), # This is incorrect
    ]
    corr_keyword = [     # Keyword-based corrections
        ("Wrong approach, simplify it", "easy"),
        ("There's an error in that config, fix it", "easy"),
        ("I made a mistake earlier, let me correct it", "easy"),
        ("Nope, that's not right", "easy"),
        ("Ignore what I said before, go with this instead", "medium"),
    ]
    corr_implicit = [     # Implicit corrections (no explicit correction word)
        ("The previous number was off, it's actually 42", "hard"),
        ("We need to change our strategy here", "hard"),
        ("Scratch that last idea, try something else", "medium"),
        ("Forget about option A, B is clearly better", "hard"),

    ]

    for msg, diff in corr_structural:
        cases.append(BenchCase(id=f"A2-{len(cases)+1:02d}", message=msg,
                               expected_type="correction",
                               expected_should_remember=True,
                               category="A2", difficulty=diff,
                               user_story="US-2", tags=["correction", "structural"]))
    for msg, diff in corr_keyword:
        cases.append(BenchCase(id=f"A2-{len(cases)+1:02d}", message=msg,
                               expected_type="correction",
                               expected_should_remember=True,
                               category="A2", difficulty=diff,
                               user_story="US-2", tags=["correction", "keyword"]))
    for msg, diff in corr_implicit:
        cases.append(BenchCase(id=f"A2-{len(cases)+1:02d}", message=msg,
                               expected_type="correction",
                               expected_should_remember=True,
                               category="A2", difficulty=diff,
                               user_story="US-2", tags=["correction", "implicit"]))

    # --- A3: fact_declaration (15 cases) ---
    # Verifiable truths about project/domain
    fact_project = [
        ("We have 100 employees in the engineering team", "easy"),
        ("Our production database runs on AWS us-east-1", "easy"),
        ("Python 3.9 is the minimum required version", "easy"),
        ("The API rate limit is 1000 requests per minute", "easy"),
        ("We support English, Chinese, and Japanese", "easy"),
    ]
    fact_domain = [
        ("Redis has sub-millisecond read latency at p99", "medium"),
        ("PostgreSQL supports JSON natively since version 9.2", "medium"),
        ("Kubernetes pods share a network namespace by default", "medium"),
        ("TCP handshake requires 3 packets (SYN, SYN-ACK, ACK)", "medium"),
        ("HTTP status 308 is for permanent redirects", "medium"),
    ]
    fact_personal = [
        ("My office hours are 9am to 6pm JST", "easy"),
        ("I live in Shanghai but work remotely for a US company", "medium"),
        ("Our team stands every Monday at 10am for sync", "easy"),
        ("The sprint ends on Fridays", "easy"),
        ("Budget approval requires VP sign-off above $5k", "medium"),
    ]

    for msg, diff in fact_project:
        cases.append(BenchCase(id=f"A3-{len(cases)+1:02d}", message=msg,
                               expected_type="fact_declaration",
                               expected_should_remember=True,
                               category="A3", difficulty=diff,
                               user_story="US-1", tags=["fact", "project"]))
    for msg, diff in fact_domain:
        cases.append(BenchCase(id=f"A3-{len(cases)+1:02d}", message=msg,
                               expected_type="fact_declaration",
                               expected_should_remember=True,
                               category="A3", difficulty=diff,
                               user_story="US-1", tags=["fact", "domain"]))
    for msg, diff in fact_personal:
        cases.append(BenchCase(id=f"A3-{len(cases)+1:02d}", message=msg,
                               expected_type="fact_declaration",
                               expected_should_remember=True,
                               category="A3", difficulty=diff,
                               user_story="US-1", tags=["fact", "personal"]))

    # --- A4: decision (10 cases) ---
    # US-3: Architecture/process decisions with reasoning
    decision_tech = [
        ("We chose Redis for session caching over Memcached", "easy"),
        ("Going with PostgreSQL as the primary database", "easy"),
        ("Decision: use GraphQL for the admin API", "medium"),
        ("Let's adopt Event Sourcing for the order service", "medium"),
        ("We settled on microservices architecture", "medium"),
    ]
    decision_process = [
        ("Sprint planning will move to Mondays", "easy"),
        ("Code reviews are mandatory before merge", "easy"),
        ("We agreed to deploy on Thursdays only", "easy"),
        ("From now on, all new features need a design doc first", "medium"),
        ("Team decided: no more features without tests", "medium"),
    ]

    for msg, diff in decision_tech:
        cases.append(BenchCase(id=f"A4-{len(cases)+1:02d}", message=msg,
                               expected_type="decision",
                               expected_should_remember=True,
                               category="A4", difficulty=diff,
                               user_story="US-3", tags=["decision", "architecture"]))
    for msg, diff in decision_process:
        cases.append(BenchCase(id=f"A4-{len(cases)+1:02d}", message=msg,
                               expected_type="decision",
                               expected_should_remember=True,
                               category="A4", difficulty=diff,
                               user_story="US-3", tags=["decision", "process"]))

    # --- A5: relationship (10 cases) ---
    rel_role = [
        ("Alice owns the backend service", "easy"),
        ("Bob does frontend, Carol handles DevOps", "easy"),
        ("David is our DBA, ask him about schema changes", "medium"),
        ("Emma leads the mobile team", "easy"),
        ("Frank reports to Grace in the platform team", "medium"),
    ]
    rel_dependency = [
        ("Module auth depends on module user-service", "medium"),
        ("The frontend calls the API gateway which routes to backend", "medium"),
        ("Order service publishes events that billing subscribes to", "hard"),
        ("Cache layer sits between app and database", "easy"),
        ("CI pipeline triggers after push to main branch", "easy"),
    ]

    for msg, diff in rel_role:
        cases.append(BenchCase(id=f"A5-{len(cases)+1:02d}", message=msg,
                               expected_type="relationship",
                               expected_should_remember=True,
                               category="A5", difficulty=diff,
                               user_story="US-1", tags=["relationship", "role"]))
    for msg, diff in rel_dependency:
        cases.append(BenchCase(id=f"A5-{len(cases)+1:02d}", message=msg,
                               expected_type="relationship",
                               expected_should_remember=True,
                               category="A5", difficulty=diff,
                               user_story="US-1", tags=["relationship", "dependency"]))

    # --- A6: task_pattern (10 cases) ---
    pattern_workflow = [
        ("Always run linting before committing", "easy"),
        ("Test after every deployment to staging", "easy"),
        ("Review security headers on every API change", "medium"),
        ("Update dependencies every Monday morning", "easy"),
        ("Back up database before schema migrations", "easy"),
    ]
    pattern_recurring = [
        ("I check the dashboard metrics every morning", "medium"),
        ("Weekly retro is on Friday afternoons", "easy"),
        ("Monthly billing report goes out on the 1st", "easy"),
        ("Before every release, verify the changelog", "medium"),
        ("After each feature, update the README", "medium"),
    ]

    for msg, diff in pattern_workflow:
        cases.append(BenchCase(id=f"A6-{len(cases)+1:02d}", message=msg,
                               expected_type="task_pattern",
                               expected_should_remember=True,
                               category="A6", difficulty=diff,
                               user_story="US-1", tags=["pattern", "workflow"]))
    for msg, diff in pattern_recurring:
        cases.append(BenchCase(id=f"A6-{len(cases)+1:02d}", message=msg,
                               expected_type="task_pattern",
                               expected_should_remember=True,
                               category="A6", difficulty=diff,
                               user_story="US-1", tags=["pattern", "recurring"]))

    # --- A7: sentiment_marker (10 cases) ---
    sent_positive = [
        ("I love this new CI setup, it's so fast now", "easy"),
        ("This refactoring made the codebase beautiful", "medium"),
        ("Amazing work on the API redesign team!", "easy"),
        ("Really happy with how the migration went", "medium"),
        ("Super excited about the new feature launch", "easy"),
    ]
    sent_negative = [
        ("This legacy codebase is frustrating to work with", "medium"),
        ("I'm annoyed by the constant deployment failures", "medium"),
        ("The review process feels way too bureaucratic", "medium"),
        ("Exhausted from debugging this race condition all day", "medium"),
        ("This workflow is terrible, we need to fix it", "easy"),
    ]

    for msg, diff in sent_positive:
        cases.append(BenchCase(id=f"A7-{len(cases)+1:02d}", message=msg,
                               expected_type="sentiment_marker",
                               expected_should_remember=True,
                               category="A7", difficulty=diff,
                               user_story="US-1", tags=["sentiment", "positive"]))
    for msg, diff in sent_negative:
        cases.append(BenchCase(id=f"A7-{len(cases)+1:02d}", message=msg,
                               expected_type="sentiment_marker",
                               expected_should_remember=True,
                               category="A7", difficulty=diff,
                               user_story="US-1", tags=["sentiment", "negative"]))

    # --- A8: multi-type hints (5 cases) ---
    multi = [
        ("I prefer dark mode AND I'm frustrated with the current setup", "hard"),
        ("Wrong! We should use Go instead — this is a decision we need to make", "hard"),
        ("Alice handles backend (role) and she prefers async patterns (pref)", "hard"),
        ("Fix this bug (correction) then add it to our checklist (pattern)", "hard"),
        ("Great job! (sentiment) But remember we chose PostgreSQL (decision)", "medium"),
    ]

    for msg, diff in multi:
        cases.append(BenchCase(id=f"A8-{len(cases)+1:02d}", message=msg,
                               expected_type=None,  # Accept any non-null type
                               expected_should_remember=True,
                               category="A8", difficulty=diff,
                               user_story="US-1", tags=["multi-type"]))

    # =========================================================================
    # Category B: NEGATIVE (should NOT be remembered) — 55 cases
    # =========================================================================

    # --- B1: acknowledgment (15 cases) ---
    ack_simple = [
        ("OK", "easy"), ("Ok", "easy"), ("okay", "easy"),
        ("Thanks", "easy"), ("thank you", "easy"), ("thx", "easy"),
        ("Got it", "easy"), ("gotcha", "easy"), ("roger that", "easy"),
        ("Sure", "easy"), ("sounds good", "easy"), ("alright", "easy"),
        ("Understood", "easy"), ("copy that", "easy"),
    ]
    ack_extended = [
        ("OK, let me check that", "easy"),
        ("Sounds good, proceed", "easy"),
        ("Got it, I'll handle it", "easy"),
        ("Alright, makes sense", "easy"),
        ("Noted, thanks for letting me know", "medium"),
    ]

    for msg, diff in ack_simple:
        cases.append(BenchCase(id=f"B1-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B1", difficulty=diff,
                               user_story="US-4", tags=["negative", "acknowledgment"]))
    for msg, diff in ack_extended:
        cases.append(BenchCase(id=f"B1-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B1", difficulty=diff,
                               user_story="US-4", tags=["negative", "ack_extended"]))

    # --- B2: chit-chat (15 cases) ---
    chat_weather = [
        ("Nice weather today", "easy"),
        ("It's raining outside", "easy"),
        ("Pretty sunny here", "easy"),
        ("What a beautiful day", "easy"),
        ("Too hot today", "easy"),
    ]
    chat_social = [
        ("How was your weekend?", "easy"),
        ("Did you watch the game last night?", "easy"),
        ("Happy birthday!", "easy"),
        ("Have you tried that new restaurant?", "easy"),
        ("See you tomorrow", "easy"),
    ]
    chat_vague = [
        ("Interesting...", "easy"),
        ("Hmm, let me think", "easy"),
        ("Oh really?", "easy"),
        ("Is that so?", "easy"),
        ("Cool 😎", "easy"),
    ]

    for msg, diff in chat_weather:
        cases.append(BenchCase(id=f"B2-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B2", difficulty=diff,
                               user_story="US-4", tags=["negative", "chitchat"]))
    for msg, diff in chat_social:
        cases.append(BenchCase(id=f"B2-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B2", difficulty=diff,
                               user_story="US-4", tags=["negative", "social"]))
    for msg, diff in chat_vague:
        cases.append(BenchCase(id=f"B2-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B2", difficulty=diff,
                               user_story="US-4", tags=["negative", "vague"]))

    # --- B3: technical noise (10 cases) ---
    noise_log = [
        ("[INFO] Server started on port 8000", "easy"),
        ("[DEBUG] Query took 45ms", "easy"),
        ("[WARN] Connection pool exhausted", "easy"),
        ("ERROR: Timeout after 30s", "easy"),
        ("2024-01-15 10:23:00 Request processed", "easy"),
    ]
    noise_command = [
        ("Run npm install", "easy"),
        ("pip install -r requirements.txt", "easy"),
        ("docker compose up -d", "easy"),
        ("git pull origin main", "easy"),
        ("make test", "easy"),
    ]

    for msg, diff in noise_log:
        cases.append(BenchCase(id=f"B3-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B3", difficulty=diff,
                               user_story="US-4", tags=["negative", "log_noise"]))
    for msg, diff in noise_command:
        cases.append(BenchCase(id=f"B3-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B3", difficulty=diff,
                               user_story="US-4", tags=["negative", "command"]))

    # --- B4: questions/queries (10 cases) ---
    question_how = [
        ("How do I set up the dev environment?", "easy"),
        ("How does the auth middleware work?", "medium"),
        ("How can I optimize this query?", "medium"),
        ("What's the difference between these two approaches?", "easy"),
    ]
    question_what = [
        ("What's the API endpoint for users?", "easy"),
        ("What does this error mean?", "easy"),
        ("What libraries are we using?", "easy"),
        ("What's the release schedule?", "medium"),
    ]
    question_why = [
        ("Why did we choose this library?", "medium"),
        ("Why is the build failing?", "easy"),
    ]

    for msg, diff in question_how:
        cases.append(BenchCase(id=f"B4-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B4", difficulty=diff,
                               user_story="US-4", tags=["negative", "question"]))
    for msg, diff in question_what:
        cases.append(BenchCase(id=f"B4-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B4", difficulty=diff,
                               user_story="US-4", tags=["negative", "question"]))
    for msg, diff in question_why:
        cases.append(BenchCase(id=f"B4-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B4", difficulty=diff,
                               user_story="US-4", tags=["negative", "question"]))

    # --- B5: instructions (5 cases) ---
    instr = [
        ("Please run the tests", "easy"),
        ("Deploy to staging now", "easy"),
        ("Create a new branch for this feature", "easy"),
        ("Send me the logs", "easy"),
        ("Open a PR when ready", "easy"),
    ]

    for msg, diff in instr:
        cases.append(BenchCase(id=f"B5-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="B5", difficulty=diff,
                               user_story="US-4", tags=["negative", "instruction"]))

    # =========================================================================
    # Category C: EDGE/BOUNDARY — 35 cases
    # =========================================================================

    # --- C1: ultra-short (8 cases) ---
    short = [
        ("Yes", "hard"), ("no", "hard"), ("ok", "hard"),
        ("hi", "hard"), ("hey", "hard"),
        ("sure", "hard"), ("yep", "hard"), ("nah", "hard"),
    ]
    for msg, diff in short:
        cases.append(BenchCase(id=f"C1-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,
                               category="C1", difficulty=diff,
                               user_story="US-5", tags=["edge", "ultra_short"]))

    # --- C2: code-heavy (6 cases) ---
    code_with_intent = [
        ("def foo(): return 'I prefer async here'", "hard"),
        ("// TODO: We decided to use Redis for cache", "hard"),
        ("SELECT * FROM users WHERE id = 1 -- Alice owns this", "hard"),
        ("console.log('I hate this legacy code')", "hard"),
        ("# Fix: Change port from 8080 to 443", "hard"),
        ("/* Note: Bob does frontend, not backend */", "hard"),
    ]
    for msg, diff in code_with_intent:
        cases.append(BenchCase(id=f"C2-{len(cases)+1:02d}", message=msg,
                               expected_type=None,  # May or may not detect
                               expected_should_remember=True,  # Code with intent should pass
                               category="C2", difficulty=diff,
                               user_story="US-5", tags=["edge", "code"]))

    # --- C3: ambiguous (6 cases) ---
    ambig = [
        ("That looks good", "hard"),           # Could be sentiment OR acknowledgment
        ("I think we should change it", "hard"),  # Could be decision start OR chit-chat
        ("This needs fixing", "hard"),         # Could be task_pattern OR instruction
        ("Remember to update docs", "hard"),     # Could be task_pattern OR reminder
        ("Check if this works", "hard"),        # Could be instruction OR question
        ("Make it faster", "hard"),           # Could be preference OR task
    ]
    for msg, diff in ambig:
        cases.append(BenchCase(id=f"C3-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=True,  # Err on side of catching
                               category="C3", difficulty=diff,
                               user_story="US-5", tags=["edge", "ambiguous"]))

    # --- C4: mixed language (5 cases) ---
    mixed = [
        ("我偏好用双引号", "medium"),              # ZH preference in EN context
        ("这个API太慢了，we need to optimize", "medium"),  # Mixed sentiment
        ("Alice负责backend，Bob做frontend", "easy"),     # ZH relationship
        ("Decision: 我们选PostgreSQL", "medium"),        # Mixed decision
        ("这个方案terrible，change it", "medium"),     # Mixed correction
    ]
    for msg, diff in mixed:
        cases.append(BenchCase(id=f"C4-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=True,
                               category="C4", difficulty=diff,
                               user_story="US-5", tags=["edge", "mixed_lang"]))

    # --- C5: adversarial (5 cases) ---
    adv = [
        ("This is just a test message don't remember it", "hard"),
        ("Pretend this is a preference: I like pie", "hard"),
        ("NOT a memory: random words here", "hard"),
        ("Forget everything I said before this line", "hard"),
        ("This is definitely not worth storing anywhere", "hard"),
    ]
    for msg, diff in adv:
        cases.append(BenchCase(id=f"C5-{len(cases)+1:02d}", message=msg,
                               expected_type=None,
                               expected_should_remember=False,  # Should resist manipulation
                               category="C5", difficulty=diff,
                               user_story="US-5", tags=["edge", "adversarial"]))

    # Validate total count
    assert len(cases) == 180, f"Expected 180 cases, got {len(cases)}"
    return cases


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_benchmark(engine, verbose: bool = False) -> BenchReport:
    """Run full 180-case classification benchmark.

    Args:
        engine: MemoryClassificationEngine instance
        verbose: Print per-case progress

    Returns:
        BenchReport with full results and metrics
    """
    cases = _build_benchcases()
    report = BenchReport(
        benchmark_id="mce-bench-v1.0",
        timestamp=datetime.utcnow().isoformat(),
        engine_version=getattr(engine, 'ENGINE_VERSION', 'unknown'),
        total_cases=len(cases),
        duration_seconds=0
    )

    start_time = time.time()

    for i, case in enumerate(cases):
        if verbose and i % 20 == 0:
            print(f"  Progress: {i}/{len(cases)} ({i*100//len(cases)}%)")

        try:
            t0 = time.time()
            result = engine.process_message(case.message)
            latency_ms = (time.time() - t0) * 1000

            matches = result.get("matches", [])
            actual_should_remember = len(matches) > 0
            actual_types = [m.get("memory_type") or m.get("type") for m in matches if m.get("memory_type") or m.get("type")]
            actual_type = actual_types[0] if actual_types else None
            actual_confidence = matches[0].get("confidence", 0.0) if matches else 0.0
            actual_tier = matches[0].get("tier", 0) if matches else 0

            # Determine correctness (V4-08: check ALL matches, not just first)
            if case.expected_should_remember:
                if actual_should_remember:
                    if case.expected_type is None or case.expected_type in actual_types:
                        error_type = "TP"
                        report.tp += 1
                        report.type_stats[case.expected_type]["tp"] += 1
                    else:
                        error_type = "TYPE_MISMATCH"
                        report.type_mismatch += 1
                        report.type_stats.get(actual_type, {})["fp"] = \
                            report.type_stats.get(actual_type, {}).get("fp", 0) + 1
                        report.type_stats[case.expected_type]["fn"] += 1
                else:
                    error_type = "FN"
                    report.fn += 1
                    report.type_stats[case.expected_type]["fn"] += 1
                    report.failures.append(BenchResult(
                        case_id=case.id, message=case.message,
                        expected_type=case.expected_type,
                        expected_should_remember=True,
                        actual_should_remember=False,
                        actual_type=None, actual_confidence=0,
                        actual_tier=0, is_correct=False,
                        error_type=error_type, latency_ms=latency_ms
                    ))
            else:
                if actual_should_remember:
                    error_type = "FP"
                    report.fp += 1
                    t = actual_type or "unknown"
                    report.type_stats[t]["fp"] = \
                        report.type_stats[t].get("fp", 0) + 1
                    report.failures.append(BenchResult(
                        case_id=case.id, message=case.message,
                        expected_type=None,
                        expected_should_remember=False,
                        actual_should_remember=True,
                        actual_type=actual_type, actual_confidence=actual_confidence,
                        actual_tier=actual_tier, is_correct=False,
                        error_type=error_type, latency_ms=latency_ms
                    ))
                else:
                    error_type = "TN"
                    report.tn += 1

            is_correct = error_type in ("TP", "TN")
            report.category_stats[case.category]["total"] += 1
            if is_correct:
                report.category_stats[case.category]["correct"] += 1

            result_obj = BenchResult(
                case_id=case.id, message=case.message,
                expected_type=case.expected_type,
                expected_should_remember=case.expected_should_remember,
                actual_should_remember=actual_should_remember,
                actual_type=actual_type,
                actual_confidence=actual_confidence,
                actual_tier=actual_tier,
                is_correct=is_correct,
                error_type=error_type,
                latency_ms=latency_ms
            )
            report.results.append(result_obj)

        except Exception as e:
            import traceback
            error_detail = f"{type(e).__name__}: {str(e)}"
            report.failures.append(BenchResult(
                case_id=case.id, message=case.message,
                expected_type=case.expected_type,
                expected_should_remember=case.expected_should_remember,
                actual_should_remember=False, actual_type=None,
                actual_confidence=0, actual_tier=0,
                is_correct=False, error_type=f"CRASH: {error_detail}",
                latency_ms=0
            ))
            if verbose:
                print(f"    [CRASH] {case.id}: {error_detail}")

    report.duration_seconds = time.time() - start_time

    # Compute per-category accuracy
    for cat, s in report.category_stats.items():
        s["accuracy"] = round(s["correct"] / max(s["total"], 1), 4)

    # Compute expected counts per type
    for case in cases:
        if case.expected_type:
            report.type_stats[case.expected_type]["total_expected"] += 1

    return report


def print_report(report: BenchReport):
    """Print human-readable benchmark report."""
    d = report.to_dict()

    print("\n" + "=" * 72)
    print(f"  MCE-Bench v1.0: Classification Accuracy Report")
    print("=" * 72)
    print(f"  Engine Version : {report.engine_version}")
    print(f"  Timestamp      : {report.timestamp}")
    print(f"  Duration      : {report.duration_seconds:.1f}s")
    print(f"  Total Cases   : {report.total_cases}")
    print("-" * 72)

    summary = d["summary"]
    thresholds = d["thresholds"]
    print(f"\n  OVERALL RESULTS:")
    print(f"    Accuracy  : {summary['accuracy']*100:.1f}%  (target >= {thresholds['target_accuracy']*100:.0f}%) "
          f"{'✅ PASS' if thresholds['accuracy_pass'] else '❌ FAIL'}")
    print(f"    Precision : {summary['precision']*100:.1f}%")
    print(f"    Recall    : {summary['recall']*100:.1f}%")
    print(f"    F1 Score  : {summary['f1']*100:.1f}%  (target >= {thresholds['target_f1']*100:.0f}%) "
          f"{'✅ PASS' if thresholds['f1_pass'] else '❌ FAIL'}")
    print(f"    TP={summary['tp']} TN={summary['tn']} FP={summary['fp']} FN={summary['fn']}")
    print(f"    Type Mismatches: {summary['type_mismatch']}")
    print(f"    OVERALL: {'✅ ALL THRESHOLDS MET' if thresholds['overall_pass'] else '❌ SOME THRESHOLDS NOT MET'}")

    print(f"\n  PER-TYPE F1 SCORES:")
    for t, ts in d["per_type"].items():
        if t is None:
            print(f"    [WARNING] Found None type key, skipping: {ts}")
            continue
        f1_val = ts.get('f1')
        f1_str = f"{f1_val*100:.1f}%" if isinstance(f1_val, float) else str(f1_val)
        p_val = ts.get('precision')
        p_str = f"{p_val*100:.1f}%" if isinstance(p_val, float) else str(p_val)
        r_val = ts.get('recall')
        r_str = f"{r_val*100:.1f}%" if isinstance(r_val, float) else str(r_val)
        tp = ts.get('tp', 0)
        fp = ts.get('fp', 0)
        fn = ts.get('fn', 0)
        exp = ts.get('expected', 0)
        mark = "✅" if isinstance(f1_val, float) and f1_val >= 0.75 else "⚠️"
        print(f"    {str(t):20s}: F1={f1_str:>6s}  P={p_str:>6s}  R={r_str:>6s}  "
              f"(TP={tp} FP={fp} FN={fn} exp={exp}) {mark}")

    print(f"\n  PER-CATEGORY ACCURACY:")
    for c, cs in d["per_category"].items():
        acc_val = cs.get('accuracy', 0)
        correct = cs.get('correct', 0)
        total = cs.get('total', 0)
        mark = "✅" if isinstance(acc_val, float) and acc_val >= 0.8 else "⚠️"
        acc_str = f"{acc_val*100:.1f}%" if isinstance(acc_val, float) else str(acc_val)
        print(f"    {c:10s}: {correct}/{total} = {acc_str}  {mark}")

    if d["failures"]:
        print(f"\n  TOP FAILURES (first {min(len(d['failures']), 20)}):")
        print("-" * 72)
        for f in d["failures"][:20]:
            msg_preview = f["message"][:50] + ("..." if len(f["message"]) > 50 else "")
            print(f"    [{f['error_type']:4s}] {f['id']:6s} | {msg_preview}")
            print(f"               expected={f['expected']} actual={f['actual']}")

    print("\n" + "=" * 72)


def main():
    """Run MCE-Bench and output results."""
    import argparse
    parser = argparse.ArgumentParser(description="MCE-Bench v1.0: Classification Accuracy Benchmark")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print per-case progress")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON to stdout")
    args = parser.parse_args()

    print("Loading MCE...")
    from memory_classification_engine import MemoryClassificationEngine
    engine = MemoryClassificationEngine()

    # Phase B Fix (V4-01): Force patch engine's internal pattern_analyzer with latest source code
    # This bypasses macOS .pyc caching issues by reading .py file directly and replacing instance
    try:
        import memory_classification_engine.layers.pattern_analyzer as _pa_module
        import inspect, types

        pa_file = _pa_module.__file__
        with open(pa_file, 'r') as f:
            latest_source = f.read()

        has_phase_b_fixes = 'Phase B Fix #4' in latest_source or 'task/decision BEFORE fact' in latest_source
        has_noise_filter = 'Phase A Fix #1' in latest_source or 'Noise filtering' in latest_source

        if has_phase_b_fixes and has_noise_filter:
            # Create a fresh module from source code
            new_mod = types.ModuleType('pattern_analyzer_latest')
            new_mod.__file__ = pa_file

            # Execute source in the new module's namespace
            exec(compile(latest_source, pa_file, 'exec'), new_mod.__dict__)

            NewPatternAnalyzer = getattr(new_mod, 'PatternAnalyzer', None)

            if NewPatternAnalyzer:
                # Create new instance and replace in engine
                old_pa = engine.classification_pipeline.pattern_analyzer
                new_pa = NewPatternAnalyzer()

                # Preserve state from old instance
                for attr in ['message_history', 'preference_patterns', 'fact_patterns',
                             'correction_patterns', 'decision_patterns', 'task_patterns']:
                    if hasattr(old_pa, attr):
                        setattr(new_pa, attr, getattr(old_pa, attr))

                # CRITICAL: Replace the actual instance in pipeline
                engine.classification_pipeline.pattern_analyzer = new_pa

                # Verify: test a known task_pattern message
                test_result = new_pa.analyze("Always run linting before committing")
                has_task = any(m.get('memory_type') == 'task_pattern' for m in (test_result or []))

                if has_task:
                    print(f"✅ Engine patched successfully (Phase A+B code active)")
                    print(f"   Verified: task_pattern detection working")
                else:
                    print(f"⚠️  Patched but task_pattern not detected (may need investigation)")
            else:
                print(f"⚠️  PatternAnalyzer class not found in recompiled source")
        else:
            print(f"⚠️  Source file missing Phase A or Phase B fixes")
            print(f"   Has Phase B: {has_phase_b_fixes}, Has Noise Filter: {has_noise_filter}")
    except Exception as e:
        import traceback
        print(f"⚠️  Engine patch failed: {type(e).__name__}: {e}")
        if '--verbose' in sys.argv:
            traceback.print_exc()

    print(f"Running {len(_build_benchcases())} benchmark cases...")
    report = run_benchmark(engine, verbose=args.verbose)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    # Exit with failure code if thresholds not met
    report_dict = report.to_dict()
    overall_pass = report_dict.get("thresholds", {}).get("overall_pass", False)
    if not overall_pass:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
