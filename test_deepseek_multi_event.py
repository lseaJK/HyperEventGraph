import asyncio
import os
import json
import logging
from pathlib import Path
import sys

# 添加项目根目录到Python路径，以便导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.event_extraction.deepseek_extractor import DeepSeekEventExtractor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 测试数据 ---
# 从真实数据文件中加载一条或多条示例文本
SAMPLE_TEXTS = []
try:
    data_path = Path(__file__).parent / "IC_data/filtered_data_demo.json"
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # 只取前几条作为测试样本
    SAMPLE_TEXTS = data[:3]
    if not SAMPLE_TEXTS:
        logging.warning("未能从数据文件中加载示例文本，将使用默认文本。")
        SAMPLE_TEXTS = ["这是第一条测试新闻。", "这是第二条。"]
except Exception as e:
    logging.error(f"加载测试数据失败: {e}")
    SAMPLE_TEXTS = ["这是第一条测试新闻。", "这是第二条。"]


async def main():
    """
    主测试函数，用于隔离测试 DeepSeekEventExtractor 的多事件抽取功能。
    """
    print("--- 开始测试 DeepSeek 多事件抽取 ---")
    
    # 确保 API 密钥已设置
    if not os.getenv("DEEPSEEK_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        print("错误: 请设置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 环境变量。")
        return

    # 1. 初始化抽取器
    try:
        extractor = DeepSeekEventExtractor()
        # 明确设置要测试的模型
        extractor.model_name = "deepseek-reasoner"
        print(f"✅ 事件抽取器初始化成功，使用模型: {extractor.model_name}")
    except Exception as e:
        print(f"❌ 初始化事件抽取器失败: {e}")
        return

    # 2. 遍历示例文本并进行抽取
    for i, text in enumerate(SAMPLE_TEXTS, 1):
        print("\n" + "="*50)
        print(f"🔄 正在处理第 {i}/{len(SAMPLE_TEXTS)} 条文本...")
        print(f"文本内容 (前100字符): {text[:100]}...")
        
        try:
            # 调用多事件抽取方法
            result = await extractor.extract_multi_events(text)
            
            # 打印原始返回结果，以便调试
            print("\n--- 原始返回结果 ---")
            print(f"类型: {type(result)}")
            print(f"内容: {result}")
            print("--------------------")

            if result:
                print(f"✅ 抽取成功，共找到 {len(result)} 个事件。")
            else:
                print("⚠️ 抽取未返回任何事件。")

        except Exception as e:
            print(f"❌ 处理文本时发生严重错误: {e}")
            import traceback
            traceback.print_exc()
        
        print("="*50 + "\n")

    print("--- 测试结束 ---")

if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())