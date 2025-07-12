#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM API连通性和响应速度测试

测试内容：
1. API连接稳定性
2. 响应时间测试
3. 并发请求测试
4. 错误处理测试
5. 成本估算
"""

import os
import time
import asyncio
import statistics
from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime

# 手动加载环境变量
def load_env_file(env_path: str) -> Dict[str, str]:
    """手动加载.env文件"""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
    return env_vars

# 加载环境变量
project_root = Path(__file__).parent
env_path = project_root / '.env'
env_vars = load_env_file(str(env_path))

# 设置环境变量
for key, value in env_vars.items():
    os.environ[key] = value

class LLMPerformanceTester:
    """LLM性能测试器"""
    
    def __init__(self):
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.base_url = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
        
        # 测试结果
        self.test_results = {
            'connection_test': {},
            'response_time_test': {},
            'concurrent_test': {},
            'error_handling_test': {},
            'cost_estimation': {}
        }
        
        print(f"初始化LLM性能测试器")
        print(f"API密钥: {'已配置' if self.api_key else '未配置'}")
        print(f"基础URL: {self.base_url}")
        print(f"模型: {self.model}")
    
    def test_basic_connection(self) -> bool:
        """测试基础连接"""
        print("\n=== 基础连接测试 ===")
        
        try:
            import requests
            
            # 测试简单请求
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': '你好，请回复"连接成功"'}
                ],
                'max_tokens': 50,
                'temperature': 0.1
            }
            
            start_time = time.time()
            response = requests.post(
                f'{self.base_url}/chat/completions',
                headers=headers,
                json=data,
                timeout=30
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                
                self.test_results['connection_test'] = {
                    'status': 'success',
                    'response_time': response_time,
                    'content': content,
                    'tokens_used': result.get('usage', {})
                }
                
                print(f"✓ 连接成功")
                print(f"✓ 响应时间: {response_time:.2f}秒")
                print(f"✓ 响应内容: {content}")
                print(f"✓ Token使用: {result.get('usage', {})}")
                return True
            else:
                self.test_results['connection_test'] = {
                    'status': 'failed',
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                print(f"✗ 连接失败: HTTP {response.status_code}")
                print(f"✗ 错误信息: {response.text}")
                return False
                
        except Exception as e:
            self.test_results['connection_test'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"✗ 连接异常: {str(e)}")
            return False
    
    def test_response_times(self, num_tests: int = 5) -> Dict[str, float]:
        """测试响应时间"""
        print(f"\n=== 响应时间测试 (共{num_tests}次) ===")
        
        response_times = []
        test_prompts = [
            "请简单介绍一下人工智能。",
            "什么是机器学习？",
            "解释一下深度学习的概念。",
            "描述一下自然语言处理。",
            "什么是计算机视觉？"
        ]
        
        try:
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            for i in range(num_tests):
                prompt = test_prompts[i % len(test_prompts)]
                
                data = {
                    'model': self.model,
                    'messages': [
                        {'role': 'user', 'content': prompt}
                    ],
                    'max_tokens': 100,
                    'temperature': 0.7
                }
                
                start_time = time.time()
                response = requests.post(
                    f'{self.base_url}/chat/completions',
                    headers=headers,
                    json=data,
                    timeout=30
                )
                end_time = time.time()
                
                response_time = end_time - start_time
                response_times.append(response_time)
                
                if response.status_code == 200:
                    print(f"测试 {i+1}: {response_time:.2f}秒 ✓")
                else:
                    print(f"测试 {i+1}: 失败 (HTTP {response.status_code}) ✗")
                
                # 避免请求过于频繁
                time.sleep(1)
            
            # 计算统计信息
            if response_times:
                stats = {
                    'min_time': min(response_times),
                    'max_time': max(response_times),
                    'avg_time': statistics.mean(response_times),
                    'median_time': statistics.median(response_times),
                    'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0
                }
                
                self.test_results['response_time_test'] = {
                    'status': 'success',
                    'num_tests': num_tests,
                    'response_times': response_times,
                    'statistics': stats
                }
                
                print(f"\n响应时间统计:")
                print(f"  最小值: {stats['min_time']:.2f}秒")
                print(f"  最大值: {stats['max_time']:.2f}秒")
                print(f"  平均值: {stats['avg_time']:.2f}秒")
                print(f"  中位数: {stats['median_time']:.2f}秒")
                print(f"  标准差: {stats['std_dev']:.2f}秒")
                
                return stats
            
        except Exception as e:
            self.test_results['response_time_test'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"✗ 响应时间测试异常: {str(e)}")
        
        return {}
    
    async def test_concurrent_requests(self, num_concurrent: int = 3) -> Dict[str, Any]:
        """测试并发请求"""
        print(f"\n=== 并发请求测试 (并发数: {num_concurrent}) ===")
        
        try:
            import aiohttp
            
            async def make_request(session, prompt_id):
                """发送单个异步请求"""
                data = {
                    'model': self.model,
                    'messages': [
                        {'role': 'user', 'content': f'这是并发测试请求 #{prompt_id}，请简单回复确认。'}
                    ],
                    'max_tokens': 50,
                    'temperature': 0.1
                }
                
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                start_time = time.time()
                async with session.post(
                    f'{self.base_url}/chat/completions',
                    json=data,
                    headers=headers,
                    timeout=30
                ) as response:
                    end_time = time.time()
                    response_time = end_time - start_time
                    
                    if response.status == 200:
                        result = await response.json()
                        return {
                            'id': prompt_id,
                            'status': 'success',
                            'response_time': response_time,
                            'tokens': result.get('usage', {})
                        }
                    else:
                        return {
                            'id': prompt_id,
                            'status': 'failed',
                            'response_time': response_time,
                            'error': f'HTTP {response.status}'
                        }
            
            # 执行并发请求
            async with aiohttp.ClientSession() as session:
                tasks = [make_request(session, i) for i in range(num_concurrent)]
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 分析结果
            successful_requests = [r for r in results if isinstance(r, dict) and r.get('status') == 'success']
            failed_requests = [r for r in results if isinstance(r, dict) and r.get('status') == 'failed']
            error_requests = [r for r in results if isinstance(r, Exception)]
            
            concurrent_stats = {
                'total_requests': num_concurrent,
                'successful': len(successful_requests),
                'failed': len(failed_requests),
                'errors': len(error_requests),
                'success_rate': len(successful_requests) / num_concurrent * 100
            }
            
            if successful_requests:
                response_times = [r['response_time'] for r in successful_requests]
                concurrent_stats['avg_response_time'] = statistics.mean(response_times)
                concurrent_stats['max_response_time'] = max(response_times)
                concurrent_stats['min_response_time'] = min(response_times)
            
            self.test_results['concurrent_test'] = {
                'status': 'success',
                'statistics': concurrent_stats,
                'detailed_results': results
            }
            
            print(f"并发测试结果:")
            print(f"  总请求数: {concurrent_stats['total_requests']}")
            print(f"  成功请求: {concurrent_stats['successful']}")
            print(f"  失败请求: {concurrent_stats['failed']}")
            print(f"  异常请求: {concurrent_stats['errors']}")
            print(f"  成功率: {concurrent_stats['success_rate']:.1f}%")
            
            if 'avg_response_time' in concurrent_stats:
                print(f"  平均响应时间: {concurrent_stats['avg_response_time']:.2f}秒")
            
            return concurrent_stats
            
        except ImportError:
            print("✗ 需要安装aiohttp库进行并发测试: pip install aiohttp")
            self.test_results['concurrent_test'] = {
                'status': 'skipped',
                'reason': 'aiohttp not available'
            }
        except Exception as e:
            self.test_results['concurrent_test'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"✗ 并发测试异常: {str(e)}")
        
        return {}
    
    def test_error_handling(self) -> Dict[str, Any]:
        """测试错误处理"""
        print("\n=== 错误处理测试 ===")
        
        error_tests = [
            {
                'name': '无效API密钥',
                'api_key': 'invalid_key',
                'expected_status': 401
            },
            {
                'name': '超长输入',
                'content': 'A' * 10000,  # 超长文本
                'expected_status': 400
            },
            {
                'name': '无效模型',
                'model': 'invalid-model-name',
                'expected_status': 400
            }
        ]
        
        error_results = []
        
        try:
            import requests
            
            for test in error_tests:
                print(f"\n测试: {test['name']}")
                
                headers = {
                    'Authorization': f'Bearer {test.get("api_key", self.api_key)}',
                    'Content-Type': 'application/json'
                }
                
                data = {
                    'model': test.get('model', self.model),
                    'messages': [
                        {'role': 'user', 'content': test.get('content', '测试错误处理')}
                    ],
                    'max_tokens': 50
                }
                
                try:
                    response = requests.post(
                        f'{self.base_url}/chat/completions',
                        headers=headers,
                        json=data,
                        timeout=10
                    )
                    
                    result = {
                        'test_name': test['name'],
                        'status_code': response.status_code,
                        'expected_status': test['expected_status'],
                        'passed': response.status_code == test['expected_status']
                    }
                    
                    if result['passed']:
                        print(f"  ✓ 按预期返回状态码 {response.status_code}")
                    else:
                        print(f"  ✗ 状态码不符预期: 期望{test['expected_status']}, 实际{response.status_code}")
                    
                    error_results.append(result)
                    
                except Exception as e:
                    error_results.append({
                        'test_name': test['name'],
                        'error': str(e),
                        'passed': False
                    })
                    print(f"  ✗ 请求异常: {str(e)}")
            
            self.test_results['error_handling_test'] = {
                'status': 'success',
                'results': error_results,
                'passed_tests': sum(1 for r in error_results if r.get('passed', False)),
                'total_tests': len(error_results)
            }
            
        except Exception as e:
            self.test_results['error_handling_test'] = {
                'status': 'error',
                'error': str(e)
            }
            print(f"✗ 错误处理测试异常: {str(e)}")
        
        return error_results
    
    def estimate_costs(self) -> Dict[str, Any]:
        """估算使用成本"""
        print("\n=== 成本估算 ===")
        
        # 基于测试结果估算成本
        connection_test = self.test_results.get('connection_test', {})
        response_time_test = self.test_results.get('response_time_test', {})
        
        if connection_test.get('status') == 'success':
            tokens_used = connection_test.get('tokens_used', {})
            prompt_tokens = tokens_used.get('prompt_tokens', 0)
            completion_tokens = tokens_used.get('completion_tokens', 0)
            total_tokens = tokens_used.get('total_tokens', 0)
            
            # DeepSeek定价 (示例价格，实际价格请查看官网)
            price_per_1k_tokens = 0.002  # 假设每1K tokens $0.002
            
            cost_per_request = (total_tokens / 1000) * price_per_1k_tokens
            
            # 估算不同使用场景的成本
            scenarios = {
                '每日100次查询': {
                    'requests_per_day': 100,
                    'daily_cost': cost_per_request * 100,
                    'monthly_cost': cost_per_request * 100 * 30
                },
                '每日1000次查询': {
                    'requests_per_day': 1000,
                    'daily_cost': cost_per_request * 1000,
                    'monthly_cost': cost_per_request * 1000 * 30
                },
                '批量处理(每日10000次)': {
                    'requests_per_day': 10000,
                    'daily_cost': cost_per_request * 10000,
                    'monthly_cost': cost_per_request * 10000 * 30
                }
            }
            
            cost_estimation = {
                'tokens_per_request': {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens
                },
                'cost_per_request': cost_per_request,
                'price_per_1k_tokens': price_per_1k_tokens,
                'scenarios': scenarios
            }
            
            self.test_results['cost_estimation'] = cost_estimation
            
            print(f"Token使用情况:")
            print(f"  输入tokens: {prompt_tokens}")
            print(f"  输出tokens: {completion_tokens}")
            print(f"  总计tokens: {total_tokens}")
            print(f"\n成本估算 (基于 ${price_per_1k_tokens}/1K tokens):")
            print(f"  单次请求成本: ${cost_per_request:.6f}")
            
            for scenario_name, scenario_data in scenarios.items():
                print(f"\n{scenario_name}:")
                print(f"  日成本: ${scenario_data['daily_cost']:.4f}")
                print(f"  月成本: ${scenario_data['monthly_cost']:.2f}")
            
            return cost_estimation
        else:
            print("无法估算成本：基础连接测试未成功")
            return {}
    
    def generate_report(self) -> str:
        """生成测试报告"""
        print("\n=== 生成测试报告 ===")
        
        report = {
            'test_time': datetime.now().isoformat(),
            'api_config': {
                'base_url': self.base_url,
                'model': self.model,
                'api_key_configured': bool(self.api_key)
            },
            'test_results': self.test_results
        }
        
        # 保存报告
        report_file = project_root / f'llm_performance_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            print(f"✓ 测试报告已保存: {report_file}")
            return str(report_file)
            
        except Exception as e:
            print(f"✗ 保存报告失败: {str(e)}")
            return ""
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始LLM API性能测试...")
        print("=" * 50)
        
        # 1. 基础连接测试
        if not self.test_basic_connection():
            print("\n基础连接测试失败，跳过后续测试")
            return
        
        # 2. 响应时间测试
        self.test_response_times(5)
        
        # 3. 并发请求测试
        asyncio.run(self.test_concurrent_requests(3))
        
        # 4. 错误处理测试
        self.test_error_handling()
        
        # 5. 成本估算
        self.estimate_costs()
        
        # 6. 生成报告
        self.generate_report()
        
        print("\n=" * 50)
        print("LLM API性能测试完成！")

if __name__ == "__main__":
    tester = LLMPerformanceTester()
    tester.run_all_tests()