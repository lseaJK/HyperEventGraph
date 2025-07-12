#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端流程测试：从文本输入到答案生成的完整流程
使用IC_data/filtered_data_demo.json数据进行测试
"""

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
import asyncio
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# 导入核心模块
from src.HyperGraphRAG_DS.hypergraphrag.hypergraphrag import HyperGraphRAG
from src.rag.query_processor import QueryProcessor
from src.rag.knowledge_retriever import KnowledgeRetriever
from src.rag.context_builder import ContextBuilder
from src.rag.answer_generator import AnswerGenerator
from src.core.graph_processor import GraphProcessor
from src.event_extraction.extractor import EventExtractor
from src.models.event_data_model import Event, EventType
from src.storage.neo4j_event_storage import Neo4jEventStorage as Neo4jStorage

class EndToEndFlowTest:
    """端到端流程测试类"""
    
    def __init__(self):
        """初始化测试环境"""
        self.data_file = "E:\\HyperEventGraph\\IC_data\\filtered_data_demo.json"
        self.test_results = []
        
        # 初始化核心组件
        print("🔧 初始化核心组件...")
        self.storage = Neo4jStorage()
        self.event_extractor = EventExtractor()
        self.graph_processor = GraphProcessor()
        self.hypergraph_rag = HyperGraphRAG()
        
        # 初始化RAG组件
        self.query_processor = QueryProcessor()
        self.knowledge_retriever = KnowledgeRetriever()
        self.context_builder = ContextBuilder()
        self.answer_generator = AnswerGenerator()
        
        print("✅ 组件初始化完成")
    
    def load_test_data(self) -> List[str]:
        """加载测试数据"""
        print(f"📂 加载测试数据: {self.data_file}")
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"✅ 成功加载 {len(data)} 条文本数据")
            return data
        except Exception as e:
            print(f"❌ 加载数据失败: {e}")
            return []
    
    async def extract_events_from_texts(self, texts: List[str]) -> List[Event]:
        """从文本中抽取事件"""
        print("🔍 开始事件抽取...")
        
        all_events = []
        
        for i, text in enumerate(texts):
            print(f"  处理文本 {i+1}/{len(texts)}...")
            
            try:
                # 使用事件抽取器抽取事件
                events = await self.event_extractor.extract_events(text)
                
                if events:
                    print(f"    ✅ 抽取到 {len(events)} 个事件")
                    all_events.extend(events)
                else:
                    print(f"    ⚠️ 未抽取到事件")
                    
            except Exception as e:
                print(f"    ❌ 事件抽取失败: {e}")
                continue
        
        print(f"✅ 事件抽取完成，共抽取 {len(all_events)} 个事件")
        return all_events
    
    async def build_knowledge_graph(self, events: List[Event]) -> bool:
        """构建知识图谱"""
        print("🏗️ 开始构建知识图谱...")
        
        try:
            # 清理现有数据（测试环境）
            print("  清理现有测试数据...")
            await self.storage.clear_all_data()
            
            # 存储事件到Neo4j
            print("  存储事件到Neo4j...")
            for event in events:
                await self.storage.store_event(event)
            
            # 使用图处理器建立关系
            print("  建立事件关系...")
            await self.graph_processor.process_events(events)
            
            print("✅ 知识图谱构建完成")
            return True
            
        except Exception as e:
            print(f"❌ 知识图谱构建失败: {e}")
            return False
    
    async def test_rag_queries(self) -> List[Dict[str, Any]]:
        """测试RAG查询功能"""
        print("🤖 开始RAG查询测试...")
        
        # 定义测试查询
        test_queries = [
            "台积电的价格策略是什么？",
            "晶圆代工行业的价格变化情况如何？",
            "日本对半导体出口管制的影响是什么？",
            "美国芯片巨头对出口限制有什么看法？",
            "先进封装市场的发展趋势如何？"
        ]
        
        results = []
        
        for i, query in enumerate(test_queries):
            print(f"\n  测试查询 {i+1}: {query}")
            
            try:
                # 1. 查询处理
                print("    1️⃣ 处理查询...")
                processed_query = await self.query_processor.process_query(query)
                print(f"      查询类型: {processed_query.query_type}")
                print(f"      实体: {processed_query.entities}")
                
                # 2. 知识检索
                print("    2️⃣ 检索知识...")
                retrieval_result = await self.knowledge_retriever.retrieve(processed_query)
                print(f"      检索到 {len(retrieval_result.events)} 个事件")
                print(f"      检索到 {len(retrieval_result.relations)} 个关系")
                
                # 3. 上下文构建
                print("    3️⃣ 构建上下文...")
                context_data = await self.context_builder.build_context(retrieval_result, processed_query)
                print(f"      上下文长度: {len(context_data.formatted_context)} 字符")
                
                # 4. 答案生成
                print("    4️⃣ 生成答案...")
                generated_answer = await self.answer_generator.generate_answer(context_data, processed_query)
                print(f"      答案长度: {len(generated_answer.answer)} 字符")
                
                # 记录结果
                result = {
                    "query": query,
                    "query_type": processed_query.query_type.value,
                    "entities_found": len(processed_query.entities),
                    "events_retrieved": len(retrieval_result.events),
                    "relations_retrieved": len(retrieval_result.relations),
                    "context_length": len(context_data.formatted_context),
                    "answer_length": len(generated_answer.answer),
                    "answer": generated_answer.answer[:200] + "..." if len(generated_answer.answer) > 200 else generated_answer.answer,
                    "success": True
                }
                
                results.append(result)
                print(f"    ✅ 查询成功完成")
                
            except Exception as e:
                print(f"    ❌ 查询失败: {e}")
                result = {
                    "query": query,
                    "success": False,
                    "error": str(e)
                }
                results.append(result)
        
        print(f"\n✅ RAG查询测试完成，成功 {sum(1 for r in results if r.get('success', False))}/{len(test_queries)} 个查询")
        return results
    
    def generate_test_report(self, events: List[Event], rag_results: List[Dict[str, Any]]) -> str:
        """生成测试报告"""
        report = f"""
# 端到端流程测试报告

## 测试时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 数据处理结果
- 输入文本数量: {len(self.load_test_data())}
- 抽取事件数量: {len(events)}
- 知识图谱构建: {'成功' if events else '失败'}

## 事件抽取详情
"""
        
        # 统计事件类型
        event_types = {}
        for event in events:
            event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        for event_type, count in event_types.items():
            report += f"- {event_type}: {count} 个\n"
        
        report += "\n## RAG查询测试结果\n"
        
        successful_queries = [r for r in rag_results if r.get('success', False)]
        failed_queries = [r for r in rag_results if not r.get('success', False)]
        
        report += f"- 总查询数: {len(rag_results)}\n"
        report += f"- 成功查询: {len(successful_queries)}\n"
        report += f"- 失败查询: {len(failed_queries)}\n"
        report += f"- 成功率: {len(successful_queries)/len(rag_results)*100:.1f}%\n\n"
        
        # 详细查询结果
        for i, result in enumerate(rag_results):
            report += f"### 查询 {i+1}: {result['query']}\n"
            if result.get('success', False):
                report += f"- 状态: ✅ 成功\n"
                report += f"- 查询类型: {result.get('query_type', 'N/A')}\n"
                report += f"- 检索事件: {result.get('events_retrieved', 0)} 个\n"
                report += f"- 检索关系: {result.get('relations_retrieved', 0)} 个\n"
                report += f"- 答案预览: {result.get('answer', 'N/A')}\n"
            else:
                report += f"- 状态: ❌ 失败\n"
                report += f"- 错误: {result.get('error', 'N/A')}\n"
            report += "\n"
        
        return report
    
    async def run_full_test(self):
        """运行完整的端到端测试"""
        print("🚀 开始端到端流程测试\n")
        
        try:
            # 1. 加载测试数据
            texts = self.load_test_data()
            if not texts:
                print("❌ 无法加载测试数据，测试终止")
                return
            
            # 2. 事件抽取
            events = await self.extract_events_from_texts(texts)
            if not events:
                print("❌ 未能抽取到任何事件，测试终止")
                return
            
            # 3. 构建知识图谱
            kg_success = await self.build_knowledge_graph(events)
            if not kg_success:
                print("❌ 知识图谱构建失败，测试终止")
                return
            
            # 4. RAG查询测试
            rag_results = await self.test_rag_queries()
            
            # 5. 生成测试报告
            report = self.generate_test_report(events, rag_results)
            
            # 保存报告
            report_file = "end_to_end_test_report.md"
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"\n📊 测试报告已保存到: {report_file}")
            print("\n" + "="*50)
            print("测试摘要:")
            print(f"- 处理文本: {len(texts)} 条")
            print(f"- 抽取事件: {len(events)} 个")
            print(f"- RAG查询: {len(rag_results)} 个")
            print(f"- 成功查询: {sum(1 for r in rag_results if r.get('success', False))} 个")
            print("="*50)
            
        except Exception as e:
            print(f"❌ 测试过程中发生错误: {e}")
            import traceback
            traceback.print_exc()

async def main():
    """主函数"""
    test = EndToEndFlowTest()
    await test.run_full_test()

if __name__ == "__main__":
    asyncio.run(main())