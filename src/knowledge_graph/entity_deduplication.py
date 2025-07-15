#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能实体去重和合并模块

提供高级的实体去重、相似度计算和智能合并功能，
支持多种匹配策略和可配置的合并规则。

作者: HyperEventGraph Team
日期: 2024-01-15
"""

import re
import json
import difflib
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
from pathlib import Path
import jieba
from fuzzywuzzy import fuzz, process
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EntitySimilarity:
    """实体相似度结果"""
    entity1_id: str
    entity2_id: str
    similarity_score: float
    match_type: str  # exact, fuzzy, semantic, alias
    confidence: float
    reasons: List[str] = field(default_factory=list)

@dataclass
class MergeCandidate:
    """合并候选对象"""
    primary_entity_id: str
    secondary_entity_id: str
    similarity: EntitySimilarity
    merge_strategy: str
    conflicts: List[str] = field(default_factory=list)

@dataclass
class DeduplicationConfig:
    """去重配置"""
    # 相似度阈值
    exact_match_threshold: float = 1.0
    fuzzy_match_threshold: float = 0.85
    semantic_match_threshold: float = 0.8
    alias_match_threshold: float = 0.9
    
    # 合并策略
    auto_merge_threshold: float = 0.95
    manual_review_threshold: float = 0.7
    
    # 实体类型特定配置
    company_name_similarity_threshold: float = 0.9
    person_name_similarity_threshold: float = 0.85
    location_similarity_threshold: float = 0.8
    
    # 特殊处理
    ignore_case: bool = True
    normalize_whitespace: bool = True
    remove_punctuation: bool = True
    
    # 公司名称标准化
    company_suffixes: List[str] = field(default_factory=lambda: [
        '有限公司', '股份有限公司', '集团有限公司', '科技有限公司',
        '投资有限公司', '控股有限公司', '实业有限公司', '贸易有限公司',
        'Ltd', 'Co.', 'Inc', 'Corp', 'LLC', 'Group', 'Holdings'
    ])
    
    # 人名标准化
    title_prefixes: List[str] = field(default_factory=lambda: [
        '先生', '女士', '博士', '教授', '总裁', '董事长', '总经理', 
        'Mr.', 'Ms.', 'Dr.', 'Prof.', 'CEO', 'CTO', 'CFO'
    ])

class EntityDeduplicator:
    """���能实体去重器"""
    
    def __init__(self, config: Optional[DeduplicationConfig] = None):
        """初始化去重器
        
        Args:
            config: 去重配置，如果为None则使用默认配置
        """
        self.config = config or DeduplicationConfig()
        self.similarity_cache: Dict[Tuple[str, str], EntitySimilarity] = {}
        self.merge_history: List[Dict[str, Any]] = []
        
        # 初始化jieba分词
        jieba.setLogLevel(logging.WARNING)
    
    def deduplicate_entities(self, entities: Dict[str, Any]) -> Tuple[Dict[str, Any], List[MergeCandidate]]:
        """对实体进行去重
        
        Args:
            entities: 实体字典 {entity_id: entity_object}
            
        Returns:
            去重后的实体字典和合并候选列表
        """
        logger.info(f"开始对 {len(entities)} 个实体进行去重")
        
        # 1. 计算实体间相似度
        similarities = self._calculate_all_similarities(entities)
        
        # 2. 识别合并候选
        merge_candidates = self._identify_merge_candidates(similarities)
        
        # 3. 执行自动合并
        deduplicated_entities, auto_merged = self._execute_auto_merge(
            entities, merge_candidates
        )
        
        # 4. 返���需要手动审核的候选
        manual_review_candidates = [
            candidate for candidate in merge_candidates 
            if candidate not in auto_merged
        ]
        
        logger.info(f"去重完成: {len(entities)} -> {len(deduplicated_entities)} 个实体")
        logger.info(f"自动合并: {len(auto_merged)} 对")
        logger.info(f"需要手动审核: {len(manual_review_candidates)} 对")
        
        return deduplicated_entities, manual_review_candidates
    
    def _calculate_all_similarities(self, entities: Dict[str, Any]) -> List[EntitySimilarity]:
        """计算所有实体间的相似度
        
        Args:
            entities: 实体字典
            
        Returns:
            相似度结果列表
        """
        similarities = []
        entity_ids = list(entities.keys())
        
        for i, entity1_id in enumerate(entity_ids):
            for entity2_id in entity_ids[i+1:]:
                # 检查缓存
                cache_key = tuple(sorted([entity1_id, entity2_id]))
                if cache_key in self.similarity_cache:
                    similarities.append(self.similarity_cache[cache_key])
                    continue
                
                entity1 = entities[entity1_id]
                entity2 = entities[entity2_id]
                
                # 只比较相同类型的实体
                if entity1.entity_type == entity2.entity_type:
                    similarity = self._calculate_entity_similarity(entity1, entity2)
                    if similarity.similarity_score > 0:
                        similarities.append(similarity)
                        self.similarity_cache[cache_key] = similarity
        
        return similarities
    
    def _calculate_entity_similarity(self, entity1: Any, entity2: Any) -> EntitySimilarity:
        """计算两个实体的相似度
        
        Args:
            entity1: 实体1
            entity2: 实体2
            
        Returns:
            相似度结果
        """
        # 确保实体类型相同
        if entity1.entity_type != entity2.entity_type:
            return EntitySimilarity(
                entity1_id=getattr(entity1, 'id', 'unknown'),
                entity2_id=getattr(entity2, 'id', 'unknown'),
                similarity_score=0.0,
                match_type="none",
                confidence=0.0,
                reasons=["实体类型不匹配"]
            )

        reasons = []
        max_score = 0.0
        best_match_type = "none"
        
        # 1. 精确匹配
        exact_score = self._exact_match_score(entity1, entity2)
        if exact_score > max_score:
            max_score = exact_score
            best_match_type = "exact"
            if exact_score == 1.0:
                reasons.append("名称完全匹配")
        
        # 2. 别名匹配
        alias_score = self._alias_match_score(entity1, entity2)
        if alias_score > max_score:
            max_score = alias_score
            best_match_type = "alias"
            if alias_score > self.config.alias_match_threshold:
                reasons.append("别名匹配")
        
        # 3. 模糊匹配
        fuzzy_score = self._fuzzy_match_score(entity1, entity2)
        if fuzzy_score > max_score:
            max_score = fuzzy_score
            best_match_type = "fuzzy"
            if fuzzy_score > self.config.fuzzy_match_threshold:
                reasons.append(f"模糊匹配 (相似度: {fuzzy_score:.2f})")
        
        # 4. 语义匹配
        semantic_score = self._semantic_match_score(entity1, entity2)
        if semantic_score > max_score:
            max_score = semantic_score
            best_match_type = "semantic"
            if semantic_score > self.config.semantic_match_threshold:
                reasons.append(f"语义匹配 (相似度: {semantic_score:.2f})")
        
        # 计算置信度
        confidence = self._calculate_confidence(entity1, entity2, max_score, best_match_type)
        
        return EntitySimilarity(
            entity1_id=getattr(entity1, 'id', 'unknown'),
            entity2_id=getattr(entity2, 'id', 'unknown'),
            similarity_score=max_score,
            match_type=best_match_type,
            confidence=confidence,
            reasons=reasons
        )
    
    def _exact_match_score(self, entity1: Any, entity2: Any) -> float:
        """计算精确匹配分数"""
        name1 = self._normalize_name(entity1.name)
        name2 = self._normalize_name(entity2.name)
        
        return 1.0 if name1 == name2 else 0.0
    
    def _alias_match_score(self, entity1: Any, entity2: Any) -> float:
        """计算别名匹配分数"""
        aliases1 = {self._normalize_name(alias) for alias in getattr(entity1, 'aliases', set())}
        aliases2 = {self._normalize_name(alias) for alias in getattr(entity2, 'aliases', set())}
        
        # 添加主名称到别名集合
        aliases1.add(self._normalize_name(entity1.name))
        aliases2.add(self._normalize_name(entity2.name))
        
        # 计算交集比例
        intersection = aliases1 & aliases2
        union = aliases1 | aliases2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _fuzzy_match_score(self, entity1: Any, entity2: Any) -> float:
        """计算模糊匹配分数"""
        name1 = self._normalize_name(entity1.name)
        name2 = self._normalize_name(entity2.name)
        
        # 使用多种模糊匹配算法
        ratio_score = fuzz.ratio(name1, name2) / 100.0
        partial_ratio_score = fuzz.partial_ratio(name1, name2) / 100.0
        token_sort_score = fuzz.token_sort_ratio(name1, name2) / 100.0
        token_set_score = fuzz.token_set_ratio(name1, name2) / 100.0
        
        # 根据实体类型选择最佳算法
        if entity1.entity_type == 'company':
            return max(token_sort_score, token_set_score)
        elif entity1.entity_type == 'person':
            return max(ratio_score, partial_ratio_score)
        else:
            return max(ratio_score, partial_ratio_score, token_sort_score)
    
    def _semantic_match_score(self, entity1: Any, entity2: Any) -> float:
        """计算语义匹配分数"""
        # 基于词汇重叠的简单语义匹配
        tokens1 = set(jieba.lcut(entity1.name))
        tokens2 = set(jieba.lcut(entity2.name))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _normalize_name(self, name: str) -> str:
        """标准化名称"""
        if not name:
            return ""
        
        normalized = name
        
        # 转换为小写
        if self.config.ignore_case:
            normalized = normalized.lower()

        # 移除公司后缀
        for suffix in self.config.company_suffixes:
            pattern = r'\s*' + re.escape(suffix.lower() if self.config.ignore_case else suffix) + '$'
            normalized = re.sub(pattern, '', normalized)

        # 标准化空白字符
        if self.config.normalize_whitespace:
            normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # 移除标点符号
        if self.config.remove_punctuation:
            normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized.strip()
    
    def _calculate_confidence(self, entity1: Any, entity2: Any, score: float, match_type: str) -> float:
        """计算匹配置信度"""
        base_confidence = score
        
        # 根据匹配类型调整置信度
        if match_type == "exact":
            base_confidence *= 1.0
        elif match_type == "alias":
            base_confidence *= 0.95
        elif match_type == "fuzzy":
            base_confidence *= 0.8
        elif match_type == "semantic":
            base_confidence *= 0.7
        
        # 根据实体信息丰富度调整
        entity1_richness = self._calculate_entity_richness(entity1)
        entity2_richness = self._calculate_entity_richness(entity2)
        richness_factor = min(entity1_richness, entity2_richness)
        
        return min(base_confidence * (0.8 + 0.2 * richness_factor), 1.0)
    
    def _calculate_entity_richness(self, entity: Any) -> float:
        """计算实体信息丰富度"""
        richness = 0.0
        
        # 名称长度
        if len(entity.name) > 2:
            richness += 0.2
        
        # 别名数量
        aliases_count = len(getattr(entity, 'aliases', set()))
        richness += min(aliases_count * 0.1, 0.3)
        
        # 属性数量
        attributes_count = len(getattr(entity, 'attributes', {}))
        richness += min(attributes_count * 0.1, 0.3)
        
        # 来源事件数量
        events_count = len(getattr(entity, 'source_events', []))
        richness += min(events_count * 0.05, 0.2)
        
        return min(richness, 1.0)
    
    def _identify_merge_candidates(self, similarities: List[EntitySimilarity]) -> List[MergeCandidate]:
        """识别合并候选"""
        candidates = []
        
        for similarity in similarities:
            if similarity.similarity_score >= self.config.manual_review_threshold:
                # 确定主要实体和次要实体
                primary_id, secondary_id = self._determine_merge_priority(
                    similarity.entity1_id, similarity.entity2_id
                )
                
                # 确定合并策略
                if similarity.similarity_score >= self.config.auto_merge_threshold:
                    merge_strategy = "auto"
                else:
                    merge_strategy = "manual"
                
                candidate = MergeCandidate(
                    primary_entity_id=primary_id,
                    secondary_entity_id=secondary_id,
                    similarity=similarity,
                    merge_strategy=merge_strategy
                )
                
                candidates.append(candidate)
        
        return candidates
    
    def _determine_merge_priority(self, entity1_id: str, entity2_id: str) -> Tuple[str, str]:
        """确定合并优先级（哪个作为主要实体）"""
        # 简单策略：ID较小的作为主要实体
        # 实际应用中可以根据实体信息丰富度、可信度等因素决定
        if entity1_id < entity2_id:
            return entity1_id, entity2_id
        else:
            return entity2_id, entity1_id
    
    def _execute_auto_merge(self, entities: Dict[str, Any], 
                           candidates: List[MergeCandidate]) -> Tuple[Dict[str, Any], List[MergeCandidate]]:
        """执行自动合并"""
        merged_entities = entities.copy()
        auto_merged = []
        
        for candidate in candidates:
            if candidate.merge_strategy == "auto":
                # 执行合并
                success = self._merge_entities(
                    merged_entities,
                    candidate.primary_entity_id,
                    candidate.secondary_entity_id
                )
                
                if success:
                    auto_merged.append(candidate)
                    
                    # 记录合并历史
                    self.merge_history.append({
                        'timestamp': str(datetime.now()),
                        'primary_entity': candidate.primary_entity_id,
                        'secondary_entity': candidate.secondary_entity_id,
                        'similarity_score': candidate.similarity.similarity_score,
                        'match_type': candidate.similarity.match_type,
                        'strategy': 'auto'
                    })
        
        return merged_entities, auto_merged
    
    def _merge_entities(self, entities: Dict[str, Any], primary_id: str, secondary_id: str) -> bool:
        """合并两个实体"""
        try:
            if primary_id not in entities or secondary_id not in entities:
                return False
            
            primary_entity = entities[primary_id]
            secondary_entity = entities[secondary_id]
            
            # 合并别名
            if hasattr(primary_entity, 'aliases') and hasattr(secondary_entity, 'aliases'):
                primary_entity.aliases.update(secondary_entity.aliases)
                primary_entity.aliases.add(secondary_entity.name)
            
            # 合并属性
            if hasattr(primary_entity, 'attributes') and hasattr(secondary_entity, 'attributes'):
                for key, value in secondary_entity.attributes.items():
                    if key not in primary_entity.attributes:
                        primary_entity.attributes[key] = value
            
            # 合并来源事件
            if hasattr(primary_entity, 'source_events') and hasattr(secondary_entity, 'source_events'):
                primary_entity.source_events.extend(secondary_entity.source_events)
                primary_entity.source_events = list(set(primary_entity.source_events))  # 去重
            
            # 删除次要实体
            del entities[secondary_id]
            
            logger.debug(f"成功合并实体: {secondary_id} -> {primary_id}")
            return True
            
        except Exception as e:
            logger.error(f"合并实体失败: {primary_id}, {secondary_id}, 错误: {str(e)}")
            return False
    
    def manual_merge_entities(self, entities: Dict[str, Any], 
                             primary_id: str, secondary_id: str) -> bool:
        """手动合并实体"""
        success = self._merge_entities(entities, primary_id, secondary_id)
        
        if success:
            # 记录手动合并历史
            self.merge_history.append({
                'timestamp': str(datetime.now()),
                'primary_entity': primary_id,
                'secondary_entity': secondary_id,
                'strategy': 'manual'
            })
        
        return success
    
    def get_merge_statistics(self) -> Dict[str, Any]:
        """获取合并统计信息"""
        if not self.merge_history:
            return {'total_merges': 0}
        
        stats = {
            'total_merges': len(self.merge_history),
            'auto_merges': len([h for h in self.merge_history if h['strategy'] == 'auto']),
            'manual_merges': len([h for h in self.merge_history if h['strategy'] == 'manual']),
            'match_types': Counter([h.get('match_type', 'unknown') for h in self.merge_history]),
            'average_similarity': sum([h.get('similarity_score', 0) for h in self.merge_history]) / len(self.merge_history)
        }
        
        return stats
    
    def export_merge_report(self, filepath: str):
        """导出合并报告"""
        report = {
            'statistics': self.get_merge_statistics(),
            'merge_history': self.merge_history,
            'config': {
                'fuzzy_match_threshold': self.config.fuzzy_match_threshold,
                'auto_merge_threshold': self.config.auto_merge_threshold,
                'manual_review_threshold': self.config.manual_review_threshold
            }
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"合并报告已导出到: {filepath}")

def main():
    """主函数 - 演示去重功能"""
    # 创建去重器
    config = DeduplicationConfig(
        fuzzy_match_threshold=0.8,
        auto_merge_threshold=0.9
    )
    deduplicator = EntityDeduplicator(config)
    
    # 模拟实体数据
    from knowledge_graph.entity_extraction import Entity
    
    entities = {
        'entity_1': Entity(
            name='腾讯控股有限公司',
            entity_type='company',
            aliases={'腾讯', 'Tencent'},
            attributes={'industry': '互联网'},
            source_events=['event_1']
        ),
        'entity_2': Entity(
            name='腾讯控股',
            entity_type='company',
            aliases={'腾讯公司'},
            attributes={'location': '深圳'},
            source_events=['event_2']
        ),
        'entity_3': Entity(
            name='阿里巴巴集团',
            entity_type='company',
            aliases={'阿里巴巴', 'Alibaba'},
            attributes={'industry': '电商'},
            source_events=['event_3']
        )
    }
    
    # 执行去重
    deduplicated, candidates = deduplicator.deduplicate_entities(entities)
    
    print(f"原始实体数量: {len(entities)}")
    print(f"去重后实体数量: {len(deduplicated)}")
    print(f"需要手动审核的候选: {len(candidates)}")
    
    # 显示合并统计
    stats = deduplicator.get_merge_statistics()
    print(f"合并统计: {stats}")

if __name__ == "__main__":
    main()
