# run_cortex_workflow.py
"""
修改版Cortex工作流 - 使用直接API调用而不是LLMClient
基于temp_cortex.py的成功实现
"""

import os
import requests
import json
import uuid
import asyncio
from pathlib import Path
import sys

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

def simple_clustering(events_to_cluster):
    """简化的聚类逻辑 - 基于事件类型进行分组"""
    clusters = {}
    cluster_assignments = {}
    
    for event in events_to_cluster:
        event_type = event.get('assigned_event_type', 'Other')
        
        if event_type not in clusters:
            clusters[event_type] = len(clusters)
        
        cluster_id = clusters[event_type]
        cluster_assignments[event['id']] = cluster_id
    
    stats = {
        'total_events_processed': len(events_to_cluster),
        'entity_parsing_success': len(events_to_cluster),
        'entity_parsing_warnings': 0,
        'clusters_found': len(clusters),
        'noise_points': 0
    }
    
    return cluster_assignments, stats

def run_cortex_workflow():
    """修改版Cortex工作流主函数"""
    print("\n--- Running Modified Cortex Workflow ---")
    
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

    # 3. Perform simplified clustering
    print("Performing simplified clustering based on event types...")
    cluster_assignments, stats = simple_clustering(events_to_cluster)
    
    # Update database with cluster results
    print("Updating database with cluster assignments...")
    clustered_events = []
    for event_id, cluster_id in cluster_assignments.items():
        # All events are assigned to clusters (no noise in simplified version)
        db_manager.update_cluster_info(event_id, cluster_id, 'pending_refinement')
        # Find the original event dict to pass to the next stage
        event_data = next((event for event in events_to_cluster if event['id'] == event_id), None)
        if event_data:
            event_data['cluster_id'] = cluster_id
            clustered_events.append(event_data)
    
    print(f"{len(clustered_events)} events assigned to clusters.")

    # Group events by cluster_id for the refinement stage
    clusters = {}
    for event in clustered_events:
        cluster_id = event['cluster_id']
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(event)

    print(f"Grouped events into {len(clusters)} coarse clusters for refinement.")

    # 4. Simplified refinement - create stories using direct API calls
    all_stories = []
    processed_events = 0
    
    if not clusters:
        print("No clusters to refine. Skipping refinement stage.")
    else:
        for cluster_id, events_in_cluster in clusters.items():
            print(f"\nProcessing Cluster #{cluster_id} with {len(events_in_cluster)} events...")
            
            # Process events in batches to avoid API limits
            batch_size = 10
            for i in range(0, len(events_in_cluster), batch_size):
                batch_events = events_in_cluster[i:i+batch_size]
                
                try:
                    # Create story for this batch
                    story_id = f"story_{uuid.uuid4().hex[:8]}"
                    
                    # Generate summary for the batch
                    batch_texts = [event['source_text'][:200] for event in batch_events]
                    combined_text = " | ".join(batch_texts)
                    
                    prompt = f"""
请为以下相关事件生成一个简短的故事摘要（1-2句话）：

事件内容：{combined_text}

请直接回复摘要内容，不要包含其他解释。
"""
                    
                    summary = direct_llm_call(prompt)
                    print(f"📝 批次摘要: {summary[:100]}...")
                    
                    # Create story record
                    story = {
                        'story_id': story_id,
                        'event_ids': [event['id'] for event in batch_events],
                        'summary': summary[:200]
                    }
                    all_stories.append(story)
                    processed_events += len(batch_events)
                    
                    print(f"✅ 批次处理完成，故事ID: {story_id}, 事件数: {len(batch_events)}")
                    
                except Exception as e:
                    print(f"❌ 批次处理失败: {e}")
                    continue

    # 5. Update database with story information
    if not all_stories:
        print("\nNo stories were generated. No database updates to perform.")
    else:
        print(f"\nGenerated a total of {len(all_stories)} stories. Updating database...")
        successful_updates = 0
        for i, story in enumerate(all_stories):
            story_id = story['story_id']
            event_ids_in_story = story['event_ids']
            
            print(f"\n更新故事 {i+1}/{len(all_stories)}: {story_id}")
            print(f"  包含事件数: {len(event_ids_in_story)}")
            print(f"  事件ID示例: {event_ids_in_story[:3] if len(event_ids_in_story) >= 3 else event_ids_in_story}")
            
            # Update all events in the story with the new story_id and set status
            # for the next stage in the pipeline.
            try:
                db_manager.update_story_info(event_ids_in_story, story_id, 'pending_relationship_analysis')
                successful_updates += 1
                print(f"  ✅ 成功更新")
            except Exception as e:
                print(f"  ❌ 更新失败: {e}")
        
        print(f"\nDatabase update完成: {successful_updates}/{len(all_stories)} 故事成功更新")
        print("Database updated with story information.")

    print("\n--- Modified Cortex Workflow Finished ---")
    print("\n--- Clustering Summary ---")
    print(f"Total Events Processed: {stats['total_events_processed']}")
    print(f"  - Successfully Processed: {processed_events}")
    print(f"  - Stories Generated: {len(all_stories)}")
    print(f"Clusters Found: {stats['clusters_found']}")
    print(f"Noise Points (unclustered): {stats['noise_points']}")
    print("--------------------------\n")

def main_standalone():
    """Entry point for standalone execution."""
    print("Initializing modified Cortex workflow...")
    try:
        run_cortex_workflow()
        print("🎉 修改版Cortex工作流完成!")
    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main_standalone()
