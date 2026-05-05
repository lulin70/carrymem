#!/usr/bin/env python3
"""
CarryMem Official LongMemEval Evaluation

Uses the official LongMemEval dataset and evaluation methodology:
1. Feed official chat history sessions to CarryMem for memorization
2. Answer questions using CarryMem's recall + LLM generation
3. Evaluate with LLM-as-judge using official prompt templates

Official method: https://github.com/xiaowu0162/LongMemEval

Deviations from official:
- Judge LLM: Claude Sonnet 4 (via Moka AI API) instead of GPT-4o
  Reason: GPT-4o API key not available; Claude Sonnet 4 is a comparable model
- Answer generation LLM: Claude Sonnet 4 instead of GPT-4o
  Reason: Same as above
- Evaluation script: Adapted from official evaluate_qa.py to support Moka AI API

Compliant aspects:
- Dataset: Official LongMemEval dataset (longmemeval_oracle / longmemeval_s_cleaned)
- Evaluation prompts: Official prompt templates from evaluate_qa.py
- Output format: Official jsonl format with question_id and hypothesis
- Scoring method: LLM-as-judge (official method)
"""

import json
import os
import sys
import time
import tempfile
import argparse
from datetime import datetime, timezone
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from memory_classification_engine import CarryMem
from openai import OpenAI
import backoff

JUDGE_API_KEY = os.environ.get(
    "MOKA_API_KEY",
    "sk-GWSmGaP4XYK3YDWi80gGZTtae8eb7id1mgCAYDdvDgoFpUzX",
)
JUDGE_BASE_URL = "https://api.moka-ai.com/v1"
JUDGE_MODEL = "code/claude-sonnet-4-6"


def get_anscheck_prompt(task, question, answer, response, abstention=False):
    if not abstention:
        if task in [
            "single-session-user",
            "single-session-assistant",
            "multi-session",
        ]:
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            return template.format(question, answer, response)
        elif task == "temporal-reasoning":
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response is equivalent to the correct answer or contains all the intermediate steps to get the correct answer, you should also answer yes. If the response only contains a subset of the information required by the answer, answer no. In addition, do not penalize off-by-one errors for the number of days. If the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., predicting 19 days when the answer is 18), the model's response is still correct. \n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            return template.format(question, answer, response)
        elif task == "knowledge-update":
            template = "I will give you a question, a correct answer, and a response from a model. Please answer yes if the response contains the correct answer. Otherwise, answer no. If the response contains some previous information along with an updated answer, the response should be considered as correct as long as the updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            return template.format(question, answer, response)
        elif task == "single-session-preference":
            template = "I will give you a question, a rubric for desired personalized response, and a response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer no. The model does not need to reflect all the points in the rubric. The response is correct as long as it recalls and utilizes the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only."
            return template.format(question, answer, response)
        else:
            raise NotImplementedError(f"Task type {task} not supported")
    else:
        template = "I will give you an unanswerable question, an explanation, and a response from a model. Please answer yes if the model correctly identifies the question as unanswerable. The model could say that the information is incomplete, or some other information is given but the asked information is not.\n\nQuestion: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the question as unanswerable? Answer yes or no only."
        return template.format(question, answer, response)


@backoff.on_exception(backoff.expo, Exception, max_tries=5)
def call_llm(client, model, messages, temperature=0, max_tokens=200):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def memorize_sessions(cm, entry, include_assistant=True):
    session_count = 0
    turn_count = 0
    for session in entry["haystack_sessions"]:
        for turn in session:
            role = turn["role"]
            if role == "user" or (include_assistant and role == "assistant"):
                try:
                    prefix = "" if role == "user" else "[Assistant said] "
                    cm.classify_and_remember(prefix + turn["content"])
                    turn_count += 1
                except Exception:
                    pass
        session_count += 1
    return session_count, turn_count


def generate_answer(client, model, question, memories):
    memory_content = "\n".join(
        [
            f"- {m.get('content', '')} (type: {m.get('type', 'unknown')})"
            for m in memories
        ]
    )

    if memory_content:
        answer_prompt = f"""Based on the following memories about the user, answer the question. Use only information from the memories. If the memories don't contain the answer, say so.

Memories:
{memory_content}

Question: {question}

Answer:"""
    else:
        answer_prompt = f"""Answer the following question. If you don't have enough information, say so.

Question: {question}

Answer:"""

    try:
        resp = call_llm(
            client, model, [{"role": "user", "content": answer_prompt}],
            temperature=0, max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"


def run_official_evaluation(
    data_file, max_questions=None, output_dir=None, stratified=None
):
    print("=" * 70)
    print("CarryMem Official LongMemEval Evaluation")
    print("=" * 70)
    print(f"\nDataset: {os.path.basename(data_file)}")
    print(f"Judge LLM: {JUDGE_MODEL} (Official: GPT-4o)")
    print(f"Answer LLM: {JUDGE_MODEL} (Official: GPT-4o)")
    print(f"Deviation: Judge model differs from official GPT-4o")
    if max_questions:
        print(f"Max questions: {max_questions}")

    with open(data_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print(f"Total questions in dataset: {len(dataset)}")

    if stratified:
        from collections import defaultdict
        by_type = defaultdict(list)
        for entry in dataset:
            by_type[entry["question_type"]].append(entry)
        sampled = []
        for qtype, entries in sorted(by_type.items()):
            n = min(stratified, len(entries))
            sampled.extend(entries[:n])
            print(f"  {qtype}: {n}/{len(entries)} sampled")
        dataset = sampled
        print(f"Stratified sample: {len(dataset)} questions ({stratified} per type)")
    elif max_questions:
        dataset = dataset[:max_questions]
        print(f"Using first {max_questions} questions")

    client = OpenAI(api_key=JUDGE_API_KEY, base_url=JUDGE_BASE_URL)

    results_dir = output_dir or os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    hyp_file = os.path.join(results_dir, f"longmemeval_hyp_{timestamp}.jsonl")
    eval_file = os.path.join(results_dir, f"longmemeval_eval_{timestamp}.json")
    report_file = os.path.join(results_dir, f"longmemeval_report_{timestamp}.json")

    print("\n[Step 1] Memorizing chat history sessions with CarryMem...")
    print("[Step 2] Generating answers with CarryMem recall + LLM...")
    print("[Step 3] Evaluating with LLM-as-judge (official method)...")

    hypotheses = []
    eval_results = []
    qtype2acc = {}
    total_sessions = 0
    total_turns = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0

    for i, entry in enumerate(dataset):
        qid = entry["question_id"]
        qtype = entry["question_type"]
        question = entry["question"]
        answer = entry["answer"]
        is_abstention = "_abs" in qid

        if qtype not in qtype2acc:
            qtype2acc[qtype] = []

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = tmp.name
        tmp.close()

        try:
            cm = CarryMem(storage="sqlite", db_path=db_path)

            s_count, t_count = memorize_sessions(cm, entry)
            total_sessions += s_count
            total_turns += t_count

            memories = cm.recall_memories(query=question, limit=20)

            hypothesis = generate_answer(client, JUDGE_MODEL, question, memories)

            cm.close()
        except Exception as e:
            hypothesis = f"Error: {e}"
            print(f"  ERROR processing {qid}: {e}")
        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

        hyp_entry = {"question_id": qid, "hypothesis": hypothesis}
        hypotheses.append(hyp_entry)

        prompt = get_anscheck_prompt(
            qtype, question, answer, hypothesis, abstention=is_abstention
        )

        try:
            eval_resp = call_llm(
                client, JUDGE_MODEL,
                [{"role": "user", "content": prompt}],
                temperature=0, max_tokens=10,
            )
            eval_response = eval_resp.choices[0].message.content.strip()
            label = "yes" in eval_response.lower()
            total_prompt_tokens += getattr(eval_resp.usage, "prompt_tokens", 0)
            total_completion_tokens += getattr(eval_resp.usage, "completion_tokens", 0)
        except Exception as e:
            print(f"  Judge error for {qid}: {e}")
            label = False

        qtype2acc[qtype].append(1 if label else 0)

        eval_entry = {
            "question_id": qid,
            "question_type": qtype,
            "question": question,
            "answer": answer,
            "hypothesis": hypothesis,
            "autoeval_label": label,
        }
        eval_results.append(eval_entry)

        status = "✅" if label else "❌"
        print(
            f"  [{i+1}/{len(dataset)}] {status} [{qtype}] {question[:60]}..."
        )

        time.sleep(0.3)

    with open(hyp_file, "w", encoding="utf-8") as f:
        for h in hypotheses:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")

    all_acc = [1 if r["autoeval_label"] else 0 for r in eval_results]
    overall = sum(all_acc) / len(all_acc) if all_acc else 0

    print("\n" + "=" * 70)
    print("Official LongMemEval Evaluation Results")
    print("=" * 70)
    print(f"\nDataset: {os.path.basename(data_file)}")
    print(f"Questions: {len(eval_results)}")
    print(f"Overall Accuracy: {overall:.1%} ({sum(all_acc)}/{len(all_acc)})")
    print(f"\nBy Question Type:")
    for qtype, accs in sorted(qtype2acc.items()):
        type_acc = sum(accs) / len(accs) if accs else 0
        print(f"  {qtype:30s}: {type_acc:.1%} ({sum(accs)}/{len(accs)})")

    print(f"\nToken Usage:")
    print(f"  Prompt tokens: {total_prompt_tokens}")
    print(f"  Completion tokens: {total_completion_tokens}")
    print(f"  Total sessions memorized: {total_sessions}")
    print(f"  Total turns memorized: {total_turns}")

    report = {
        "benchmark": "LongMemEval-Official",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": os.path.basename(data_file),
        "methodology": {
            "memorization": "CarryMem classify_and_remember (online)",
            "recall": "CarryMem recall_memories (top-20)",
            "answer_generation": f"LLM ({JUDGE_MODEL}) based on recalled memories",
            "evaluation": "LLM-as-judge (official prompt templates from evaluate_qa.py)",
            "judge_model": JUDGE_MODEL,
            "official_judge_model": "GPT-4o",
            "deviation_note": (
                "Judge model differs from official (Claude Sonnet 4 via Moka AI "
                "vs GPT-4o). This may affect scoring as different LLMs may judge "
                "differently. All other aspects follow the official methodology: "
                "official dataset, official prompt templates, official output format."
            ),
        },
        "results": {
            "overall_accuracy": round(overall, 4),
            "total_questions": len(eval_results),
            "correct": sum(all_acc),
            "by_type": {
                qt: round(sum(a) / len(a), 4)
                for qt, a in qtype2acc.items()
                if a
            },
        },
        "token_usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
        },
        "scale": {
            "total_sessions": total_sessions,
            "total_turns": total_turns,
        },
        "details": eval_results,
    }

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nHypotheses saved to: {hyp_file}")
    print(f"Evaluation results saved to: {eval_file}")
    print(f"Full report saved to: {report_file}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CarryMem Official LongMemEval Evaluation"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default=os.path.join(
            os.path.dirname(__file__),
            "LongMemEval/data/longmemeval_oracle.json",
        ),
        help="Path to official LongMemEval dataset",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=None,
        help="Maximum number of questions to evaluate (for testing)",
    )
    parser.add_argument(
        "--stratified",
        type=int,
        default=None,
        help="Number of questions per type for stratified sampling",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for results",
    )
    args = parser.parse_args()

    run_official_evaluation(
        data_file=args.data_file,
        max_questions=args.max_questions,
        output_dir=args.output_dir,
        stratified=args.stratified,
    )
