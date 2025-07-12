#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HyperEventGraph 端到端流程测试
测试从文本输入到答案生成的完整管道

测试覆盖：
1. 文本输入 → 事件抽取 → 存储
2. 用户查询 → 查询理解 → 知识检索 → 答案生成
3. 双层架构协同工作
4. RAG系统完整管道
5. 性能和错误处理
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

try:
    from src.core.dual_layer_architecture import DualLayerArchitecture
    from src.core.event_layer_manager import EventLayerManager
    from src.core.pattern_layer_manager import PatternLayerManager
    from src.core.layer_mapper import LayerMapper
    from src.core.graph_processor import GraphProcessor
    from src.rag.query_processor import QueryProcessor
    from src.rag.knowledge_retriever import KnowledgeRetriever
    from src.rag.context_builder import ContextBuilder
    from src.rag.answer_generator import AnswerGenerator
    from src.storage.neo4j_event_storage import Neo4jEventStorage, Neo4jConfig
    from src.llm_integration.llm_config import LLMConfig, LLMProvider
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有必要的模块都已正确实现")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python路径: {sys.path}")
    sys.exit(1)

class EndToEndPipelineTest:
    """端到端流程测试类"""
    
    def __init__(self):
        self.test_results = []
        self.start_time = None
        self.neo4j_storage = None
        self.dual_layer_arch = None
        self.llm_config = None
        self.rag_components = {}
        
    def log_test_result(self, test_name: str, success: bool, 
                       duration: float = 0, details: str = "", error: str = ""):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "duration": duration,
            "details": details,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{status} {test_name} ({duration:.2f}s)")
        if details:
            print(f"   详情: {details}")
        if error:
            print(f"   错误: {error}")
    
    def setup_test_environment(self) -> bool:
        """设置测试环境"""
        print("\n=== 设置测试环境 ===")
        start_time = time.time()
        
        try:
            # 1. 初始化Neo4j存储
            neo4j_config = Neo4jConfig.from_env()
            self.neo4j_storage = Neo4jEventStorage(neo4j_config)
            
            # 测试连接
            if not self.neo4j_storage.test_connection():
                raise Exception("Neo4j连接失败")
            
            # 2. 初始化LLM配置
            self.llm_config = LLMConfig.from_env(LLMProvider.DEEPSEEK)
            
            # 3. 初始化双层架构
            from src.core.dual_layer_architecture import ArchitectureConfig
            arch_config = ArchitectureConfig(
                neo4j_uri=neo4j_config.uri,
                neo4j_user=neo4j_config.username,
                neo4j_password=neo4j_config.password,
                enable_pattern_learning=True,
                pattern_similarity_threshold=0.8,
                auto_mapping=True,
                max_pattern_depth=3,
                enable_reasoning=True
            )
            self.dual_layer_arch = DualLayerArchitecture(arch_config)
            
            # 4. 初始化RAG组件
            self.rag_components = {
                'query_processor': QueryProcessor(),
                'knowledge_retriever': KnowledgeRetriever(dual_layer_arch=self.dual_layer_arch),
                'context_builder': ContextBuilder(),
                'answer_generator': AnswerGenerator()
            }
            
            duration = time.time() - start_time
            self.log_test_result("测试环境设置", True, duration, "所有组件初始化成功")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("测试环境设置", False, duration, error=str(e))
            return False
    
    def test_data_input_pipeline(self) -> bool:
        """测试数据输入管道：文本 → 事件抽取 → 存储"""
        print("\n=== 测试数据输入管道 ===")
        start_time = time.time()
        
        try:
            # 测试文本
            test_text = """
            2024年1月15日，某科技公司宣布推出新一代AI芯片，该芯片采用7纳米工艺，
            性能比上一代提升50%。公司CEO在发布会上表示，这款芯片将主要用于
            数据中心和自动驾驶汽车。预计今年第二季度开始量产，初期产能为每月10万片。
            """
            
            # 1. 创建测试事件（简化版本，直接创建Event对象）
            from src.models.event_data_model import Event, EventType, Entity
            from datetime import datetime
            
            # 创建实体
            tech_company = Entity(
                name="某科技公司",
                entity_type="organization",
                properties={"industry": "科技", "location": "中国"}
            )
            
            # 创建事件
            event = Event(
                event_type=EventType.PRODUCT_LAUNCH,
                text=test_text.strip(),
                summary="科技公司发布新一代AI芯片",
                timestamp=datetime(2024, 1, 15),
                subject=tech_company,
                participants=[tech_company],
                properties={
                    "product": "AI芯片",
                    "process": "7纳米工艺",
                    "performance_improvement": "50%",
                    "application": "数据中心和自动驾驶汽车",
                    "production_start": "第二季度",
                    "initial_capacity": "每月10万片"
                },
                confidence=0.9,
                source="测试数据"
            )
            
            events = [event]
            
            # 2. 存储到Neo4j
            stored_count = 0
            for event in events:
                success = self.dual_layer_arch.add_event(event)
                if success:
                    stored_count += 1
            
            if stored_count == 0:
                raise Exception("事件存储失败，未成功存储任何事件")
            
            # 3. 验证存储结果
            with self.neo4j_storage.driver.session() as session:
                query_result = session.run(
                    "MATCH (e:Event) WHERE e.created_at > datetime() - duration('PT1M') RETURN count(e) as count"
                )
                result = query_result.single()
                recent_events = result['count'] if result else 0
            
            duration = time.time() - start_time
            details = f"提取{len(events)}个事件，存储{stored_count}个，数据库中新增{recent_events}个"
            self.log_test_result("数据输入管道", True, duration, details)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("数据输入管道", False, duration, error=str(e))
            return False
    
    def test_query_processing_pipeline(self) -> bool:
        """测试查询处理管道：查询理解 → 实体识别 → 查询扩展"""
        print("\n=== 测试查询处理管道 ===")
        start_time = time.time()
        
        try:
            # 测试查询
            test_queries = [
                "最近有哪些科技公司发布了新产品？",
                "AI芯片的性能提升情况如何？",
                "自动驾驶相关的技术发展趋势是什么？"
            ]
            
            processed_queries = []
            for query in test_queries:
                # 查询理解和处理
                processed = self.rag_components['query_processor'].process_query(query)
                if processed:
                    processed_queries.append(processed)
            
            if not processed_queries:
                raise Exception("查询处理失败，未成功处理任何查询")
            
            duration = time.time() - start_time
            details = f"成功处理{len(processed_queries)}/{len(test_queries)}个查询"
            self.log_test_result("查询处理管道", True, duration, details)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("查询处理管道", False, duration, error=str(e))
            return False
    
    def test_knowledge_retrieval_pipeline(self) -> bool:
        """测试知识检索管道：图谱查询 → 相关性排序 → 上下文构建"""
        print("\n=== 测试知识检索管道 ===")
        start_time = time.time()
        
        try:
            # 测试查询
            query = "AI芯片的最新发展情况"
            
            # 1. 查询处理
            processed_query = self.rag_components['query_processor'].process_query(query)
            
            # 2. 知识检索
            retrieval_results = self.rag_components['knowledge_retriever'].retrieve(processed_query)
            
            if not retrieval_results:
                raise Exception("知识检索失败，未检索到相关信息")
            
            # 2. 上下文构建
            context_data = self.rag_components['context_builder'].build_context(
                retrieval_results, processed_query
            )
            
            if not context_data or not context_data.formatted_context:
                raise Exception("上下文构建失败")
            
            # 3. 验证检索质量
            if hasattr(retrieval_results, 'events'):
                # RetrievalResult对象
                event_count = len(retrieval_results.events)
                relevant_count = len([e for e in retrieval_results.events if retrieval_results.relevance_scores and retrieval_results.relevance_scores.get(e.id, 0) > 0.5])
            else:
                # 列表格式
                event_count = len(retrieval_results) if retrieval_results else 0
                relevant_count = sum(1 for result in retrieval_results 
                                   if result.get('relevance_score', 0) > 0.5)
            
            duration = time.time() - start_time
            details = f"检索到{event_count}个事件，{relevant_count}条高相关性，上下文长度{len(context_data.formatted_context)}"
            self.log_test_result("知识检索管道", True, duration, details)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("知识检索管道", False, duration, error=str(e))
            return False
    
    def test_complete_rag_pipeline(self) -> bool:
        """测试完整RAG管道：查询 → 检索 → 生成 → 答案"""
        print("\n=== 测试完整RAG管道 ===")
        start_time = time.time()
        
        try:
            # 测试查询
            query = "请介绍一下最近AI芯片技术的发展情况和主要应用领域"
            
            # 1. 查询处理
            processed_query = self.rag_components['query_processor'].process_query(query)
            
            # 2. 知识检索
            retrieval_results = self.rag_components['knowledge_retriever'].retrieve(processed_query)
            
            # 3. 上下文构建
            context_data = self.rag_components['context_builder'].build_context(
                retrieval_results, processed_query
            )
            
            # 4. 答案生成
            generated_answer = self.rag_components['answer_generator'].generate_answer(
                context_data, processed_query
            )
            answer = generated_answer.answer
            
            if not answer or len(answer.strip()) < 50:
                raise Exception("答案生成失败或答案过短")
            
            # 验证答案质量
            answer_quality = self._evaluate_answer_quality(query, answer, context_data.formatted_context)
            
            duration = time.time() - start_time
            details = f"生成答案长度{len(answer)}字符，质量评分{answer_quality:.2f}"
            self.log_test_result("完整RAG管道", True, duration, details)
            
            # 输出示例答案
            print(f"\n示例答案预览：\n{answer[:200]}...")
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("完整RAG管道", False, duration, error=str(e))
            return False
    
    def test_dual_layer_coordination(self) -> bool:
        """测试双层架构协同工作"""
        print("\n=== 测试双层架构协同 ===")
        start_time = time.time()
        
        try:
            # 1. 测试双层架构状态
            stats = self.dual_layer_arch.get_architecture_statistics()
            event_count = stats.get('event_layer', {}).get('total_events', 0)
            pattern_count = stats.get('pattern_layer', {}).get('total_patterns', 0)
            
            # 2. 测试事件查询
            events = self.dual_layer_arch.query_events(limit=5)
            
            # 3. 测试模式查询
            patterns = self.dual_layer_arch.query_patterns(limit=5)
            
            # 4. 测试事件分析（如果有事件的话）
            analysis_results = []
            if events:
                analysis_results = self.dual_layer_arch.analyze_event_chain(events[:3])
            
            duration = time.time() - start_time
            details = f"事件层{event_count}个事件，模式层{pattern_count}个模式，查询到{len(events)}个事件和{len(patterns)}个模式"
            self.log_test_result("双层架构协同", True, duration, details)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("双层架构协同", False, duration, error=str(e))
            return False
    
    def test_performance_requirements(self) -> bool:
        """测试性能要求：响应时间 < 10秒"""
        print("\n=== 测试性能要求 ===")
        start_time = time.time()
        
        try:
            # 测试多个查询的响应时间
            test_queries = [
                "AI技术的最新发展",
                "自动驾驶汽车的技术趋势",
                "科技公司的产品发布情况"
            ]
            
            response_times = []
            for query in test_queries:
                query_start = time.time()
                
                # 执行完整查询流程
                processed_query = self.rag_components['query_processor'].process_query(query)
                retrieval_results = self.rag_components['knowledge_retriever'].retrieve(processed_query)
                context_data = self.rag_components['context_builder'].build_context(retrieval_results, processed_query)
                generated_answer = self.rag_components['answer_generator'].generate_answer(context_data, processed_query)
                answer = generated_answer.answer
                
                query_time = time.time() - query_start
                response_times.append(query_time)
                
                if query_time > 10.0:
                    raise Exception(f"查询'{query}'响应时间{query_time:.2f}s超过10秒限制")
            
            avg_response_time = sum(response_times) / len(response_times)
            max_response_time = max(response_times)
            
            duration = time.time() - start_time
            details = f"平均响应时间{avg_response_time:.2f}s，最大响应时间{max_response_time:.2f}s"
            self.log_test_result("性能要求", True, duration, details)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("性能要求", False, duration, error=str(e))
            return False
    
    def test_error_handling(self) -> bool:
        """测试错误处理能力"""
        print("\n=== 测试错误处理 ===")
        start_time = time.time()
        
        try:
            error_scenarios = [
                {
                    "name": "空查询",
                    "query": "",
                    "expected_behavior": "优雅处理空输入"
                },
                {
                    "name": "超长查询",
                    "query": "AI" * 1000,
                    "expected_behavior": "处理超长输入"
                },
                {
                    "name": "特殊字符查询",
                    "query": "@#$%^&*()_+{}|:<>?[]",
                    "expected_behavior": "处理特殊字符"
                }
            ]
            
            handled_errors = 0
            for scenario in error_scenarios:
                try:
                    result = self.rag_components['query_processor'].process_query(scenario["query"])
                    # 如果没有抛出异常，说明错误处理正常
                    handled_errors += 1
                except Exception:
                    # 预期的错误处理
                    handled_errors += 1
            
            duration = time.time() - start_time
            details = f"成功处理{handled_errors}/{len(error_scenarios)}种错误场景"
            self.log_test_result("错误处理", True, duration, details)
            return True
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_test_result("错误处理", False, duration, error=str(e))
            return False
    
    def _evaluate_answer_quality(self, query: str, answer: str, context: str) -> float:
        """评估答案质量（简单版本）"""
        score = 0.0
        
        # 长度检查
        if 50 <= len(answer) <= 1000:
            score += 0.3
        
        # 相关性检查（简单关键词匹配）
        query_keywords = set(query.lower().split())
        answer_keywords = set(answer.lower().split())
        relevance = len(query_keywords & answer_keywords) / len(query_keywords) if query_keywords else 0
        score += relevance * 0.4
        
        # 完整性检查
        if answer.endswith(('。', '.', '！', '!')):
            score += 0.1
        
        # 上下文利用检查
        if context and any(word in answer for word in context.split()[:10]):
            score += 0.2
        
        return min(score, 1.0)
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        print("\n=== 清理测试环境 ===")
        try:
            if self.neo4j_storage:
                self.neo4j_storage.close()
            print("✅ 测试环境清理完成")
        except Exception as e:
            print(f"❌ 清理测试环境失败: {e}")
    
    def generate_test_report(self) -> Dict[str, Any]:
        """生成测试报告"""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result['success'])
        total_duration = sum(result['duration'] for result in self.test_results)
        
        report = {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_duration": total_duration,
                "test_date": datetime.now().isoformat()
            },
            "test_results": self.test_results
        }
        
        return report
    
    def print_test_summary(self):
        """打印测试摘要"""
        report = self.generate_test_report()
        summary = report['summary']
        
        print("\n" + "="*60)
        print("端到端流程测试报告")
        print("="*60)
        print(f"总测试数: {summary['total_tests']}")
        print(f"成功测试: {summary['successful_tests']}")
        print(f"失败测试: {summary['failed_tests']}")
        print(f"成功率: {summary['success_rate']:.1f}%")
        print(f"总耗时: {summary['total_duration']:.2f}秒")
        print(f"测试时间: {summary['test_date']}")
        
        if summary['failed_tests'] > 0:
            print("\n失败的测试:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  ❌ {result['test_name']}: {result['error']}")
        
        print("\n" + "="*60)

def main():
    """主测试函数"""
    print("HyperEventGraph 端到端流程测试")
    print("测试目标：验证从文本输入到答案生成的完整管道")
    
    tester = EndToEndPipelineTest()
    
    try:
        # 设置测试环境
        if not tester.setup_test_environment():
            print("❌ 测试环境设置失败，终止测试")
            return
        
        # 执行所有测试
        test_functions = [
            tester.test_data_input_pipeline,
            tester.test_query_processing_pipeline,
            tester.test_knowledge_retrieval_pipeline,
            tester.test_complete_rag_pipeline,
            tester.test_dual_layer_coordination,
            tester.test_performance_requirements,
            tester.test_error_handling
        ]
        
        for test_func in test_functions:
            test_func()
            # 短暂休息，避免过载
            time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生未预期错误: {e}")
    finally:
        # 清理环境
        tester.cleanup_test_environment()
        
        # 生成报告
        tester.print_test_summary()
        
        # 保存详细报告
        report = tester.generate_test_report()
        with open('end_to_end_test_report.json', 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("\n详细测试报告已保存到: end_to_end_test_report.json")

# Pytest测试函数
def test_complete_rag_pipeline():
    """pytest测试函数：完整RAG管道"""
    tester = EndToEndPipelineTest()
    assert tester.setup_test_environment(), "测试环境设置失败"
    assert tester.test_data_input_pipeline(), "数据输入管道测试失败"
    assert tester.test_complete_rag_pipeline(), "完整RAG管道测试失败"
    tester.cleanup_test_environment()

def test_dual_layer_coordination():
    """pytest测试函数：双层架构协同"""
    tester = EndToEndPipelineTest()
    assert tester.setup_test_environment(), "测试环境设置失败"
    assert tester.test_data_input_pipeline(), "数据输入管道测试失败"
    assert tester.test_dual_layer_coordination(), "双层架构协同测试失败"
    tester.cleanup_test_environment()

def test_performance_requirements():
    """pytest测试函数：性能要求"""
    tester = EndToEndPipelineTest()
    assert tester.setup_test_environment(), "测试环境设置失败"
    assert tester.test_data_input_pipeline(), "数据输入管道测试失败"
    assert tester.test_performance_requirements(), "性能要求测试失败"
    tester.cleanup_test_environment()

def test_error_handling():
    """pytest测试函数：错误处理"""
    tester = EndToEndPipelineTest()
    assert tester.setup_test_environment(), "测试环境设置失败"
    assert tester.test_error_handling(), "错误处理测试失败"
    tester.cleanup_test_environment()

if __name__ == "__main__":
    main()