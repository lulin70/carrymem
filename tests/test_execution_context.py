#!/usr/bin/env python3
"""
测试执行反馈信号接入 Layer 2
"""

from memory_classification_engine import MemoryClassificationEngine
import sys
import os

# 重定向 stderr 到 /dev/null 以减少错误信息
sys.stderr = open(os.devnull, 'w')

def test_execution_context():
    print("Testing execution context feedback signals...")
    
    # 初始化引擎
    engine = MemoryClassificationEngine()
    
    # 测试用例 1: 正面反馈
    print("\n1. Testing positive feedback:")
    execution_context = {
        'user_feedback': '对了，这个方案很好',
        'tool_error': False,
        'retry_count': 0,
        'execution_time': 1.5,
        'context_position': 'normal'
    }
    
    result = engine.process_message(
        "我们应该使用双引号",
        execution_context=execution_context
    )
    
    matches = result.get('matches', [])
    print(f"   Matches found: {len(matches)}")
    for match in matches:
        print(f"   - {match.get('memory_type')}: {match.get('content')} (confidence: {match.get('confidence', 0):.2f})")
    
    # 测试用例 2: 负面反馈
    print("\n2. Testing negative feedback:")
    execution_context = {
        'user_feedback': '不对，应该使用空格',
        'tool_error': False,
        'retry_count': 0,
        'execution_time': 2.0,
        'context_position': 'normal'
    }
    
    result = engine.process_message(
        "使用制表符缩进",
        execution_context=execution_context
    )
    
    matches = result.get('matches', [])
    print(f"   Matches found: {len(matches)}")
    for match in matches:
        print(f"   - {match.get('memory_type')}: {match.get('content')} (confidence: {match.get('confidence', 0):.2f})")
    
    # 测试用例 3: 工具错误
    print("\n3. Testing tool error feedback:")
    execution_context = {
        'user_feedback': '',
        'tool_error': True,
        'retry_count': 0,
        'execution_time': 3.0,
        'context_position': 'normal'
    }
    
    result = engine.process_message(
        "执行工具失败",
        execution_context=execution_context
    )
    
    matches = result.get('matches', [])
    print(f"   Matches found: {len(matches)}")
    for match in matches:
        print(f"   - {match.get('memory_type')}: {match.get('content')} (confidence: {match.get('confidence', 0):.2f})")
    
    # 测试用例 4: 重试反馈
    print("\n4. Testing retry feedback:")
    execution_context = {
        'user_feedback': '',
        'tool_error': False,
        'retry_count': 2,
        'execution_time': 4.0,
        'context_position': 'normal'
    }
    
    result = engine.process_message(
        "需要重试",
        execution_context=execution_context
    )
    
    matches = result.get('matches', [])
    print(f"   Matches found: {len(matches)}")
    for match in matches:
        print(f"   - {match.get('memory_type')}: {match.get('content')} (confidence: {match.get('confidence', 0):.2f})")
    
    # 测试用例 5: 性能问题
    print("\n5. Testing performance issue feedback:")
    execution_context = {
        'user_feedback': '',
        'tool_error': False,
        'retry_count': 0,
        'execution_time': 15.0,  # 超过10秒阈值
        'context_position': 'normal'
    }
    
    result = engine.process_message(
        "执行时间过长",
        execution_context=execution_context
    )
    
    matches = result.get('matches', [])
    print(f"   Matches found: {len(matches)}")
    for match in matches:
        print(f"   - {match.get('memory_type')}: {match.get('content')} (confidence: {match.get('confidence', 0):.2f})")
    
    # 测试用例 6: 上下文位置
    print("\n6. Testing context position feedback:")
    execution_context = {
        'user_feedback': '',
        'tool_error': False,
        'retry_count': 0,
        'execution_time': 1.0,
        'context_position': 'correction_followup'
    }
    
    result = engine.process_message(
        "根据你的纠正",
        execution_context=execution_context
    )
    
    matches = result.get('matches', [])
    print(f"   Matches found: {len(matches)}")
    for match in matches:
        print(f"   - {match.get('memory_type')}: {match.get('content')} (confidence: {match.get('confidence', 0):.2f})")
    
    print("\n✅ Execution context tests completed!")

if __name__ == "__main__":
    test_execution_context()
