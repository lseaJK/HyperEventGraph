#!/usr/bin/env python3
"""
最基础的SiliconFlow API连通性测试
不依赖项目配置框架，直接测试API连接
"""
import os
import json
import requests

def test_basic_api_connection():
    """测试基础API连接"""
    
    # 检查API密钥
    api_key = os.getenv('SILICONFLOW_API_KEY')
    if not api_key:
        print("❌ 未找到SILICONFLOW_API_KEY环境变量")
        print("请设置: export SILICONFLOW_API_KEY=your_api_key")
        return False
    
    print(f"✅ 找到API密钥: {api_key[:10]}...")
    
    # 基础API测试
    url = "https://api.siliconflow.cn/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 最简单的请求参数
    data = {
        "model": "deepseek-ai/DeepSeek-V2.5",
        "messages": [
            {"role": "user", "content": "请回复'连接成功'"}
        ],
        "max_tokens": 10,
        "temperature": 0.1
    }
    
    print("🔍 测试API请求...")
    print(f"URL: {url}")
    print(f"Model: {data['model']}")
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"📊 HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            print(f"✅ API响应成功: {content}")
            return True
        else:
            print(f"❌ API请求失败:")
            print(f"   状态码: {response.status_code}")
            print(f"   响应内容: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 网络连接错误")
        return False
    except Exception as e:
        print(f"❌ 其他错误: {e}")
        return False

def test_model_availability():
    """测试模型可用性"""
    api_key = os.getenv('SILICONFLOW_API_KEY')
    if not api_key:
        print("❌ 需要API密钥才能测试模型")
        return False
        
    url = "https://api.siliconflow.cn/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    print("\n🔍 测试模型列表...")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            models = response.json()
            deepseek_models = [m for m in models.get('data', []) if 'deepseek' in m.get('id', '').lower()]
            print(f"✅ 可用的DeepSeek模型:")
            for model in deepseek_models[:5]:  # 只显示前5个
                print(f"   - {model['id']}")
            return True
        else:
            print(f"❌ 模型列表请求失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 模型列表测试失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始基础API连通性测试\n")
    
    # 测试基础连接
    basic_test = test_basic_api_connection()
    
    # 测试模型可用性
    model_test = test_model_availability()
    
    print("\n" + "="*50)
    if basic_test:
        print("✅ 基础API连接正常")
        if model_test:
            print("✅ 模型列表获取正常")
        print("\n建议：可以继续调试项目配置问题")
    else:
        print("❌ 基础API连接失败")
        print("\n建议：请检查网络连接和API密钥")
