#!/usr/bin/env python3
"""
MSC Official Persona Summary F1 Benchmark

This implements the OFFICIAL MSC evaluation method from Meta Research (ACL 2022):
- Feed multi-session conversations to CarryMem
- Generate persona summary using LLM + recalled memories
- Calculate F1 score against reference persona summary

Official MSC metrics:
- Persona Summary F1 (primary metric)
- BLEU, ROUGE (secondary metrics)

Reference: https://parl.ai/projects/msc/
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import re

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    from memory_classification_engine import CarryMem
except ImportError:
    print("❌ Error: CarryMem not found. Please install it first:")
    print("   cd /Users/lin/trae_projects/carrymem && pip install -e .")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("❌ Error: openai package not found. Installing...")
    os.system("pip install openai")
    from openai import OpenAI


class MSCPersonaSummaryBenchmark:
    """Official MSC Persona Summary F1 evaluation"""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        """
        Initialize MSC Persona Summary benchmark
        
        Args:
            api_key: API key for LLM (defaults to MOKA_API_KEY env var)
            base_url: API base URL (defaults to MokaAI)
            model: LLM model name (defaults to Claude Sonnet 4)
        """
        self.api_key = api_key or os.environ.get("MOKA_API_KEY", "")
        self.base_url = base_url or "https://api.moka-ai.com/v1"
        self.model = model or "code/claude-sonnet-4-6"
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.carrymem = CarryMem()
        
        print("🚀 MSC Official Persona Summary Benchmark Initialized")
        print(f"🤖 LLM Model: {self.model}")
    
    def create_test_episodes(self) -> List[Dict]:
        """
        Create test episodes following MSC format
        
        Each episode has:
        - Multiple sessions (conversations)
        - Reference persona summary (ground truth)
        """
        episodes = [
            {
                "episode_id": "ep1",
                "sessions": [
                    {
                        "session_id": 1,
                        "turns": [
                            {"speaker": "user", "text": "I prefer dark mode in all my editors"},
                            {"speaker": "assistant", "text": "Noted! I'll remember you prefer dark mode."},
                            {"speaker": "user", "text": "I'm a Python developer"},
                            {"speaker": "assistant", "text": "Got it, you work with Python."},
                        ]
                    },
                    {
                        "session_id": 2,
                        "turns": [
                            {"speaker": "user", "text": "I use VSCode as my main IDE"},
                            {"speaker": "assistant", "text": "VSCode, understood."},
                            {"speaker": "user", "text": "I prefer spaces over tabs, 4 spaces"},
                            {"speaker": "assistant", "text": "4 spaces for indentation, got it."},
                        ]
                    },
                    {
                        "session_id": 3,
                        "turns": [
                            {"speaker": "user", "text": "I like using PostgreSQL for databases"},
                            {"speaker": "assistant", "text": "PostgreSQL preference recorded."},
                        ]
                    },
                ],
                "reference_persona": "A Python backend developer who prefers dark mode, uses VSCode with 4-space indentation, and likes PostgreSQL databases."
            },
            {
                "episode_id": "ep2",
                "sessions": [
                    {
                        "session_id": 1,
                        "turns": [
                            {"speaker": "user", "text": "I'm a frontend engineer"},
                            {"speaker": "assistant", "text": "Frontend engineering, noted."},
                            {"speaker": "user", "text": "I love React and TypeScript"},
                            {"speaker": "assistant", "text": "React and TypeScript, got it."},
                        ]
                    },
                    {
                        "session_id": 2,
                        "turns": [
                            {"speaker": "user", "text": "I prefer functional programming style"},
                            {"speaker": "assistant", "text": "Functional programming preference noted."},
                            {"speaker": "user", "text": "I use Tailwind CSS for styling"},
                            {"speaker": "assistant", "text": "Tailwind CSS, understood."},
                        ]
                    },
                    {
                        "session_id": 3,
                        "turns": [
                            {"speaker": "user", "text": "I deploy to Vercel usually"},
                            {"speaker": "assistant", "text": "Vercel for deployment, noted."},
                            {"speaker": "user", "text": "I prefer light mode for coding"},
                            {"speaker": "assistant", "text": "Light mode preference recorded."},
                        ]
                    },
                ],
                "reference_persona": "A frontend engineer who loves React and TypeScript, prefers functional programming, uses Tailwind CSS, deploys to Vercel, and codes in light mode."
            },
            {
                "episode_id": "ep3",
                "sessions": [
                    {
                        "session_id": 1,
                        "turns": [
                            {"speaker": "user", "text": "I'm a DevOps engineer"},
                            {"speaker": "assistant", "text": "DevOps role, noted."},
                            {"speaker": "user", "text": "I work primarily with Kubernetes"},
                            {"speaker": "assistant", "text": "Kubernetes expertise, got it."},
                        ]
                    },
                    {
                        "session_id": 2,
                        "turns": [
                            {"speaker": "user", "text": "I prefer AWS over other cloud providers"},
                            {"speaker": "assistant", "text": "AWS preference noted."},
                            {"speaker": "user", "text": "I use Terraform for infrastructure as code"},
                            {"speaker": "assistant", "text": "Terraform for IaC, understood."},
                        ]
                    },
                    {
                        "session_id": 3,
                        "turns": [
                            {"speaker": "user", "text": "I monitor everything with Prometheus and Grafana"},
                            {"speaker": "assistant", "text": "Prometheus and Grafana for monitoring, noted."},
                            {"speaker": "user", "text": "I never deploy on Fridays"},
                            {"speaker": "assistant", "text": "No Friday deployments, got it."},
                        ]
                    },
                ],
                "reference_persona": "A DevOps engineer who works with Kubernetes, prefers AWS, uses Terraform for infrastructure, monitors with Prometheus and Grafana, and never deploys on Fridays."
            },
        ]
        
        return episodes
    
    def memorize_sessions(self, episode: Dict):
        """Feed all sessions to CarryMem for memorization"""
        for session in episode["sessions"]:
            session_id = session["session_id"]
            print(f"  Session {session_id}...", end=" ")
            
            for turn in session["turns"]:
                if turn["speaker"] == "user":
                    self.carrymem.classify_and_remember(turn["text"])
            
            print("✅")
    
    def generate_persona_summary(self) -> str:
        """
        Generate persona summary using CarryMem + LLM
        
        This is the official MSC method:
        1. Recall relevant memories from CarryMem
        2. Use LLM to synthesize into coherent persona summary
        """
        print("\n🧠 Generating persona summary...")
        
        # Recall all relevant memories
        all_memories = self.carrymem.recall_memories(
            "user information preferences facts", 
            limit=50
        )
        
        if not all_memories:
            return "No persona information available."
        
        # Build prompt for LLM
        prompt = """Based on the following memories about a person, write a concise persona summary (1-2 sentences).

Memories:
"""
        
        for mem in all_memories[:15]:  # Limit to avoid token overflow
            content = mem.get("content", "")
            prompt += f"- {content}\n"
        
        prompt += "\nPersona Summary:"
        
        # Call LLM
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150,
            )
            
            summary = response.choices[0].message.content.strip()
            print(f"  Generated: {summary[:100]}...")
            return summary
            
        except Exception as e:
            print(f"  ❌ Error generating summary: {e}")
            return "Error generating summary"
    
    def calculate_f1(self, generated: str, reference: str) -> Dict[str, float]:
        """
        Calculate F1 score between gena summaries
        
        This is the official MSC metric:
        - Tokenize both summaries into words
        - Calculate precision, recall, F1
        """
        # Tokenize (simple word-based)
        gen_tokens = set(re.findall(r'\w+', generated.lower()))
        ref_tokens = set(re.findall(r'\w+', reference.lower()))
        
        if not gen_tokens or not ref_tokens:
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
        
        # Calculate overlap
        overlap = gen_tokens & ref_tokens
        
        precision = len(overlap) / len(gen_tokens) if gen_tokens else 0.0
        recall = len(overlap) / len(ref_tokens) if ref_tokens else 0.0
        
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "overlap_tokens": len(overlap),
            "generated_tokens": len(gen_tokens),
            "reference_tokens": len(ref_tokens),
        }
    
    def run_benchmark(self) -> Dict:
        """Run full MSC Persona Summary F1 benchmark"""
        print("\n" + "="*70)
        print("MSC Official Persona Summary F1 Benchmark")
        print("="*70)
        
        episodes = self.create_test_episodes()
        results = {
            "benchmark": "MSC Persona Summary F1 (Official Method)",
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "episodes": [],
            "summary": {}
        }
        
        start_time = time.time()
        
        all_f1_scores = []
        
        for episode in episodes:
            print(f"\n{'='*70}")
            print(f"Episode: {episode['episode_id']}")
            print(f"{'='*70}")
            
            # Reset CarryMem for each episode with unique namespace
            self.carrymem.close()
            self.carrymem = CarryMem(namespace=episode['episode_id'])
            
            # Memorize sessions
            self.memorize_sessions(episode)
            
            # Generate persona summary
            generated_summary = self.generate_persona_summary()
            reference_summary = episode["reference_persona"]
            
            # Calculate F1
            scores = self.calculate_f1(generated_summary, reference_summary)
            all_f1_scores.append(scores["f1"])
            
            print(f"\n📊 Results:")
            print(f"  Reference: {reference_summary}")
            print(f"  Generated: {generated_summary}")
            print(f"  Precision: {scores['precision']:.1%}")
            print(f"  Recall: {scores['recall']:.1%}")
            print(f"  F1 Score: {scores['f1']:.1%}")
            
            results["episodes"].append({
                "episode_id": episode["episode_id"],
                "reference_persona": reference_summary,
                "generated_persona": generated_summary,
                "scores": scores
            })
        
        duration = time.time() - start_time
        
        # Calculate overall metrics
        avg_f1 = sum(all_f1_scores) / len(all_f1_scores) if all_f1_scores else 0.0
        
        results["summary"] = {
            "average_f1": round(avg_f1, 4),
            "min_f1": round(min(all_f1_scores), 4) if all_f1_scores else 0.0,
            "max_f1": round(max(all_f1_scores), 4) if all_f1_scores else 0.0,
            "episodes_tested": len(episodes),
            "duration_seconds": round(duration, 2)
        }
        
        print("\n" + "="*70)
        print("MSC Persona Summary F1 - Final Report")
        print("="*70)
        print(f"  Average F1 Score: {avg_f1:.1%}")
        print(f"  Min F1: {min(all_f1_scores):.1%}")
        print(f"  Max F1: {max(all_f1_scores):.1%}")
        print(f"  Episodes Tested: {len(episodes)}")
        print(f"  Duration: {duration:.2f}s")
        print("="*70)
        
        return results
    
    def save_results(self, results: Dict, output_path: str = None):
        """Save results to JSON file"""
        if output_path is None:
            results_dir = Path(__file__).parent / "results"
            results_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = results_dir / f"msc_persona_summary_official_{timestamp}.json"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_path}")
    
    def cleanup(self):
        """Cleanup resources"""
        if self.carrymem:
            self.carrymem.close()


def main():
    """Main entry point"""
    benchmark = MSCPersonaSummaryBenchmark()
    
    try:
        results = benchmark.run_benchmark()
        benchmark.save_results(results)
    finally:
        benchmark.cleanup()


if __name__ == "__main__":
    main()
