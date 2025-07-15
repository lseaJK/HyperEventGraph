#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON到unique_contexts格式转换器

将事件JSON数据转换为HyperGraphRAG所需的unique_contexts格式，
实现无损转换并保持数据完整性。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class HyperEdge:
    """超边数据结构"""
    edge_id: str
    edge_type: str
    nodes: List[str]
    edge_attributes: Dict[str, Any]

@dataclass
class UniqueContext:
    """unique_contexts格式数据结构"""
    context_id: str
    content: str
    metadata: Dict[str, Any]
    hyperedges: List[HyperEdge]

class JSONToContextsConverter:
    """JSON到unique_contexts格式转换器"""
    
    def __init__(self):
        """初始化转换器"""
        self.event_templates = {
            "公司并购": "{}于{}宣布收购{}，交易金额达{}。此次并购旨在{}。收购方为{}，被收购方为{}，交易状态为{}。",
            "投融资": "{}于{}完成{}轮融资，融资金额为{}。投资方包括{}，本轮融资将用于{}。",
            "高管变动": "{}于{}宣布高管变动，{}担任{}职位。此次任命{}，生效日期为{}。",
            "业务合作": "{}与{}于{}达成战略合作协议，合作内容涉及{}。双方将在{}等领域展开深度合作。",
            "产品发布": "{}于{}正式发布{}产品，该产品具有{}等特点。预计将在{}市场产生重要影响。",
            "财务报告": "{}发布{}财务报告，营收达到{}，同比增长{}。净利润为{}，业绩表现{}。",
            "法律诉讼": "{}与{}之间的法律纠纷于{}进入新阶段，争议焦点为{}。案件当前状态为{}。",
            "监管政策": "{}于{}发布新的监管政策，涉及{}领域。政策要求{}，预计将对{}产生影响。",
            "市场动态": "{}市场于{}出现重要变化，{}价格{}，市场表现{}。分析师认为{}。",
            "技术创新": "{}在{}领域取得技术突破，新技术{}具有{}优势。该技术预计将应用于{}。"
        }
        
        self.entity_type_mapping = {
            "公司": "company",
            "人员": "person", 
            "产品": "product",
            "地点": "location",
            "时间": "time",
            "金额": "amount",
            "技术": "technology",
            "政策": "policy"
        }
        
        self.edge_type_mapping = {
            "公司并购": "merger_acquisition_event",
            "投融资": "investment_event",
            "高管变动": "executive_change_event",
            "业务合作": "business_cooperation_event",
            "产品发布": "product_launch_event",
            "财务报告": "financial_report_event",
            "法律诉讼": "legal_dispute_event",
            "监管政策": "regulatory_policy_event",
            "市场动态": "market_dynamics_event",
            "技术创新": "technology_innovation_event"
        }
    
    def convert_events_to_contexts(self, events: List[Dict[str, Any]]) -> List[UniqueContext]:
        """将事件列表转换为unique_contexts格式
        
        Args:
            events: 事件JSON数据列表
            
        Returns:
            转换后的unique_contexts列表
        """
        contexts = []
        
        for event in events:
            try:
                context = self._convert_single_event(event)
                if context:
                    contexts.append(context)
            except Exception as e:
                logger.error(f"转换事件失败: {event.get('event_id', 'unknown')}, 错误: {str(e)}")
                continue
        
        logger.info(f"成功转换 {len(contexts)} 个事件为unique_contexts格式")
        return contexts
    
    def _convert_single_event(self, event: Dict[str, Any]) -> Optional[UniqueContext]:
        """转换单个事件
        
        Args:
            event: 单个事件JSON数据
            
        Returns:
            转换后的UniqueContext对象
        """
        # 生成context_id
        context_id = self._generate_context_id(event)
        
        # 生成自然语言内容
        content = self._generate_content(event)
        
        # 构建元数据
        metadata = self._build_metadata(event)
        
        # 构建超边
        hyperedges = self._build_hyperedges(event)
        
        return UniqueContext(
            context_id=context_id,
            content=content,
            metadata=metadata,
            hyperedges=hyperedges
        )
    
    def _generate_context_id(self, event: Dict[str, Any]) -> str:
        """生成context_id
        
        Args:
            event: 事件数据
            
        Returns:
            生成的context_id
        """
        event_type = event.get('event_type', 'unknown')
        domain = event.get('domain', 'general')
        timestamp = event.get('timestamp', datetime.now().strftime('%Y%m%d'))
        event_id = event.get('event_id', str(uuid.uuid4())[:8])
        
        # 格式: ctx_evt_{domain}_{event_type_abbr}_{timestamp}_{id}
        type_abbr = self._get_event_type_abbreviation(event_type)
        context_id = f"ctx_evt_{domain}_{type_abbr}_{timestamp}_{event_id}"
        
        return context_id.replace(' ', '_').replace('-', '_').lower()
    
    def _get_event_type_abbreviation(self, event_type: str) -> str:
        """获取事件类型缩写
        
        Args:
            event_type: 事件类型
            
        Returns:
            事件类型缩写
        """
        abbreviations = {
            "公司并购": "ma",
            "投融资": "inv",
            "高管变动": "exec",
            "业务合作": "coop",
            "产品发布": "prod",
            "财务报告": "fin",
            "法律诉讼": "legal",
            "监管政策": "reg",
            "市场动态": "market",
            "技术创新": "tech"
        }
        return abbreviations.get(event_type, "general")
    
    def _generate_content(self, event: Dict[str, Any]) -> str:
        """生成自然语言内容
        
        Args:
            event: 事件数据
            
        Returns:
            生成的自然语言描述
        """
        event_type = event.get('event_type', '')
        entities = event.get('entities', {})
        attributes = event.get('attributes', {})
        
        # 使用模板生成内容
        if event_type in self.event_templates:
            try:
                content = self._apply_template(event_type, entities, attributes)
            except Exception as e:
                logger.warning(f"模板应用失败，使用默认格式: {str(e)}")
                content = self._generate_default_content(event)
        else:
            content = self._generate_default_content(event)
        
        return content
    
    def _apply_template(self, event_type: str, entities: Dict, attributes: Dict) -> str:
        """应用事件模板生成内容
        
        Args:
            event_type: 事件类型
            entities: 实体信息
            attributes: 事件属性
            
        Returns:
            生成的内容
        """
        template = self.event_templates[event_type]
        
        # 根据事件类型提取相关信息
        if event_type == "公司并购":
            acquirer = entities.get('收购方', [''])[0] if entities.get('收购方') else ''
            target = entities.get('被收购方', [''])[0] if entities.get('被收购方') else ''
            amount = attributes.get('交易金额', '')
            date = attributes.get('公告日期', '')
            purpose = attributes.get('并购目的', '加强市场地位')
            status = attributes.get('交易状态', '进行中')
            
            content = template.format(
                acquirer, date, target, amount, purpose, 
                acquirer, target, status
            )
        
        elif event_type == "投融资":
            company = entities.get('融资方', [''])[0] if entities.get('融资方') else ''
            investors = ', '.join(entities.get('投资方', []))
            amount = attributes.get('融资金额', '')
            round_type = attributes.get('融资轮次', '')
            date = attributes.get('融资日期', '')
            purpose = attributes.get('资金用途', '业务发展')
            
            content = template.format(
                company, date, round_type, amount, investors, purpose
            )
        
        else:
            # 其他事件类型的默认处理
            content = self._generate_default_content({
                'event_type': event_type,
                'entities': entities,
                'attributes': attributes
            })
        
        return content
    
    def _generate_default_content(self, event: Dict[str, Any]) -> str:
        """生成默认格式的内容
        
        Args:
            event: 事件数据
            
        Returns:
            默认格式的内容描述
        """
        event_type = event.get('event_type', '未知事件')
        entities = event.get('entities', {})
        attributes = event.get('attributes', {})
        
        # 构建基本描述
        content_parts = [f"发生了{event_type}事件"]
        
        # 添加实体信息
        if entities:
            entity_desc = []
            for role, entity_list in entities.items():
                if entity_list:
                    entity_desc.append(f"{role}为{', '.join(entity_list)}")
            if entity_desc:
                content_parts.append("，".join(entity_desc))
        
        # 添加属性信息
        if attributes:
            attr_desc = []
            for key, value in attributes.items():
                if value:
                    attr_desc.append(f"{key}为{value}")
            if attr_desc:
                content_parts.append("，".join(attr_desc))
        
        return "，".join(content_parts) + "。"
    
    def _build_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """构建元数据
        
        Args:
            event: 事件数据
            
        Returns:
            元数据字典
        """
        entities_list = []
        for entity_list in event.get('entities', {}).values():
            entities_list.extend(entity_list)
        
        metadata = {
            "event_id": event.get('event_id', ''),
            "event_type": event.get('event_type', ''),
            "domain": event.get('domain', 'general'),
            "entities": list(set(entities_list)),  # 去重
            "timestamp": event.get('timestamp', ''),
            "source": event.get('source', ''),
            "confidence": event.get('confidence', 0.0)
        }
        
        # 添加原始事件的其他信息
        if 'attributes' in event:
            metadata['original_attributes'] = event['attributes']
        
        return metadata
    
    def _build_hyperedges(self, event: Dict[str, Any]) -> List[HyperEdge]:
        """构建超边
        
        Args:
            event: 事件数据
            
        Returns:
            超边列表
        """
        hyperedges = []
        
        # 主要超边：事件连接所有相关实体
        main_edge = self._create_main_hyperedge(event)
        if main_edge:
            hyperedges.append(main_edge)
        
        # 可选：创建子超边（实体间的特定关系）
        sub_edges = self._create_sub_hyperedges(event)
        hyperedges.extend(sub_edges)
        
        return hyperedges
    
    def _create_main_hyperedge(self, event: Dict[str, Any]) -> Optional[HyperEdge]:
        """创建主要超边
        
        Args:
            event: 事件数据
            
        Returns:
            主要超边对象
        """
        event_type = event.get('event_type', '')
        entities = event.get('entities', {})
        attributes = event.get('attributes', {})
        
        # 收集所有节点
        nodes = []
        for entity_list in entities.values():
            nodes.extend(entity_list)
        
        # 添加重要属性作为节点
        important_attrs = ['时间', '金额', '地点']
        for attr_key, attr_value in attributes.items():
            if any(important in attr_key for important in important_attrs) and attr_value:
                nodes.append(str(attr_value))
        
        if not nodes:
            return None
        
        # 生成边ID
        edge_id = f"he_{self._get_event_type_abbreviation(event_type)}_{event.get('event_id', str(uuid.uuid4())[:8])}"
        
        # 获取边类型
        edge_type = self.edge_type_mapping.get(event_type, "general_event")
        
        # 构建边属性
        edge_attributes = {}
        for key, value in attributes.items():
            if value:
                edge_attributes[key] = value
        
        return HyperEdge(
            edge_id=edge_id,
            edge_type=edge_type,
            nodes=list(set(nodes)),  # 去重
            edge_attributes=edge_attributes
        )
    
    def _create_sub_hyperedges(self, event: Dict[str, Any]) -> List[HyperEdge]:
        """创建子超边（实体间特定关系）
        
        Args:
            event: 事件数据
            
        Returns:
            子超边列表
        """
        # 暂时返回空列表，后续可根据需要扩展
        return []
    
    def save_contexts_to_file(self, contexts: List[UniqueContext], output_path: str) -> bool:
        """保存contexts到文件
        
        Args:
            contexts: unique_contexts列表
            output_path: 输出文件路径
            
        Returns:
            是否保存成功
        """
        try:
            # 转换为字典格式
            contexts_dict = []
            for context in contexts:
                context_dict = {
                    "context_id": context.context_id,
                    "content": context.content,
                    "metadata": context.metadata,
                    "hyperedges": [asdict(edge) for edge in context.hyperedges]
                }
                contexts_dict.append(context_dict)
            
            # 确保输出目录存在
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存到文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(contexts_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"成功保存 {len(contexts)} 个contexts到文件: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存contexts到文件失败: {str(e)}")
            return False
    
    def load_events_from_file(self, input_path: str) -> List[Dict[str, Any]]:
        """从文件加载事件数据
        
        Args:
            input_path: 输入文件路径
            
        Returns:
            事件数据列表
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                events = json.load(f)
            
            logger.info(f"成功从文件加载 {len(events)} 个事件: {input_path}")
            return events
            
        except Exception as e:
            logger.error(f"从文件加载事件失败: {str(e)}")
            return []

def main():
    """主函数 - 演示转换功能"""
    # 创建转换器
    converter = JSONToContextsConverter()
    
    # 示例事件数据
    sample_events = [
        {
            "event_id": "evt_financial_ma_20240115_001",
            "event_type": "公司并购",
            "domain": "financial",
            "timestamp": "2024-01-15",
            "source": "新浪财经",
            "confidence": 0.92,
            "entities": {
                "收购方": ["腾讯控股"],
                "被收购方": ["某游戏公司"]
            },
            "attributes": {
                "交易金额": "50亿元人民币",
                "公告日期": "2024年1月15日",
                "交易状态": "进行中",
                "并购目的": "加强腾讯在游戏领域的市场地位"
            }
        }
    ]
    
    # 转换为unique_contexts格式
    contexts = converter.convert_events_to_contexts(sample_events)
    
    # 打印结果
    for context in contexts:
        print(f"Context ID: {context.context_id}")
        print(f"Content: {context.content}")
        print(f"Metadata: {context.metadata}")
        print(f"HyperEdges: {len(context.hyperedges)}")
        print("-" * 50)
    
    # 保存到文件
    output_path = "data/unique_contexts/sample_contexts.json"
    converter.save_contexts_to_file(contexts, output_path)

if __name__ == "__main__":
    main()