#!/usr/bin/env python3
"""
专门针对科创板数据的智能聚类系统
基于投资分析需求设计的多维度聚类策略
"""

import os
import requests
import json
import uuid
import argparse
import re
from pathlib import Path
import sys
from typing import List, Dict, Set
from collections import defaultdict
from datetime import datetime, timedelta

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
        "temperature": 0.3  # 降低温度以获得更一致的结果
    }
    
    response = requests.post(url, headers=headers, json=data, timeout=30)
    
    if response.status_code == 200:
        result = response.json()
        return result['choices'][0]['message']['content']
    else:
        raise Exception(f"API调用失败: {response.status_code} - {response.text}")

class CompanyExtractor:
    """公司名称提取器"""
    
    def __init__(self):
        # 常见的公司后缀
        self.company_suffixes = [
            '公司', '集团', '股份', '有限公司', '科技', '电子', '半导体', '微电子',
            '实业', '控股', '投资', '发展', '国际', '技术', '工业', '制造',
            'Corp', 'Inc', 'Ltd', 'Technology', 'Electronics', 'Semiconductor'
        ]
        
        # 排除的通用词
        self.exclude_words = {'中国', '全球', '国内', '海外', '市场', '行业', '产业'}
    
    def extract_companies(self, text: str) -> Set[str]:
        """从文本中提取公司名称"""
        companies = set()
        
        # 方法1：正则表达式匹配
        # 匹配中文公司名（2-10个汉字 + 公司后缀）
        pattern_cn = r'([一-龥]{2,10}(?:' + '|'.join(self.company_suffixes[:12]) + '))'
        matches_cn = re.findall(pattern_cn, text)
        companies.update(matches_cn)
        
        # 方法2：匹配英文公司名
        pattern_en = r'([A-Z][A-Za-z\s]{2,20}(?:' + '|'.join(self.company_suffixes[12:]) + '))'
        matches_en = re.findall(pattern_en, text)
        companies.update(matches_en)
        
        # 方法3：匹配股票代码相关的公司名
        pattern_stock = r'([一-龥A-Za-z]{2,10})[（(][\d]{6}[）)]'
        matches_stock = re.findall(pattern_stock, text)
        companies.update(matches_stock)
        
        # 过滤结果
        filtered_companies = set()
        for company in companies:
            if (len(company) >= 2 and 
                company not in self.exclude_words and
                not company.isdigit()):
                filtered_companies.add(company)
        
        return filtered_companies

class ThemeExtractor:
    """主题提取器"""
    
    def __init__(self):
        # 科创板相关的关键主题
        self.themes = {
            '芯片短缺': ['芯片短缺', '缺芯', '芯片供应', '芯片紧张', '半导体短缺'],
            '产能扩张': ['扩产', '产能', '新建产线', '投产', '量产', '开工建设'],
            '价格波动': ['涨价', '降价', '价格上涨', '价格下跌', '价格波动', '成本上升'],
            '业绩发布': ['净利润', '营收', '财报', '业绩', '年报', '季报', '半年报'],
            '技术突破': ['突破', '创新', '研发', '技术', '专利', '工艺', '制程'],
            '合作并购': ['合作', '并购', '收购', '投资', '战略合作', '合资'],
            '政策影响': ['政策', '监管', '政府', '补贴', '税收', '法规'],
            '供应链': ['供应链', '上游', '下游', '供应商', '客户', '订单'],
            '新产品发布': ['发布', '推出', '上市', '新品', '产品', '解决方案'],
            '市场变化': ['市场', '需求', '销售', '出货', '库存', '渠道']
        }
    
    def extract_themes(self, text: str) -> List[str]:
        """从文本中提取主题"""
        found_themes = []
        text_lower = text.lower()
        
        for theme, keywords in self.themes.items():
            if any(keyword in text for keyword in keywords):
                found_themes.append(theme)
        
        return found_themes

class SmartClustering:
    """智能聚类系统"""
    
    def __init__(self, clustering_mode='company'):
        self.company_extractor = CompanyExtractor()
        self.theme_extractor = ThemeExtractor()
        self.clustering_mode = clustering_mode
    
    def company_based_clustering(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """基于公司的聚类"""
        print("🏢 执行基于公司的聚类...")
        
        company_groups = defaultdict(list)
        
        for event in events:
            text = event.get('source_text', '')
            companies = self.company_extractor.extract_companies(text)
            
            if companies:
                # 使用第一个识别的公司作为主要公司
                main_company = list(companies)[0]
                company_groups[main_company].append(event)
            else:
                # 未识别到公司的事件放入通用组
                company_groups['其他公司'].append(event)
        
        print(f"📊 识别到 {len(company_groups)} 个公司分组")
        for company, events in list(company_groups.items())[:10]:  # 显示前10个
            print(f"  - {company}: {len(events)} 个事件")
        
        return dict(company_groups)
    
    def theme_based_clustering(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """基于主题的聚类"""
        print("🎯 执行基于主题的聚类...")
        
        theme_groups = defaultdict(list)
        
        for event in events:
            text = event.get('source_text', '')
            themes = self.theme_extractor.extract_themes(text)
            
            if themes:
                # 使用第一个识别的主题作为主要主题
                main_theme = themes[0]
                theme_groups[main_theme].append(event)
            else:
                # 未识别到主题的事件根据事件类型分组
                event_type = event.get('assigned_event_type', '其他')
                theme_groups[f"其他_{event_type}"].append(event)
        
        print(f"📊 识别到 {len(theme_groups)} 个主题分组")
        for theme, events in theme_groups.items():
            print(f"  - {theme}: {len(events)} 个事件")
        
        return dict(theme_groups)
    
    def hybrid_clustering(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """混合聚类：公司+主题"""
        print("🔄 执行混合聚类（公司+主题）...")
        
        hybrid_groups = defaultdict(list)
        
        for event in events:
            text = event.get('source_text', '')
            companies = self.company_extractor.extract_companies(text)
            themes = self.theme_extractor.extract_themes(text)
            
            # 构建复合键
            if companies and themes:
                company = list(companies)[0]
                theme = themes[0]
                key = f"{company}_{theme}"
            elif companies:
                company = list(companies)[0]
                key = f"{company}_综合事件"
            elif themes:
                theme = themes[0]
                key = f"行业_{theme}"
            else:
                event_type = event.get('assigned_event_type', '其他')
                key = f"其他_{event_type}"
            
            hybrid_groups[key].append(event)
        
        print(f"📊 识别到 {len(hybrid_groups)} 个混合分组")
        for key, events in list(hybrid_groups.items())[:10]:  # 显示前10个
            print(f"  - {key}: {len(events)} 个事件")
        
        return dict(hybrid_groups)
    
    def cluster_events(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        """根据模式执行聚类"""
        if self.clustering_mode == 'company':
            return self.company_based_clustering(events)
        elif self.clustering_mode == 'theme':
            return self.theme_based_clustering(events)
        elif self.clustering_mode == 'hybrid':
            return self.hybrid_clustering(events)
        else:
            raise ValueError(f"不支持的聚类模式: {self.clustering_mode}")

def process_cluster_with_refinement(group_name: str, events: List[Dict], max_story_size: int = 20) -> List[Dict]:
    """处理单个聚类组，如果事件过多则进一步细分"""
    stories = []
    
    if len(events) <= max_story_size:
        # 事件数量适中，直接创建一个故事
        story = create_story_from_events(group_name, events)
        stories.append(story)
    else:
        # 事件过多，需要进一步细分
        print(f"  📦 {group_name} 事件过多({len(events)})，进行细分...")
        
        # 按时间排序
        sorted_events = sorted(events, key=lambda x: x.get('last_updated', ''), reverse=True)
        
        # 分批处理
        for i in range(0, len(sorted_events), max_story_size):
            batch_events = sorted_events[i:i+max_story_size]
            batch_name = f"{group_name}_批次{i//max_story_size + 1}"
            story = create_story_from_events(batch_name, batch_events)
            stories.append(story)
    
    return stories

def create_story_from_events(group_name: str, events: List[Dict]) -> Dict:
    """从事件列表创建故事"""
    try:
        story_id = f"story_{uuid.uuid4().hex[:8]}"
        
        # 生成智能摘要
        if len(events) <= 3:
            # 事件较少，直接拼接
            texts = [event['source_text'][:100] for event in events]
            summary = " | ".join(texts)
        else:
            # 事件较多，使用LLM生成摘要
            texts = [f"{i+1}. {event['source_text'][:150]}" for i, event in enumerate(events[:5])]
            combined_text = "\n".join(texts)
            
            prompt = f"""
请为以下关于"{group_name}"的{len(events)}个相关事件生成一个简洁的投资分析摘要（2-3句话）：

{combined_text}

摘要应该：
1. 突出关键的投资信息和市场影响
2. 识别主要的风险或机会
3. 保持客观和专业的语调

请直接回复摘要内容：
"""
            
            try:
                summary = direct_llm_call(prompt)
            except:
                summary = f"{group_name}相关的{len(events)}个事件"
        
        return {
            'story_id': story_id,
            'event_ids': [event['id'] for event in events],
            'summary': summary[:300],  # 限制摘要长度
            'group_name': group_name,
            'event_count': len(events)
        }
        
    except Exception as e:
        print(f"❌ 创建故事失败: {e}")
        return None

def run_smart_clustering_workflow(clustering_mode='company', max_story_size=20):
    """智能聚类工作流主函数"""
    print(f"\n--- Running Smart Clustering Workflow ---")
    print(f"🎯 聚类模式: {clustering_mode}")
    print(f"📊 最大故事大小: {max_story_size}")
    
    # 0. Load configuration
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

    # 3. 执行智能聚类
    clusterer = SmartClustering(clustering_mode)
    cluster_groups = clusterer.cluster_events(events_to_cluster)
    
    # 4. 处理每个聚类组
    all_stories = []
    processed_events = 0
    
    print(f"\n🔄 处理 {len(cluster_groups)} 个聚类组...")
    
    for group_name, group_events in cluster_groups.items():
        print(f"\n📝 处理分组: {group_name} ({len(group_events)} 个事件)")
        
        # 处理单个聚类组
        stories = process_cluster_with_refinement(group_name, group_events, max_story_size)
        
        for story in stories:
            if story:
                all_stories.append(story)
                processed_events += story['event_count']
                print(f"  ✅ 故事 {story['story_id']}: {story['event_count']} 个事件")
                print(f"     摘要: {story['summary'][:80]}...")

    # 5. Update database with story information
    if not all_stories:
        print("\nNo stories were generated. No database updates to perform.")
    else:
        print(f"\n📊 聚类统计:")
        print(f"  总事件数: {len(events_to_cluster)}")
        print(f"  成功处理: {processed_events}")
        print(f"  生成故事: {len(all_stories)}")
        print(f"  平均每故事事件数: {processed_events / len(all_stories):.1f}")
        
        print("\nUpdating database...")
        successful_updates = 0
        
        for i, story in enumerate(all_stories):
            story_id = story['story_id']
            event_ids_in_story = story['event_ids']
            
            try:
                db_manager.update_story_info(event_ids_in_story, story_id, 'pending_relationship_analysis')
                successful_updates += 1
                
                if i % 20 == 0:  # 每20个故事显示一次进度
                    print(f"  ✅ 已更新 {i+1}/{len(all_stories)} 个故事")
                    
            except Exception as e:
                print(f"  ❌ 故事 {story_id} 更新失败: {e}")
        
        print(f"\n✅ Database update完成: {successful_updates}/{len(all_stories)} 故事成功更新")

    print("\n--- Smart Clustering Workflow Finished ---")

def main():
    """Entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="科创板智能聚类工作流")
    parser.add_argument("--mode", choices=['company', 'theme', 'hybrid'], default='company',
                       help="聚类模式 (默认: company)")
    parser.add_argument("--max_story_size", type=int, default=20,
                       help="单个故事的最大事件数 (默认: 20)")
    
    args = parser.parse_args()
    
    print("Initializing smart clustering workflow...")
    try:
        run_smart_clustering_workflow(args.mode, args.max_story_size)
        print("🎉 智能聚类工作流完成!")
    except Exception as e:
        print(f"❌ 工作流执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
