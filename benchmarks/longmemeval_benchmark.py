#!/usr/bin/env python3
"""
LongMemEval: Comprehensive Memory System Benchmark

Evaluates 5 dimensions of long-term memory capability:
1. Memory Storage Accuracy - Can the system correctly classify and store memories?
2. Memory Recall Accuracy - Can the system retrieve relevant memories?
3. Long-term Retention - Does the system retain memories over time?
4. Conflict Resolution - Can the system detect and handle conflicting memories?
5. Privacy Compliance - Does the system respect namespace/scope boundaries?

Based on the LongMemEval framework methodology, adapted for CarryMem.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine import CarryMem


class LongMemEvalBenchmark:
    """LongMemEval benchmark suite for CarryMem."""

    def __init__(self):
        import tempfile
        self._tmp_dir = tempfile.mkdtemp(prefix="carrymem_lme_")
        self._counter = 0
        self.results: Dict[str, Any] = {
            "benchmark": "LongMemEval",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dimensions": {},
            "summary": {},
        }

    def _fresh_cm(self) -> CarryMem:
        self._counter += 1
        db_path = os.path.join(self._tmp_dir, f"memories_{self._counter}.db")
        return CarryMem(storage="sqlite", db_path=db_path)

    def test_storage_accuracy(self) -> Dict[str, Any]:
        """Dimension 1: Memory Storage Accuracy"""
        cm = self._fresh_cm()

        test_cases = [
            {"message": "I prefer dark mode in all my editors", "expected_type": "user_preference"},
            {"message": "We decided to use PostgreSQL for the main database", "expected_type": "decision"},
            {"message": "Actually, the deadline is next Friday not Monday", "expected_type": "correction"},
            {"message": "The API rate limit is 1000 requests per minute", "expected_type": "fact_declaration"},
            {"message": "Always use TypeScript strict mode in new projects", "expected_type": "user_preference"},
            {"message": "Let's go with microservices architecture", "expected_type": "decision"},
            {"message": "That was wrong, use the async version instead", "expected_type": "correction"},
            {"message": "Our team has 15 engineers", "expected_type": "fact_declaration"},
            {"message": "I like using vim for quick edits", "expected_type": "user_preference"},
            {"message": "We chose AWS over GCP for cloud hosting", "expected_type": "decision"},
            {"message": "Correction: the port should be 5432 not 5433", "expected_type": "correction"},
            {"message": "The staging server is at 10.0.1.50", "expected_type": "fact_declaration"},
            {"message": "Never deploy on Fridays", "expected_type": "user_preference"},
            {"message": "We agreed to use trunk-based development", "expected_type": "decision"},
            {"message": "No, use spaces not tabs for indentation", "expected_type": "correction"},
            {"message": "Redis cache TTL is set to 3600 seconds", "expected_type": "fact_declaration"},
            {"message": "Prefer composition over inheritance", "expected_type": "user_preference"},
            {"message": "Decided to migrate from REST to GraphQL", "expected_type": "decision"},
            {"message": "That approach is incorrect, try the simpler one", "expected_type": "correction"},
            {"message": "Sprint duration is 2 weeks", "expected_type": "fact_declaration"},
        ]

        correct = 0
        total = len(test_cases)
        details = []

        for case in test_cases:
            result = cm.classify_and_remember(case["message"])
            stored_type = result.get("type", "unknown")
            is_correct = stored_type == case["expected_type"]

            if is_correct:
                correct += 1
            details.append({
                "message": case["message"][:60],
                "expected": case["expected_type"],
                "actual": stored_type,
                "correct": is_correct,
            })

        accuracy = correct / total
        return {
            "accuracy": round(accuracy, 4),
            "correct": correct,
            "total": total,
            "details": details,
        }

    def test_recall_accuracy(self) -> Dict[str, Any]:
        """Dimension 2: Memory Recall Accuracy"""
        cm = self._fresh_cm()

        memories_to_store = [
            "I prefer dark mode in all my editors",
            "We decided to use PostgreSQL for the main database",
            "The API rate limit is 1000 requests per minute",
            "Always use TypeScript strict mode in new projects",
            "Our team chose AWS for cloud hosting",
            "Never deploy on Fridays",
            "The staging server IP is 10.0.1.50",
            "Redis cache TTL is set to 3600 seconds",
            "We agreed to use trunk-based development",
            "Prefer composition over inheritance in class design",
        ]

        for mem in memories_to_store:
            cm.classify_and_remember(mem)

        recall_tests = [
            {"query": "theme preference", "expected_content": "dark mode"},
            {"query": "database choice", "expected_content": "PostgreSQL"},
            {"query": "API limits", "expected_content": "rate limit"},
            {"query": "TypeScript configuration", "expected_content": "strict mode"},
            {"query": "cloud provider", "expected_content": "AWS"},
            {"query": "deployment rules", "expected_content": "Friday"},
            {"query": "server address", "expected_content": "10.0.1.50"},
            {"query": "cache settings", "expected_content": "Redis"},
            {"query": "development workflow", "expected_content": "trunk"},
            {"query": "design patterns", "expected_content": "composition"},
        ]

        correct = 0
        total = len(recall_tests)
        details = []

        for test in recall_tests:
            results = cm.recall_memories(query=test["query"], limit=5)
            found = any(
                test["expected_content"].lower() in mem.get("content", "").lower()
                for mem in results
            )

            if found:
                correct += 1
            details.append({
                "query": test["query"],
                "expected_keyword": test["expected_content"],
                "found": found,
                "result_count": len(results),
            })

        recall_rate = correct / total
        return {
            "recall_rate": round(recall_rate, 4),
            "correct": correct,
            "total": total,
            "details": details,
        }

    def test_long_term_retention(self) -> Dict[str, Any]:
        """Dimension 3: Long-term Retention (simulated time progression)"""
        cm = self._fresh_cm()

        memories_to_store = [
            "I prefer dark mode in all my editors",
            "We decided to use PostgreSQL for the main database",
            "Always use TypeScript strict mode in new projects",
            "Our team chose AWS for cloud hosting",
            "Never deploy on Fridays",
        ]

        for mem in memories_to_store:
            cm.classify_and_remember(mem)

        recall_queries = [
            {"query": "theme preference", "expected": "dark mode"},
            {"query": "database", "expected": "PostgreSQL"},
            {"query": "TypeScript", "expected": "strict"},
            {"query": "cloud", "expected": "AWS"},
            {"query": "deployment", "expected": "Friday"},
        ]

        retention_results = {}

        for day in [0, 1, 7, 30, 90]:
            correct = 0
            total = len(recall_queries)

            for test in recall_queries:
                results = cm.recall_memories(query=test["query"], limit=5)
                found = any(
                    test["expected"].lower() in mem.get("content", "").lower()
                    for mem in results
                )
                if found:
                    correct += 1

            rate = correct / total
            retention_results[f"day_{day}"] = {
                "recall_rate": round(rate, 4),
                "correct": correct,
                "total": total,
                "description": self._day_description(day),
            }

        day0_rate = retention_results["day_0"]["recall_rate"]
        day30_rate = retention_results["day_30"]["recall_rate"]
        day90_rate = retention_results["day_90"]["recall_rate"]

        retention_score = (day0_rate * 0.2 + day30_rate * 0.4 + day90_rate * 0.4)

        return {
            "retention_score": round(retention_score, 4),
            "day_0": day0_rate,
            "day_30": day30_rate,
            "day_90": day90_rate,
            "retention_curve": retention_results,
        }

    def _day_description(self, day: int) -> str:
        descriptions = {
            0: "Immediate recall",
            1: "Short-term (1 day)",
            7: "Medium-term (1 week)",
            30: "Half-life test (30 days)",
            90: "Long-term (90 days)",
        }
        return descriptions.get(day, f"Day {day}")

    def test_conflict_resolution(self) -> Dict[str, Any]:
        """Dimension 4: Conflict Resolution"""
        cm = self._fresh_cm()

        cm.classify_and_remember("I prefer dark mode")
        cm.classify_and_remember("I prefer light mode")

        conflicts = cm.check_conflicts()

        contradiction_detected = len(conflicts) > 0

        cm2 = self._fresh_cm()
        cm2.classify_and_remember("We use MySQL for the database")
        cm2.classify_and_remember("We decided to switch to PostgreSQL for the database")

        conflicts2 = cm2.check_conflicts()
        preference_change_detected = len(conflicts2) > 0

        cm3 = self._fresh_cm()
        cm3.classify_and_remember("Always use Python 3.11+")
        cm3.classify_and_remember("Always use Python 3.11+")

        conflicts3 = cm3.check_conflicts()
        duplicate_detected = len(conflicts3) > 0

        scenarios = [contradiction_detected, preference_change_detected]
        passed = sum(scenarios)
        total = len(scenarios)

        return {
            "resolution_rate": round(passed / total, 4),
            "scenarios_passed": passed,
            "total_scenarios": total,
            "contradiction_detected": contradiction_detected,
            "preference_change_detected": preference_change_detected,
            "duplicate_detected": duplicate_detected,
        }

    def test_privacy_compliance(self) -> Dict[str, Any]:
        """Dimension 5: Privacy Compliance (namespace isolation)"""
        self._counter += 1
        ns1_path = os.path.join(self._tmp_dir, f"memories_{self._counter}_ns1.db")
        ns2_path = os.path.join(self._tmp_dir, f"memories_{self._counter}_ns2.db")
        cm1 = CarryMem(storage="sqlite", db_path=ns1_path, namespace="user_alice")
        cm2 = CarryMem(storage="sqlite", db_path=ns2_path, namespace="user_bob")

        cm1.classify_and_remember("I prefer dark mode")
        cm1.classify_and_remember("We use PostgreSQL")
        cm2.classify_and_remember("I prefer light mode")
        cm2.classify_and_remember("We use MySQL")

        alice_memories = cm1.recall_memories(limit=20)
        bob_memories = cm2.recall_memories(limit=20)

        alice_has_dark = any("dark mode" in m.get("content", "") for m in alice_memories)
        alice_no_light = not any("light mode" in m.get("content", "") for m in alice_memories)
        bob_has_light = any("light mode" in m.get("content", "") for m in bob_memories)
        bob_no_dark = not any("dark mode" in m.get("content", "") for m in bob_memories)

        alice_isolated = alice_has_dark and alice_no_light
        bob_isolated = bob_has_light and bob_no_dark

        scenarios = [alice_isolated, bob_isolated]
        passed = sum(scenarios)
        total = len(scenarios)

        return {
            "compliance_rate": round(passed / total, 4),
            "scenarios_passed": passed,
            "total_scenarios": total,
            "alice_isolated": alice_isolated,
            "bob_isolated": bob_isolated,
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all LongMemEval dimensions."""
        print("=" * 60)
        print("LongMemEval: Comprehensive Memory System Benchmark")
        print("=" * 60)

        start = time.time()

        print("\n[1/5] Memory Storage Accuracy...")
        storage = self.test_storage_accuracy()
        print(f"  Accuracy: {storage['accuracy']:.1%} ({storage['correct']}/{storage['total']})")
        self.results["dimensions"]["storage_accuracy"] = storage

        print("\n[2/5] Memory Recall Accuracy...")
        recall = self.test_recall_accuracy()
        print(f"  Recall Rate: {recall['recall_rate']:.1%} ({recall['correct']}/{recall['total']})")
        self.results["dimensions"]["recall_accuracy"] = recall

        print("\n[3/5] Long-term Retention...")
        retention = self.test_long_term_retention()
        print(f"  Day 0: {retention['day_0']:.1%} | Day 30: {retention['day_30']:.1%} | Day 90: {retention['day_90']:.1%}")
        self.results["dimensions"]["long_term_retention"] = retention

        print("\n[4/5] Conflict Resolution...")
        conflict = self.test_conflict_resolution()
        print(f"  Resolution Rate: {conflict['resolution_rate']:.1%} ({conflict['scenarios_passed']}/{conflict['total_scenarios']})")
        self.results["dimensions"]["conflict_resolution"] = conflict

        print("\n[5/5] Privacy Compliance...")
        privacy = self.test_privacy_compliance()
        print(f"  Compliance Rate: {privacy['compliance_rate']:.1%} ({privacy['scenarios_passed']}/{privacy['total_scenarios']})")
        self.results["dimensions"]["privacy_compliance"] = privacy

        duration = time.time() - start

        weights = {
            "storage_accuracy": 0.20,
            "recall_accuracy": 0.25,
            "long_term_retention": 0.25,
            "conflict_resolution": 0.15,
            "privacy_compliance": 0.15,
        }

        score_keys = {
            "storage_accuracy": "accuracy",
            "recall_accuracy": "recall_rate",
            "long_term_retention": "retention_score",
            "conflict_resolution": "resolution_rate",
            "privacy_compliance": "compliance_rate",
        }

        total_score = sum(
            self.results["dimensions"][dim][score_keys[dim]] * weight
            for dim, weight in weights.items()
        )

        if total_score >= 0.90:
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
        print("LongMemEval Final Report")
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
    benchmark = LongMemEvalBenchmark()
    results = benchmark.run_all()

    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    result_path = os.path.join(results_dir, f"longmemeval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_path}")


if __name__ == "__main__":
    main()
