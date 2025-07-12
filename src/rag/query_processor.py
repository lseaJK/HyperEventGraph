# -*- coding: utf-8 -*-
"""
查询处理器 - 实现自然语言查询解析和意图识别
对应todo.md任务：5.1.1-5.1.3
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import jieba
import jieba.posseg as pseg
from datetime import datetime, timedelta


class QueryType(Enum):
    """查询类型枚举"""
    EVENT_SEARCH = "event_search"  # 事件搜索
    RELATION_QUERY = "relation_query"  # 关系查询
    CAUSAL_ANALYSIS = "causal_analysis"  # 因果分析
    TEMPORAL_ANALYSIS = "temporal_analysis"  # 时序分析
    ENTITY_QUERY = "entity_query"  # 实体查询
    GENERAL_QA = "general_qa"  # 一般问答


@dataclass
class QueryIntent:
    """查询意图结构"""
    query_type: QueryType
    confidence: float
    entities: List[str]
    time_range: Optional[Tuple[datetime, datetime]]
    keywords: List[str]
    original_query: str
    processed_query: str


class QueryProcessor:
    """查询处理器 - 负责自然语言查询的解析和理解"""
    
    def __init__(self):
        """初始化查询处理器"""
        # 初始化jieba分词
        jieba.initialize()
        
        # 查询类型关键词映射
        self.query_type_keywords = {
            QueryType.EVENT_SEARCH: [
                "事件", "发生", "什么事", "事情", "情况", "活动"
            ],
            QueryType.RELATION_QUERY: [
                "关系", "关联", "联系", "相关", "影响", "关于"
            ],
            QueryType.CAUSAL_ANALYSIS: [
                "原因", "导致", "因为", "由于", "造成", "引起", "为什么"
            ],
            QueryType.TEMPORAL_ANALYSIS: [
                "时间", "何时", "什么时候", "之前", "之后", "期间", "顺序"
            ],
            QueryType.ENTITY_QUERY: [
                "公司", "企业", "人员", "组织", "机构", "个人"
            ]
        }
        
        # 时间表达式模式
        self.time_patterns = {
            r'(\d{4})年': lambda m: datetime(int(m.group(1)), 1, 1),
            r'(\d{4})年(\d{1,2})月': lambda m: datetime(int(m.group(1)), int(m.group(2)), 1),
            r'(\d{4})-(\d{1,2})-(\d{1,2})': lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
            r'最近(\d+)天': lambda m: (datetime.now() - timedelta(days=int(m.group(1))), datetime.now()),
            r'最近(\d+)个月': lambda m: (datetime.now() - timedelta(days=int(m.group(1))*30), datetime.now()),
            r'去年': lambda m: (datetime(datetime.now().year-1, 1, 1), datetime(datetime.now().year-1, 12, 31))
        }
        
        # 同义词词典（简化版）
        self.synonyms = {
            "公司": ["企业", "公司", "集团", "有限公司", "股份公司"],
            "合作": ["合作", "协作", "联合", "合伙", "联盟"],
            "投资": ["投资", "融资", "注资", "入股", "参股"],
            "收购": ["收购", "并购", "兼并", "购买", "收买"]
        }
    
    def process_query(self, query: str) -> QueryIntent:
        """处理查询，返回查询意图"""
        # 1. 预处理查询文本
        processed_query = self._preprocess_query(query)
        
        # 2. 识别查询类型
        query_type, confidence = self._identify_query_type(processed_query)
        
        # 3. 提取实体
        entities = self._extract_entities(processed_query)
        
        # 4. 提取时间信息
        time_range = self._extract_time_range(processed_query)
        
        # 5. 提取关键词
        keywords = self._extract_keywords(processed_query)
        
        # 6. 查询扩展
        expanded_keywords = self._expand_query(keywords)
        
        return QueryIntent(
            query_type=query_type,
            confidence=confidence,
            entities=entities,
            time_range=time_range,
            keywords=expanded_keywords,
            original_query=query,
            processed_query=processed_query
        )
    
    def _preprocess_query(self, query: str) -> str:
        """预处理查询文本"""
        # 去除多余空格和标点
        query = re.sub(r'\s+', ' ', query.strip())
        query = re.sub(r'[？?！!。.，,；;：:]', '', query)
        return query
    
    def _identify_query_type(self, query: str) -> Tuple[QueryType, float]:
        """识别查询类型"""
        scores = {}
        
        for query_type, keywords in self.query_type_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in query:
                    score += 1
            scores[query_type] = score / len(keywords) if keywords else 0
        
        # 找到得分最高的查询类型
        best_type = max(scores, key=scores.get)
        confidence = scores[best_type]
        
        # 如果没有明确匹配，默认为一般问答
        if confidence == 0:
            return QueryType.GENERAL_QA, 0.5
        
        return best_type, min(confidence * 2, 1.0)  # 调整置信度
    
    def _extract_entities(self, query: str) -> List[str]:
        """提取实体（简化版实现）"""
        entities = []
        
        # 使用jieba进行词性标注
        words = pseg.cut(query)
        
        for word, flag in words:
            # 提取名词、机构名、人名等
            if flag in ['n', 'nr', 'ns', 'nt', 'nz'] and len(word) > 1:
                entities.append(word)
        
        # 去重并过滤
        entities = list(set(entities))
        entities = [e for e in entities if len(e) > 1 and not e.isdigit()]
        
        return entities
    
    def _extract_time_range(self, query: str) -> Optional[Tuple[datetime, datetime]]:
        """提取时间范围"""
        for pattern, parser in self.time_patterns.items():
            match = re.search(pattern, query)
            if match:
                try:
                    result = parser(match)
                    if isinstance(result, tuple):
                        return result
                    else:
                        # 单个日期，返回当天范围
                        return (result, result + timedelta(days=1))
                except:
                    continue
        
        return None
    
    def _extract_keywords(self, query: str) -> List[str]:
        """提取关键词"""
        # 使用jieba分词
        words = jieba.cut(query)
        
        # 过滤停用词和短词
        stopwords = {'的', '了', '在', '是', '有', '和', '与', '或', '但', '而', '等'}
        keywords = []
        
        for word in words:
            if len(word) > 1 and word not in stopwords:
                keywords.append(word)
        
        return keywords
    
    def _expand_query(self, keywords: List[str]) -> List[str]:
        """查询扩展 - 添加同义词"""
        expanded = set(keywords)
        
        for keyword in keywords:
            # 查找同义词
            for base_word, synonyms in self.synonyms.items():
                if keyword in synonyms:
                    expanded.update(synonyms)
                    break
        
        return list(expanded)
    
    def get_query_suggestions(self, partial_query: str) -> List[str]:
        """获取查询建议（简化版）"""
        suggestions = [
            f"{partial_query}的原因是什么？",
            f"{partial_query}相关的事件有哪些？",
            f"{partial_query}的影响是什么？",
            f"{partial_query}发生在什么时候？"
        ]
        
        return suggestions[:3]  # 返回前3个建议