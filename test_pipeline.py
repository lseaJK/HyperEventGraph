#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据流管道的基本功能
"""

import asyncio
import sys
import os
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.core.workflow_controller import WorkflowController, PipelineConfig

async def test_pipeline():
    """测试数据流管道"""
    print("🚀 开始测试数据流管道...")
    
    # 配置
    config = PipelineConfig(
        chroma_config={"host": "localhost", "port": 8000},
        neo4j_config={"uri": "bolt://localhost:7687", "user": "neo4j", "password": "neo123456"},
        llm_config={
            "provider": "deepseek",
            "api_key": os.getenv("DEEPSEEK_API_KEY"),
            "model_name": "deepseek-chat",
            "base_url": "https://api.deepseek.com"
        },
        batch_size=10,
        max_workers=2,
        enable_monitoring=True,
        output_path="./test_output"
    )
    
    # 创建工作流控制器
    controller = WorkflowController(config)
    
    try:
        # 启动监控
        await controller.start_monitoring()
        print("✅ 监控已启动")
        
        # 测试文本
        test_text = """
        2024年1月15日，腾讯公司宣布与华为公司达成战略合作协议，双方将在云计算和人工智能领域展开深度合作。
        此次合作预计将推动两家公司在技术创新方面的发展，并为用户提供更优质的服务体验。
        腾讯CEO马化腾表示，这次合作标志着公司在AI领域的重要里程碑。
        """
        
        print(f"📝 测试文本长度: {len(test_text)} 字符")
        
        # 执行流水线
        print("🔄 开始执行流水线...")
        result = await controller.execute_pipeline(
            pipeline_id="test_pipeline_001",
            input_data=test_text
        )
        
        # 输出结果
        print(f"\n📊 流水线执行结果:")
        print(f"  状态: {result.status.value}")
        print(f"  执行时间: {result.total_execution_time:.2f}秒")
        print(f"  处理项目数: {result.processed_items}")
        print(f"  错误数量: {result.error_count}")
        
        # 显示各阶段结果
        print(f"\n📋 各阶段执行情况:")
        for stage_result in result.stage_results:
            status_emoji = "✅" if stage_result.status.value == "completed" else "❌"
            print(f"  {status_emoji} {stage_result.stage.value}: {stage_result.execution_time:.2f}秒")
            if stage_result.error:
                print(f"    错误: {stage_result.error}")
        
        # 获取统计信息
        stats = controller.get_statistics()
        print(f"\n📈 系统统计信息:")
        print(f"  总流水线数: {stats['total_pipelines']}")
        print(f"  成功流水线数: {stats['successful_pipelines']}")
        print(f"  失败流水线数: {stats['failed_pipelines']}")
        print(f"  平均执行时间: {stats['avg_execution_time']:.2f}秒")
        
        return result.status.value == "completed"
        
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {e}")
        return False
        
    finally:
        # 关闭控制器
        await controller.shutdown()
        print("🔒 工作流控制器已关闭")

if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(test_pipeline())
    
    if success:
        print("\n🎉 数据流管道测试成功！")
        exit(0)
    else:
        print("\n💥 数据流管道测试失败！")
        exit(1)