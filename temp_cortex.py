#!/usr/bin/env python3
"""
绕过LLMClient的临时Cortex运行脚本
"""
import os
import requests
import json
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager

def direct_llm_call(prompt, model="deepseek-ai/DeepSeek-V2.5"):
    """直接调用API，绕过项目的LLMClient"""
    api_key = os.getenv('SILICONFLOW_API_KEY')
    if not api_key:
        raise ValueError("需要SILICONFLOW_API_KEY环境变量")
    
    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        raise Exception(f"API调用失败: {response.status_code} - {response.text}")

def simple_event_clustering():
    """简化版事件聚类处理"""
    print("🚀 开始简化版Cortex处理\n")
    
    # 加载配置和数据库
    config_path = project_root / "config.yaml"
    load_config(config_path)
    config = get_config()
    
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)
    
    # 获取待聚类事件
    print("📊 获取待聚类事件...")
    events_df = db_manager.get_records_by_status_as_df('pending_clustering')
    
    if events_df.empty:
        print("❌ 没有找到待聚类事件")
        return
    
    print(f"✅ 找到 {len(events_df)} 条待聚类事件")
    
    # 处理小批量事件（避免一次性处理太多）
    batch_size = 5
    processed = 0
    
    for i in range(0, min(batch_size, len(events_df))):
        try:
            event = events_df.iloc[i]
            event_id = event['id']
            source_text = event['source_text'][:500]  # 截取前500字符
            
            print(f"\n🔄 处理事件 {i+1}/{batch_size}: {event_id[:8]}...")
            
            # 构建简单的故事总结prompt
            prompt = f"""
请为以下事件生成一个简短的故事摘要（1-2句话）：

事件内容：{source_text}

请直接回复摘要内容，不要包含其他解释。
"""
            
            # 调用API生成摘要
            summary = direct_llm_call(prompt)
            print(f"📝 摘要: {summary[:100]}...")
            
            # 生成故事ID并更新数据库
            import uuid
            story_id = f"story_{uuid.uuid4().hex[:8]}"
            
            # 更新数据库状态
            db_manager.update_story_info(event_id, story_id, summary[:200])
            db_manager.update_status(event_id, 'pending_relationship_analysis')
            
            processed += 1
            print(f"✅ 事件处理完成，故事ID: {story_id}")
            
        except Exception as e:
            print(f"❌ 事件处理失败: {e}")
            continue
    
    print(f"\n🎉 批量处理完成! 成功处理 {processed} 条事件")
    print("📈 这些事件已准备好进行关系分析")
    
    return processed

def main():
    try:
        processed_count = simple_event_clustering()
        
        if processed_count and processed_count > 0:
            print(f"\n✅ 临时Cortex处理成功!")
            print(f"📊 处理事件数: {processed_count}")
            print("🔄 下一步可以运行关系分析工作流")
        else:
            print("\n⚠️ 未处理任何事件")
            
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
