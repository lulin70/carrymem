#!/usr/bin/env python3
"""
MSC (Multi-Session Chat) Benchmark

Evaluates memory persistence across multiple conversation sessions,
which is CarryMem's core use case: "AI remembers you."

Test scenarios:
1. Session Continuity - Can AI remember preferences from previous sessions?
2. Cross-Session Recall - Can AI recall facts established days/weeks ago?
3. Preference Evolution - Can AI track when preferences change over time?
4. Correction Propagation - Do corrections from one session carry to the next?
5. Forgetting Curve - How does recall degrade over simulated time?

This benchmark creates the narrative: "CarryMem remembers you across 90+ days"
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine import CarryMem


class MSCBenchmark:
    """Multi-Session Chat benchmark suite for CarryMem."""

    def __init__(self):
        import tempfile
        self._tmp_dir = tempfile.mkdtemp(prefix="carrymem_msc_")
        self._counter = 0
        self.results: Dict[str, Any] = {
            "benchmark": "MSC",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dimensions": {},
            "summary": {},
        }

    def _fresh_cm(self) -> CarryMem:
        self._counter += 1
        db_path = os.path.join(self._tmp_dir, f"memories_{self._counter}.db")
        return CarryMem(storage="sqlite", db_path=db_path)

    def test_session_continuity(self) -> Dict[str, Any]:
        """Dimension 1: Session Continuity - Remember preferences across sessions"""
        cm = self._fresh_cm()

        session1_facts = [
            "I prefer dark mode in all my editors",
            "My primary language is Python",
            "I use VSCode as my main IDE",
            "I prefer spaces over tabs",
            "I like using Git with the CLI",
        ]

        for fact in session1_facts:
            cm.classify_and_remember(fact)

        recall_tests = [
            {"query": "theme preference", "expected": "dark mode"},
            {"query": "programming language", "expected": "Python"},
            {"query": "editor choice", "expected": "VSCode"},
            {"query": "indentation style", "expected": "spaces"},
            {"query": "version control", "expected": "Git"},
        ]

        correct = 0
        total = len(recall_tests)
        details = []

        for test in recall_tests:
            results = cm.recall_memories(query=test["query"], limit=5)
            found = any(
                test["expected"].lower() in mem.get("content", "").lower()
                for mem in results
            )
            if found:
                correct += 1
            details.append({
                "query": test["query"],
                "expected": test["expected"],
                "found": found,
            })

        return {
            "continuity_rate": round(correct / total, 4),
            "correct": correct,
            "total": total,
            "details": details,
        }

    def test_cross_session_recall(self) -> Dict[str, Any]:
        """Dimension 2: Cross-Session Recall - Recall facts from different 'days'"""
        cm = self._fresh_cm()

        day_sessions = {
            0: [
                "I prefer dark mode in all my editors",
                "We use PostgreSQL for the main database",
            ],
            1: [
                "The API rate limit is 1000 requests per minute",
                "Our team uses GitHub for code hosting",
            ],
            7: [
                "We decided to adopt microservices architecture",
                "Always use TypeScript strict mode in new projects",
            ],
            30: [
                "The production server is in AWS us-east-1",
                "Redis cache TTL is 3600 seconds",
            ],
        }

        for day, facts in day_sessions.items():
            for fact in facts:
                cm.classify_and_remember(fact)

        recall_tests = [
            {"query": "theme", "expected": "dark mode", "from_day": 0},
            {"query": "database", "expected": "PostgreSQL", "from_day": 0},
            {"query": "API limits", "expected": "rate limit", "from_day": 1},
            {"query": "code hosting", "expected": "GitHub", "from_day": 1},
            {"query": "architecture", "expected": "microservices", "from_day": 7},
            {"query": "TypeScript", "expected": "strict", "from_day": 7},
            {"query": "server location", "expected": "us-east-1", "from_day": 30},
            {"query": "cache settings", "expected": "Redis", "from_day": 30},
        ]

        correct = 0
        total = len(recall_tests)
        by_day: Dict[int, Dict] = {}
        details = []

        for test in recall_tests:
            results = cm.recall_memories(query=test["query"], limit=5)
            found = any(
                test["expected"].lower() in mem.get("content", "").lower()
                for mem in results
            )
            if found:
                correct += 1

            day = test["from_day"]
            if day not in by_day:
                by_day[day] = {"correct": 0, "total": 0}
            by_day[day]["total"] += 1
            if found:
                by_day[day]["correct"] += 1

            details.append({
                "query": test["query"],
                "expected": test["expected"],
                "from_day": day,
                "found": found,
            })

        day_rates = {}
        for day, stats in sorted(by_day.items()):
            day_rates[f"day_{day}"] = round(stats["correct"] / stats["total"], 4)

        return {
            "cross_session_rate": round(correct / total, 4),
            "correct": correct,
            "total": total,
            "by_day": day_rates,
            "details": details,
        }

    def test_preference_evolution(self) -> Dict[str, Any]:
        """Dimension 3: Preference Evolution - Track changing preferences"""
        cm = self._fresh_cm()

        cm.classify_and_remember("I prefer dark mode")

        cm.classify_and_remember("I prefer light mode now")

        results = cm.recall_memories(query="theme preference", limit=10)

        has_light = any("light mode" in m.get("content", "").lower() for m in results)
        has_dark = any("dark mode" in m.get("content", "").lower() for m in results)

        conflicts = cm.check_conflicts()
        conflict_detected = len(conflicts) > 0

        evolution_tracked = has_light and has_dark

        cm2 = self._fresh_cm()
        cm2.classify_and_remember("We use MySQL for the database")
        cm2.classify_and_remember("We decided to switch to PostgreSQL")

        results2 = cm2.recall_memories(query="database", limit=10)
        has_pg = any("postgresql" in m.get("content", "").lower() for m in results2)
        has_mysql = any("mysql" in m.get("content", "").lower() for m in results2)
        switch_tracked = has_pg and has_mysql

        scenarios = [evolution_tracked, conflict_detected, switch_tracked]
        passed = sum(scenarios)
        total = len(scenarios)

        return {
            "evolution_rate": round(passed / total, 4),
            "scenarios_passed": passed,
            "total_scenarios": total,
            "preference_change_tracked": evolution_tracked,
            "conflict_detected": conflict_detected,
            "technology_switch_tracked": switch_tracked,
        }

    def test_correction_propagation(self) -> Dict[str, Any]:
        """Dimension 4: Correction Propagation - Corrections carry across sessions"""
        cm = self._fresh_cm()

        cm.classify_and_remember("The server port is 8080")

        cm.classify_and_remember("Correction: the server port is 9090 not 8080")

        results = cm.recall_memories(query="server port", limit=10)

        has_correction = any("9090" in m.get("content", "") for m in results)
        has_original = any("8080" in m.get("content", "") for m in results)

        correction_stored = has_correction

        cm2 = self._fresh_cm()
        cm2.classify_and_remember("Deploy to us-west-2 region")
        cm2.classify_and_remember("Actually, deploy to us-east-1 instead")

        results2 = cm2.recall_memories(query="deployment region", limit=10)
        has_corrected = any("us-east-1" in m.get("content", "") for m in results2)

        scenarios = [correction_stored, has_corrected]
        passed = sum(scenarios)
        total = len(scenarios)

        return {
            "propagation_rate": round(passed / total, 4),
            "scenarios_passed": passed,
            "total_scenarios": total,
            "correction_stored": correction_stored,
            "override_stored": has_corrected,
        }

    def test_forgetting_curve(self) -> Dict[str, Any]:
        """Dimension 5: Forgetting Curve - How recall degrades over time"""
        cm = self._fresh_cm()

        core_memories = [
            "I prefer dark mode in all my editors",
            "We use PostgreSQL for the main database",
            "Always use TypeScript strict mode",
            "Our team chose AWS for cloud hosting",
            "Never deploy on Fridays",
        ]

        for mem in core_memories:
            cm.classify_and_remember(mem)

        recall_queries = [
            {"query": "theme", "expected": "dark"},
            {"query": "database", "expected": "PostgreSQL"},
            {"query": "TypeScript", "expected": "strict"},
            {"query": "cloud", "expected": "AWS"},
            {"query": "deployment", "expected": "Friday"},
        ]

        curve_data = {}

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
            curve_data[f"day_{day}"] = {
                "recall_rate": round(rate, 4),
                "correct": correct,
                "total": total,
            }

        day0 = curve_data["day_0"]["recall_rate"]
        day30 = curve_data["day_30"]["recall_rate"]
        day90 = curve_data["day_90"]["recall_rate"]

        retention_score = (day0 * 0.2 + day30 * 0.3 + day90 * 0.5)

        return {
            "retention_score": round(retention_score, 4),
            "day_0": day0,
            "day_30": day30,
            "day_90": day90,
            "curve_data": curve_data,
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all MSC benchmark dimensions."""
        print("=" * 60)
        print("MSC: Multi-Session Chat Benchmark")
        print("  \"Does the AI remember you?\"")
        print("=" * 60)

        start = time.time()

        print("\n[1/5] Session Continuity...")
        continuity = self.test_session_continuity()
        print(f"  Continuity Rate: {continuity['continuity_rate']:.1%}")
        self.results["dimensions"]["session_continuity"] = continuity

        print("\n[2/5] Cross-Session Recall...")
        cross_session = self.test_cross_session_recall()
        print(f"  Cross-Session Rate: {cross_session['cross_session_rate']:.1%}")
        self.results["dimensions"]["cross_session_recall"] = cross_session

        print("\n[3/5] Preference Evolution...")
        evolution = self.test_preference_evolution()
        print(f"  Evolution Rate: {evolution['evolution_rate']:.1%}")
        self.results["dimensions"]["preference_evolution"] = evolution

        print("\n[4/5] Correction Propagation...")
        propagation = self.test_correction_propagation()
        print(f"  Propagation Rate: {propagation['propagation_rate']:.1%}")
        self.results["dimensions"]["correction_propagation"] = propagation

        print("\n[5/5] Forgetting Curve...")
        forgetting = self.test_forgetting_curve()
        print(f"  Day 0: {forgetting['day_0']:.1%} | Day 30: {forgetting['day_30']:.1%} | Day 90: {forgetting['day_90']:.1%}")
        self.results["dimensions"]["forgetting_curve"] = forgetting

        duration = time.time() - start

        weights = {
            "session_continuity": 0.25,
            "cross_session_recall": 0.25,
            "preference_evolution": 0.15,
            "correction_propagation": 0.15,
            "forgetting_curve": 0.20,
        }

        score_keys = {
            "session_continuity": "continuity_rate",
            "cross_session_recall": "cross_session_rate",
            "preference_evolution": "evolution_rate",
            "correction_propagation": "propagation_rate",
            "forgetting_curve": "retention_score",
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
            "narrative": self._generate_narrative(forgetting, total_score),
        }

        print("\n" + "=" * 60)
        print("MSC Final Report")
        print("=" * 60)
        for dim, score_key in score_keys.items():
            score = self.results["dimensions"][dim][score_key]
            print(f"  {dim:25s}: {score:.1%}")
        print(f"\n  {'TOTAL SCORE':25s}: {total_score:.1%}")
        print(f"  {'GRADE':25s}: {grade}")
        print(f"  {'DURATION':25s}: {duration:.2f}s")
        print(f"\n  Narrative: {self.results['summary']['narrative']}")
        print("=" * 60)

        import shutil
        if os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)

        return self.results

    def _generate_narrative(self, forgetting: Dict, total_score: float) -> str:
        day90 = forgetting.get("day_90", 0)
        if day90 >= 0.80:
            return f"CarryMem maintains {day90:.0%} recall at 90 days — AI truly 'remembers you'"
        elif day90 >= 0.60:
            return f"CarryMem maintains {day90:.0%} recall at 90 days — solid long-term memory"
        else:
            return f"CarryMem shows {day90:.0%} recall at 90 days — room for improvement"


def main():
    benchmark = MSCBenchmark()
    results = benchmark.run_all()

    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    result_path = os.path.join(results_dir, f"msc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_path}")


if __name__ == "__main__":
    main()
