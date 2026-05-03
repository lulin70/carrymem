#!/usr/bin/env python3
"""MCE-Bench: Run benchmark from JSON dataset and output results."""
import json
import sys
import os
import time
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine.engine import MemoryClassificationEngine


def load_dataset(lang=None):
    dataset_dir = os.path.join(os.path.dirname(__file__), 'dataset')
    langs = [lang] if lang else ['en', 'zh', 'ja']
    cases = []
    for l in langs:
        path = os.path.join(dataset_dir, f'{l}.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                cases.extend(json.load(f))
    return cases


def run_benchmark(cases):
    engine = MemoryClassificationEngine()
    results = []
    tp = tn = fp = fn = 0
    type_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "expected": 0})
    lang_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    category_stats = defaultdict(lambda: {"total": 0, "correct": 0})

    start = time.time()
    for case in cases:
        msg = case["message"]
        expected_type = case.get("expected_type")
        should_remember = case["should_remember"]
        lang = case.get("language", "unknown")
        category = case.get("category", "unknown")

        result = engine.process_message(msg)
        matches = result.get("matches", [])
        actual_types = [m.get("memory_type") or m.get("type") for m in matches]
        got_match = len(matches) > 0

        type_stats[expected_type or "none"]["expected"] += 1

        if should_remember and got_match:
            if expected_type in actual_types:
                tp += 1
                type_stats[expected_type]["tp"] += 1
                is_correct = True
                error_type = "TP"
            else:
                fn += 1
                type_stats[expected_type]["fn"] += 1
                is_correct = False
                error_type = "TYPE_MISMATCH"
        elif should_remember and not got_match:
            fn += 1
            type_stats[expected_type]["fn"] += 1
            is_correct = False
            error_type = "FN"
        elif not should_remember and not got_match:
            tn += 1
            is_correct = True
            error_type = "TN"
        else:
            fp += 1
            type_stats[matches[0].get("memory_type", "unknown")]["fp"] += 1
            is_correct = False
            error_type = "FP"

        lang_stats[lang]["total"] += 1
        if is_correct:
            lang_stats[lang]["correct"] += 1

        category_stats[category]["total"] += 1
        if is_correct:
            category_stats[category]["correct"] += 1

        results.append({
            "id": case["id"],
            "message": msg[:80],
            "expected": expected_type,
            "actual": actual_types[0] if actual_types else None,
            "correct": is_correct,
            "error_type": error_type,
        })

    duration = time.time() - start
    total = len(cases)
    accuracy = (tp + tn) / max(total, 1)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 0.001)

    report = {
        "benchmark_id": f"mce-bench-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "timestamp": datetime.utcnow().isoformat(),
        "engine_version": "0.3.0",
        "total_cases": total,
        "duration_seconds": round(duration, 2),
        "summary": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        },
        "per_type": {},
        "per_language": {},
        "per_category": {},
        "failures": [r for r in results if not r["correct"]][:30],
    }

    for t, s in type_stats.items():
        if s["expected"] > 0 and t != "none":
            p = s["tp"] / max(s["tp"] + s["fp"], 1)
            r = s["tp"] / max(s["tp"] + s["fn"], 1)
            report["per_type"][t] = {
                "f1": round(2 * p * r / max(p + r, 0.001), 4),
                "precision": round(p, 4),
                "recall": round(r, 4),
                "expected": s["expected"],
            }

    for l, s in lang_stats.items():
        report["per_language"][l] = {
            "total": s["total"],
            "correct": s["correct"],
            "accuracy": round(s["correct"] / max(s["total"], 1), 4),
        }

    for c, s in category_stats.items():
        report["per_category"][c] = {
            "total": s["total"],
            "correct": s["correct"],
            "accuracy": round(s["correct"] / max(s["total"], 1), 4),
        }

    return report


def print_report(report):
    s = report["summary"]
    print("=" * 60)
    print(f"MCE-Bench Report — {report['benchmark_id']}")
    print(f"Engine: CarryMem v{report['engine_version']}")
    print(f"Cases: {report['total_cases']} | Duration: {report['duration_seconds']}s")
    print("=" * 60)
    print(f"  Accuracy:  {s['accuracy']:.1%}")
    print(f"  Precision: {s['precision']:.1%}")
    print(f"  Recall:    {s['recall']:.1%}")
    print(f"  F1:        {s['f1']:.1%}")
    print(f"  TP={s['tp']} TN={s['tn']} FP={s['fp']} FN={s['fn']}")
    print()

    print("Per Type:")
    print("-" * 50)
    for t, stats in sorted(report["per_type"].items()):
        print(f"  {t:25s} F1={stats['f1']:.1%}  P={stats['precision']:.1%}  R={stats['recall']:.1%}  (n={stats['expected']})")
    print()

    print("Per Language:")
    print("-" * 50)
    for l, stats in sorted(report["per_language"].items()):
        print(f"  {l:5s} Accuracy={stats['accuracy']:.1%}  ({stats['correct']}/{stats['total']})")
    print()

    failures = report["failures"]
    if failures:
        print(f"Failures (showing {len(failures)}):")
        print("-" * 50)
        for f in failures:
            print(f"  [{f['error_type']}] {f['id']}: expected={f['expected']} got={f['actual']}")
            print(f"    \"{f['message']}\"")

    print()
    pass_all = s["accuracy"] >= 0.85 and s["f1"] >= 0.75
    print(f"{'✅ PASS' if pass_all else '❌ FAIL'} (threshold: Acc≥85%, F1≥75%)")


if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else None
    cases = load_dataset(lang)
    print(f"Running MCE-Bench with {len(cases)} cases...")
    report = run_benchmark(cases)
    print_report(report)

    results_dir = os.path.join(os.path.dirname(__file__), 'results')
    os.makedirs(results_dir, exist_ok=True)
    result_path = os.path.join(results_dir, f"{report['benchmark_id']}.json")
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {result_path}")
