#!/usr/bin/env python3
"""MCE-Bench Leaderboard: Aggregate results and output Markdown table."""
import json
import os
import glob
from datetime import datetime


def load_results(results_dir=None):
    if results_dir is None:
        results_dir = os.path.join(os.path.dirname(__file__), 'results')
    if not os.path.exists(results_dir):
        return []

    results = []
    for path in sorted(glob.glob(os.path.join(results_dir, '*.json'))):
        with open(path, 'r', encoding='utf-8') as f:
            results.append(json.load(f))
    return results


def generate_leaderboard(results):
    if not results:
        print("No benchmark results found. Run `python benchmarks/run_benchmark.py` first.")
        return

    print("# MCE-Bench Leaderboard")
    print()
    print(f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print()

    print("## Overall Results")
    print()
    print("| # | Benchmark ID | Date | Cases | Accuracy | F1 | Precision | Recall | FP | FN |")
    print("|---|-------------|------|-------|----------|-----|-----------|--------|----|----|")
    for i, r in enumerate(results, 1):
        s = r["summary"]
        date_str = r["timestamp"][:10]
        print(f"| {i} | {r['benchmark_id']} | {date_str} | {r['total_cases']} | "
              f"{s['accuracy']:.1%} | {s['f1']:.1%} | {s['precision']:.1%} | {s['recall']:.1%} | "
              f"{s['fp']} | {s['fn']} |")

    latest = results[-1]
    print()
    print("## Latest: Per-Type F1")
    print()
    print("| Type | F1 | Precision | Recall | Cases |")
    print("|------|-----|-----------|--------|-------|")
    for t, stats in sorted(latest.get("per_type", {}).items()):
        print(f"| {t} | {stats['f1']:.1%} | {stats['precision']:.1%} | {stats['recall']:.1%} | {stats['expected']} |")

    print()
    print("## Latest: Per-Language Accuracy")
    print()
    print("| Language | Accuracy | Correct / Total |")
    print("|----------|----------|-----------------|")
    for l, stats in sorted(latest.get("per_language", {}).items()):
        print(f"| {l} | {stats['accuracy']:.1%} | {stats['correct']} / {stats['total']} |")

    print()
    print("## Thresholds")
    print()
    s = latest["summary"]
    checks = [
        ("Accuracy ≥ 85%", s["accuracy"] >= 0.85),
        ("F1 ≥ 75%", s["f1"] >= 0.75),
        ("FP rate ≤ 10%", s["fp"] / max(latest["total_cases"], 1) <= 0.10),
        ("FN rate ≤ 20%", s["fn"] / max(latest["total_cases"], 1) <= 0.20),
    ]
    for label, passed in checks:
        print(f"- {'✅' if passed else '❌'} {label}")


if __name__ == "__main__":
    results = load_results()
    generate_leaderboard(results)
