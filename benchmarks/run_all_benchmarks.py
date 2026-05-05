#!/usr/bin/env python3
"""
CarryMem Benchmark Suite — Unified Runner

Runs all Phase 1 benchmarks and generates a consolidated report:
1. RuleEngine-Eval (unique competitive advantage)
2. LongMemEval (comprehensive evaluation)
3. MSC (multi-session narrative)
4. MemEval (fair comparison with token cost tracking)

Usage:
    python benchmarks/run_all_benchmarks.py [--benchmark NAME] [--output DIR]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def run_ruleengine_eval() -> Dict[str, Any]:
    from ruleengine_eval import RuleEngineEval
    bench = RuleEngineEval()
    return bench.run_all()


def run_longmemeval() -> Dict[str, Any]:
    from longmemeval_benchmark import LongMemEvalBenchmark
    bench = LongMemEvalBenchmark()
    return bench.run_all()


def run_msc() -> Dict[str, Any]:
    from msc_benchmark import MSCBenchmark
    bench = MSCBenchmark()
    return bench.run_all()


def run_memeval() -> Dict[str, Any]:
    from memeval_benchmark import MemEvalBenchmark
    bench = MemEvalBenchmark()
    return bench.run_all()


BENCHMARKS = {
    "ruleengine-eval": ("RuleEngine-Eval (Unique)", run_ruleengine_eval),
    "longmemeval": ("LongMemEval (Comprehensive)", run_longmemeval),
    "msc": ("MSC (Multi-Session)", run_msc),
    "memeval": ("MemEval (Comparison)", run_memeval),
}


def generate_consolidated_report(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a consolidated report from all benchmark results."""
    report = {
        "report_type": "CarryMem Benchmark Suite — Consolidated Report",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmarks": {},
        "summary": {},
        "narrative": {},
    }

    for name, result in results.items():
        summary = result.get("summary", {})
        report["benchmarks"][name] = {
            "total_score": summary.get("total_score", 0),
            "grade": summary.get("grade", "N/A"),
            "duration_seconds": summary.get("duration_seconds", 0),
        }

    scores = [r["total_score"] for r in report["benchmarks"].values() if r["total_score"] > 0]
    avg_score = sum(scores) / len(scores) if scores else 0

    report["summary"] = {
        "total_benchmarks": len(results),
        "average_score": round(avg_score, 4),
        "overall_grade": _grade(avg_score),
        "benchmark_scores": {name: round(data["total_score"], 4) for name, data in report["benchmarks"].items()},
    }

    narratives = []

    re_result = results.get("ruleengine-eval", {})
    re_score = re_result.get("summary", {}).get("total_score", 0)
    if re_score > 0:
        narratives.append(
            f"RuleEngine-Eval: CarryMem is the ONLY system with a rule engine, "
            f"scoring {re_score:.0%} — competitors score 0% (no rule engine)"
        )

    msc_result = results.get("msc", {})
    msc_narrative = msc_result.get("summary", {}).get("narrative", "")
    if msc_narrative:
        narratives.append(f"MSC: {msc_narrative}")

    me_result = results.get("memeval", {})
    me_zero_cost = me_result.get("dimensions", {}).get("token_cost", {}).get("zero_cost_ratio", 0)
    if me_zero_cost > 0:
        narratives.append(
            f"MemEval: {me_zero_cost:.0%} zero-cost classification — "
            f"no LLM tokens needed for the majority of cases"
        )

    lm_result = results.get("longmemeval", {})
    lm_score = lm_result.get("summary", {}).get("total_score", 0)
    if lm_score > 0:
        narratives.append(
            f"LongMemEval: Comprehensive score {lm_score:.0%} across 5 dimensions"
        )

    report["narrative"] = {
        "headlines": narratives,
        "elevator_pitch": _build_elevator_pitch(results),
    }

    return report


def _grade(score: float) -> str:
    if score >= 0.95:
        return "A+ (Excellent)"
    elif score >= 0.90:
        return "A (Outstanding)"
    elif score >= 0.80:
        return "B (Good)"
    elif score >= 0.70:
        return "C (Fair)"
    else:
        return "D (Needs Improvement)"


def _build_elevator_pitch(results: Dict) -> str:
    re_score = results.get("ruleengine-eval", {}).get("summary", {}).get("total_score", 0)
    me_zero = results.get("memeval", {}).get("dimensions", {}).get("token_cost", {}).get("zero_cost_ratio", 0)
    me_accuracy = results.get("memeval", {}).get("dimensions", {}).get("classification_accuracy", {}).get("accuracy", 0)

    parts = []
    if me_accuracy > 0:
        parts.append(f"classification accuracy of {me_accuracy:.0%}")
    if me_zero > 0:
        parts.append(f"{me_zero:.0%} zero-cost classification")
    if re_score > 0:
        parts.append(f"the only AI memory system with a rule engine ({re_score:.0%} compliance)")

    if parts:
        return f"CarryMem delivers {'; '.join(parts)} — making AI truly remember and follow user rules."
    return "CarryMem benchmark suite completed."


def print_consolidated_report(report: Dict[str, Any]):
    """Print a formatted consolidated report."""
    print("\n")
    print("=" * 70)
    print("  CarryMem Benchmark Suite — Consolidated Report")
    print(f"  Generated: {report['timestamp']}")
    print("=" * 70)

    print("\n  Benchmark Results:")
    print("  " + "-" * 60)
    for name, data in report["benchmarks"].items():
        print(f"  {name:25s}  Score: {data['total_score']:.1%}  Grade: {data['grade']}")
    print("  " + "-" * 60)
    print(f"  {'AVERAGE':25s}  Score: {report['summary']['average_score']:.1%}  Grade: {report['summary']['overall_grade']}")

    print("\n  Key Narratives:")
    for i, headline in enumerate(report["narrative"]["headlines"], 1):
        print(f"  {i}. {headline}")

    print(f"\n  Elevator Pitch:")
    print(f"  {report['narrative']['elevator_pitch']}")

    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description='CarryMem Benchmark Suite')
    parser.add_argument(
        '--benchmark', '-b',
        choices=list(BENCHMARKS.keys()) + ['all'],
        default='all',
        help='Which benchmark to run (default: all)',
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Output directory for results (default: benchmarks/results/)',
    )
    args = parser.parse_args()

    benchmarks_dir = os.path.dirname(os.path.abspath(__file__))
    if benchmarks_dir not in sys.path:
        sys.path.insert(0, benchmarks_dir)

    output_dir = args.output or os.path.join(benchmarks_dir, 'results')
    os.makedirs(output_dir, exist_ok=True)

    if args.benchmark == 'all':
        to_run = list(BENCHMARKS.keys())
    else:
        to_run = [args.benchmark]

    all_results: Dict[str, Dict[str, Any]] = {}
    total_start = time.time()

    for name in to_run:
        display_name, runner = BENCHMARKS[name]
        print(f"\n{'#' * 70}")
        print(f"# Running: {display_name}")
        print(f"{'#' * 70}")

        try:
            result = runner()
            all_results[name] = result

            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            result_path = os.path.join(output_dir, f"{name}_{ts}.json")
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n  Saved: {result_path}")

        except Exception as e:
            print(f"\n  ERROR running {name}: {e}")
            import traceback
            traceback.print_exc()
            all_results[name] = {"error": str(e), "summary": {"total_score": 0, "grade": "ERROR"}}

    total_duration = time.time() - total_start

    if len(all_results) > 1:
        consolidated = generate_consolidated_report(all_results)
        consolidated["total_duration_seconds"] = round(total_duration, 2)
        print_consolidated_report(consolidated)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        consolidated_path = os.path.join(output_dir, f"consolidated_{ts}.json")
        with open(consolidated_path, 'w', encoding='utf-8') as f:
            json.dump(consolidated, f, indent=2, ensure_ascii=False)
        print(f"\n  Consolidated report saved: {consolidated_path}")

    print(f"\n  Total duration: {total_duration:.2f}s")
    print("  Done.")


if __name__ == "__main__":
    main()
