#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实体链接和知识库对齐模块

提供实体链接功能，将提取的实体与外部知识库（如Wikidata、DBpedia等）
进行对齐，增强实体的语义信息和结构化属性。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import re
import json
import requests
import time
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
from pathlib import Path
from urllib.parse import quote, urljoin
from datetime import datetime
import hashlib

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class KnowledgeBaseEntity:
    """知识库实体"""
    kb_id: str  # 知识库中的ID
    kb_name: str  # 知识库名称 (wikidata, dbpedia, etc.)
    uri: str  # 实体URI
    label: str  # 实体标签
    description: str  # 实体描述
    aliases: Set[str] = field(default_factory=set)  # 别名
    types: Set[str] = field(default_factory=set)  # 实体类型
    properties: Dict[str, Any] = field(default_factory=dict)  # 属性
    confidence: float = 0.0  # 链接置信度

@dataclass
class EntityLinkingResult:
    """实体链接结果"""
    entity_id: str  # 原始实体ID
    entity_name: str  # 原始实体名称
    candidates: List[KnowledgeBaseEntity] = field(default_factory=list)  # 候选实体
    best_match: Optional[KnowledgeBaseEntity] = None  # 最佳匹配
    linking_confidence: float = 0.0  # 链接置信度
    linking_method: str = ""  # 链接方法
    timestamp: str = field(default_factory=lambda: str(datetime.now()))

@dataclass
class EntityLinkingConfig:
    """实体链接配置"""
    # API配置
    wikidata_endpoint: str = "https://www.wikidata.org/w/api.php"
    dbpedia_endpoint: str = "https://lookup.dbpedia.org/api/search"
    request_timeout: int = 10
    request_delay: float = 0.1  # 请求间隔
    max_retries: int = 3
    
    # 链接阈值
    min_confidence_threshold: float = 0.7
    exact_match_bonus: float = 0.2
    alias_match_bonus: float = 0.15
    type_match_bonus: float = 0.1
    
    # 候选数量限制
    max_candidates_per_entity: int = 10
    max_search_results: int = 20
    
    # 缓存配置
    enable_cache: bool = True
    cache_expiry_days: int = 30
    
    # 实体类型映射
    entity_type_mapping: Dict[str, List[str]] = field(default_factory=lambda: {
        'company': ['Q4830453', 'Q783794', 'Q6881511'],  # enterprise, company, organization
        'person': ['Q5'],  # human
        'location': ['Q17334923', 'Q2221906'],  # geographic location, place
        'product': ['Q2424752'],  # product
        'event': ['Q1656682']  # event
    })

class EntityLinker:
    """实体链接器"""
    
    def __init__(self, config: Optional[EntityLinkingConfig] = None):
        """初始化实体链接器
        
        Args:
            config: 链接配置，如果为None则使用默认配置
        """
        self.config = config or EntityLinkingConfig()
        self.cache: Dict[str, EntityLinkingResult] = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'HyperEventGraph/1.0 (https://github.com/hypereventgraph)'
        })
        
        # 加载缓存
        if self.config.enable_cache:
            self._load_cache()
    
    def link_entities(self, entities: Dict[str, Any]) -> Dict[str, EntityLinkingResult]:
        """链接实体到知识库
        
        Args:
            entities: 实体字典 {entity_id: entity_object}
            
        Returns:
            链接结果字典 {entity_id: EntityLinkingResult}
        """
        logger.info(f"开始链接 {len(entities)} 个实体到知识库")
        
        results = {}
        
        for entity_id, entity in entities.items():
            try:
                # 检查缓存
                cache_key = self._generate_cache_key(entity.name, entity.entity_type)
                if cache_key in self.cache:
                    cached_result = self.cache[cache_key]
                    cached_result.entity_id = entity_id  # 更新实体ID
                    results[entity_id] = cached_result
                    logger.debug(f"使用缓存结果: {entity.name}")
                    continue
                
                # 执行实体链接
                result = self._link_single_entity(entity_id, entity)
                results[entity_id] = result
                
                # 缓存结果
                if self.config.enable_cache and result.best_match:
                    self.cache[cache_key] = result
                
                # 请求延迟
                time.sleep(self.config.request_delay)
                
            except Exception as e:
                logger.error(f"链接实体失败: {entity.name}, 错误: {str(e)}")
                results[entity_id] = EntityLinkingResult(
                    entity_id=entity_id,
                    entity_name=entity.name
                )
        
        # 保存缓存
        if self.config.enable_cache:
            self._save_cache()
        
        logger.info(f"实体链接完成，成功链接: {len([r for r in results.values() if r.best_match])} 个")
        return results
    
    def _link_single_entity(self, entity_id: str, entity: Any) -> EntityLinkingResult:
        """链接单个实体
        
        Args:
            entity_id: 实体ID
            entity: 实体对象
            
        Returns:
            链接结果
        """
        result = EntityLinkingResult(
            entity_id=entity_id,
            entity_name=entity.name
        )
        
        # 1. 搜索Wikidata候选
        wikidata_candidates = self._search_wikidata(entity)
        result.candidates.extend(wikidata_candidates)
        
        # 2. 搜索DBpedia候选
        dbpedia_candidates = self._search_dbpedia(entity)
        result.candidates.extend(dbpedia_candidates)
        
        # 3. 对候选进行排序和筛选
        if result.candidates:
            result.candidates = self._rank_candidates(entity, result.candidates)
            result.candidates = result.candidates[:self.config.max_candidates_per_entity]
            
            # 4. 选择最佳匹配
            best_candidate = result.candidates[0]
            if best_candidate.confidence >= self.config.min_confidence_threshold:
                result.best_match = best_candidate
                result.linking_confidence = best_candidate.confidence
                result.linking_method = f"{best_candidate.kb_name}_search"
        
        return result
    
    def _search_wikidata(self, entity: Any) -> List[KnowledgeBaseEntity]:
        """在Wikidata中搜索实体
        
        Args:
            entity: 实体对象
            
        Returns:
            候选实体列表
        """
        candidates = []
        
        try:
            # 构建搜索查询
            search_terms = [entity.name]
            if hasattr(entity, 'aliases') and entity.aliases:
                search_terms.extend(list(entity.aliases)[:3])  # 限制别名数量
            
            for search_term in search_terms:
                params = {
                    'action': 'wbsearchentities',
                    'search': search_term,
                    'language': 'zh',
                    'format': 'json',
                    'limit': self.config.max_search_results // len(search_terms)
                }
                
                response = self.session.get(
                    self.config.wikidata_endpoint,
                    params=params,
                    timeout=self.config.request_timeout
                )
                response.raise_for_status()
                
                data = response.json()
                
                if 'search' in data:
                    for item in data['search']:
                        candidate = self._parse_wikidata_entity(item, entity)
                        if candidate:
                            candidates.append(candidate)
                
                time.sleep(self.config.request_delay)
        
        except Exception as e:
            logger.warning(f"Wikidata搜索失败: {entity.name}, 错误: {str(e)}")
        
        return candidates
    
    def _search_dbpedia(self, entity: Any) -> List[KnowledgeBaseEntity]:
        """在DBpedia中搜索实体
        
        Args:
            entity: 实体对象
            
        Returns:
            候选实体列表
        """
        candidates = []
        
        try:
            params = {
                'query': entity.name,
                'format': 'json',
                'maxResults': self.config.max_search_results
            }
            
            response = self.session.get(
                self.config.dbpedia_endpoint,
                params=params,
                timeout=self.config.request_timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            if 'docs' in data:
                for item in data['docs']:
                    candidate = self._parse_dbpedia_entity(item, entity)
                    if candidate:
                        candidates.append(candidate)
        
        except Exception as e:
            logger.warning(f"DBpedia搜索失败: {entity.name}, 错误: {str(e)}")
        
        return candidates
    
    def _parse_wikidata_entity(self, item: Dict[str, Any], original_entity: Any) -> Optional[KnowledgeBaseEntity]:
        """解析Wikidata实体
        
        Args:
            item: Wikidata API返回的实体项
            original_entity: 原始实体
            
        Returns:
            知识库实体对象
        """
        try:
            entity = KnowledgeBaseEntity(
                kb_id=item.get('id', ''),
                kb_name='wikidata',
                uri=item.get('concepturi', ''),
                label=item.get('label', ''),
                description=item.get('description', '')
            )
            
            # 添加别名
            if 'aliases' in item:
                entity.aliases = {alias for alias in item['aliases']}
            
            # 计算置信度
            entity.confidence = self._calculate_wikidata_confidence(entity, original_entity)
            
            return entity
            
        except Exception as e:
            logger.warning(f"解析Wikidata实体失败: {str(e)}")
            return None
    
    def _parse_dbpedia_entity(self, item: Dict[str, Any], original_entity: Any) -> Optional[KnowledgeBaseEntity]:
        """解析DBpedia实体
        
        Args:
            item: DBpedia API返回的实体项
            original_entity: 原始实体
            
        Returns:
            知识库实体对象
        """
        try:
            entity = KnowledgeBaseEntity(
                kb_id=item.get('uri', '').split('/')[-1],
                kb_name='dbpedia',
                uri=item.get('uri', ''),
                label=item.get('label', ''),
                description=item.get('comment', '')
            )
            
            # 添加类型
            if 'classes' in item:
                entity.types = {cls.get('uri', '') for cls in item['classes']}
            
            # 计算置信度
            entity.confidence = self._calculate_dbpedia_confidence(entity, original_entity)
            
            return entity
            
        except Exception as e:
            logger.warning(f"解析DBpedia实体失败: {str(e)}")
            return None
    
    def _calculate_wikidata_confidence(self, kb_entity: KnowledgeBaseEntity, 
                                     original_entity: Any) -> float:
        """计算Wikidata实体的置信度
        
        Args:
            kb_entity: 知识库实体
            original_entity: 原始实体
            
        Returns:
            置信度分数
        """
        confidence = 0.0
        
        # 基础相似度
        name_similarity = self._calculate_string_similarity(
            original_entity.name, kb_entity.label
        )
        confidence += name_similarity * 0.6
        
        # 精确匹配奖励
        if original_entity.name.lower() == kb_entity.label.lower():
            confidence += self.config.exact_match_bonus
        
        # 别名匹配奖励
        if hasattr(original_entity, 'aliases') and original_entity.aliases:
            for alias in original_entity.aliases:
                if alias.lower() in {a.lower() for a in kb_entity.aliases}:
                    confidence += self.config.alias_match_bonus
                    break
        
        # 描述质量奖励
        if kb_entity.description and len(kb_entity.description) > 20:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_dbpedia_confidence(self, kb_entity: KnowledgeBaseEntity, 
                                    original_entity: Any) -> float:
        """计算DBpedia实体的置信度
        
        Args:
            kb_entity: 知识库实体
            original_entity: 原始实体
            
        Returns:
            置信度分数
        """
        confidence = 0.0
        
        # 基础相似度
        name_similarity = self._calculate_string_similarity(
            original_entity.name, kb_entity.label
        )
        confidence += name_similarity * 0.6
        
        # 类型匹配奖励
        if hasattr(original_entity, 'entity_type') and original_entity.entity_type:
            expected_types = self.config.entity_type_mapping.get(
                original_entity.entity_type, []
            )
            if any(expected_type in kb_entity.types for expected_type in expected_types):
                confidence += self.config.type_match_bonus
        
        # 精确匹配奖励
        if original_entity.name.lower() == kb_entity.label.lower():
            confidence += self.config.exact_match_bonus
        
        return min(confidence, 1.0)
    
    def _calculate_string_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度
        
        Args:
            str1: 字符串1
            str2: 字符串2
            
        Returns:
            相似度分数 (0-1)
        """
        if not str1 or not str2:
            return 0.0
        
        # 简单的编辑距离相似度
        from difflib import SequenceMatcher
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def _rank_candidates(self, original_entity: Any, 
                        candidates: List[KnowledgeBaseEntity]) -> List[KnowledgeBaseEntity]:
        """对候选实体进行排序
        
        Args:
            original_entity: 原始实体
            candidates: 候选实体列表
            
        Returns:
            排序后的候选实体列表
        """
        # 按置信度降序排序
        return sorted(candidates, key=lambda x: x.confidence, reverse=True)
    
    def _generate_cache_key(self, entity_name: str, entity_type: str) -> str:
        """生成缓存键
        
        Args:
            entity_name: 实体名称
            entity_type: 实体类型
            
        Returns:
            缓存键
        """
        key_string = f"{entity_name}_{entity_type}"
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def _load_cache(self):
        """加载缓存"""
        cache_file = Path('data/entity_linking_cache.json')
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                # 转换为对象
                for key, data in cache_data.items():
                    result = EntityLinkingResult(**data)
                    if result.best_match:
                        result.best_match = KnowledgeBaseEntity(**result.best_match)
                    result.candidates = [
                        KnowledgeBaseEntity(**candidate) 
                        for candidate in result.candidates
                    ]
                    self.cache[key] = result
                
                logger.info(f"加载缓存: {len(self.cache)} 条记录")
                
            except Exception as e:
                logger.warning(f"加载缓存失败: {str(e)}")
    
    def _save_cache(self):
        """保存缓存"""
        cache_file = Path('data/entity_linking_cache.json')
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 转换为字典
            cache_data = {}
            for key, result in self.cache.items():
                cache_data[key] = {
                    'entity_id': result.entity_id,
                    'entity_name': result.entity_name,
                    'candidates': [candidate.__dict__ for candidate in result.candidates],
                    'best_match': result.best_match.__dict__ if result.best_match else None,
                    'linking_confidence': result.linking_confidence,
                    'linking_method': result.linking_method,
                    'timestamp': result.timestamp
                }
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.info(f"保存缓存: {len(cache_data)} 条记录")
            
        except Exception as e:
            logger.warning(f"保存缓存失败: {str(e)}")
    
    def get_linking_statistics(self, results: Dict[str, EntityLinkingResult]) -> Dict[str, Any]:
        """获取链接统计信息
        
        Args:
            results: 链接结果字典
            
        Returns:
            统计信息
        """
        total_entities = len(results)
        linked_entities = len([r for r in results.values() if r.best_match])
        
        kb_distribution = Counter()
        confidence_scores = []
        
        for result in results.values():
            if result.best_match:
                kb_distribution[result.best_match.kb_name] += 1
                confidence_scores.append(result.linking_confidence)
        
        stats = {
            'total_entities': total_entities,
            'linked_entities': linked_entities,
            'linking_rate': linked_entities / total_entities if total_entities > 0 else 0,
            'kb_distribution': dict(kb_distribution),
            'average_confidence': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
            'min_confidence': min(confidence_scores) if confidence_scores else 0,
            'max_confidence': max(confidence_scores) if confidence_scores else 0
        }
        
        return stats
    
    def export_linking_results(self, results: Dict[str, EntityLinkingResult], 
                              filepath: str):
        """导出链接结果
        
        Args:
            results: 链接结果字典
            filepath: 导出文件路径
        """
        export_data = {
            'metadata': {
                'timestamp': str(datetime.now()),
                'total_entities': len(results),
                'linked_entities': len([r for r in results.values() if r.best_match])
            },
            'statistics': self.get_linking_statistics(results),
            'results': {}
        }
        
        for entity_id, result in results.items():
            export_data['results'][entity_id] = {
                'entity_name': result.entity_name,
                'best_match': result.best_match.__dict__ if result.best_match else None,
                'linking_confidence': result.linking_confidence,
                'linking_method': result.linking_method,
                'candidates_count': len(result.candidates)
            }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"链接结果已导出到: {filepath}")

def main():
    """主函数 - 演示实体链接功能"""
    # 创建实体链接器
    config = EntityLinkingConfig(
        min_confidence_threshold=0.6,
        max_candidates_per_entity=5
    )
    linker = EntityLinker(config)
    
    # 模拟实体数据
    from knowledge_graph.entity_extraction import Entity
    
    entities = {
        'entity_1': Entity(
            id='entity_1',
            name='腾讯控股有限公司',
            entity_type='company',
            aliases={'腾讯', 'Tencent'},
            attributes={'industry': '互联网'},
            source_events=['event_1']
        ),
        'entity_2': Entity(
            id='entity_2',
            name='马化腾',
            entity_type='person',
            aliases={'Pony Ma'},
            attributes={'title': 'CEO'},
            source_events=['event_2']
        ),
        'entity_3': Entity(
            id='entity_3',
            name='深圳',
            entity_type='location',
            aliases={'深圳市', 'Shenzhen'},
            attributes={'country': '中国'},
            source_events=['event_3']
        )
    }
    
    # 执行实体链接
    results = linker.link_entities(entities)
    
    # 显示结果
    print(f"实体链接完成，处理 {len(entities)} 个实体")
    
    for entity_id, result in results.items():
        print(f"\n实体: {result.entity_name}")
        if result.best_match:
            print(f"  最佳匹配: {result.best_match.label}")
            print(f"  知识库: {result.best_match.kb_name}")
            print(f"  URI: {result.best_match.uri}")
            print(f"  置信度: {result.linking_confidence:.3f}")
            if result.best_match.description:
                print(f"  描述: {result.best_match.description[:100]}...")
        else:
            print("  未找到匹配")
        
        print(f"  候选数量: {len(result.candidates)}")
    
    # 显示统计信息
    stats = linker.get_linking_statistics(results)
    print(f"\n链接统计: {stats}")

if __name__ == "__main__":
    main()