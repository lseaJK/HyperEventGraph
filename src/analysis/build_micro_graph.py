

import json
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network
import os
import re

# --- 配置 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUT_FILE = os.path.join(BASE_DIR, 'docs', 'output', 'structured_events.jsonl')
OUTPUT_DIR = os.path.join(BASE_DIR, 'docs', 'output')
OUTPUT_VIS_FILE = os.path.join(OUTPUT_DIR, 'micro_knowledge_graph.html')

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 实体标准化 ---
# 简单的规则，用于演示，未来可以替换为更复杂的实体链接模块
ALIAS_MAPPING = {
    "华为技术有限公司": "华为",
    "苹果公司": "苹果",
    "三星电子": "三星",
    "腾讯控股": "腾讯",
    "阿里巴巴集团": "阿里巴巴"
}

def normalize_entity_name(name):
    """一个简单的实体名称标准化函数"""
    name = name.strip()
    return ALIAS_MAPPING.get(name, name)

# --- 主逻辑 ---
def load_data(file_path):
    """从jsonl文件加载数据"""
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"警告: 无法解析行: {line.strip()}")
    return data

def build_graph(events):
    """使用networkx构建图"""
    G = nx.Graph()
    
    print(f"开始构建图谱，共 {len(events)} 个事件...")
    
    for i, event in enumerate(events):
        # 1. 添加事件节点
        event_id = f"event_{i}"
        event_type = event.get('event_type', 'Unknown')
        event_description = event.get('description', '')
        
        G.add_node(
            event_id, 
            type='Event', 
            label=f"事件:{event_type}",
            title=event_description, # pyvis悬停时显示
            color='#FFC107' # 事件节点用黄色
        )
        
        # 2. 添加实体节点并创建关系
        entities = event.get('involved_entities', [])
        if not entities:
            continue
            
        for entity_info in entities:
            entity_name_raw = entity_info.get('name')
            if not entity_name_raw:
                continue
            
            # 标准化实体名称
            entity_name_normalized = normalize_entity_name(entity_name_raw)
            
            # 如果节点不存在，则添加
            if not G.has_node(entity_name_normalized):
                G.add_node(
                    entity_name_normalized,
                    type='Entity',
                    label=entity_name_normalized,
                    title=f"实体: {entity_name_normalized}",
                    color='#1E90FF' # 实体节点用蓝色
                )
            
            # 3. 添加从实体到事件的边
            G.add_edge(entity_name_normalized, event_id, label='participated_in')

    print("图谱构建完成。")
    print(f" - 节点数: {G.number_of_nodes()}")
    print(f" - 边数: {G.number_of_edges()}")
    return G

def visualize_with_pyvis(G, output_path):
    """使用pyvis进行交互式可视化"""
    if G.number_of_nodes() == 0:
        print("图中没有节点，无法进行可视化。")
        return
        
    print(f"正在生成交互式可视化文件到: {output_path}")
    
    net = Network(height='800px', width='100%', notebook=False, cdn_resources='remote', directed=False)
    net.from_nx(G)
    
    # 增加一些物理效果调整，使其更快稳定
    net.set_options("""
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000,
          "springConstant": 0.04,
          "springLength": 200
        },
        "minVelocity": 0.75
      }
    }
    """)
    
    try:
        net.save_graph(output_path)
        print("可视化文件生成成功！")
    except Exception as e:
        print(f"生成可视化文件时出错: {e}")


def main():
    """主函数"""
    print(f"正在从 {INPUT_FILE} 加载数据...")
    events = load_data(INPUT_FILE)
    
    if not events:
        print("未能加载任何事件数据，程序退出。")
        return
        
    # 为避免浏览器卡顿，我们只取一小部分数据进行可视化
    sample_events = events[:200] # 只处理前200个事件作为示例
    print(f"为提高性能，仅使用前 {len(sample_events)} 个事件进行可视化。")
    
    G = build_graph(sample_events)
    
    visualize_with_pyvis(G, OUTPUT_VIS_FILE)
    
    print(f"\n任务完成。请在浏览器中打开 '{OUTPUT_VIS_FILE}' 查看交互式图谱。")

if __name__ == "__main__":
    main()
