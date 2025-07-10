import asyncio
import json
import os
from typing import List, Dict, Any
from datetime import datetime
from deepseek_extractor import DeepSeekEventExtractor, extract_events_from_text, extract_multi_events_from_text

# 测试数据
TEST_TEXTS = {
    "financial_merger": """
    2024年1月15日，腾讯控股有限公司宣布以120亿美元的价格收购字节跳动旗下的TikTok业务。
    此次并购交易预计将在2024年第二季度完成，收购完成后，腾讯将获得TikTok在全球的运营权。
    腾讯CEO马化腾表示，此次收购将大幅提升公司在短视频领域的竞争力。
    """,
    
    "financial_investment": """
    小米集团今日宣布完成C轮融资，本轮融资金额达到50亿人民币，由红杉资本中国基金领投，
    IDG资本、晨兴资本等知名投资机构跟投。本轮融资将主要用于AI技术研发和海外市场拓展。
    小米创始人雷军表示，此次融资将加速公司在人工智能领域的布局。
    """,
    
    "circuit_breakthrough": """
    中芯国际今日宣布成功研发出7纳米制程工艺技术，这一突破性技术将大幅提升芯片性能，
    降低功耗30%以上。该技术主要应用于高端智能手机和服务器芯片领域。
    中芯国际技术总监表示，这一技术突破标志着中国在半导体制造领域达到了国际先进水平。
    """,
    
    "multi_events": """
    2024年科技行业重大事件回顾：
    1. 华为与中科院达成战略合作协议，共同研发6G通信技术，合作期限为5年。
    2. 比亚迪宣布投资200亿元扩建电池产能，新工厂预计2025年投产，年产能将达到100GWh。
    3. 阿里巴巴完成对优酷的全资收购，交易金额达到80亿美元。
    4. 台积电发布3纳米制程技术，性能提升15%，功耗降低25%。
    """
}

class DeepSeekExtractorTester:
    """
    DeepSeek事件抽取器测试类
    """
    
    def __init__(self):
        self.extractor = None
        self.test_results = []
    
    async def setup(self):
        """
        初始化测试环境
        """
        try:
            self.extractor = DeepSeekEventExtractor()
            print("✅ DeepSeek事件抽取器初始化成功")
            print(f"支持的领域: {self.extractor.get_supported_domains()}")
            return True
        except Exception as e:
            print(f"❌ 初始化失败: {str(e)}")
            print("请确保已设置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")
            return False
    
    async def test_single_event_extraction(self):
        """
        测试单事件抽取功能
        """
        print("\n=== 测试单事件抽取功能 ===")
        
        test_cases = [
            ("financial", "company_merger_and_acquisition", TEST_TEXTS["financial_merger"]),
            ("financial", "investment_and_financing", TEST_TEXTS["financial_investment"]),
            ("circuit", "technological_breakthrough", TEST_TEXTS["circuit_breakthrough"])
        ]
        
        for domain, event_type, text in test_cases:
            try:
                print(f"\n测试 {domain} - {event_type}:")
                print(f"输入文本: {text[:100]}...")
                
                result = await self.extractor.extract_single_event(
                    text=text,
                    domain=domain,
                    event_type=event_type,
                    metadata={"test_case": f"{domain}_{event_type}"}
                )
                
                # 验证结果
                is_valid = await self.extractor.validate_extraction_result(result, domain, event_type)
                
                print(f"抽取状态: {result['metadata'].get('extraction_status', 'unknown')}")
                print(f"置信度: {result['metadata'].get('confidence_score', 0)}")
                print(f"验证结果: {'✅ 通过' if is_valid else '❌ 失败'}")
                
                if result['event_data']:
                    print(f"抽取的事件数据: {json.dumps(result['event_data'], ensure_ascii=False, indent=2)}")
                
                self.test_results.append({
                    "test_type": "single_event",
                    "domain": domain,
                    "event_type": event_type,
                    "success": result['metadata'].get('extraction_status') == 'success',
                    "valid": is_valid,
                    "confidence": result['metadata'].get('confidence_score', 0)
                })
                
            except Exception as e:
                print(f"❌ 测试失败: {str(e)}")
                self.test_results.append({
                    "test_type": "single_event",
                    "domain": domain,
                    "event_type": event_type,
                    "success": False,
                    "valid": False,
                    "error": str(e)
                })
    
    async def test_multi_event_extraction(self):
        """
        测试多事件抽取功能
        """
        print("\n=== 测试多事件抽取功能 ===")
        
        try:
            text = TEST_TEXTS["multi_events"]
            print(f"输入文本: {text[:200]}...")
            
            results = await self.extractor.extract_multi_events(
                text=text,
                target_domains=["financial", "circuit"],
                metadata={"test_case": "multi_events"}
            )
            
            print(f"抽取到 {len(results)} 个事件:")
            
            for i, result in enumerate(results):
                print(f"\n事件 {i+1}:")
                print(f"  领域: {result['metadata'].get('domain', 'unknown')}")
                print(f"  类型: {result['metadata'].get('event_type', 'unknown')}")
                print(f"  状态: {result['metadata'].get('extraction_status', 'unknown')}")
                print(f"  置信度: {result['metadata'].get('confidence_score', 0)}")
                
                if result['event_data']:
                    print(f"  数据: {json.dumps(result['event_data'], ensure_ascii=False, indent=4)}")
            
            self.test_results.append({
                "test_type": "multi_event",
                "events_found": len(results),
                "success": len(results) > 0
            })
            
        except Exception as e:
            print(f"❌ 多事件抽取测试失败: {str(e)}")
            self.test_results.append({
                "test_type": "multi_event",
                "success": False,
                "error": str(e)
            })
    
    async def test_batch_processing(self):
        """
        测试批量处理功能
        """
        print("\n=== 测试批量处理功能 ===")
        
        try:
            texts = [
                TEST_TEXTS["financial_merger"],
                TEST_TEXTS["financial_investment"]
            ]
            
            metadata_list = [
                {"source": "test_batch_1", "batch_id": "batch_001"},
                {"source": "test_batch_2", "batch_id": "batch_001"}
            ]
            
            print(f"批量处理 {len(texts)} 个文本...")
            
            results = await self.extractor.batch_extract(
                texts=texts,
                domain="financial",
                event_type="company_merger_and_acquisition",
                batch_size=2,
                metadata_list=metadata_list
            )
            
            print(f"批量处理完成，共处理 {len(results)} 个结果:")
            
            success_count = 0
            for i, result in enumerate(results):
                status = result['metadata'].get('extraction_status', 'unknown')
                print(f"  文本 {i+1}: {status}")
                if status == 'success':
                    success_count += 1
            
            print(f"成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
            
            self.test_results.append({
                "test_type": "batch_processing",
                "total_texts": len(texts),
                "success_count": success_count,
                "success_rate": success_count/len(results)
            })
            
        except Exception as e:
            print(f"❌ 批量处理测试失败: {str(e)}")
            self.test_results.append({
                "test_type": "batch_processing",
                "success": False,
                "error": str(e)
            })
    
    async def test_convenience_functions(self):
        """
        测试便捷函数
        """
        print("\n=== 测试便捷函数 ===")
        
        try:
            # 测试单事件便捷函数
            print("测试单事件便捷函数...")
            result = await extract_events_from_text(
                text=TEST_TEXTS["financial_merger"],
                domain="financial",
                event_type="company_merger_and_acquisition"
            )
            print(f"单事件便捷函数结果: {result['metadata'].get('extraction_status', 'unknown')}")
            
            # 测试多事件便捷函数
            print("测试多事件便捷函数...")
            results = await extract_multi_events_from_text(
                text=TEST_TEXTS["multi_events"],
                target_domains=["financial", "circuit"]
            )
            print(f"多事件便捷函数结果: 抽取到 {len(results)} 个事件")
            
            self.test_results.append({
                "test_type": "convenience_functions",
                "single_event_success": result['metadata'].get('extraction_status') == 'success',
                "multi_event_count": len(results)
            })
            
        except Exception as e:
            print(f"❌ 便捷函数测试失败: {str(e)}")
            self.test_results.append({
                "test_type": "convenience_functions",
                "success": False,
                "error": str(e)
            })
    
    def generate_test_report(self):
        """
        生成测试报告
        """
        print("\n" + "="*50)
        print("测试报告")
        print("="*50)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results if result.get('success', False))
        
        print(f"总测试数: {total_tests}")
        print(f"成功测试数: {successful_tests}")
        print(f"成功率: {successful_tests/total_tests*100:.1f}%" if total_tests > 0 else "成功率: 0%")
        
        print("\n详细结果:")
        for i, result in enumerate(self.test_results, 1):
            print(f"{i}. {result['test_type']}: {'✅' if result.get('success', False) else '❌'}")
            if 'error' in result:
                print(f"   错误: {result['error']}")
        
        # 保存测试报告
        report_data = {
            "test_timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": successful_tests/total_tests if total_tests > 0 else 0,
            "detailed_results": self.test_results
        }
        
        report_file = f"deepseek_extractor_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n测试报告已保存到: {report_file}")
    
    async def run_all_tests(self):
        """
        运行所有测试
        """
        print("开始DeepSeek事件抽取器测试...")
        
        # 初始化
        if not await self.setup():
            return
        
        # 运行各项测试
        await self.test_single_event_extraction()
        await self.test_multi_event_extraction()
        await self.test_batch_processing()
        await self.test_convenience_functions()
        
        # 生成报告
        self.generate_test_report()

async def main():
    """
    主测试函数
    """
    # 检查API密钥
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ 未找到API密钥")
        print("请设置环境变量:")
        print("  export DEEPSEEK_API_KEY='your_api_key'")
        print("  或")
        print("  export OPENAI_API_KEY='your_deepseek_api_key'")
        return
    
    # 运行测试
    tester = DeepSeekExtractorTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())