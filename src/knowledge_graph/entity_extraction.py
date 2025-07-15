#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体识别和标准化模块
从事件JSON中提取实体并进行标准化处理
"""

import re
import json
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """实体类"""
    name: str  # 实体名称
    entity_type: str  # 实体类型
    aliases: Set[str]  # 别名集合
    attributes: Dict[str, Any]  # 实体属性
    source_events: List[str]  # 来源事件ID列表
    
    def __post_init__(self):
        if isinstance(self.aliases, list):
            self.aliases = set(self.aliases)
        if not self.aliases:
            self.aliases = set()
        # 将实体名称也加入别名集合
        self.aliases.add(self.name)


class EntityExtractor:
    """实体抽取器"""
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}  # 实体ID -> 实体对象
        self.name_to_id: Dict[str, str] = {}  # 实体名称 -> 实体ID
        self.entity_counter = 0
        
        # 实体类型映射
        self.entity_type_mapping = {
            # 金融领域
            'acquirer': 'company',
            'acquired': 'company', 
            'company': 'company',
            'investors': 'company',
            'plaintiff': 'organization',
            'defendant': 'organization',
            'executive_name': 'person',
            
            # 集成电路领域
            'organization': 'organization',
            'partners': 'organization',
            
            # 通用
            'location': 'location',
            'source': 'source'
        }
        
        # 公司名称标准化规则
        self.company_suffixes = [
            '有限公司', '股份有限公司', '集团有限公司', '科技有限公司',
            'Co., Ltd.', 'Inc.', 'Corp.', 'LLC', 'Ltd.', 'Group',
            '株式会社', '(株)', 'AG', 'GmbH', 'S.A.', 'N.V.'
        ]
        
        # 人名标准化规则
        self.name_patterns = [
            r'^[\u4e00-\u9fff]{2,4}$',  # 中文姓名
            r'^[A-Z][a-z]+ [A-Z][a-z]+$',  # 英文姓名
        ]
    
    def extract_entities_from_event(self, event_data: Dict[str, Any], event_id: str = None) -> List[Entity]:
        """从单个事件中提取实体"""
        entities = []
        
        if not event_id:
            event_id = f"event_{self.entity_counter}"
        
        # 遍历事件字段，提取实体
        for field_name, field_value in event_data.items():
            if field_name in ['event_type', 'source']:
                continue
                
            entity_type = self._get_entity_type(field_name)
            if not entity_type:
                continue
                
            # 处理不同类型的字段值
            if isinstance(field_value, str) and field_value.strip():
                entity = self._create_entity(
                    name=field_value.strip(),
                    entity_type=entity_type,
                    source_event=event_id
                )
                entities.append(entity)
                
            elif isinstance(field_value, list):
                for item in field_value:
                    if isinstance(item, str) and item.strip():
                        entity = self._create_entity(
                            name=item.strip(),
                            entity_type=entity_type,
                            source_event=event_id
                        )
                        entities.append(entity)
        
        return entities
    
    def _get_entity_type(self, field_name: str) -> Optional[str]:
        """根据字段名获取实体类型"""
        return self.entity_type_mapping.get(field_name)
    
    def _create_entity(self, name: str, entity_type: str, source_event: str) -> Entity:
        """创建实体对象"""
        # 标准化实体名称
        standardized_name = self._standardize_entity_name(name, entity_type)
        
        # 检查是否已存在相同实体
        existing_id = self._find_existing_entity(standardized_name, entity_type)
        
        if existing_id:
            # 更新现有实体
            entity = self.entities[existing_id]
            entity.aliases.add(name)
            if source_event not in entity.source_events:
                entity.source_events.append(source_event)
            return entity
        else:
            # 创建新实体
            entity_id = f"{entity_type}_{self.entity_counter}"
            self.entity_counter += 1
            
            entity = Entity(
                name=standardized_name,
                entity_type=entity_type,
                aliases={name, standardized_name},
                attributes={},
                source_events=[source_event]
            )
            
            self.entities[entity_id] = entity
            self.name_to_id[standardized_name] = entity_id
            
            return entity
    
    def _standardize_entity_name(self, name: str, entity_type: str) -> str:
        """标准化实体名称"""
        if entity_type == 'company':
            return self._standardize_company_name(name)
        elif entity_type == 'person':
            return self._standardize_person_name(name)
        elif entity_type == 'location':
            return self._standardize_location_name(name)
        else:
            return name.strip()
    
    def _standardize_company_name(self, name: str) -> str:
        """标准化公司名称"""
        name = name.strip()
        
        # 移除括号内容（如股票代码）
        name = re.sub(r'\([^)]*\)', '', name).strip()
        
        # 统一公司后缀
        for suffix in self.company_suffixes:
            if name.endswith(suffix):
                base_name = name[:-len(suffix)].strip()
                return f"{base_name}有限公司"  # 统一使用中文后缀
        
        return name
    
    def _standardize_person_name(self, name: str) -> str:
        """标准化人名"""
        name = name.strip()
        
        # 移除职位信息
        name = re.sub(r'(先生|女士|总裁|CEO|CTO|CFO|董事长|总经理)$', '', name).strip()
        
        return name
    
    def _standardize_location_name(self, name: str) -> str:
        """标准化地名"""
        name = name.strip()
        
        # 统一地名格式
        location_mappings = {
            '北京市': '北京',
            '上海市': '上海',
            '深圳市': '深圳',
            '广州市': '广州',
            '杭州市': '杭州',
            '南京市': '南京',
            '苏州市': '苏州',
            '成都市': '成都',
            '西安市': '西安',
            '武汉市': '武汉'
        }
        
        return location_mappings.get(name, name)
    
    def _find_existing_entity(self, name: str, entity_type: str) -> Optional[str]:
        """查找是否存在相同的实体"""
        # 精确匹配
        if name in self.name_to_id:
            entity_id = self.name_to_id[name]
            if self.entities[entity_id].entity_type == entity_type:
                return entity_id
        
        # 模糊匹配（基于别名）
        for entity_id, entity in self.entities.items():
            if entity.entity_type == entity_type:
                if name in entity.aliases:
                    return entity_id
                # 公司名称相似度匹配
                if entity_type == 'company':
                    if self._is_similar_company_name(name, entity.name):
                        return entity_id
        
        return None
    
    def _is_similar_company_name(self, name1: str, name2: str) -> bool:
        """判断两个公司名称是否相似"""
        # 移除公司后缀进行比较
        base1 = self._remove_company_suffix(name1)
        base2 = self._remove_company_suffix(name2)
        
        # 如果基础名称相同，认为是同一公司
        return base1 == base2
    
    def _remove_company_suffix(self, name: str) -> str:
        """移除公司后缀"""
        for suffix in self.company_suffixes:
            if name.endswith(suffix):
                return name[:-len(suffix)].strip()
        return name
    
    def merge_similar_entities(self) -> int:
        """合并相似实体"""
        merged_count = 0
        entities_to_remove = set()
        
        entity_list = list(self.entities.items())
        
        for i, (id1, entity1) in enumerate(entity_list):
            if id1 in entities_to_remove:
                continue
                
            for j, (id2, entity2) in enumerate(entity_list[i+1:], i+1):
                if id2 in entities_to_remove:
                    continue
                    
                if entity1.entity_type == entity2.entity_type:
                    if self._should_merge_entities(entity1, entity2):
                        # 合并实体
                        entity1.aliases.update(entity2.aliases)
                        entity1.source_events.extend(entity2.source_events)
                        entity1.attributes.update(entity2.attributes)
                        
                        # 更新名称映射
                        for alias in entity2.aliases:
                            self.name_to_id[alias] = id1
                        
                        entities_to_remove.add(id2)
                        merged_count += 1
        
        # 删除被合并的实体
        for entity_id in entities_to_remove:
            del self.entities[entity_id]
        
        logger.info(f"合并了 {merged_count} 个相似实体")
        return merged_count
    
    def _should_merge_entities(self, entity1: Entity, entity2: Entity) -> bool:
        """判断两个实体是否应该合并"""
        # 检查别名重叠
        if entity1.aliases & entity2.aliases:
            return True
        
        # 公司名称相似度检查
        if entity1.entity_type == 'company':
            return self._is_similar_company_name(entity1.name, entity2.name)
        
        return False
    
    def get_entity_statistics(self) -> Dict[str, Any]:
        """获取实体统计信息"""
        stats = {
            'total_entities': len(self.entities),
            'entity_types': defaultdict(int),
            'entities_with_multiple_aliases': 0,
            'entities_from_multiple_events': 0
        }
        
        for entity in self.entities.values():
            stats['entity_types'][entity.entity_type] += 1
            
            if len(entity.aliases) > 1:
                stats['entities_with_multiple_aliases'] += 1
            
            if len(entity.source_events) > 1:
                stats['entities_from_multiple_events'] += 1
        
        return dict(stats)
    
    def export_entities(self) -> List[Dict[str, Any]]:
        """导出实体数据"""
        entities_data = []
        
        for entity_id, entity in self.entities.items():
            entity_data = {
                'id': entity_id,
                'name': entity.name,
                'type': entity.entity_type,
                'aliases': list(entity.aliases),
                'attributes': entity.attributes,
                'source_events': entity.source_events
            }
            entities_data.append(entity_data)
        
        return entities_data
    
    def save_entities(self, filepath: str):
        """保存实体到文件"""
        entities_data = self.export_entities()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entities_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"实体数据已保存到 {filepath}")
    
    def load_entities(self, filepath: str):
        """从文件加载实体"""
        with open(filepath, 'r', encoding='utf-8') as f:
            entities_data = json.load(f)
        
        self.entities.clear()
        self.name_to_id.clear()
        
        for entity_data in entities_data:
            entity = Entity(
                name=entity_data['name'],
                entity_type=entity_data['type'],
                aliases=set(entity_data['aliases']),
                attributes=entity_data['attributes'],
                source_events=entity_data['source_events']
            )
            
            entity_id = entity_data['id']
            self.entities[entity_id] = entity
            
            for alias in entity.aliases:
                self.name_to_id[alias] = entity_id
        
        # 更新计数器
        if self.entities:
            max_counter = max([int(eid.split('_')[-1]) for eid in self.entities.keys() if '_' in eid])
            self.entity_counter = max_counter + 1
        
        logger.info(f"从 {filepath} 加载了 {len(self.entities)} 个实体")


def main():
    """测试函数"""
    # 创建实体抽取器
    extractor = EntityExtractor()
    
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
    
    # 提取实体
    for i, event in enumerate(test_events):
        entities = extractor.extract_entities_from_event(event, f"event_{i}")
        print(f"事件 {i} 提取到 {len(entities)} 个实体")
    
    # 合并相似实体
    merged_count = extractor.merge_similar_entities()
    print(f"合并了 {merged_count} 个相似实体")
    
    # 显示统计信息
    stats = extractor.get_entity_statistics()
    print("\n实体统计信息:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # 显示所有实体
    print("\n提取的实体:")
    for entity_id, entity in extractor.entities.items():
        print(f"  {entity_id}: {entity.name} ({entity.entity_type})")
        print(f"    别名: {entity.aliases}")
        print(f"    来源事件: {entity.source_events}")


if __name__ == "__main__":
    main()