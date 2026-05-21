#!/usr/bin/env python3
"""
CarryMem Official Full-Scale Benchmark Suite
使用官方框架和数据运行完整的benchmark测试
确保结果真实可信，符合学术标准
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
import time


def setup_environment():
    """Setup API keys and paths"""
    # API配置 - keys must be set via environment variables
    if not os.environ.get("OPENAI_API_KEY"):
        raise EnvironmentError("OPENAI_API_KEY environment variable is required")
    if not os.environ.get("OPENAI_API_BASE"):
        os.environ["OPENAI_API_BASE"] = "https://api.moka-ai.com/v1"
    if not os.environ.get("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = "https://api.moka-ai.com/v1"
    
    # 路径配置
    benchmark_dir = Path(__file__).parent
    memeval_dir = benchmark_dir / "MemEval"
    
    # 添加到Python路径
    sys.path.insert(0, str(memeval_dir))
    sys.path.insert(0, str(benchmark_dir.parent / "src"))
    
    return benchmark_dir, memeval_dir


def run_longmemeval_memeval(memeval_dir, results_dir):
    """
    LongMemEval - 使用官方MemEval框架
    Framework: MemEval Official
    LLM: Claude Sonnet 4
    Data: Full dataset (longmemeval_oracle.json)
    """
    print("\n" + "=" * 80)
    print("1. LongMemEval - FULL SCALE (Official MemEval Framework)")
    print("=" * 80)
    print("Framework: MemEval Official")
    print("LLM: Claude Sonnet 4")
    print("Data: Full longmemeval_oracle.json dataset")
    print("=" * 80)
    
    try:
        start_time = time.time()
        
        # 使用MemEval官方脚本
        cmd = [
            "python3",
            str(memeval_dir / "scripts" / "run_full_benchmark.py"),
            "--benchmark", "longmemeval",
            "--systems", "carrymem",
            "--llm-model", "claude-sonnet-4-20250514",
            "--skip-judge",
            "--output-dir", str(results_dir / "longmemeval_full")
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(memeval_dir), capture_output=True, text=True)
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ LongMemEval completed ({elapsed/60:.1f} min)")
            print(result.stdout)
            return {
                "status": "success",
                "elapsed_minutes": elapsed/60,
                "framework": "MemEval Official",
                "model": "claude-sonnet-4-20250514"
            }
        else:
            print(f"❌ LongMemEval failed")
            print(result.stderr)
            return {
                "status": "failed",
                "error": result.stderr,
                "ela  import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


def run_locomo_memeval(memeval_dir, results_dir):
    """
    LoCoMo - 使用官方MemEval框架
    Framework: MemEval Official
    LLM: GPT-4o (官方指定)
    Data: Full locomo10.json dataset (10 conversations)
    """
    print("\n" + "=" * 80)
    print("2. LoCoMo - FULL SCALE (Official MemEval Framework)")
    print("=" * 80)
    print("Framework: MemEval Official")
    print("LLM: GPT-4o (as specified in paper)")
    print("Data: Full locomo10.json dataset (10 convations)")
    print("=" * 80)
    
    try:
        start_time = time.time()
        
        # 使用MemEval官方脚本
        cmd = [
            "python3",
            str(memeval_dir / "scripts" / "run_full_benchmark.py"),
            "--benchmark", "locomo",
            "--systems", "carrymem",
            "--llm-model", "gpt-4o",
            "--num-samples", "10",
            "--skip-judge",
            "--output-dir", str(results_dir / "locomo_full")
        ]
        
        print(f"Runningand: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(memeval_dir), capture_output=True, text=True)
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ LoCoMo completed ({elapsed/60:.1f} min)")
            print(result.stdout)
            return {
                "status": "success",
                "elapsed_minutes": elapsed/60,
                "framework": "MemEval Official",
                "model": "gpt-4o"
            }
        else:
            print(f"❌o failed")
            print(result.stderr)
            return {
                "status": "failed",
                "error": result.stderr,
                "elapsed_minutes": elapsed/60
            }
            
    except Exception as e:
        print(f"❌ LoCoMo exception: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}


def main():
    print("=" * 80)
    print("C)")
    print("Scale: Full datasets")
    print("Using official frameworks and data sources")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    benchmark_dir, memeval_dir = setup_environment()
    results_dir = benchmark_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    overall_start = time.time()
    all_results = {}
    
    # 1. LongMemEval (MemEval官方框架)
    all_results["longmemeval"] = run_longmemeval_memeval(memeval_dir, results_dir)
    
    # 2. LoCoMo (MemEval官方框架)
    all_results["locomo"] = run_locomo_memeval(memeval_dir, results_dir)
    
    overall_elapsed = time.time() - overall_start
    
    # Save combined results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"official_full_scale_{timestamp}.json"
    
    final_output = {
        "suite": "CarryMem Official Full-Scale Benchmarks",
        "timestamp": datetime.now().isoformat(),
        "total_elapsed_minutes": overall_elapsed/60,
        "benchmarks": all_results,
        "credibilit