#!/usr/bin/env python3
"""
LaMP-2 Benchmark全量测试脚本
使用CarryMem进行个性化电影标签预测（完整数据集）
"""

import os
import sys
import json
from datetime import datetime
from openai import OpenAI

# 添加CarryMem路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from carrymem import CarryMem

def load_lamp2_data():
    """加载LaMP-2完整数据"""
    # 尝试多个可能的数据文件
    possible_files = [
        "LaMP_official_data/lamp2_full.json",
        "LaMP_official_data/lamp2.json",
        "LaMP-main/LaMP/data/LaMP_2/dev_questions.json",
        "LaMP_data/lamp2_sample.json"  # 备用
    ]
    
    for data_file in possible_files:
        if os.path.exists(data_file):
            print(f"✅ 找到数据文件: {data_file}")
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"✅ 加载了 {len(data)} 条LaMP-2数据")
            return data
    
    print(f"❌ 未找到LaMP-2数据文件")
    print("尝试的路径:")
    for f in possible_files:
        print(f"  - {f}")
    return None

def run_lamp2_full_test():
    """运行LaMP-2完整测试"""
    print("=" * 70)
    print("LaMP-2 Benchmark全量测试")
    print("=" * 70)
    
    # 加载数据
    data = load_lamp2_data()
    if not data:
        return
    
    # 初始化CarryMem
    print("\n初始化CarryMem...")
    carrymem = CarryMem()
    
    # 初始化LLM (Claude)
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.moka-ai.com/v1")
    )
    
    # 全量测试
    test_size = len(data)
    print(f"\n测试规模: {test_size} 条数据（全量）")
    print("预计时间: 20-40分钟")
    print()
    
    results = []
    correct = 0
    errors = 0
    
    for i, item in enumerate(data):
        print(f"\n[{i+1}/{test_size}] 处理中... ({(i+1)/test_size*100:.1f}%)")
        
        try:
            # 提取用户历史和问题
            profile = item.get('profile', '')
            question = item.get('input', '')
            ground_truth = item.get('output', '')
            
            # 处理profile（可能是字符串或列表）
            if profile:
                if isinstance(profile, list):
                    profile_text = '\n'.join(str(p) for p in profile)
                else:
                    profile_text = str(profile)
                carrymem.classify_and_remember(profile_text)
            
            # 召回相关记忆
            memories = carrymem.recall_memories(question, limit=5)
            # 修复：memories可能是Memory对象列表，需要正确提取content
            if memories and hasattr(memories[0], 'content'):
                memory_context = "\n".join([m.content for m in memories])
            elif memories and isinstance(memories[0], dict):
                memory_context = "\n".join([m.get('content', '') for m in memories])
            else:
                memory_context = ""
            
            # 构建prompt
            prompt = f"""Based on the user's movie preferences:
{memory_context}

Question: {question}

Provide movie tags that match the user's preferences."""
            
            # 调用LLM
            response = client.chat.completions.create(
                model="moka/claude-sonnet-4-6",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            prediction = response.choices[0].message.content
            
            # 简单评估 (检查关键词匹配)
            # 修复：ground_truth可能是列表
            if isinstance(ground_truth, list):
                gt_tags = ground_truth[:3]
            else:
                gt_tags = str(ground_truth).split(',')[:3]
            
            is_correct = any(str(tag).strip().lower() in prediction.lower() 
                           for tag in gt_tags)
            
            if is_correct:
                correct += 1
            
            results.append({
                "id": i + 1,
                "question": str(question)[:100],
                "ground_truth": str(ground_truth) if not isinstance(ground_truth, list) else ground_truth,
                "prediction": str(prediction)[:200],
                "correct": is_correct,
                "memories_recalled": len(memories) if memories else 0
            })
            
            # 每10个打印一次进度
            if (i + 1) % 10 == 0:
                print(f"  当前准确率: {correct}/{i+1} = {correct/(i+1):.1%}")
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            errors += 1
            results.append({
                "id": i + 1,
                "error": str(e)
            })
    
    # 计算准确率
    accuracy = correct / test_size if test_size > 0 else 0
    
    # 保存结果
    output = {
        "benchmark": "LaMP-2",
        "test_type": "full_scale",
        "timestamp": datetime.now().isoformat(),
        "test_size": test_size,
        "correct": correct,
        "errors": errors,
        "accuracy": accuracy,
        "llm": "moka/claude-sonnet-4-6",
        "memory_system": "CarryMem",
        "results": results
    }
    
    output_file = f"results/lamp2_full_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("results", exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 打印总结
    print("\n" + "=" * 70)
    print("LaMP-2 全量测试完成")
    print("=" * 70)
    print(f"测试规模: {test_size}")
    print(f"正确数: {correct}")
    print(f"错误数: {errors}")
    print(f"准确率: {accuracy:.1%}")
    print(f"结果文件: {output_file}")
    print("=" * 70)
    
    return output

if __name__ == "__main__":
    run_lamp2_full_test()
