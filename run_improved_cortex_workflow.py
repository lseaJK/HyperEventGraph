#!/usr/bin/env python3
"""
改进的Cortex工作流 - 支持可配置的分层聚类
"""

import os
import requests
import json
import uuid
import argparse
from pathlib import Path
import sys
from typing import List, Dict

# Add project root to sys.path
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

def intelligent_clustering(events_to_cluster, batch_size=200, cluster_ratio=0.3):
    """
    智能聚类逻辑 - 基于事件类型和时间进行分组
    
    Args:
        events_to_cluster: 待聚类的事件列表
        batch_size: 每个批次的大小
        cluster_ratio: 聚类比例（批次大小 * cluster_ratio = 目标故事数量）
    """
    print(f"📊 使用智能聚类策略，批次大小: {batch_size}, 聚类比例: {cluster_ratio}")
    
    # 第一步：按事件类型预分组
    type_groups = {}
    for event in events_to_cluster:
        event_type = event.get('assigned_event_type', 'Other')
        if event_type not in type_groups:
            type_groups[event_type] = []
        type_groups[event_type].append(event)
    
    print(f"📋 预分组结果: {len(type_groups)} 个事件类型")
    for event_type, events in type_groups.items():
        print(f"  - {event_type}: {len(events)} 个事件")
    
    # 第二步：在每个类型组内进行批次处理
    all_batches = []
    batch_id = 0
    
    for event_type, events in type_groups.items():
        print(f"\n处理事件类型: {event_type} ({len(events)} 个事件)")
        
        # 将事件分成批次
        for i in range(0, len(events), batch_size):
            batch_events = events[i:i+batch_size]
            batch_info = {
                'batch_id': batch_id,
                'event_type': event_type,
                'events': batch_events,
                'target_stories': max(1, int(len(batch_events) * cluster_ratio))
            }
            all_batches.append(batch_info)
            print(f"  📦 批次 {batch_id}: {len(batch_events)} 个事件 → 目标 {batch_info['target_stories']} 个故事")
            batch_id += 1
    
    return all_batches

def process_batch_with_llm(batch_events, target_stories, event_type):
    """
    使用LLM对批次内的事件进行智能聚类
    """
    if len(batch_events) <= target_stories:
        # 如果事件数量少于目标故事数，每个事件独立成故事
        return [[event] for event in batch_events]
    
    # 准备事件摘要用于LLM分析
    event_summaries = []
    for i, event in enumerate(batch_events):
        summary = {
            'index': i,
            'text': event['source_text'][:200],
            'type': event.get('assigned_event_type', 'Unknown'),
            'entities': event.get('involved_entities', '[]')
        }
        event_summaries.append(summary)
    
    # 构建LLM提示词
    events_text = "\n".join([
        f"{i}. {summary['text']}" 
        for i, summary in enumerate(event_summaries)
    ])
    
    prompt = f"""
请将以下{len(batch_events)}个{event_type}类型的事件分成{target_stories}个相关的故事组。
每个故事组应该包含逻辑相关、主题相似或时间相近的事件。

事件列表：
{events_text}

请返回JSON格式的分组结果，格式如下：
{{
  "groups": [
    {{"story_id": 1, "event_indices": [0, 1, 5], "reason": "这些事件都涉及同一家公司的业务变化"}},
    {{"story_id": 2, "event_indices": [2, 3], "reason": "这些事件都是行业趋势相关"}}
  ]
}}

确保所有事件索引（0-{len(batch_events)-1}）都被分配到某个组中。
"""
    
    try:
        response = direct_llm_call(prompt)
        # 尝试解析JSON
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            groups = result.get('groups', [])
            
            # 验证分组结果
            story_groups = []
            used_indices = set()
            
            for group in groups:
                event_indices = group.get('event_indices', [])
                valid_indices = [i for i in event_indices if 0 <= i < len(batch_events) and i not in used_indices]
                if valid_indices:
                    story_group = [batch_events[i] for i in valid_indices]
                    story_groups.append(story_group)
                    used_indices.update(valid_indices)
            
            # 处理未分配的事件
            unassigned_indices = set(range(len(batch_events))) - used_indices
            for idx in unassigned_indices:
                story_groups.append([batch_events[idx]])
            
            return story_groups
        
    except Exception as e:
        print(f"⚠️ LLM聚类失败，使用简单策略: {e}")
    
    # 回退到简单聚类策略
    simple_groups = []
    events_per_group = max(1, len(batch_events) // target_stories)
    
    for i in range(0, len(batch_events), events_per_group):
        group = batch_events[i:i+events_per_group]
        simple_groups.append(group)
    
    return simple_groups

def run_improved_cortex_workflow(batch_size=200, cluster_ratio=0.3):
    """改进的Cortex工作流主函数"""
    print(f"\n--- Running Improved Cortex Workflow ---")
    print(f"📊 参数设置: 批次大小={batch_size}, 聚类比例={cluster_ratio}")
    
    # 0. Load configuration first
    config_path = project_root / "config.yaml"
    load_config(config_path)
    print("✅ Configuration loaded successfully")
    
    # 1. Initialization
    config = get_config()
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)

    # 2. Fetch pending events
    print("Fetching events pending clustering from the database...")
    events_to_cluster = db_manager.get_records_by_status_as_df('pending_clustering').to_dict('records')
    
    if not events_to_cluster:
        print("No events found pending clustering. Workflow complete.")
        return

    print(f"Found {len(events_to_cluster)} events to process.")

    # 3. Perform intelligent clustering
    print("Performing intelligent clustering...")
    batches = intelligent_clustering(events_to_cluster, batch_size, cluster_ratio)
    
    # 4. Process each batch
    all_stories = []
    processed_events = 0
    
    for batch_info in batches:
        batch_id = batch_info['batch_id']
        event_type = batch_info['event_type']
        batch_events = batch_info['events']
        target_stories = batch_info['target_stories']
        
        print(f"\n🔄 处理批次 {batch_id} ({event_type}): {len(batch_events)} 个事件 → {target_stories} 个故事")
        
        # 使用LLM进行批次内聚类
        story_groups = process_batch_with_llm(batch_events, target_stories, event_type)
        
        # 为每个故事组创建故事记录
        for group_idx, story_events in enumerate(story_groups):
            try:
                story_id = f"story_{uuid.uuid4().hex[:8]}"
                
                # 生成故事摘要
                story_texts = [event['source_text'][:150] for event in story_events]
                combined_text = " | ".join(story_texts)
                
                prompt = f"""
请为以下{len(story_events)}个相关的{event_type}事件生成一个简短的故事摘要（1-2句话）：

{combined_text}

请直接回复摘要内容，突出事件的共同主题和关键信息。
"""
                
                summary = direct_llm_call(prompt)
                
                # 创建故事记录
                story = {
                    'story_id': story_id,
                    'event_ids': [event['id'] for event in story_events],
                    'summary': summary[:200],
                    'event_type': event_type,
                    'batch_id': batch_id
                }
                all_stories.append(story)
                processed_events += len(story_events)
                
                print(f"  📝 故事 {story_id}: {len(story_events)} 个事件")
                print(f"     摘要: {summary[:80]}...")
                
            except Exception as e:
                print(f"  ❌ 故事生成失败: {e}")
                continue

    # 5. Update database with story information
    if not all_stories:
        print("\nNo stories were generated. No database updates to perform.")
    else:
        print(f"\n📊 生成统计: {len(all_stories)} 个故事，覆盖 {processed_events} 个事件")
        print("Updating database...")
        
        successful_updates = 0
        for i, story in enumerate(all_stories):
            story_id = story['story_id']
            event_ids_in_story = story['event_ids']
            
            try:
                db_manager.update_story_info(event_ids_in_story, story_id, 'pending_relationship_analysis')
                successful_updates += 1
                if i % 10 == 0:  # 每10个故事显示一次进度
                    print(f"  ✅ 已更新 {i+1}/{len(all_stories)} 个故事")
            except Exception as e:
                print(f"  ❌ 故事 {story_id} 更新失败: {e}")
        
        print(f"\n✅ Database update完成: {successful_updates}/{len(all_stories)} 故事成功更新")

    print("\n--- Improved Cortex Workflow Finished ---")
    print("\n--- 聚类统计 ---")
    print(f"总事件数: {len(events_to_cluster)}")
    print(f"成功处理: {processed_events}")
    print(f"生成故事: {len(all_stories)}")
    print(f"平均每故事事件数: {processed_events / len(all_stories) if all_stories else 0:.1f}")
    print("--------------------------\n")

def main():
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="改进的Cortex聚类工作流")
    parser.add_argument("--batch_size", type=int, default=200, 
                       help="每个批次的大小 (默认: 200)")
    parser.add_argument("--cluster_ratio", type=float, default=0.3,
                       help="聚类比例，控制故事密度 (默认: 0.3)")
    
    args = parser.parse_args()
    
    print("Initializing improved Cortex workflow...")
    try:
        run_improved_cortex_workflow(args.batch_size, args.cluster_ratio)
        print("🎉 改进版Cortex工作流完成!")
    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
