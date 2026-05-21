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
    data_file = "MSC_official_data/msc_val_10pct.json"
    
    if not os.path.exists(data_file):
        print(f"❌ 未找到数据文件: {data_file}")
        return None, None
    
    print(f"✅ 找到数据文件: {data_file}")
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"✅ 加载了 {len(data)} 个对话")
    return data, data_file

def run_msc_local(num_conversations=None):
    """运行MSC本地数据测试"""
    print("=" * 80)
    print("MSC 本地数据Benchmark测试")
    print("=" * 80)
    print("数据集: 本地MSC数据文件")
    print("指标: Token F1")
    print("LLM: gpt-4o")
    print()
    
    # 加载本地数据
    print("加载数据...")
    dataset, data_file = load_local_msc_data()
    
    if not dataset:
        print("❌ 无法加载数据，退出")
        return None
    
    if num_conversations:
        dataset = dataset[:num_conversations]
        print(f"限制测试数量: {len(dataset)} 个对话")
    
    print()
    
    # 初始化
    carrymem = CarryMem()
    client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://api.moka-ai.com/v1")
    )
    
    # 测试
    all_f1_scores = []
    results = []
    
    for idx, conversation in enumerate(dataset):
        print(f"\n[{idx+1}/{len(dataset)}] 处理对话 ID={conversation.get('id', idx)}...")
        
        try:
            if 'sessions' not in conversation:
                print("  ⚠️  无sessions字段，跳过")
                continue
            
            sessions = conversation['sessions']
            if not sessions:
                print("  ⚠️  空sessions，跳过")
                continue
            
            conv_f1_scores = []
            
            # 处理每个session
            for session_idx, session in enumerate(sessions):
                if 'dialogue' not in session:
                    continue
                
                dialogue = session['dialogue']
                if not dialogue:
                    continue
                
                # MSC格式: 对话是交替的 Speaker 1 和 Speaker 2
                # 我们将 Speaker 1 作为用户，Speaker 2 作为助手
                for turn_idx in range(0, len(dialogue) - 1, 2):
                    user_turn = dialogue[turn_idx]
                    assistant_turn = dialogue[turn_idx + 1]
                    
                    user_msg = user_turn.get('text', '')
                    ground_truth = assistant_turn.get('text', '')
                    
                    if not user_msg or not ground_truth:
                        continue
                    
                    # 召回记忆
                    memories = carrymem.recall_memories(query=user_msg, limit=5)
                    memory_context = "\n".join([m['content'] for m in memories])
                    
                    # 生成回复
                    prompt = f"Context: {memory_context}\n\nUser: {user_msg}\n\nAssistant:"
                    
                    try:
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
                    
                    except Exception as api_error:
                        # 处理内容过滤或其他API错误
                        if "content_filter" in str(api_error) or "content management policy" in str(api_error):
                            print(f"    ⚠️  内容被过滤，跳过此turn")
                            # 使用ground truth作为fallback，F1=1.0
                            conv_f1_scores.append(0.0)
                            all_f1_scores.append(0.0)
                        else:
                            # 其他错误，重新抛出
                            raise
            
            avg_f1 = sum(conv_f1_scores) / len(conv_f1_scores) if conv_f1_scores else 0
            print(f"  对话F1: {avg_f1:.3f} ({len(conv_f1_scores)} turns)")
            
            results.append({
                "conversation_id": conversation.get('id', idx),
                "num_turns": len(conv_f1_scores),
                "avg_f1": avg_f1,
                "f1_scores": conv_f1_scores
            })
            
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # 计算总体指标
    overall_f1 = sum(all_f1_scores) / len(all_f1_scores) if all_f1_scores else 0
    
    print("\n" + "=" * 80)
    print("MSC 本地数据测试完成")
    print("=" * 80)
    print(f"数据源: {data_file}")
    print(f"测试对话数: {len(results)}")
    print(f"总Turn数: {len(all_f1_scores)}")
    print(f"平均Token F1: {overall_f1:.4f}")
    print("=" * 80)
    
    # 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"results/msc_local_results_{timestamp}.json"
    os.makedirs("results", exist_ok=True)
    
    with open(result_file, "w") as f:
        json.dump({
            "benchmark": "MSC_Local",
            "data_source": data_file,
            "timestamp": timestamp,
            "num_conversations": len(results),
            "num_turns": len(all_f1_scores),
            "overall_f1": overall_f1,
            "results": results
        }, f, indent=2)
    
    print(f"结果文件: {result_file}")
    print("=" * 80)
    print()
    
    return overall_f1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run MSC local benchmark")
    parser.add_argument("--num_conversations", type=int, default=None,
                       help="Number of conversations to test (default: all)")
    args = parser.parse_args()
    
    run_msc_local(args.num_conversations)
