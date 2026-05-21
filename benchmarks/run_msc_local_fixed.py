#!/usr/bin/env python3
"""
MSC (Multi-Session Chat) 本地数据测试
使用本地MSC数据文件，避免HuggingFace连接问题
使用官方Token F1指标
"""

import os
import sys
import json
import argparse
from datetime import datetime
from openai import OpenAI

# 添加CarryMem路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from carrymem import CarryMem

def compute_token_f1(predicted: str, ground_truth: str) -> float:
    """计算Token F1 (官方MSC指标)"""
    pred_tokens = set(predicted.lower().split())
    gt_tokens = set(ground_truth.lower().split())
    
    if not pred_tokens or not gt_tokens:
        return 0.0
    
    common = pred_tokens & gt_tokens
    if not common:
        return 0.0
    
    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(gt_tokens)
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1

def load_local_msc_data():
    """加载本地MSC数据"""
    possible_files = [
        "MSC/data/msc_val.json",
        "MSC_official_data/msc_val_10pct.json",
        "MSC/data/msc_session1_val.jsonl",
        "../MSC/data/msc_val.json"
    ]
    
    for data_file in possible_files:
        if os.path.exists(data_file):
            print(f"✅ 找到数据文件: {data_file}")
            
            if data_file.endswith('.json'):
                with open(data_file, 'r', encoding='utf-8') as f:
                  data = json.load(f)
            elif data_file.endswith('.jsonl'):
                data = []
                with open(data_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        data.append(json.loads(line))
            
            print(f"✅ 加载了 {len(data)} 个对话")
            return data, data_file
    
    print("❌ 未找到MSC数据文件")
    print("尝试的路径:")
    for f in possible_files:
        print(f"  - {f}")
    return None, None

def run_msc_local(num_conversations=None):
    """运行MSC本地数据测试"""
    print("=" * 80)
    print("MSC 本地数据Benchmark测试")
    print("=" * 80)
    print("数据集: 本地MSC数据文件")
    print("指标: Token F1"ata()
    
    if not dataset:
        prinsations:
        dataset = dataset[:num_conversations]
        print(f"限制测试数量: {len(dataset)} 个对话")
    
    print()
    
    # 初始化
    carrymem = CarryMem()
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.moka-ai.com/v1")
    )
    
    # 测试
    all_f1_scores = []
    results = []
    
    for idx, conversation in enumerate(dataset):
        print(f"\n[{idx+1}/{len(dataset)}] 处理对话...")
        
        try:
            # 兼容不同的数据格式
            if 'dialog' in conversation:
                turns = conversation['dialog']
            elif 'dialogue' in conversation:
                turns = conversation['dialogue']
            elif 'turns' in conversation:
                turns = conversation['turns']
            else:
                print(f"  ⚠️  无法找到对话内容，跳过")
                continue
            
            if not turns:
                print("  ⚠️  空对话，跳过             continue
            
            conv_f1_scores = []
            
            for turn_idx, turn in enumerate(turns):
                # 兼容不同的字段名
                if isinstance(turn, dict):
                    user_msg = turn.get('text', turn.get('utterance', ''))
                    ground_truth = turn.get('response', turn.get  memories = carrymem.recall_memories(user_msg, top_k=5)
                memory_context = "\n".join([m['content'] for m in memories])
                
                # 生成回复
                prompt = f"Context: {memory_context}\n\nUser: {user_msg}\n\nAssistant:"
                
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                
                prediction = response.choices[0].message.content
                
                # 计算Token F1
                f1 = compute_token_f1(prediction, ground_truth)
                conv_f1_scores.append(f1)
                all_f1_scores.append(f1)
                
                # 存储对话历史
                carrymem.classify_and_remember(f"User: {user_msg}\nAssistant: {prediction}")
            
            avg_f1 = sum(conv_f1_scores) / len(conv_f1_scores) if conv_f1_scores else             "conversation_id": idx,
                "num_turns": len(conv_f1_scores),
                "avg_f1": avg_f1,
                "turn_f1_scores": conv_f1_scores
            })
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            continue
    
    # 计算总体指标
    overall_f1 = sum(all_f1_scores) / len(all_f1_scores) if all_f1_scores else 0
    
    print("\n" + "=" * 80)
    print("MSC 本地数据测试完成")
    print("=" * 80)
    print(f"数据源: {data_file}")
    print(f"测试对话数: {len(results)}")
    print(f"总Turn数: {len(allres)}")
    print(f"平均Token F1: {overall_f1:.4f}")
    print("=" * 80)
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"results/msc_local_results_{timestamp}.json"
    os.makedirs("results", exist_ok=True)
    
    with open(result_file, "w") as f:
        json.dump({
            "benchmark": "MSC_Local",
            "data_source": data_firesults
        }, f, indent=2)
    
    print(f"结果文件: {result_file}")
    print("=" * 80)
    print()
    
    return overall_f1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_conversations", type=int, default=None,
                       help="Number of conversations to test (default: all)")
    args = parser.parse_args()
    
    run_msc_local(args.num_conversations)
