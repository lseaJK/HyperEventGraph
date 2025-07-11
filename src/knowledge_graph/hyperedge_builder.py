#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件超边结构构建模块
将事件作为超边连接多个实体节点
"""

import json
import uuid
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class HyperEdge:
    """超边类 - 表示一个事件"""
    id: str  # 超边ID
    event_type: str  # 事件类型
    connected_entities: List[str]  # 连接的实体ID列表
    properties: Dict[str, Any]  # 事件属性
    timestamp: Optional[str] = None  # 时间戳
    source: Optional[str] = None  # 信息来源
    confidence: float = 1.0  # 置信度
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class HyperNode:
    """超节点类 - 表示一个实体"""
    id: str  # 节点ID
    name: str  # 实体名称
    entity_type: str  # 实体类型
    properties: Dict[str, Any] = field(default_factory=dict)  # 实体属性
    aliases: Set[str] = field(default_factory=set)  # 别名
    connected_hyperedges: Set[str] = field(default_factory=set)  # 连接的超边ID
    
    def __post_init__(self):
        if isinstance(self.aliases, list):
            self.aliases = set(self.aliases)
        if isinstance(self.connected_hyperedges, list):
            self.connected_hyperedges = set(self.connected_hyperedges)


class HyperGraphBuilder:
    """超图构建器"""
    
    def __init__(self):
        self.hypernodes: Dict[str, HyperNode] = {}  # 节点ID -> 节点对象
        self.hyperedges: Dict[str, HyperEdge] = {}  # 边ID -> 边对象
        self.entity_name_to_id: Dict[str, str] = {}  # 实体名称 -> 节点ID
        
        # 事件类型到角色映射
        self.event_role_mapping = {
            "公司并购": {
                "acquirer": "收购方",
                "acquired": "被收购方",
                "deal_amount": "交易金额",
                "status": "状态",
                "announcement_date": "公告日期"
            },
            "投融资": {
                "investors": "投资方",
                "company": "融资方",
                "funding_amount": "融资金额",
                "round": "融资轮次",
                "related_products": "相关产品",
                "publish_date": "发布日期"
            },
            "高管变动": {
                "company": "公司",
                "executive_name": "高管",
                "position": "职位",
                "change_type": "变动类型",
                "change_date": "变动日期"
            },
            "法律诉讼": {
                "plaintiff": "原告",
                "defendant": "被告",
                "cause_of_action": "诉讼原因",
                "amount_involved": "涉及金额",
                "judgment": "判决结果",
                "filing_date": "立案日期"
            },
            "产能扩张": {
                "company": "公司",
                "location": "地点",
                "investment_amount": "投资金额",
                "new_capacity": "新增产能",
                "technology_node": "技术节点",
                "estimated_production_time": "预计投产时间"
            },
            "技术突破": {
                "organization": "机构",
                "technology_name": "技术名称",
                "key_metrics": "关键指标",
                "application_field": "应用领域",
                "release_date": "发布日期"
            },
            "供应链动态": {
                "company": "公司",
                "dynamic_type": "动态类型",
                "affected_link": "影响环节",
                "involved_materials": "涉及物料",
                "affected_objects": "影响对象",
                "publish_date": "发布日期"
            },
            "合作合资": {
                "partners": "合作方",
                "domain": "领域",
                "method": "合作方式",
                "goal": "目标",
                "validity_period": "有效期",
                "publish_date": "发布日期"
            },
            "知识产权": {
                "company": "公司",
                "ip_type": "IP类型",
                "ip_details": "IP详情",
                "amount_involved": "涉及金额",
                "judgment_result": "判决结果",
                "publish_date": "发布日期"
            }
        }
    
    def build_hypergraph_from_events(self, events_data: List[Dict[str, Any]]) -> Tuple[Dict[str, HyperNode], Dict[str, HyperEdge]]:
        """从事件数据构建超图"""
        logger.info(f"开始构建超图，处理 {len(events_data)} 个事件")
        
        for i, event_data in enumerate(events_data):
            try:
                self._process_single_event(event_data, f"event_{i}")
            except Exception as e:
                logger.error(f"处理事件 {i} 时出错: {e}")
                continue
        
        logger.info(f"超图构建完成: {len(self.hypernodes)} 个节点, {len(self.hyperedges)} 个超边")
        return self.hypernodes, self.hyperedges
    
    def _process_single_event(self, event_data: Dict[str, Any], event_id: str):
        """处理单个事件"""
        event_type = event_data.get('event_type', 'unknown')
        
        # 提取实体和创建节点
        entity_ids = []
        event_properties = {}
        timestamp = None
        source = event_data.get('source', '')
        
        # 获取事件角色映射
        role_mapping = self.event_role_mapping.get(event_type, {})
        
        for field_name, field_value in event_data.items():
            if field_name in ['event_type']:
                continue
            
            # 处理时间字段
            if 'date' in field_name or 'time' in field_name:
                if isinstance(field_value, str) and field_value.strip():
                    timestamp = field_value.strip()
                    event_properties[role_mapping.get(field_name, field_name)] = field_value
                continue
            
            # 处理数值字段
            if isinstance(field_value, (int, float)):
                event_properties[role_mapping.get(field_name, field_name)] = field_value
                continue
            
            # 处理字符串实体字段
            if isinstance(field_value, str) and field_value.strip():
                if field_name == 'source':
                    source = field_value
                    continue
                
                entity_id = self._create_or_get_entity(
                    name=field_value.strip(),
                    entity_type=self._infer_entity_type(field_name),
                    role=role_mapping.get(field_name, field_name)
                )
                if entity_id:
                    entity_ids.append(entity_id)
            
            # 处理列表实体字段
            elif isinstance(field_value, list):
                for item in field_value:
                    if isinstance(item, str) and item.strip():
                        entity_id = self._create_or_get_entity(
                            name=item.strip(),
                            entity_type=self._infer_entity_type(field_name),
                            role=role_mapping.get(field_name, field_name)
                        )
                        if entity_id:
                            entity_ids.append(entity_id)
            
            # 处理其他属性
            else:
                event_properties[role_mapping.get(field_name, field_name)] = field_value
        
        # 创建超边
        if entity_ids:
            hyperedge = HyperEdge(
                id=event_id,
                event_type=event_type,
                connected_entities=entity_ids,
                properties=event_properties,
                timestamp=timestamp,
                source=source
            )
            
            self.hyperedges[event_id] = hyperedge
            
            # 更新节点的连接信息
            for entity_id in entity_ids:
                if entity_id in self.hypernodes:
                    self.hypernodes[entity_id].connected_hyperedges.add(event_id)
    
    def _infer_entity_type(self, field_name: str) -> str:
        """推断实体类型"""
        type_mapping = {
            'acquirer': 'company',
            'acquired': 'company',
            'company': 'company',
            'investors': 'investor',
            'partners': 'organization',
            'organization': 'organization',
            'plaintiff': 'organization',
            'defendant': 'organization',
            'executive_name': 'person',
            'location': 'location',
            'technology_name': 'technology',
            'involved_materials': 'material',
            'related_products': 'product'
        }
        
        return type_mapping.get(field_name, 'entity')
    
    def _create_or_get_entity(self, name: str, entity_type: str, role: str = None) -> Optional[str]:
        """创建或获取实体节点"""
        # 标准化实体名称
        standardized_name = self._standardize_name(name, entity_type)
        
        # 检查是否已存在
        if standardized_name in self.entity_name_to_id:
            return self.entity_name_to_id[standardized_name]
        
        # 创建新节点
        node_id = f"{entity_type}_{len(self.hypernodes)}"
        
        hypernode = HyperNode(
            id=node_id,
            name=standardized_name,
            entity_type=entity_type,
            properties={'role': role} if role else {},
            aliases={name, standardized_name}
        )
        
        self.hypernodes[node_id] = hypernode
        self.entity_name_to_id[standardized_name] = node_id
        
        # 也为原始名称建立映射（如果不同）
        if name != standardized_name:
            self.entity_name_to_id[name] = node_id
        
        return node_id
    
    def _standardize_name(self, name: str, entity_type: str) -> str:
        """标准化名称"""
        name = name.strip()
        
        if entity_type == 'company':
            # 移除括号内容
            name = re.sub(r'\([^)]*\)', '', name).strip()
            
            # 统一公司后缀
            suffixes = ['有限公司', '股份有限公司', 'Co., Ltd.', 'Inc.', 'Corp.', 'LLC']
            for suffix in suffixes:
                if name.endswith(suffix):
                    base_name = name[:-len(suffix)].strip()
                    return f"{base_name}有限公司"
        
        elif entity_type == 'person':
            # 移除职位信息
            name = re.sub(r'(先生|女士|总裁|CEO|CTO|CFO|董事长|总经理)$', '', name).strip()
        
        return name
    
    def add_hyperedge_properties(self, hyperedge_id: str, properties: Dict[str, Any]):
        """为超边添加属性"""
        if hyperedge_id in self.hyperedges:
            self.hyperedges[hyperedge_id].properties.update(properties)
    
    def add_hypernode_properties(self, hypernode_id: str, properties: Dict[str, Any]):
        """为超节点添加属性"""
        if hypernode_id in self.hypernodes:
            self.hypernodes[hypernode_id].properties.update(properties)
    
    def get_entity_connections(self, entity_id: str) -> List[str]:
        """获取实体的所有连接"""
        if entity_id not in self.hypernodes:
            return []
        
        return list(self.hypernodes[entity_id].connected_hyperedges)
    
    def get_event_entities(self, event_id: str) -> List[str]:
        """获取事件连接的所有实体"""
        if event_id not in self.hyperedges:
            return []
        
        return self.hyperedges[event_id].connected_entities
    
    def find_related_events(self, entity_id: str, max_hops: int = 2) -> Set[str]:
        """查找与实体相关的事件（多跳）"""
        related_events = set()
        visited_entities = set()
        current_entities = {entity_id}
        
        for hop in range(max_hops):
            next_entities = set()
            
            for eid in current_entities:
                if eid in visited_entities:
                    continue
                
                visited_entities.add(eid)
                
                # 获取直接连接的事件
                connected_events = self.get_entity_connections(eid)
                related_events.update(connected_events)
                
                # 获取这些事件连接的其他实体
                for event_id in connected_events:
                    event_entities = self.get_event_entities(event_id)
                    next_entities.update(event_entities)
            
            current_entities = next_entities - visited_entities
            
            if not current_entities:
                break
        
        return related_events
    
    def get_hypergraph_statistics(self) -> Dict[str, Any]:
        """获取超图统计信息"""
        node_types = {}
        edge_types = {}
        
        for node in self.hypernodes.values():
            node_types[node.entity_type] = node_types.get(node.entity_type, 0) + 1
        
        for edge in self.hyperedges.values():
            edge_types[edge.event_type] = edge_types.get(edge.event_type, 0) + 1
        
        # 计算连接度统计
        node_degrees = [len(node.connected_hyperedges) for node in self.hypernodes.values()]
        edge_degrees = [len(edge.connected_entities) for edge in self.hyperedges.values()]
        
        return {
            'total_nodes': len(self.hypernodes),
            'total_edges': len(self.hyperedges),
            'node_types': node_types,
            'edge_types': edge_types,
            'avg_node_degree': sum(node_degrees) / len(node_degrees) if node_degrees else 0,
            'avg_edge_degree': sum(edge_degrees) / len(edge_degrees) if edge_degrees else 0,
            'max_node_degree': max(node_degrees) if node_degrees else 0,
            'max_edge_degree': max(edge_degrees) if edge_degrees else 0
        }
    
    def export_to_dict(self) -> Dict[str, Any]:
        """导出超图为字典格式"""
        nodes_data = []
        for node_id, node in self.hypernodes.items():
            nodes_data.append({
                'id': node_id,
                'name': node.name,
                'type': node.entity_type,
                'properties': node.properties,
                'aliases': list(node.aliases),
                'connected_hyperedges': list(node.connected_hyperedges)
            })
        
        edges_data = []
        for edge_id, edge in self.hyperedges.items():
            edges_data.append({
                'id': edge_id,
                'event_type': edge.event_type,
                'connected_entities': edge.connected_entities,
                'properties': edge.properties,
                'timestamp': edge.timestamp,
                'source': edge.source,
                'confidence': edge.confidence
            })
        
        return {
            'nodes': nodes_data,
            'hyperedges': edges_data,
            'statistics': self.get_hypergraph_statistics()
        }
    
    def save_hypergraph(self, filepath: str):
        """保存超图到文件"""
        hypergraph_data = self.export_to_dict()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(hypergraph_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"超图已保存到 {filepath}")
    
    def load_hypergraph(self, filepath: str):
        """从文件加载超图"""
        with open(filepath, 'r', encoding='utf-8') as f:
            hypergraph_data = json.load(f)
        
        # 清空现有数据
        self.hypernodes.clear()
        self.hyperedges.clear()
        self.entity_name_to_id.clear()
        
        # 加载节点
        for node_data in hypergraph_data['nodes']:
            node = HyperNode(
                id=node_data['id'],
                name=node_data['name'],
                entity_type=node_data['type'],
                properties=node_data['properties'],
                aliases=set(node_data['aliases']),
                connected_hyperedges=set(node_data['connected_hyperedges'])
            )
            
            self.hypernodes[node.id] = node
            
            # 重建名称映射
            for alias in node.aliases:
                self.entity_name_to_id[alias] = node.id
        
        # 加载超边
        for edge_data in hypergraph_data['hyperedges']:
            edge = HyperEdge(
                id=edge_data['id'],
                event_type=edge_data['event_type'],
                connected_entities=edge_data['connected_entities'],
                properties=edge_data['properties'],
                timestamp=edge_data.get('timestamp'),
                source=edge_data.get('source'),
                confidence=edge_data.get('confidence', 1.0)
            )
            
            self.hyperedges[edge.id] = edge
        
        logger.info(f"从 {filepath} 加载了超图: {len(self.hypernodes)} 个节点, {len(self.hyperedges)} 个超边")


def main():
    """测试函数"""
    import re
    
    # 创建超图构建器
    builder = HyperGraphBuilder()
    
    # 测试事件数据
    test_events = [
        {
            "event_type": "公司并购",
            "acquirer": "腾讯控股有限公司",
            "acquired": "搜狗科技有限公司",
            "deal_amount": 3500000,
            "announcement_date": "2021-07-26",
            "source": "财经新闻"
        },
        {
            "event_type": "投融资",
            "investors": ["红杉资本", "IDG资本"],
            "company": "字节跳动有限公司",
            "funding_amount": 1000000,
            "round": "D轮",
            "publish_date": "2021-08-15",
            "source": "投资界"
        },
        {
            "event_type": "高管变动",
            "company": "腾讯控股有限公司",
            "executive_name": "马化腾",
            "position": "董事长",
            "change_type": "上任",
            "change_date": "2021-09-01",
            "source": "公司公告"
        }
    ]
    
    # 构建超图
    nodes, edges = builder.build_hypergraph_from_events(test_events)
    
    # 显示统计信息
    stats = builder.get_hypergraph_statistics()
    print("\n超图统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 显示节点
    print("\n超节点:")
    for node_id, node in nodes.items():
        print(f"  {node_id}: {node.name} ({node.entity_type})")
        print(f"    连接的超边: {node.connected_hyperedges}")
    
    # 显示超边
    print("\n超边:")
    for edge_id, edge in edges.items():
        print(f"  {edge_id}: {edge.event_type}")
        print(f"    连接的实体: {edge.connected_entities}")
        print(f"    属性: {edge.properties}")
    
    # 测试关联查询
    if nodes:
        first_node_id = list(nodes.keys())[0]
        related_events = builder.find_related_events(first_node_id, max_hops=2)
        print(f"\n实体 {first_node_id} 的相关事件: {related_events}")


if __name__ == "__main__":
    main()