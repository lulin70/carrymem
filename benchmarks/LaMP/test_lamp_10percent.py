#!/usr/bin/env python3
"""
LaMP (Language Model Personalization) 10% Data Test Script
Tests CarryMem on 10% of LaMP-2, LaMP-3, LaMP-4 datasets for quick evaluation
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


def load_lamp_dataset(lamp_dir, task_id, sample_ratio=0.1):
    """Load LaMP dataset and sample 10% for testing"""
    task_dir = Path(lamp_dir) / f"LaMP-{task_id}"
    
    if not task_dir.exists():
        print(f"ERROR: LaMP-{task_id} dataset not found at {task_dir}")
        print("Please download the dataset first.")
        return None
    
    # Load test set
    test_file = task_dir / "test.json"
    if not test_file.exists():
        test_file = task_dir / "dev.json"  # Try dev set
    
    if not test_file.exists():
        print(f"ERROR: Cannot find test/dev file in {task_dir}")
        return None
    
    print(f"Loading LaMP-{task_id} from {test_file}")
    
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    # Sample 10%
    if isinstance(data, list):
        sample_size = max(1, int(len(data) * sample_ratio))
        sampled = random.sample(data, sample_size)
    elif isinstance(data, dict) and 'data' in data:
        sample_size = max(1, int(len(data['data']) * sample_ratio))
        sampled = random.sample(data['data'], sample_size)
    else:
        print(f"ERROR: Unexpected data format in {test_file}")
        return None 
    print(f"Loaded {len(data) if isinstance(data, list) else len(data['data'])} samples, using {len(sampled)} (10%)")
    return sampled


def evaluate_lamp2(carrymem_instance, samples):
    """Evaluate LaMP-2: Movie Tagging"""
    correct = 0
    total = len(samples)
    
    results = []
    
    for idx, sample in enumerate(samples):
        # Extract user profile and query
        profile = sample.get('profile', [])
        query = sample.get('input', '')
        expected_tags = sample.get('output', [])
        
        # Store profile in memory
        for item in profile:
            carrymem_instance.add_memory(
                content=f"User watched: {item.get('text', '')}",
                metadata={"type": "movie_history", "sample_id": idx}
            )
        
        # Query for relevant memories
        recalled = carrymem_instance.query_memory(query=query, top_k=5)
        
        # Simple evaluation: check if we can recall relevant history
        is_correct = len(recalled) > 0
        if is_correct:
            correct += 1
        
        results.append({
            'sample_id': idx,
            'query': query,
            'expected_tags': expected_tags,
            'recalled_count': len(recalled),
            'is_correct': is_correct
        })
        
        if (idx + 1) % 10 == 0:
            print(f"  Progress: {idx+1}/{total}, Accuracy: {correct/(idx+1)*100:.2f}%")
    
    return results, correct, total


def evaluate_lamp3(carrymem_instance, samples):
    """Evaluate LaMP-3: Personalized Product Rating"""
    correct = 0
    total = len(samples)
    
    results = []
    
    for idx, sample in enumerate(samples):
        profile = sample.get('profile', [])
        query = sample.get('input', '')
        expected_rating = sample.get('output', '')
        
        # Store profile
        for item in profile:
            carrymem_instance.add_memory(
                content=f"User rated: {item.get('text', '')} - Rating: {item.get('rating', 'N/A')}",
                metadata={"type": "rating_history", "sample_id": idx}
            )
        
        # Query
        recalled = carrymem_instance.query_memory(query=query, top_k=5)
        
        is_correct = len(recalled) > 0
        if is_correct:
            correct += 1
        
        results.append({
            'sample_id': idx,
            'query': query,
            'expected_rating': expected_rating,
            'recalled_count': len(recalled),
            'is_correct': is_correct
        })
        
        if (idx + 1) % 10 == 0:
            print(f"  Progress: {idx+1}/{total}, Accuracy: {correct/(idx+1)*100:.2f}%")
    
    return results, correct, total


def evaluate_lamp4(carrymem_instance, samples):
    """Evaluate LaMP-4: Personalized News Headline Generation"""
    correct = 0
    total = len(samples)
    
    results = []
    
    for idx, sample in enumerate(samples):
        profile = sample.get('profile', [])
        query = sample.get('input', '')
        expected_headline = sample.get('output', '')
        
        # Store profile
        for item in profile:
            carrymem_instance.add_memory(
                content=f"User read: {item.get('text', '')}",
                metadata={"type": "reading_history", "sample_id": idx}
            )
        
        # Query
        recalled = carrymem_instance.query_memory(query=query, top_k=5)
        
        is_correct = len(recalled) > 0
        if is_correct:
            correct += 1
        
        results.append({
            'sample_id': idx,
            'query': query,
            'expected_headline': expected_headline,
            'recalled_count': len(recalled),
            'is_correct': is_correct
        })
        
        if (idx + 1) % 10 == 0:
            print(f"  Progress: {idx+1}/{total}, Accuracy: {correct/(idx+1)*100:.2f}%")
    
    return results, correct, total


def main():
    print("="*70)
    print("LaMP (Language Model Personalization) 10% Test")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Configuration
    lamp_dir = Path(__file__).parent / "LaMP-official" / "data"
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
    
    all_results = {}
    
    # Test LaMP-2
    print("\n" + "="*70)
    print("Testing LaMP-2: Movie Tagging")
    print("="*70)
    samples_2 = load_lamp_dataset(lamp_dir, 2, sample_ratio=0.1)
    if samples_2:
        results_2, correct_2, total_2 = evaluate_lamp2(carrymem, samples_2)
        accuracy_2 = (correct_2 / total_2 * 100) if total_2 > 0 else 0
        print(f"LaMP-2 Accuracy: {accuracy_2:.2f}%")
        all_results['lamp2'] = {
            'accuracy': accuracy_2,
            'correct': correct_2,
            'total': total_2,
            'details': results_2
        }
    
    # Test LaMP-3
    print("\n" + "="*70)
    print("Testing LaMP-3: Personalized Product Rating")
    print("="*70)
    samples_3 = load_lamp_dataset(lamp_dir, 3, sample_ratio=0.1)
    if samples_3:
        results_3, correct_3, total_3 = evaluate_lamp3(carrymem, samples_3)
        accuracy_3 = (correct_3 / total_3 * 100) if total_3 > 0 else 0
        print(f"LaMP-3 Accuracy: {accuracy_3:.2f}%")
        all_results['lamp3'] = {
            'accuracy': accuracy_3,
            'correct': correct_3,
            'total': total_3,
            'details': results_3
        }
    
    # Test LaMP-4
    print("\n" + "="*70)
    print("Testing LaMP-4: Personalized News Headline Generation")
    print("="*70)
    samples_4 = load_lamp_dataset(lamp_dir, 4, sample_ratio=0.1)
    if samples_4:
        results_4, correct_4, total_4 = evaluate_lamp4(carrymem, samples_4)
        accuracy_4 = (correct_4 / total_4 * 100) if total_4 > 0 else 0
        print(f"LaMP-4 Accuracy: {accuracy_4:.2f}%")
        all_results['lamp4'] = {
            'accuracy': accuracy_4,
            'correct': correct_4,
            'total': total_4,
            'details': results_4
        }
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = output_dir / f"lamp_10percent_results_{timestamp}.json"
    
    with open(result_file, 'w') as f:
        json.dump({
            'test_config': {
                'model': 'claude-sonnet-4-20250514',
                'sample_ratio': 0.1,
                'tasks': ['lamp2', 'lamp3', 'lamp4']
            },
            'results': all_results
        }, f, indent=2)
    
    print(f"\nResults saved to: {result_file}")
    
    # Generate report
    report_file = output_dir / f"lamp_10percent_report_{timestamp}.md"
    
    with open(report_file, 'w') as f:
        f.write(f"# LaMP 10% Test Report\n\n")
        f.write(f"**Test Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model**: Claude Sonnet 4\n")
        f.write(f"**Data**: 10% of LaMP-2, LaMP-3, LaMP-4\n\n")
        f.write("## Results\n\n")
        
        for task, data in all_results.items():
            f.write(f"### {task.upper()}\n")
            f.write(f"- Accuracy: {data['accuracy']:.2f}%\n")
            f.write(f"- Correct: {data['correct']}/{data['total']}\n\n")
        
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
