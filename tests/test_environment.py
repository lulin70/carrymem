#!/usr/bin/env python3
"""
环境检测测试

测试系统环境、依赖、配置等是否正常
"""

import os
import sys
import subprocess
import importlib
import sqlite3
from typing import Dict, Any


def test_system_dependencies():
    """测试系统依赖"""
    print("🧪 测试: 系统依赖")
    print("-" * 60)
    
    # 测试 Python 版本
    python_version = sys.version
    print(f"✅ Python 版本: {python_version}")
    
    # 测试必要的 Python 包
    required_packages = [
        "yaml",
        "langdetect",
        "pycld2"
    ]
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package} 已安装")
        except ImportError:
            print(f"❌ {package} 未安装")
    
    print("-" * 60)


def test_model_files():
    """测试模型文件"""
    print("\n🧪 测试: 模型文件")
    print("-" * 60)
    
    # 测试模型目录
    model_dir = "models"
    if os.path.exists(model_dir):
        print(f"✅ 模型目录存在: {model_dir}")
        
        # 测试模型文件
        model_files = os.listdir(model_dir)
        if model_files:
            print(f"✅ 模型文件存在: {len(model_files)} 个文件")
            for file in model_files[:5]:  # 只显示前 5 个文件
                print(f"   - {file}")
        else:
            print("❌ 模型目录为空")
    else:
        print(f"❌ 模型目录不存在: {model_dir}")
    
    print("-" * 60)


def test_database_connections():
    """测试数据库连接"""
    print("\n🧪 测试: 数据库连接")
    print("-" * 60)
    
    # 测试 SQLite 连接
    try:
        conn = sqlite3.connect(":memory:")
        conn.close()
        print("✅ SQLite 连接正常")
    except Exception as e:
        print(f"❌ SQLite 连接失败: {e}")
    
    print("-" * 60)


def test_network_connections():
    """测试网络连接"""
    print("\n🧪 测试: 网络连接")
    print("-" * 60)
    
    # 测试 Hugging Face 连接
    try:
        import requests
        response = requests.get("https://huggingface.co", timeout=5)
        if response.status_code == 200:
            print("✅ Hugging Face 连接正常")
        else:
            print(f"❌ Hugging Face 连接失败: 状态码 {response.status_code}")
    except Exception as e:
        print(f"❌ Hugging Face 连接失败: {e}")
    
    print("-" * 60)


def test_mcp_service():
    """测试 MCP 服务状态"""
    print("\n🧪 测试: MCP 服务状态")
    print("-" * 60)
    
    # 测试 MCP 服务是否可以启动
    try:
        # 启动 MCP 服务进程
        process = subprocess.Popen(
            [sys.executable, "-m", "memory_classification_engine", "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={
                **dict(os.environ),
                "PYTHONPATH": "src",
                "HF_DATASETS_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
            }
        )
        
        # 等待服务启动
        import time
        import select
        start_time = time.time()
        max_wait_time = 15  # 15秒超时
        
        # 读取输出，检查服务是否启动成功
        while time.time() - start_time < max_wait_time:
            # 检查是否有可用的输出
            ready, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
            
            # 读取标准输出
            if process.stdout in ready:
                line = process.stdout.readline()
                if line:
                    if "MCP Server initialized" in line or "MCP Server starting..." in line:
                        print("✅ MCP 服务启动成功")
                        break
            
            # 读取标准错误
            if process.stderr in ready:
                line = process.stderr.readline()
                if line:
                    if "MCP Server initialized" in line or "MCP Server starting..." in line:
                        print("✅ MCP 服务启动成功")
                        break
            
            # 检查进程是否已经退出
            if process.poll() is not None:
                print("❌ MCP 服务进程已退出")
                break
            
            time.sleep(0.1)
        else:
            # 超时
            print("❌ MCP 服务启动超时")
        
        # 关闭进程
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            
    except Exception as e:
        print(f"❌ MCP 服务启动失败: {e}")
    
    print("-" * 60)


def run_all_environment_tests():
    """运行所有环境测试"""
    print("=" * 60)
    print("环境检测测试")
    print("=" * 60)
    
    test_system_dependencies()
    test_model_files()
    test_database_connections()
    test_network_connections()
    test_mcp_service()
    
    print("\n" + "=" * 60)
    print("环境检测测试完成")
    print("=" * 60)


if __name__ == "__main__":
    run_all_environment_tests()
