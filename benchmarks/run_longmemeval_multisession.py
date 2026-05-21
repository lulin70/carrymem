#!/usr/bin/env python3
"""LongMemEval Multi-Session benchmark for CarryMem.

Tests CarryMem's ability to handle multi-session reasoning questions
from the LongMemEval benchmark (ICLR 2025).

Usage:
    cd benchmarks
    python run_longmemeval_multisession.py --num-samples 10
    python run_longmemeval_multisession.py --num-samples 133 --skip-judge
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from tqdm import tqdm

BENCHMARKS_DIR = Path(__file__).resolve().parent
DATA_DIR = BENCHMARKS_DIR / "LongMemEval" / "data"
SRC_DIR = BENCHMARKS_DIR.parent / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

CATEGORY_NAMES = {
    "single-session-user": "Single-Session User",
    "single-session-assistant": "Single-Session Assistant",
    "single-session-preference": "Single-Session Preference",
    "multi-session": "Multi-Session",
    "temporal-reasoning": "Temporal Reasoning",
    "knowledge-update": "Knowledge Update",
}

LLM_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.moka-ai.com/v1")
LLM_API_KEY = os.environ.get("OPENAI_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "code/claude-sonnet-4-6")


def _normalize_item(item: dict) -> dict:
    conversation = {"speaker_a": "user", "speaker_b": "assistant"}
    haystack_sessions = item.get("haystack_sessions", [])
    haystack_dates = item.get("haystack_dates", [])
    haystack_ids = item.get("haystack_session_ids", [])

    for idx, session in enumerate(haystack_sessions):
        session_num = idx + 1
        date_str = haystack_dates[idx] if idx < len(haystack_dates) else ""
        session_id = haystack_ids[idx] if idx < len(haystack_ids) else f"session_{session_num}"

        turns = []
        for turn_idx, msg in enumerate(session):
            role = msg.get("role", "user")
            turns.append({
                "speaker": role,
                "text": msg.get("content", ""),
                "dia_id": f"{session_id}_{turn_idx}",
            })

        conversation[f"session_{session_num}"] = turns
        conversation[f"session_{session_num}_date_time"] = date_str

    answer = item.get("answer", "")
    if not isinstance(answer, str):
        answer = str(answer)

    question_id = item.get("question_id", "unknown")
    return {
        "sample_id": question_id,
        "conversation": conversation,
        "qa": [{
            "question": item.get("question", ""),
            "answer": answer,
            "category": item.get("question_type", "unknown"),
            "question_id": question_id,
        }],
    }


def extract_dialogues(conv: dict):
    dialogues = []
    conv_data = conv.get("conversation", {})
    session_nums = []
    for key in conv_data.keys():
        if key.startswith("session_") and not key.endswith("_date_time"):
            try:
                num = int(key.split("_")[1])
                session_nums.append(num)
            except (ValueError, IndexError):
                pass

    for num in sorted(session_nums):
        session_key = f"session_{num}"
        datetime_key = f"session_{num}_date_time"
        session_time = conv_data.get(datetime_key, "")
        session_turns = conv_data.get(session_key, [])

        if not isinstance(session_turns, list):
            continue

        for turn in session_turns:
            if isinstance(turn, dict):
                dialogues.append({
                    "speaker": turn.get("speaker", "Unknown"),
                    "text": turn.get("text", ""),
                    "dia_id": turn.get("dia_id", ""),
                    "timestamp": session_time,
                })

    return dialogues


def compute_f1(predicted: str, ground_truth: str) -> float:
    pred_tokens = set(re.findall(r'\b\w+\b', predicted.lower()))
    truth_tokens = set(re.findall(r'\b\w+\b', ground_truth.lower()))
    if not pred_tokens or not truth_tokens:
        return 0.0
    common = pred_tokens & truth_tokens
    if not common:
        return 0.0
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(truth_tokens)
    return 2 * precision * recall / (precision + recall)


def load_multisession_questions(split: str = "s", num_samples: int = 0):
    filename = {
        "oracle": "longmemeval_oracle.json",
        "s": "longmemeval_s_cleaned.json",
        "m": "longmemeval_m_cleaned.json",
    }[split]
    local_path = DATA_DIR / filename

    if not local_path.exists():
        print(f"Error: {local_path} not found. Download from HuggingFace first.")
        print(f"  wget https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned/resolve/main/{filename}")
        sys.exit(1)

    with open(local_path) as f:
        data = json.load(f)

    ms_items = [item for item in data if item.get("question_type") == "multi-session"]
    cats = Counter(item.get("question_type", "unknown") for item in data)
    print(f"LongMemEval ({split}): {len(data)} total questions")
    for cat, count in sorted(cats.items()):
        marker = " <<<" if cat == "multi-session" else ""
        print(f"  {cat}: {count}{marker}")

    if num_samples > 0:
        ms_items = ms_items[:num_samples]

    normalized = [_normalize_item(item) for item in ms_items]
    print(f"  Selected: {len(normalized)} multi-session questions")
    return normalized


def run_carrymem(conv: dict, llm_model: str) -> list[dict]:
    from carrymem import CarryMem

    dialogues = extract_dialogues(conv)
    n_sessions = len([k for k in conv.get("conversation", {}).keys()
                      if k.startswith("session_") and not k.endswith("_date_time")])
    n_turns = len(dialogues)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = tmp.name
    tmp.close()

    cm = CarryMem(storage="sqlite", db_path=db_path)

    for d in dialogues:
        speaker = d.get("speaker", "").lower()
        if speaker in ("user", "person1"):
            try:
                cm.classify_and_remember(d["text"])
            except Exception:
                pass
        elif speaker in ("assistant", "bot", "person2"):
            try:
                cm.classify_and_remember("[Assistant said] " + d["text"])
            except Exception:
                pass

    profile = cm.get_memory_profile()
    n_memories = profile.get("total_memories", 0)

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    model = llm_model or LLM_MODEL

    def answer_fn(question: str) -> str:
        prompt = cm.build_qa_prompt(question=question)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=200,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {e}"

    qa_pairs = conv.get("qa", [])
    sample_id = conv.get("sample_id", "unknown")
    results = []

    for qa in qa_pairs:
        question = qa.get("question", "")
        ground_truth = qa.get("answer", "")
        category = qa.get("category", "multi-session")
        question_id = qa.get("question_id", "")

        predicted = answer_fn(question)
        f1 = compute_f1(predicted, ground_truth)

        results.append({
            "sample_id": sample_id,
            "question": question,
            "ground_truth": ground_truth,
            "predicted": predicted,
            "category": category,
            "category_name": CATEGORY_NAMES.get(category, str(category)),
            "f1": f1,
            "n_sessions": n_sessions,
            "n_turns": n_turns,
            "n_memories": n_memories,
            "question_id": question_id,
        })

    try:
        cm.close()
    except Exception:
        pass
    try:
        os.remove(db_path)
    except OSError:
        pass

    return results


def main():
    parser = argparse.ArgumentParser(description="LongMemEval Multi-Session benchmark for CarryMem")
    parser.add_argument("--split", type=str, default="s", choices=["oracle", "s", "m"])
    parser.add_argument("--num-samples", type=int, default=10)
    parser.add_argument("--llm-model", type=str, default=None)
    args = parser.parse_args()

    load_dotenv(BENCHMARKS_DIR / "MemEval" / ".env")

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return

    llm_model = args.llm_model or os.environ.get("LLM_MODEL", LLM_MODEL)
    conversations = load_multisession_questions(args.split, args.num_samples)

    print("=" * 70)
    print("LongMemEval Multi-Session Benchmark for CarryMem")
    print("=" * 70)
    print(f"  Split: {args.split}")
    print(f"  Questions: {len(conversations)}")
    print(f"  LLM: {llm_model}")
    print("=" * 70)

    all_results = []
    for conv in tqdm(conversations, desc="multi-session"):
        sample_id = conv.get("sample_id", "unknown")
        try:
            results = run_carrymem(conv, llm_model)
            all_results.extend(results)
        except Exception as err:
            print(f"  ERROR on {sample_id}: {err}")
            import traceback
            traceback.print_exc()
            continue

        if all_results:
            running_f1 = np.mean([r["f1"] for r in all_results])
            print(f"  Running F1: {running_f1:.4f} ({len(all_results)} questions)")

    if not all_results:
        print("No results!")
        return

    f1s = [r["f1"] for r in all_results]
    print(f"\n{'='*70}")
    print("RESULTS — LongMemEval Multi-Session")
    print(f"{'='*70}")
    print(f"  Overall F1: {np.mean(f1s):.4f} +/- {np.std(f1s):.4f}")
    print(f"  Median F1:  {np.median(f1s):.4f}")
    print(f"  Questions:  {len(all_results)}")

    f1_dist = Counter()
    for f in f1s:
        if f == 0:
            f1_dist["0.00"] += 1
        elif f < 0.3:
            f1_dist["0.01-0.29"] += 1
        elif f < 0.6:
            f1_dist["0.30-0.59"] += 1
        elif f < 0.9:
            f1_dist["0.60-0.89"] += 1
        else:
            f1_dist["0.90-1.00"] += 1
    print(f"  F1 Distribution:")
    for bucket in ["0.00", "0.01-0.29", "0.30-0.59", "0.60-0.89", "0.90-1.00"]:
        count = f1_dist.get(bucket, 0)
        pct = count / len(f1s) * 100
        print(f"    {bucket}: {count} ({pct:.0f}%)")

    avg_sessions = np.mean([r["n_sessions"] for r in all_results])
    avg_memories = np.mean([r["n_memories"] for r in all_results])
    print(f"  Avg sessions per question: {avg_sessions:.1f}")
    print(f"  Avg memories stored: {avg_memories:.1f}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = DATA_DIR / f"multisession_{args.split}_{ts}_results.json"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "split": args.split,
        "llm_model": llm_model,
        "n_questions": len(all_results),
        "overall_f1_mean": float(np.mean(f1s)),
        "overall_f1_std": float(np.std(f1s)),
        "overall_f1_median": float(np.median(f1s)),
        "avg_sessions": float(avg_sessions),
        "avg_memories": float(avg_memories),
        "results": all_results,
    }

    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
