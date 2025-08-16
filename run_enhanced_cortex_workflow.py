#!/usr/bin/env python3
"""
Enhanced Cortex Workflow - 增强版智能聚类工作流
使用新的多维度聚类算法替代简单的基于类型的分组

特性：
1. 时间-实体-语义-类型多维度特征
2. DBSCAN + 后处理的层次化聚类
3. 智能故事摘要生成
4. 可配置的权重和参数
"""

import os
import json
import uuid
import asyncio
import requests
from pathlib import Path
import sys
from typing import List, Dict

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.agents.enhanced_cortex_agent import EnhancedCortexAgent

def direct_llm_call(prompt, model="deepseek-ai/DeepSeek-V2.5"):
    """直接调用API进行故事摘要生成"""
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

def enhanced_cortex_workflow():
    """增强版 Cortex 工作流主函数"""
    print("🧠 启动增强版智能聚类工作流...")
    
    # 1. 加载配置和初始化 (use explicit project-root config path to avoid ambiguity)
    config_path = project_root / "config.yaml"
    load_config(config_path)
    config = get_config()
    print(f"Configuration loaded from: {config_path}")
    db_manager = DatabaseManager(config['database']['path'])
    
    print("✅ 配置加载成功")
    # debug: show database path used
    db_path_debug = config.get('database', {}).get('path')
    print(f"Using database path: {db_path_debug}")
    
    # 2. 获取待聚类事件
    pending_events_df = db_manager.get_records_by_status_as_df('pending_clustering')
    
    if pending_events_df.empty:
        print("ℹ️ 没有待聚类的事件")
        return
    
    print(f"📊 发现 {len(pending_events_df)} 个待聚类事件")
    
    # 检查测试限制
    test_limit = os.getenv('TEST_LIMIT')
    if test_limit:
        try:
            limit = int(test_limit)
            if len(pending_events_df) > limit:
                pending_events_df = pending_events_df.head(limit)
                print(f"🧪 测试模式: 限制处理 {limit} 个事件")
        except ValueError:
            print("⚠️ TEST_LIMIT 环境变量无效，忽略限制")
    
    # 3. 初始化增强版 Cortex 代理
    cortex_agent = EnhancedCortexAgent()
    
    # 4. 准备事件数据
    events = []
    for _, row in pending_events_df.iterrows():
        event_data = {
            'id': row['id'],
            'source_text': row['source_text'],
            'assigned_event_type': row.get('assigned_event_type', ''),
            'structured_data': row.get('structured_data', ''),
            'involved_entities': row.get('involved_entities', ''),
            'event_date': '',  # 需要从 structured_data 中提取
        }
        
        # 从 structured_data 中提取日期
        if event_data['structured_data']:
            try:
                structured = json.loads(event_data['structured_data'])
                event_data['event_date'] = structured.get('event_date', '')
                event_data['micro_event_type'] = structured.get('micro_event_type', '')
            except:
                pass
        
        events.append(event_data)
    
    # 5. 执行智能聚类
    print("🔍 开始智能多维度聚类...")
    clusters = cortex_agent.intelligent_clustering(events)
    
    if not clusters:
        print("⚠️ 未发现任何聚类")
        return
    
    print(f"✅ 聚类完成，发现 {len(clusters)} 个故事簇")
    
    # 6. 为每个簇生成故事
    stories = []
    
    for i, cluster_indices in enumerate(clusters):
        print(f"\n--- 处理簇 #{i+1} ({len(cluster_indices)} 个事件) ---")
        
        # 生成故事ID
        story_id = f"story_{uuid.uuid4().hex[:8]}"
        
        # 生成增强故事摘要
        enhanced_summary = cortex_agent.generate_enhanced_story_summary(cluster_indices, events)
        print(f"📝 增强摘要: {enhanced_summary}")
        
        # 准备事件文本用于LLM摘要 - 限制大小避免API错误
        cluster_texts = []
        cluster_event_ids = []
        max_events_for_llm = 50  # 限制LLM处理的事件数量
        
        for idx in cluster_indices[:max_events_for_llm]:  # 只取前50个事件
            event = events[idx]
            cluster_event_ids.append(event['id'])
            
            # 构建事件描述
            structured_data = event.get('structured_data', '')
            if structured_data:
                try:
                    structured = json.loads(structured_data)
                    description = structured.get('description', '')
                    if description:
                        cluster_texts.append(f"事件{idx+1}: {description[:100]}...")  # 限制单个事件长度
                    else:
                        cluster_texts.append(f"事件{idx+1}: {event['source_text'][:80]}...")
                except:
                    cluster_texts.append(f"事件{idx+1}: {event['source_text'][:80]}...")
            else:
                cluster_texts.append(f"事件{idx+1}: {event['source_text'][:80]}...")
        
        # 所有事件ID都要更新，不只是用于LLM的前50个
        cluster_event_ids = [events[idx]['id'] for idx in cluster_indices]
        
        # 使用LLM生成故事摘要 - 添加大簇提示
        events_text = "\\n".join(cluster_texts)
        size_note = f" (注：此簇共{len(cluster_indices)}个事件，以下仅展示前{min(len(cluster_indices), max_events_for_llm)}个)" if len(cluster_indices) > max_events_for_llm else ""
        
        prompt = f"""请基于以下相关事件，生成一个连贯的故事摘要{size_note}：

{events_text}

要求：
1. 摘要应该突出事件之间的关联性和逻辑关系
2. 控制在150字以内
3. 使用中文
4. 重点关注因果关系、时间顺序、涉及实体

故事摘要："""
        
        try:
            llm_summary = direct_llm_call(prompt)
            print(f"📝 LLM摘要: {llm_summary[:100]}...")
        except Exception as e:
            print(f"⚠️ LLM摘要生成失败: {e}")
            llm_summary = enhanced_summary  # 使用增强摘要作为备用
        
        # 保存故事信息
        story_info = {
            'story_id': story_id,
            'event_ids': cluster_event_ids,
            'enhanced_summary': enhanced_summary,
            'llm_summary': llm_summary,
            'event_count': len(cluster_indices)
        }
        
        stories.append(story_info)
        print(f"✅ 故事 {story_id} 生成完成")
    
    # 7. 更新数据库
    print(f"\\n📊 开始更新数据库...")
    
    for i, story in enumerate(stories):
        print(f"\\n更新故事 {i+1}/{len(stories)}: {story['story_id']}")
        print(f"  包含事件数: {story['event_count']}")
        print(f"  事件ID示例: {story['event_ids'][:3]}")
        
        try:
            # 使用 DatabaseManager 的 update_story_info 方法
            db_manager.update_story_info(
                event_ids=story['event_ids'],
                story_id=story['story_id'],
                new_status='story_assigned'
            )
            print(f"  ✅ 成功更新")
        except Exception as e:
            print(f"  ❌ 更新失败: {e}")
    
    # 8. 最终统计
    print(f"\\n🎉 增强版Cortex工作流完成!")
    print(f"\\n--- 聚类统计 ---")
    print(f"总事件数: {len(events)}")
    print(f"生成故事数: {len(stories)}")
    print(f"平均每故事事件数: {len(events)/len(stories):.1f}")
    
    # 显示故事分布
    for i, story in enumerate(stories):
        print(f"故事 {i+1}: {story['event_count']} 个事件")
    
    return True

if __name__ == "__main__":
    try:
        success = enhanced_cortex_workflow()
        
        if success:
            print("\\n🎯 建议下一步:")
            print("1. 检查故事质量: python check_database_status.py")
            print("2. 运行关系分析: python run_relationship_analysis.py")
            print("3. 查看知识图谱: 在Neo4j Browser中探索")
        
    except KeyboardInterrupt:
        print("\\n⚠️ 用户中断操作")
    except Exception as e:
        print(f"\\n❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()
