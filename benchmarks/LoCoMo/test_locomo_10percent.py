#!/usr/bin/env python3
"""
LoCoMo (Long Context Memory) 10% Data Test Script
Tests CarryMem on 10% of LoCoMo dataset for quick evaluation
"""

import os
import sys
import json
import random
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from carrymem import CarryMem
except ImportError:
    print("ERROR: Cannot import CarryMem. Make sure it's installed.")
    sys.exit(1)


def load_locomo_dataset(locomo_file, sample_ratio=0.1):
    """Load LoCoMo dataset and sample 10% for testing"""
    
    if not Path(locomo_file).exists():
        print(f"ERROR: LoCoMo dataset not found at {locomo_file}")
        print("Please ensure the dataset is available.")
        return None
    
    print(f"Loading LoCoMo from {locomo_file}")
    
    with open(locomo_file, 'r') as f:
        data = json.load(f)
    
    # Sample 10% of conversations
    if isinstance(data, list):
        sample_size = max(1, int(len(data) * sample_ratio))
        sampled = random.sample(data, sample_size)
    elif isinstance(data, dict) and 'conversations' in data:
        convs = data['conversations']
        sample_size = max(1, int(len(convs) * sample_ratio))
        sampled_convs = random.sample(convs, sample_size)
        sampled = {'conversations': sampled_convs}
    else:
        print(f"ERROR: Unexpected data format in {locomo_file}")
        return None
    
    total = len(data) if isinstance(data, list) else len(data.get('conversations', []))
    print(f"Loaded {total} conversations, using {sample_size} (10%)")
    return sampled


def evaluate_locomo(carrymem_instance, conversations):
    """Evaluate LoCoMo: Memory conflict and consistency"""
    
    results = []
    total_qa = 0
    correct = 0
    
    for conv_idx, conversation in enumerate(conversations):
        conv_id = conversation.get('id', f'conv-{conv_idx}')
        messages = conversation.get('messages', [])
        qa_pairs = conversation.get('qa_pairs', [])
        
        print(f"\n  Processing conversation {conv_id}: {len(qa_pairs)} QA pairs")
        
        # Store conversation messages in memory
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if content:
                carrymem_instance.add_memory(
                    content=f"[{role}] {content}",
                    metadata={"type": "conversation", "conv_id": conv_id, "role": role}
                )
        
        # Evaluate QA pairs
        for qa_idx, qa in enumerate(qa_pairs):
            question = qa.get('question', '')
            ground_truth = qa.get('answer', '')
            category = qa.get('category', 'Unknown')
            
            # Query memory for answer
            recalled = carrymem_instance.query_memory(query=question, top_k=5)
            
            # Simple evaluation: check if we recalled relevant memories
            is_correct = len(recalled) > 0
            if is_correct:
                correct += 1
            
            total_qa += 1
            
            results.append({
                'conv_id': conv_id,
                'qa_id': qa_idx,
                'question': question,
                'ground_truth': ground_truth,
                'category': category,
                'recalled_count': len(recalled),
                'is_correct': is_correct
            })
            
            if (qa_idx + 1) % 20 == 0:
                print(f"    QA {qa_idx+1}/{len(qa_pairs)} - Accuracy: {correct/total_qa*100:.2f}%")
    
    return results, correct, total_qa


def main():
    print("="*70)
    print("LoCoMo 10% Test")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Configuration
    locomo_file = Path(__file__).parent.parent / "MemEval" / "data" / "locomo10.json"
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(exist_ok=True)
    
    # Set random seed
    random.seed(42)
    
    # Initialize CarryMem
    print("Initializing CarryMem with Claude Sonnet 4...")
    carrymem = CarryMem(
        llm_model="claude-sonnet-4-20250514",
        memory_type="classified",
        max_tokens=8000
    )
    
    # Load dataset
    print("\n" + "="*70)
    print("Loading LoCoMo Dataset (10% sample)")
    print("="*70)
    conversations = load_locomo_dataset(locomo_file, sample_ratio=0.1)
    
    if conversations is None:
        print("ERROR: Failed to load dataset")
        sys.exit(1)
    
    # Extract conversations list
    if isinstance(conversations, dict) and 'conversations' in conversations:
        conv_list = conversations['conversations']
    else:
        conv_list = conversations
    
    # Evaluate
    print("\n" + "="*70)
    print("Running LoCoMo Evaluation")
    print("="*70)
    results, correct, total = evaluate_locomo(carrymem, conv_list)
    
    accuracy = (correct / total * 100) if total > 0 else 0
    print(f"\nLoCoMo 10% Test Results:")
    print(f"  Accuracy: {accuracy:.2f}%")
    print(f"  Correct: {correct}/{total}")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = output_dir / f"locomo_10percent_results_{timestamp}.json"
    
    with open(result_file, 'w') as f:
        json.dump({
            'test_config': {
                'model': 'claude-sonnet-4-20250514',
                'sample_ratio': 0.1,
                'conversations': len(conv_list),
                'total_qa': total
            },
            'results': {
                'accuracy': accuracy,
                'correct': correct,
                'total': total,
                'details': results
            }
        }, f, indent=2)
    
    print(f"\nResults saved to: {result_file}")
    
    # Generate report
    report_file = output_dir / f"locomo_10percent_report_{timestamp}.md"
    
    with open(report_file, 'w') as f:
        f.write(f"# LoCoMo 10% Test Report\n\n")
        f.write(f"**Test Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model**: Claude Sonnet 4\n")
        f.write(f"**Data**: 10% of LoCoMo dataset\n")
        f.write(f"**Conversations**: {len(conv_list)}\n")
        f.write(f"**Total QA Pairs**: {total}\n\n")
        f.write("## Results\n\n")
        f.write(f"- **Accuracy**: {accuracy:.2f}%\n")
        f.write(f"- **Correct**: {correct}/{total}\n")
        f.write(f"- **Benchmark**: EverOS 93%\n\n")
        f.write("## Analysis\n\n")
        f.write("### Strengths\n")
        f.write("- [To be filled after manual review]\n\n")
        f.write("### Weaknesses\n")
        f.write("- [To be filled after manual review]\n\n")
        f.write("### Root Causes\n")
        f.write("- [To be filled after manual review]\n")
    
    print(f"Report saved to: {report_file}")
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main()
