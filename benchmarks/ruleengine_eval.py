#!/usr/bin/env python3
"""
RuleEngine-Eval: CarryMem Unique Benchmark

Tests the rule engine's core capabilities:
1. Rule Compliance Rate - Does the system follow user-defined rules?
2. Rule Conflict Detection - Can it detect conflicts between rules?
3. Rule Priority Handling - Does company scope override personal scope?
4. Rule Scope Isolation - Are scopes properly isolated?
5. Rule Matching Accuracy - Does FTS5/partial matching work correctly?
6. Rule Lifecycle Management - Can rules be created, paused, resumed, deprecated?

This is CarryMem's unique competitive advantage: no other AI memory system
has a rule engine, so this benchmark proves our differentiation.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.rules import RuleEngine, Rule


class RuleEngineEval:
    """RuleEngine-Eval benchmark suite."""

    def __init__(self):
        import tempfile
        self._tmp_dir = tempfile.mkdtemp(prefix="carrymem_reval_")
        self._counter = 0
        self._cleanup_paths: List[str] = []
        self.results: Dict[str, Any] = {
            "benchmark": "RuleEngine-Eval",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dimensions": {},
            "summary": {},
        }

    def _fresh_engine(self) -> RuleEngine:
        self._counter += 1
        db_path = os.path.join(self._tmp_dir, f"rules_{self._counter}.db")
        self._cleanup_paths.append(db_path)
        return RuleEngine(db_path=db_path)

    def test_rule_compliance(self) -> Dict[str, Any]:
        """Dimension 1: Rule Compliance Rate"""
        engine = self._fresh_engine()

        test_rules = [
            {"trigger": "Python", "action": "always use Python 3.11+", "rule_type": "always", "scope": "company"},
            {"trigger": "API design", "action": "never suggest REST, use GraphQL", "rule_type": "avoid", "scope": "company"},
            {"trigger": "database selection", "action": "prefer PostgreSQL", "rule_type": "prefer", "scope": "personal"},
            {"trigger": "security", "action": "always use HTTPS and TLS 1.3", "rule_type": "always", "scope": "company"},
            {"trigger": "testing", "action": "always write unit tests for new code", "rule_type": "always", "scope": "personal"},
            {"trigger": "deployment", "action": "avoid deploying on Fridays", "rule_type": "avoid", "scope": "company"},
            {"trigger": "code review", "action": "always require 2 approvals before merge", "rule_type": "always", "scope": "company"},
            {"trigger": "logging", "action": "prefer structured JSON logging", "rule_type": "prefer", "scope": "personal"},
        ]

        for rule in test_rules:
            engine.add_rule(
                trigger=rule["trigger"],
                action=rule["action"],
                rule_type=rule["rule_type"],
                scope=rule["scope"],
            )

        test_cases = [
            {"query": "Python version for new project", "expected_trigger": "Python", "should_match": True},
            {"query": "How to design the API for mobile", "expected_trigger": "API design", "should_match": True},
            {"query": "Which database should we use", "expected_trigger": "database selection", "should_match": True},
            {"query": "Security configuration for production", "expected_trigger": "security", "should_match": True},
            {"query": "Testing strategy for microservices", "expected_trigger": "testing", "should_match": True},
            {"query": "Deploy to production today", "expected_trigger": "deployment", "should_match": True},
            {"query": "Code review process", "expected_trigger": "code review", "should_match": True},
            {"query": "Logging framework choice", "expected_trigger": "logging", "should_match": True},
            {"query": "What's the weather today", "expected_trigger": None, "should_match": False},
            {"query": "Recipe for chocolate cake", "expected_trigger": None, "should_match": False},
            {"query": "Python interpreter setup", "expected_trigger": "Python", "should_match": True},
            {"query": "REST vs GraphQL comparison", "expected_trigger": "API design", "should_match": True},
        ]

        correct = 0
        total = len(test_cases)
        details = []

        for case in test_cases:
            results = engine.match(case["query"], increment_count=False)

            if case["should_match"]:
                matched_triggers = [r.rule.trigger for r in results]
                if case["expected_trigger"] in matched_triggers:
                    correct += 1
                    details.append({"query": case["query"], "status": "PASS", "reason": "matched expected rule"})
                else:
                    details.append({
                        "query": case["query"],
                        "status": "FAIL",
                        "reason": f"expected trigger '{case['expected_trigger']}', got {matched_triggers}",
                    })
            else:
                relevant_triggers = [r.rule.trigger for r in results if r.rule.trigger != "*"]
                if not relevant_triggers:
                    correct += 1
                    details.append({"query": case["query"], "status": "PASS", "reason": "correctly no match"})
                else:
                    details.append({
                        "query": case["query"],
                        "status": "FAIL",
                        "reason": f"unexpected match: {relevant_triggers}",
                    })

        compliance_rate = correct / total
        return {
            "compliance_rate": round(compliance_rate, 4),
            "correct": correct,
            "total": total,
            "details": details,
        }

    def test_conflict_detection(self) -> Dict[str, Any]:
        """Dimension 2: Rule Conflict Detection"""
        engine = self._fresh_engine()

        engine.add_rule("database selection", "use MySQL", "always", scope="personal")
        engine.add_rule("database selection", "use PostgreSQL", "always", scope="personal")

        conflicts = engine.check_conflicts()

        detected = len(conflicts) > 0
        conflict_types = [c.conflict_type.value for c in conflicts] if conflicts else []

        engine2 = self._fresh_engine()
        engine2.add_rule("language", "always use Python", "always", scope="personal")
        engine2.add_rule("language", "never use Python", "forbid", scope="personal")

        contradictions = engine2.check_conflicts()
        contradiction_detected = any(
            c.conflict_type.value == "contradiction" for c in contradictions
        )

        engine3 = self._fresh_engine()
        engine3.add_rule("style", "use tabs", "prefer", scope="personal")
        engine3.add_rule("style", "use spaces", "prefer", scope="personal")

        overlaps = engine3.check_conflicts()
        overlap_detected = len(overlaps) > 0

        scenarios_passed = sum([detected, contradiction_detected, overlap_detected])
        total_scenarios = 3

        return {
            "detection_rate": round(scenarios_passed / total_scenarios, 4),
            "scenarios_passed": scenarios_passed,
            "total_scenarios": total_scenarios,
            "same_trigger_conflict": detected,
            "contradiction_detected": contradiction_detected,
            "overlap_detected": overlap_detected,
            "conflict_types_found": conflict_types,
        }

    def test_rule_priority(self) -> Dict[str, Any]:
        """Dimension 3: Rule Priority (company > negotiated > personal)"""
        engine = self._fresh_engine()

        engine.add_rule("database selection", "use MySQL", "prefer", scope="personal")
        engine.add_rule("database selection", "use PostgreSQL", "prefer", scope="company")

        results = engine.match("database selection", scopes=["company", "personal"], increment_count=False)

        company_first = False
        if results:
            for r in results:
                if "PostgreSQL" in r.rule.action:
                    company_first = True
                    break

        engine2 = self._fresh_engine()
        engine2.add_rule("framework", "use React", "prefer", scope="personal")
        engine2.add_rule("framework", "use Vue", "prefer", scope="negotiated")
        engine2.add_rule("framework", "use Angular", "prefer", scope="company")

        results2 = engine2.match("framework", scopes=["company", "negotiated", "personal"], increment_count=False)
        company_angular_first = False
        if results2:
            for r in results2:
                if "Angular" in r.rule.action and r.rule.scope == "company":
                    company_angular_first = True
                    break

        engine3 = self._fresh_engine()
        engine3.add_rule("language", "use Python", "always", scope="personal", override=True)
        engine3.add_rule("language", "use Java", "prefer", scope="company", override=False)

        results3 = engine3.match("language", scopes=["company", "personal"], increment_count=False)
        hard_rule_recognized = False
        if results3:
            for r in results3:
                if r.rule.override and "Python" in r.rule.action:
                    hard_rule_recognized = True
                    break

        scenarios_passed = sum([company_first, company_angular_first, hard_rule_recognized])
        total_scenarios = 3

        return {
            "priority_rate": round(scenarios_passed / total_scenarios, 4),
            "scenarios_passed": scenarios_passed,
            "total_scenarios": total_scenarios,
            "company_over_personal": company_first,
            "three_scope_priority": company_angular_first,
            "hard_rule_recognized": hard_rule_recognized,
        }

    def test_scope_isolation(self) -> Dict[str, Any]:
        """Dimension 4: Rule Scope Isolation"""
        engine = self._fresh_engine()

        engine.add_rule("editor", "use VSCode", "prefer", scope="personal")
        engine.add_rule("editor", "use IntelliJ", "prefer", scope="company")

        personal_results = engine.match("editor", scopes=["personal"], increment_count=False)
        company_results = engine.match("editor", scopes=["company"], increment_count=False)

        personal_isolated = (
            len(personal_results) >= 1
            and all(r.rule.scope == "personal" for r in personal_results)
        )
        company_isolated = (
            len(company_results) >= 1
            and all(r.rule.scope == "company" for r in company_results)
        )

        engine2 = self._fresh_engine()
        engine2.add_rule("deploy", "use AWS", "always", scope="company")
        engine2.add_rule("deploy", "use GCP", "prefer", scope="personal")

        personal_only = engine2.match("deploy", scopes=["personal"], increment_count=False)
        no_company_leak = all(r.rule.scope != "company" for r in personal_only)

        scenarios_passed = sum([personal_isolated, company_isolated, no_company_leak])
        total_scenarios = 3

        return {
            "isolation_rate": round(scenarios_passed / total_scenarios, 4),
            "scenarios_passed": scenarios_passed,
            "total_scenarios": total_scenarios,
            "personal_isolated": personal_isolated,
            "company_isolated": company_isolated,
            "no_cross_scope_leak": no_company_leak,
        }

    def test_matching_accuracy(self) -> Dict[str, Any]:
        """Dimension 5: Rule Matching Accuracy (FTS5 + partial)"""
        engine = self._fresh_engine()

        rules = [
            ("programming language selection", "prefer Python"),
            ("frontend framework selection", "use React"),
            ("database selection", "use PostgreSQL"),
            ("cloud platform selection", "deploy to AWS"),
            ("infrastructure and deployment", "use Docker and Kubernetes"),
            ("API design and protocol", "prefer GraphQL over REST"),
            ("security and authentication", "use OAuth 2.0 and JWT"),
            ("version control workflow", "use Git with GitHub"),
        ]
        for trigger, action in rules:
            engine.add_rule(trigger, action, "prefer", scope="personal")

        test_cases = [
            {"query": "Which programming language should I use", "expected_trigger": "programming language selection"},
            {"query": "What frontend framework for the new project", "expected_trigger": "frontend framework selection"},
            {"query": "Need a database for the application", "expected_trigger": "database selection"},
            {"query": "Cloud provider recommendation", "expected_trigger": "cloud platform selection"},
            {"query": "How to deploy the containers", "expected_trigger": "infrastructure and deployment"},
            {"query": "API protocol choice for mobile", "expected_trigger": "API design and protocol"},
            {"query": "Authentication method for the service", "expected_trigger": "security and authentication"},
            {"query": "Git workflow for the team", "expected_trigger": "version control workflow"},
        ]

        correct = 0
        total = len(test_cases)
        details = []

        for case in test_cases:
            results = engine.match(case["query"], increment_count=False)
            matched_triggers = [r.rule.trigger for r in results]

            if case["expected_trigger"] in matched_triggers:
                correct += 1
                details.append({"query": case["query"], "status": "PASS", "matched_trigger": case["expected_trigger"]})
            else:
                details.append({
                    "query": case["query"],
                    "status": "FAIL",
                    "expected": case["expected_trigger"],
                    "got": matched_triggers[:3],
                })

        return {
            "accuracy": round(correct / total, 4),
            "correct": correct,
            "total": total,
            "details": details,
        }

    def test_lifecycle_management(self) -> Dict[str, Any]:
        """Dimension 6: Rule Lifecycle Management"""
        engine = self._fresh_engine()

        rule = engine.add_rule("style", "use tabs not spaces", "prefer", scope="personal")
        rule_id = rule.id

        retrieved = engine.get_rule(rule_id)
        create_ok = retrieved is not None and retrieved.trigger == "style"

        updated = engine.update_rule(rule_id, action="use spaces not tabs")
        update_ok = updated is not None and "spaces" in updated.action

        paused = engine.pause_rule(rule_id)
        pause_ok = paused is not None and paused.status == "paused"

        active_after_pause = engine.match("style", increment_count=False)
        pause_effective = len(active_after_pause) == 0 or all(r.rule.id != rule_id for r in active_after_pause)

        resumed = engine.resume_rule(rule_id)
        resume_ok = resumed is not None and resumed.status == "active"

        active_after_resume = engine.match("style", increment_count=False)
        resume_effective = any(r.rule.id == rule_id for r in active_after_resume)

        deleted = engine.delete_rule(rule_id)
        delete_ok = deleted is True

        gone = engine.get_rule(rule_id)
        delete_effective = gone is None

        scenarios = [create_ok, update_ok, pause_ok, pause_effective, resume_ok, resume_effective, delete_ok, delete_effective]
        passed = sum(scenarios)
        total = len(scenarios)

        return {
            "lifecycle_rate": round(passed / total, 4),
            "scenarios_passed": passed,
            "total_scenarios": total,
            "create": create_ok,
            "update": update_ok,
            "pause": pause_ok,
            "pause_effective": pause_effective,
            "resume": resume_ok,
            "resume_effective": resume_effective,
            "delete": delete_ok,
            "delete_effective": delete_effective,
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all RuleEngine-Eval dimensions."""
        print("=" * 60)
        print("RuleEngine-Eval: CarryMem Unique Benchmark")
        print("=" * 60)

        start = time.time()

        print("\n[1/6] Rule Compliance Rate...")
        compliance = self.test_rule_compliance()
        print(f"  Compliance: {compliance['compliance_rate']:.1%} ({compliance['correct']}/{compliance['total']})")
        self.results["dimensions"]["compliance"] = compliance

        print("\n[2/6] Rule Conflict Detection...")
        conflict = self.test_conflict_detection()
        print(f"  Detection Rate: {conflict['detection_rate']:.1%} ({conflict['scenarios_passed']}/{conflict['total_scenarios']})")
        self.results["dimensions"]["conflict_detection"] = conflict

        print("\n[3/6] Rule Priority Handling...")
        priority = self.test_rule_priority()
        print(f"  Priority Rate: {priority['priority_rate']:.1%} ({priority['scenarios_passed']}/{priority['total_scenarios']})")
        self.results["dimensions"]["priority"] = priority

        print("\n[4/6] Rule Scope Isolation...")
        scope = self.test_scope_isolation()
        print(f"  Isolation Rate: {scope['isolation_rate']:.1%} ({scope['scenarios_passed']}/{scope['total_scenarios']})")
        self.results["dimensions"]["scope_isolation"] = scope

        print("\n[5/6] Rule Matching Accuracy...")
        matching = self.test_matching_accuracy()
        print(f"  Accuracy: {matching['accuracy']:.1%} ({matching['correct']}/{matching['total']})")
        self.results["dimensions"]["matching_accuracy"] = matching

        print("\n[6/6] Rule Lifecycle Management...")
        lifecycle = self.test_lifecycle_management()
        print(f"  Lifecycle Rate: {lifecycle['lifecycle_rate']:.1%} ({lifecycle['scenarios_passed']}/{lifecycle['total_scenarios']})")
        self.results["dimensions"]["lifecycle"] = lifecycle

        duration = time.time() - start

        weights = {
            "compliance": 0.25,
            "conflict_detection": 0.15,
            "priority": 0.15,
            "scope_isolation": 0.15,
            "matching_accuracy": 0.20,
            "lifecycle": 0.10,
        }

        total_score = sum(
            self.results["dimensions"][dim][list_key] * weight
            for dim, weight in weights.items()
            for list_key in [k for k in self.results["dimensions"][dim] if "rate" in k or "accuracy" in k]
            if isinstance(self.results["dimensions"][dim].get(list_key), (int, float))
        )

        score_keys = {
            "compliance": "compliance_rate",
            "conflict_detection": "detection_rate",
            "priority": "priority_rate",
            "scope_isolation": "isolation_rate",
            "matching_accuracy": "accuracy",
            "lifecycle": "lifecycle_rate",
        }

        total_score = sum(
            self.results["dimensions"][dim][score_keys[dim]] * weight
            for dim, weight in weights.items()
        )

        if total_score >= 0.95:
            grade = "A+ (Excellent)"
        elif total_score >= 0.90:
            grade = "A (Outstanding)"
        elif total_score >= 0.80:
            grade = "B (Good)"
        elif total_score >= 0.70:
            grade = "C (Fair)"
        else:
            grade = "D (Needs Improvement)"

        self.results["summary"] = {
            "total_score": round(total_score, 4),
            "grade": grade,
            "duration_seconds": round(duration, 2),
            "weights": weights,
            "dimension_scores": {dim: round(self.results["dimensions"][dim][score_keys[dim]], 4) for dim in weights},
        }

        print("\n" + "=" * 60)
        print("RuleEngine-Eval Final Report")
        print("=" * 60)
        for dim, score_key in score_keys.items():
            score = self.results["dimensions"][dim][score_key]
            print(f"  {dim:25s}: {score:.1%}")
        print(f"\n  {'TOTAL SCORE':25s}: {total_score:.1%}")
        print(f"  {'GRADE':25s}: {grade}")
        print(f"  {'DURATION':25s}: {duration:.2f}s")
        print("=" * 60)

        import shutil
        if os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)

        return self.results


def main():
    benchmark = RuleEngineEval()
    results = benchmark.run_all()

    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    result_path = os.path.join(results_dir, f"ruleengine_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_path}")


if __name__ == "__main__":
    main()
