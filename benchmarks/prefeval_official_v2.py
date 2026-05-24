#!/usr/bin/env python3
"""PrefEval Official Protocol Evaluation for CarryMem.

Aligned with the official PrefEval evaluation methodology (ICLR 2025 Oral):
- Multi-turn dialogue protocol (0/2/4/6/8/10 inter-turn conversations)
- Preference stated in Turn 0, inter-turns as noise, question in final turn
- Zero-shot vs Reminder vs CarryMem comparison
- LLM-as-judge 4-dimension evaluation (acknowledge/violate/hallucinate/helpful)
- Official dataset: 20 topics, 1000 explicit preference items

Usage:
    # Quick test (1 topic, 10 turns)
    python benchmarks/prefeval_official_v2.py --num-topics 1 --num-turns 10 --limit 5

    # Zero-shot + Reminder baseline (1 topic)
    python benchmarks/prefeval_official_v2.py --num-topics 1 --num-turns 10 --conditions zero-shot,reminder --limit 20

    # Full CarryMem evaluation (all topics, 10 turns)
    python benchmarks/prefeval_official_v2.py --num-topics 20 --num-turns 10 --conditions carrymem --limit 1000

    # All conditions, all topics
    python benchmarks/prefeval_official_v2.py --num-topics 20 --num-turns 10 --conditions zero-shot,reminder,carrymem
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import numpy as np
from openai import OpenAI

BENCHMARKS_DIR = Path(__file__).resolve().parent
OFFICIAL_DIR = BENCHMARKS_DIR / "PrefEval_official"
DATA_DIR = OFFICIAL_DIR / "benchmark_dataset" / "explicit_preference"
INTER_TURNS_PATH = OFFICIAL_DIR / "benchmark_dataset" / "filtered_inter_turns.json"
ERROR_TYPE_DIR = OFFICIAL_DIR / "error_type"
SRC_DIR = BENCHMARKS_DIR.parent / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

LLM_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.moka-ai.com/v1")
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "code/claude-sonnet-4-6")
JUDGE_BASE_URL = os.environ.get("JUDGE_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.moka-ai.com/v1"))
JUDGE_API_KEY = os.environ.get("JUDGE_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "code/claude-sonnet-4-6")

REMINDER_TEXT = "\nIn your response, please ensure that you take into account our earlier discussion, and provide an answer that is consistent with my preference."


def load_official_data(num_topics: int = 20, limit: int = 0, seed: int = 42):
    topics = sorted([f.replace('.json', '') for f in os.listdir(DATA_DIR) if f.endswith('.json')])
    if num_topics < len(topics):
        rng = random.Random(seed)
        rng.shuffle(topics)
        topics = topics[:num_topics]

    all_items = []
    for topic in topics:
        with open(DATA_DIR / f"{topic}.json") as f:
            items = json.load(f)
        for item in items:
            item['topic'] = topic
        all_items.extend(items)

    if limit > 0:
        rng = random.Random(seed + 1)
        rng.shuffle(all_items)
        all_items = all_items[:limit]

    print(f"Loaded {len(all_items)} items from {len(topics)} topics (seed={seed})")
    return all_items


def load_inter_turns():
    with open(INTER_TURNS_PATH) as f:
        convs = json.load(f)
    all_turns = []
    for conv in convs:
        all_turns.extend(conv['conversation'])
    print(f"Loaded {len(all_turns)} inter-turn messages from {len(convs)} conversations")
    return all_turns


def build_messages(preference: str, question: str, inter_turns: list,
                   num_turns: int, condition: str, carrymem_prompt: str = None):
    """Build OpenAI-format messages following the official PrefEval protocol.

    Protocol:
    - Turn 0: User states preference -> Assistant acknowledges
    - Turn 1~N: Inter-turn noise conversations
    - Turn N+1: User asks question (with optional reminder)
    """
    messages = [{"role": "system", "content": "You are an AI assistant."}]

    # Turn 0: User states preference
    messages.append({"role": "user", "content": preference})
    messages.append({"role": "assistant", "content": f"I understand your preference. You've mentioned that {preference.lower()} I'll keep this in mind."})

    # Turn 1~N: Inter-turn noise
    turn_count = 0
    for turn in inter_turns:
        if turn_count >= num_turns:
            break
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            messages.append({"role": "assistant", "content": content})
            turn_count += 1

    # Final turn: User asks question
    if condition == "reminder":
        messages.append({"role": "user", "content": question + REMINDER_TEXT})
    elif condition == "carrymem":
        if carrymem_prompt:
            system_msg = messages[0]
            system_msg["content"] = carrymem_prompt
            messages.append({"role": "user", "content": question})
        else:
            messages.append({"role": "user", "content": question})
    else:
        messages.append({"role": "user", "content": question})

    return messages


def generate_response(client: OpenAI, model: str, messages: list, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return f"Error: {e}"


def _parse_xml_answer(text: str, tag: str) -> str:
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _judge_call(judge_client: OpenAI, prompt: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            resp = judge_client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
                timeout=60,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
            else:
                raise e


def evaluate_acknowledge(judge_client: OpenAI, question: str, response: str) -> dict:
    prompt_path = ERROR_TYPE_DIR / "check_acknowledge.txt"
    prompt_template = prompt_path.read_text()
    prompt = prompt_template.replace("{question}", question).replace("{end_generation}", response)

    try:
        text = _judge_call(judge_client, prompt)
        preference = _parse_xml_answer(text, "preference")
        answer = _parse_xml_answer(text, "answer").lower()
        return {"acknowledged": "yes" in answer, "restatement": preference}
    except Exception as e:
        return {"acknowledged": None, "restatement": "", "error": str(e)}


def evaluate_violation(judge_client: OpenAI, preference: str, question: str, response: str) -> dict:
    prompt_path = ERROR_TYPE_DIR / "check_violation.txt"
    prompt_template = prompt_path.read_text()
    prompt = prompt_template.replace("{preference}", preference).replace("{question}", question).replace("{end_generation}", response)

    try:
        text = _judge_call(judge_client, prompt)
        answer = _parse_xml_answer(text, "answer").lower()
        return {"violated": "yes" in answer}
    except Exception as e:
        return {"violated": None, "error": str(e)}


def evaluate_hallucination(judge_client: OpenAI, preference: str, restatement: str) -> dict:
    if not restatement:
        return {"hallucinated": False}

    prompt_path = ERROR_TYPE_DIR / "check_hallucination.txt"
    prompt_template = prompt_path.read_text()
    prompt = prompt_template.replace("{preference}", preference).replace("{assistant_restatement}", restatement)

    try:
        text = _judge_call(judge_client, prompt)
        answer = _parse_xml_answer(text, "answer").lower()
        return {"hallucinated": "yes" in answer}
    except Exception as e:
        return {"hallucinated": None, "error": str(e)}


def evaluate_helpful(judge_client: OpenAI, question: str, response: str) -> dict:
    prompt_path = ERROR_TYPE_DIR / "check_helpful.txt"
    prompt_template = prompt_path.read_text()
    prompt = prompt_template.replace("{question}", question).replace("{end_generation}", response)

    try:
        text = _judge_call(judge_client, prompt)
        answer = _parse_xml_answer(text, "answer").lower()
        return {"helpful": "yes" in answer}
    except Exception as e:
        return {"helpful": None, "error": str(e)}


def compute_accuracy(results: list[dict]) -> dict:
    valid = [r for r in results if all(
        r.get(k) is not None for k in ["acknowledged", "violated", "hallucinated", "helpful"]
    )]
    errors = [r for r in results if r not in valid]
    total = len(valid)
    if total == 0:
        return {"accuracy": 0.0, "total": len(results), "valid": 0, "judge_errors": len(errors)}

    n_ack = sum(1 for r in valid if r.get("acknowledged", False))
    n_violate = sum(1 for r in valid if r.get("violated", False))
    n_hallucinate = sum(1 for r in valid if r.get("hallucinated", False))
    n_unhelpful = sum(1 for r in valid if not r.get("helpful", True))

    n_inconsistent = sum(1 for r in valid
                         if r.get("acknowledged") and not r.get("hallucinated") and r.get("violated") and r.get("helpful"))
    n_halluc_violate = sum(1 for r in valid
                           if r.get("acknowledged") and r.get("hallucinated") and r.get("violated") and r.get("helpful"))
    n_unaware_violate = sum(1 for r in valid
                            if not r.get("acknowledged") and r.get("violated") and r.get("helpful"))

    n_errors = n_inconsistent + n_halluc_violate + n_unaware_violate + n_unhelpful
    accuracy = (total - n_errors) / total

    return {
        "accuracy": accuracy,
        "total": len(results),
        "valid": total,
        "judge_errors": len(errors),
        "acknowledged": n_ack,
        "violated": n_violate,
        "hallucinated": n_hallucinate,
        "unhelpful": n_unhelpful,
        "inconsistent": n_inconsistent,
        "hallucination_violation": n_halluc_violate,
        "unaware_violation": n_unaware_violate,
    }


def run_carrymem_condition(item: dict, inter_turns: list, num_turns: int,
                           llm_client: OpenAI, llm_model: str) -> tuple[str, str]:
    """Run CarryMem condition: store preference + inter-turns, then build_qa_prompt."""
    from carrymem import CarryMem

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()

    cm = CarryMem(storage="sqlite", db_path=db_path, namespace=f"prefeval_{item['topic']}")

    try:
        cm.classify_and_remember(item["preference"])

        turn_count = 0
        for turn in inter_turns:
            if turn_count >= num_turns:
                break
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role == "user":
                # Store inter-turn user messages as session_summary to prevent
                # noise (e.g., Terraform code) from being classified as preferences.
                try:
                    cm.classify_and_remember(
                        content,
                        force_type="session_summary",
                    )
                except Exception:
                    pass
            elif role == "assistant":
                # Store assistant replies as session_summary to preserve
                # context without polluting preference retrieval.
                try:
                    cm.classify_and_remember(
                        content,
                        force_type="session_summary",
                    )
                except Exception:
                    pass
                turn_count += 1

        prompt = cm.build_qa_prompt(question=item["question"])
        messages = build_messages(
            item["preference"], item["question"], inter_turns,
            num_turns, "carrymem", carrymem_prompt=prompt
        )
        response = generate_response(llm_client, llm_model, messages)
        return response, prompt
    finally:
        try:
            cm.close()
        except Exception:
            pass
        try:
            os.remove(db_path)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="PrefEval Official Protocol Evaluation")
    parser.add_argument("--num-topics", type=int, default=1)
    parser.add_argument("--num-turns", type=int, default=10, help="Number of inter-turn conversations (0/2/4/6/8/10)")
    parser.add_argument("--conditions", type=str, default="zero-shot,reminder,carrymem")
    parser.add_argument("--limit", type=int, default=0, help="Max items to evaluate (0=all)")
    parser.add_argument("--llm-model", type=str, default=None)
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--report", action="store_true", help="Generate Markdown comparison report")
    args = parser.parse_args()

    from dotenv import load_dotenv
    env_paths = [
        BENCHMARKS_DIR / "MemEval" / ".env",
        BENCHMARKS_DIR.parent / ".env",
        Path.home() / ".env",
    ]
    for ep in env_paths:
        if ep.exists():
            load_dotenv(ep)
            print(f"  Loaded .env from {ep}")
            break

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    llm_model = args.llm_model or os.environ.get("LLM_MODEL", LLM_MODEL)
    conditions = [c.strip() for c in args.conditions.split(",")]
    inter_turns = load_inter_turns()
    items = load_official_data(args.num_topics, args.limit, seed=args.seed)

    llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    judge_client = OpenAI(api_key=JUDGE_API_KEY, base_url=JUDGE_BASE_URL)

    print("=" * 70)
    print("PrefEval Official Protocol Evaluation")
    print("=" * 70)
    print(f"  Topics: {args.num_topics}")
    print(f"  Inter-turns: {args.num_turns}")
    print(f"  Conditions: {conditions}")
    print(f"  Items: {len(items)}")
    print(f"  LLM: {llm_model}")
    print(f"  Judge: {JUDGE_MODEL}")
    print(f"  Judge enabled: {not args.skip_judge}")
    print("=" * 70)

    all_condition_results = {}
    consecutive_judge_errors = 0

    for condition in conditions:
        print(f"\n{'='*60}")
        print(f"  CONDITION: {condition}")
        print(f"{'='*60}")

        results = []
        for i, item in enumerate(items):
            preference = item["preference"]
            question = item["question"]
            topic = item.get("topic", "unknown")

            if condition == "carrymem":
                response, system_prompt = run_carrymem_condition(
                    item, inter_turns, args.num_turns, llm_client, llm_model
                )
            else:
                messages = build_messages(preference, question, inter_turns, args.num_turns, condition)
                response = generate_response(llm_client, llm_model, messages)
                system_prompt = None

            result = {
                "index": i,
                "topic": topic,
                "preference": preference,
                "question": question,
                "response": response,
                "condition": condition,
                "num_turns": args.num_turns,
            }

            if system_prompt:
                result["system_prompt"] = system_prompt[:500]

            if not args.skip_judge:
                ack = evaluate_acknowledge(judge_client, question, response)
                result["acknowledged"] = ack["acknowledged"]
                result["restatement"] = ack.get("restatement", "")

                # Check for judge errors and pause if API is unstable
                if ack.get("error"):
                    consecutive_judge_errors += 1
                    if consecutive_judge_errors >= 3:
                        print(f"  ⚠️  {consecutive_judge_errors} consecutive judge errors — pausing 30s for API recovery...")
                        import time as _time
                        _time.sleep(30)
                        ack = evaluate_acknowledge(judge_client, question, response)
                        result["acknowledged"] = ack["acknowledged"]
                        result["restatement"] = ack.get("restatement", "")
                        if ack.get("error"):
                            print(f"  ❌ Judge still failing after pause. Stopping to avoid wasting time.")
                            print(f"  Completed {i}/{len(items)} items. Run with --skip-judge to continue without judging.")
                            break
                        consecutive_judge_errors = 0
                else:
                    consecutive_judge_errors = 0

                hal = evaluate_hallucination(judge_client, preference, result.get("restatement", ""))
                result["hallucinated"] = hal["hallucinated"]

                vio = evaluate_violation(judge_client, preference, question, response)
                result["violated"] = vio["violated"]

                hlp = evaluate_helpful(judge_client, question, response)
                result["helpful"] = hlp["helpful"]

            results.append(result)

            if (i + 1) % 5 == 0:
                acc = compute_accuracy(results)
                print(f"  [{condition}] {i+1}/{len(items)} — Running accuracy: {acc['accuracy']:.3f}")

        acc = compute_accuracy(results)
        print(f"\n  {condition} Results:")
        print(f"    Accuracy: {acc['accuracy']:.3f} ({acc['total']} items)")
        print(f"    Acknowledged: {acc['acknowledged']}/{acc['total']}")
        print(f"    Violated: {acc['violated']}/{acc['total']}")
        print(f"    Hallucinated: {acc['hallucinated']}/{acc['total']}")
        print(f"    Unhelpful: {acc['unhelpful']}/{acc['total']}")

        all_condition_results[condition] = {"accuracy": acc, "results": results}

    # Save results
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = BENCHMARKS_DIR / "PrefEval_official" / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"prefeval_{args.num_turns}turn_{ts}.json"

    summary = {}
    for cond, data in all_condition_results.items():
        summary[cond] = data["accuracy"]

    # Config fingerprint for reproducibility tracking
    config_str = f"{llm_model}|{JUDGE_MODEL}|{args.num_topics}|{args.num_turns}|{args.seed}|{','.join(sorted(conditions))}"
    config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]

    payload = {
        "timestamp": datetime.now().isoformat(),
        "num_topics": args.num_topics,
        "num_turns": args.num_turns,
        "seed": args.seed,
        "llm_model": llm_model,
        "judge_model": JUDGE_MODEL,
        "conditions": conditions,
        "config_hash": config_hash,
        "summary": summary,
        "results": {cond: data["results"] for cond, data in all_condition_results.items()},
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")

    # Print comparison table
    print(f"\n{'='*70}")
    print(f"PREFEVAL RESULTS ({args.num_turns} inter-turns, {len(items)} items)")
    print(f"{'='*70}")
    print(f"  {'Condition':15} {'Accuracy':>10} {'Ack':>6} {'Violate':>8} {'Halluc':>8} {'Unhelp':>8}")
    print(f"  {'-'*15} {'-'*10} {'-'*6} {'-'*8} {'-'*8} {'-'*8}")
    for cond in conditions:
        acc = summary[cond]
        print(f"  {cond:15} {acc['accuracy']:>10.3f} {acc['acknowledged']:>6} {acc['violated']:>8} {acc['hallucinated']:>8} {acc['unhelpful']:>8}")

    # Generate Markdown report
    if args.report:
        report_path = out_dir / f"prefeval_report_{ts}.md"
        _generate_markdown_report(payload, report_path, len(items))
        print(f"\n  Report: {report_path}")


def _generate_markdown_report(payload: dict, report_path: Path, total_items: int):
    """Generate a structured Markdown comparison report."""
    lines = []
    lines.append("# PrefEval Evaluation Report\n")
    lines.append(f"**Date**: {payload['timestamp']}")
    lines.append(f"**Config Hash**: `{payload['config_hash']}`")
    lines.append(f"**Seed**: {payload['seed']}")
    lines.append(f"**LLM Model**: {payload['llm_model']}")
    lines.append(f"**Judge Model**: {payload['judge_model']}")
    lines.append(f"**Topics**: {payload['num_topics']}")
    lines.append(f"**Inter-turns**: {payload['num_turns']}")
    lines.append(f"**Total Items**: {total_items}")
    lines.append("")

    # Summary table
    lines.append("## Results Summary\n")
    lines.append("| Condition | Accuracy | Acknowledged | Violated | Hallucinated | Unhelpful |")
    lines.append("|-----------|----------|-------------|----------|-------------|-----------|")
    for cond in payload["conditions"]:
        acc = payload["summary"][cond]
        lines.append(
            f"| {cond} | {acc['accuracy']:.3f} | {acc['acknowledged']}/{acc['total']} "
            f"| {acc['violated']}/{acc['total']} | {acc['hallucinated']}/{acc['total']} "
            f"| {acc['unhelpful']}/{acc['total']} |"
        )
    lines.append("")

    # Per-topic breakdown (if available)
    results = payload.get("results", {})
    if results:
        topic_stats = {}
        for cond, items_list in results.items():
            for item in items_list:
                topic = item.get("topic", "unknown")
                if topic not in topic_stats:
                    topic_stats[topic] = {}
                if cond not in topic_stats[topic]:
                    topic_stats[topic][cond] = {"total": 0, "violated": 0, "hallucinated": 0, "unhelpful": 0}
                topic_stats[topic][cond]["total"] += 1
                if item.get("violated"):
                    topic_stats[topic][cond]["violated"] += 1
                if item.get("hallucinated"):
                    topic_stats[topic][cond]["hallucinated"] += 1
                if not item.get("helpful", True):
                    topic_stats[topic][cond]["unhelpful"] += 1

        if topic_stats:
            lines.append("## Per-Topic Breakdown\n")
            lines.append("| Topic | Condition | Violated | Hallucinated | Unhelpful |")
            lines.append("|-------|-----------|----------|-------------|-----------|")
            for topic in sorted(topic_stats.keys()):
                for cond in payload["conditions"]:
                    if cond in topic_stats[topic]:
                        s = topic_stats[topic][cond]
                        lines.append(
                            f"| {topic} | {cond} | {s['violated']}/{s['total']} "
                            f"| {s['hallucinated']}/{s['total']} | {s['unhelpful']}/{s['total']} |"
                        )
            lines.append("")

    # CarryMem vs Reminder comparison
    carrymem_acc = payload["summary"].get("carrymem", {}).get("accuracy")
    reminder_acc = payload["summary"].get("reminder", {}).get("accuracy")
    if carrymem_acc is not None and reminder_acc is not None:
        lines.append("## CarryMem vs Reminder\n")
        diff = carrymem_acc - reminder_acc
        lines.append(f"- CarryMem: **{carrymem_acc:.3f}**")
        lines.append(f"- Reminder: {reminder_acc:.3f}")
        lines.append(f"- Delta: **{diff:+.3f}** ({'CarryMem leads' if diff > 0 else 'Reminder leads'})")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by PrefEval Official V2 (seed={payload['seed']}, config={payload['config_hash']})*")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
