#!/usr/bin/env python3
"""
PrefEval Official Benchmark Adapter for CarryMem

Uses the official PrefEval evaluation methodology (ICLR 2025 Oral, Amazon Science):
- LLM-as-judge with 4 error types: acknowledge, violate, hallucinate, helpful
- Preference Following Accuracy = 1 - (inconsistent + hallucination_violation + unaware_violation + unhelpful) / total
- Supports both generation task and classification task
- Compares CarryMem (reminder) vs zero-shot baseline

Reference: https://github.com/amazon-science/PrefEval

Usage:
    # Quick test (10 samples, generation task)
    python benchmarks/prefeval_official.py --limit 10 --api-key YOUR_KEY --model gpt-4o

    # Full generation task with CarryMem vs zero-shot comparison
    python benchmarks/prefeval_official.py --limit 100 --api-key YOUR_KEY --model gpt-4o --compare

    # Classification task
    python benchmarks/prefeval_official.py --limit 50 --api-key YOUR_KEY --model gpt-4o --task classification

    # Store preferences only (no LLM evaluation)
    python benchmarks/prefeval_official.py --limit 50 --store-only
"""

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from carrymem import CarryMem

EVAL_PROMPT_ACKNOWLEDGE = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant acknowledges any user preference in answering the user's query.
Evaluate the response based on these stringent criteria:
1. Check if the response explicitly or implicitly mentions or references a user preference. 2. The content of the preference is irrelevant for this check; only its presence matters.
Answer "Yes" if:
1. The response explicitly mentions or refers to a user preference in answering the user's question. Examples include: "Based on your previous preference for xxxx"; "Based on your previous preference, I would suggest you xxxx"; "Since you mentioned you prefer/dislike xxxx"; "Since you are a xxxx"; "I will recommend the following given your preference for xxx", etc. You should extract the "xxxx" in your answer. If it only says "Based on our previous conversation, I recommend..." and does not explicitly mention any preference, you should answer 'No'.
2. The response assumes the user preference in answering the user's question implicitly. For example, when the user asks 'Can you recommend me cars to drive?', if the response is 'Based on your preference, I will recommend non-EV cars, ...', then this indicates the assistant assumes that the user's preference is a dislike of EV cars, and you should answer "Yes".
Answer "No" if the response does not mention or refer to any user preference explicitly or implicitly. If you cannot extract the sentence stating what the preference is, answer 'No'.
Here is the assistant's response:
The user's question is: {question}
Assistant response: {end_generation}
Examine the response meticulously and answer. Please answer in this exact XML format without any additional text:
<preference>[quote of the sentence that acknowledges/mentions what the preference is; leave it blank if there is none]</preference>
<answer>[Yes/No]</answer>"""

EVAL_PROMPT_VIOLATE = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's response violates the user's stated preference.
Evaluate the response based on these criteria:
Answer "Yes" if:
1. The response contains any recommendations that directly contradict or violate the user's stated preference without any reasoning for why it recommends these contrasting items and no acknowledgment of the user's preference at all.
Answer "No" if:
1. The response respects the user's stated preference.
2. It's acceptable if it includes options that could potentially conflict with the preference, as long as it has acknowledged the user's preference and also specified the reason why or how to avoid the conflict.
3. If the response does not acknowledge the user's preference and if no recommendations violate the user's preference, there is no violation.
Here is the conversation:
User's preference: {preference}
User query: {question}
Assistant response: {end_generation}
Examine the response meticulously and answer. Answer in this exact XML format:
<explanation>[1 very short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

EVAL_PROMPT_HALLUCINATE = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's restatement of the user's stated preference is the same preference. Evaluate the response based on these stringent criteria to answer if the assistant has hallucinated the preference or not:
Answer "Yes" if:
1. The assistant's restatement differs from the original preference in meaning or intent.
2. The assistant's restatement contradicts the original preference.
3. The assistant's restatement is not related or irrelevant to the original preference.
Answer "No" if has not hallucinated:
1. The assistant's restatement matches the original preference.
2. The assistant's restatement is a minor paraphrase that fully preserves the meaning and intent of the original preference.
3. The restatement is just empty, no hallucination.
Here is the information:
Original user preference: "{preference}"
Assistant's restatement: "{assistant_restatement}"
Examine the original preference and the assistant's restatement meticulously and answer. Please answer in this exact XML format without any other additional text:
<explanation>[1 short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""

EVAL_PROMPT_HELPFUL = """You will analyze a conversation between a user and an assistant, focusing on whether the assistant's response is helpful in answering the user's question.
Evaluate the response based on these criteria:
Answer "Yes" if the response is helpful and provides a reasonable answer to the user's question.
Answer "No" if the response is completely unhelpful, irrelevant, or refuses to answer without justification.
Here is the conversation:
User's preference: {preference}
User query: {question}
Assistant response: {end_generation}
Examine the response meticulously and answer. Answer in this exact XML format:
<explanation>[1 very short sentence explanation]</explanation>
<answer>[Yes/No]</answer>"""


def parse_xml_response(text, tag):
    try:
        root = ET.fromstring(f"<root>{text}</root>")
        elem = root.find(tag)
        if elem is not None:
            return (elem.text or "").strip()
        return ""
    except ET.ParseError:
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""


def parse_answer(text):
    answer = parse_xml_response(text, "answer")
    return answer.lower().strip()


def parse_preference(text):
    return parse_xml_response(text, "preference")


def parse_explanation(text):
    return parse_xml_response(text, "explanation")


def load_prefeval_data(limit=None, hf_endpoint=None):
    from datasets import load_dataset
    if hf_endpoint:
        os.environ["HF_ENDPOINT"] = hf_endpoint
    ds = load_dataset("siyanzhao/prefeval_explicit", split="train")
    if limit:
        ds = ds.select(range(min(limit, len(ds))))
    return ds


def store_preferences(cm, samples):
    results = []
    for i, sample in enumerate(samples):
        preference = sample["preference"]
        question = sample["question"]
        topic = sample.get("topic", "unknown")

        result = cm.classify_and_remember(
            message=preference,
            session_id=f"prefeval_{topic}",
        )

        results.append({
            "index": i,
            "preference": preference,
            "question": question,
            "topic": topic,
            "stored": bool(result),
        })

    return results


def generate_llm_response(client, model, system_prompt, user_message, max_tokens=300, max_retries=3):
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=max_tokens,
                temperature=0.0,
                timeout=60.0,
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return f"ERROR: {e}"


def evaluate_single_response(judge_client, judge_model, preference, question, response):
    error_analysis = {}

    eval_system = "You are a helpful assistant in evaluating an AI assistant's response. You should be fair and strict and follow the user's instruction"

    ack_prompt = EVAL_PROMPT_ACKNOWLEDGE.format(question=question, end_generation=response)
    ack_resp = generate_llm_response(judge_client, judge_model, eval_system, ack_prompt, max_tokens=200)
    ack_answer = parse_answer(ack_resp)
    ack_pref = parse_preference(ack_resp)
    error_analysis["acknowledge"] = {
        "answer": ack_answer,
        "extracted_preference": ack_pref,
    }

    viol_prompt = EVAL_PROMPT_VIOLATE.format(
        preference=preference, question=question, end_generation=response,
    )
    viol_resp = generate_llm_response(judge_client, judge_model, eval_system, viol_prompt, max_tokens=200)
    viol_answer = parse_answer(viol_resp)
    viol_expl = parse_explanation(viol_resp)
    error_analysis["violate"] = {
        "answer": viol_answer,
        "explanation": viol_expl,
    }

    hallu_prompt = EVAL_PROMPT_HALLUCINATE.format(
        preference=preference, assistant_restatement=ack_pref,
    )
    hallu_resp = generate_llm_response(judge_client, judge_model, eval_system, hallu_prompt, max_tokens=200)
    hallu_answer = parse_answer(hallu_resp)
    hallu_expl = parse_explanation(hallu_resp)
    error_analysis["hallucinate"] = {
        "answer": hallu_answer,
        "explanation": hallu_expl,
    }

    help_prompt = EVAL_PROMPT_HELPFUL.format(
        preference=preference, question=question, end_generation=response,
    )
    help_resp = generate_llm_response(judge_client, judge_model, eval_system, help_prompt, max_tokens=200)
    help_answer = parse_answer(help_resp)
    help_expl = parse_explanation(help_resp)
    error_analysis["helpful"] = {
        "answer": help_answer,
        "explanation": help_expl,
    }

    return error_analysis


def compute_preference_following_accuracy(results):
    total = len(results)
    if total == 0:
        return 0.0, {}

    stats = {
        "acknowledgement": 0,
        "hallucination": 0,
        "violation": 0,
        "error_unhelpful": 0,
        "error_inconsistent": 0,
        "hallucination_of_preference_violation": 0,
        "preference_unaware_violation": 0,
        "preference_adherence_accuracy": 0,
    }

    for entry in results:
        if "error_analysis" not in entry:
            continue

        ea = entry["error_analysis"]
        is_acknowledgement = "yes" in ea.get("acknowledge", {}).get("answer", "").lower()
        is_hallucination = is_acknowledgement and "yes" in ea.get("hallucinate", {}).get("answer", "").lower()
        is_violation = "yes" in ea.get("violate", {}).get("answer", "").lower()
        is_unhelpful = "no" in ea.get("helpful", {}).get("answer", "").lower()

        is_inconsistent = is_acknowledgement and not is_hallucination and is_violation and not is_unhelpful
        is_hallu_violation = is_acknowledgement and is_hallucination and is_violation and not is_unhelpful
        is_unaware_violation = not is_acknowledgement and is_violation and not is_unhelpful

        preference_following = not any([
            is_inconsistent, is_hallu_violation, is_unaware_violation, is_unhelpful,
        ])

        stats["acknowledgement"] += is_acknowledgement
        stats["hallucination"] += is_hallucination
        stats["violation"] += is_violation
        stats["error_unhelpful"] += is_unhelpful
        stats["error_inconsistent"] += is_inconsistent
        stats["hallucination_of_preference_violation"] += is_hallu_violation
        stats["preference_unaware_violation"] += is_unaware_violation
        stats["preference_adherence_accuracy"] += preference_following

    accuracy = (stats["preference_adherence_accuracy"] / total) * 100
    return accuracy, stats


def run_generation_task(cm, samples, client, model, condition="carrymem", judge_client=None, judge_model=None):
    results = []
    for i, sample in enumerate(samples):
        preference = sample["preference"]
        question = sample["question"]
        topic = sample.get("topic", "unknown")

        if condition == "carrymem":
            from carrymem import MemoryEntry
            sample_ns = f"prefeval_sample_{i}"
            sample_cm = CarryMem(
                namespace=sample_ns,
                config={"enable_vector_search": True, "noise_filter_mode": "soft"},
            )
            entry = MemoryEntry(
                id="",
                type="user_preference",
                content=preference,
                confidence=1.0,
                tier=2,
                source_layer="declaration",
                reasoning="Explicit preference from PrefEval",
                suggested_action="store",
                metadata={"auto_rule": "prefer", "source": "prefeval"},
            )
            sample_cm._adapter.remember(entry)
            system_prompt = sample_cm.build_qa_prompt(
                question=question,
                max_tokens=4000,
                language="en",
                include_question=False,
            ).strip()
        elif condition == "carrymem-direct":
            system_prompt = f"You are a helpful assistant.\n\nIMPORTANT: Remember that the user has the following preference: {preference}"
        elif condition == "zero-shot":
            system_prompt = "You are a helpful assistant."
        elif condition == "reminder":
            system_prompt = f"You are a helpful assistant.\n\nIMPORTANT: Remember that the user has the following preference: {preference}"
        else:
            system_prompt = "You are a helpful assistant."

        response = generate_llm_response(client, model, system_prompt, question, max_tokens=300)

        entry = {
            "index": i,
            "topic": topic,
            "preference": preference[:100],
            "question": question[:100],
            "condition": condition,
            "system_prompt": system_prompt[:500],
            "response": response[:500] if response else None,
        }

        if response and not response.startswith("ERROR"):
            jc = judge_client or client
            jm = judge_model or model
            error_analysis = evaluate_single_response(jc, jm, preference, question, response)
            entry["error_analysis"] = error_analysis

        results.append(entry)

        if (i + 1) % 10 == 0:
            acc, _ = compute_preference_following_accuracy(results)
            print(f"  [{condition}] {i + 1}/{len(samples)} — Accuracy so far: {acc:.1f}%")

    return results


def run_classification_task(cm, samples, client, model, condition="carrymem"):
    results = []
    correct = 0
    total = 0

    for i, sample in enumerate(samples):
        preference = sample["preference"]
        question = sample["question"]
        topic = sample.get("topic", "unknown")

        options = sample.get("classification_task_options", None)
        if not options or len(options) < 2:
            continue

        option_text = "\n".join([f"{chr(65 + j)}. {opt}" for j, opt in enumerate(options)])

        if condition == "carrymem":
            sample_ns = f"prefeval_sample_{i}"
            sample_cm = CarryMem(
                namespace=sample_ns,
                config={"enable_vector_search": True, "noise_filter_mode": "soft"},
            )
            sample_cm.classify_and_remember(
                message=preference,
                session_id=f"prefeval_{topic}",
            )
            system_prompt = sample_cm.build_qa_prompt(
                question=question,
                max_tokens=4000,
                language="en",
            )
        elif condition == "zero-shot":
            system_prompt = "You are a helpful assistant."
        elif condition == "reminder":
            system_prompt = f"You are a helpful assistant.\n\nIMPORTANT: Remember that the user has the following preference: {preference}"
        else:
            system_prompt = "You are a helpful assistant."

        user_msg = f"{question}\n\nChoose the best option:\n{option_text}\n\nAnswer with just the letter (A, B, C, or D)."

        response = generate_llm_response(client, model, system_prompt, user_msg, max_tokens=10)

        choice = None
        for letter in ["A", "B", "C", "D"]:
            if letter in response.upper():
                choice = letter
                break

        correct_idx = sample.get("correct_idx", None)

        is_correct = choice == correct_idx if (choice and correct_idx) else False
        if is_correct:
            correct += 1
        total += 1

        results.append({
            "index": i,
            "topic": topic,
            "preference": preference[:80],
            "condition": condition,
            "choice": choice,
            "correct_idx": correct_idx,
            "is_correct": is_correct,
        })

        if total > 0 and total % 10 == 0:
            print(f"  [{condition}] {total} processed — Accuracy: {correct / total * 100:.1f}%")

    accuracy = (correct / total * 100) if total > 0 else 0
    return results, accuracy


def main():
    parser = argparse.ArgumentParser(description="PrefEval Official Benchmark for CarryMem")
    parser.add_argument("--limit", type=int, default=10, help="Number of samples")
    parser.add_argument("--store-only", action="store_true", help="Only store preferences")
    parser.add_argument("--model", type=str, default="gpt-4o", help="LLM model")
    parser.add_argument("--api-key", type=str, default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--api-base", type=str, default=os.environ.get("OPENAI_API_BASE"))
    parser.add_argument("--hf-endpoint", type=str, default=None, help="HuggingFace mirror")
    parser.add_argument("--namespace", type=str, default="prefeval", help="CarryMem namespace")
    parser.add_argument("--task", type=str, default="generation", choices=["generation", "classification"])
    parser.add_argument("--compare", action="store_true", help="Compare CarryMem vs zero-shot vs reminder")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path")
    parser.add_argument("--judge-api-key", type=str, default=os.environ.get("JUDGE_API_KEY"))
    parser.add_argument("--judge-api-base", type=str, default=os.environ.get("JUDGE_BASE_URL"))
    parser.add_argument("--judge-model", type=str, default=os.environ.get("JUDGE_MODEL", "gpt-4o"))
    args = parser.parse_args()

    print("=" * 70)
    print("PrefEval Official Benchmark for CarryMem")
    print("  Evaluation: LLM-as-judge (4 error types)")
    print("  Metric: Preference Following Accuracy (official formula)")
    print("=" * 70)

    print(f"\nLoading PrefEval data (limit={args.limit})...")
    samples = load_prefeval_data(limit=args.limit, hf_endpoint=args.hf_endpoint)
    print(f"  Loaded {len(samples)} samples")
    topics = sorted(set(s.get("topic", "unknown") for s in samples))
    print(f"  Topics: {topics}")

    print("\nInitializing CarryMem...")
    cm = CarryMem(
        namespace=args.namespace,
        config={"enable_vector_search": True, "noise_filter_mode": "soft"},
    )

    print("\nStoring preferences into CarryMem...")
    store_results = store_preferences(cm, samples)
    stored_count = sum(1 for r in store_results if r["stored"])
    print(f"  Stored {stored_count}/{len(samples)} preferences")

    if args.store_only:
        print("\n[Store-only mode] Done.")
        return

    if not args.api_key:
        print("\nERROR: --api-key or OPENAI_API_KEY env var required for LLM evaluation")
        return

    from openai import OpenAI
    client = OpenAI(api_key=args.api_key, base_url=args.api_base)
    print(f"\nLLM: {args.model}")

    judge_client = None
    judge_model = args.judge_model
    if args.judge_api_key:
        judge_client = OpenAI(api_key=args.judge_api_key, base_url=args.judge_api_base)
        print(f"Judge: {args.judge_model} (separate API)")
    else:
        judge_client = client
        judge_model = args.model
        print(f"Judge: {args.model} (same as LLM)")

    all_results = {}

    conditions = ["carrymem"]
    if args.compare:
        conditions = ["zero-shot", "carrymem", "carrymem-direct", "reminder"]

    if args.task == "generation":
        for condition in conditions:
            print(f"\n{'=' * 50}")
            print(f"Running generation task: {condition}")
            print(f"{'=' * 50}")

            results = run_generation_task(cm, samples, client, args.model, condition=condition, judge_client=judge_client, judge_model=judge_model)
            accuracy, stats = compute_preference_following_accuracy(results)

            all_results[condition] = {
                "accuracy": accuracy,
                "stats": stats,
                "total": len(results),
                "results": results,
            }

            print(f"\n--- {condition} Results ---")
            print(f"Preference Following Accuracy: {accuracy:.2f}%")
            print(f"  Acknowledgement: {stats['acknowledgement']}/{len(results)}")
            print(f"  Violation: {stats['violation']}/{len(results)}")
            print(f"  Hallucination: {stats['hallucination']}/{len(results)}")
            print(f"  Unhelpful: {stats['error_unhelpful']}/{len(results)}")
            print(f"  Inconsistent: {stats['error_inconsistent']}/{len(results)}")
            print(f"  Hallucination Violation: {stats['hallucination_of_preference_violation']}/{len(results)}")
            print(f"  Unaware Violation: {stats['preference_unaware_violation']}/{len(results)}")

    elif args.task == "classification":
        for condition in conditions:
            print(f"\n{'=' * 50}")
            print(f"Running classification task: {condition}")
            print(f"{'=' * 50}")

            results, accuracy = run_classification_task(cm, samples, client, args.model, condition=condition)

            all_results[condition] = {
                "accuracy": accuracy,
                "total": len(results),
                "correct": sum(1 for r in results if r.get("is_correct")),
                "results": results,
            }

            print(f"\n--- {condition} Results ---")
            print(f"Classification Accuracy: {accuracy:.2f}%")

    print("\n" + "=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)
    print(f"{'Condition':<20} {'Accuracy':>10}")
    print("-" * 30)
    for condition, data in all_results.items():
        print(f"{condition:<20} {data['accuracy']:>9.2f}%")

    print("\n--- PrefEval Paper Baselines (10 turns, explicit, generation) ---")
    print(f"{'Model':<25} {'Zero-shot':>12} {'Reminder':>12}")
    print("-" * 50)
    print(f"{'GPT-4o':<25} {'7%':>12} {'98%':>12}")
    print(f"{'Claude-3-Sonnet':<25} {'5%':>12} {'96%':>12}")
    print(f"{'o1-preview':<25} {'50%':>12} {'98%':>12}")
    print(f"{'CarryMem+GPT-4o':<25} {'—':>12} {all_results.get('carrymem', {}).get('accuracy', '—'):>11}%")

    if args.output:
        output_data = {}
        for condition, data in all_results.items():
            output_data[condition] = {
                "accuracy": data["accuracy"],
                "stats": data.get("stats", {}),
                "total": data["total"],
                "results": data.get("results", []),
            }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to {args.output}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
