"""事件层管理器

负责管理事件层的具体事件实例，包括：
- 事件的存储和检索
- 事件相似性计算
- 事件关系分析
- 时间序列查询
"""

from typing import Dict, List, Any, Optional, Tuple, Set, Union
import logging
from datetime import datetime, timedelta
import math
from collections import defaultdict, Counter
import threading
import time
from functools import lru_cache
import hashlib
import json

from ..models.event_data_model import Event, EventType, Entity, EventRelation

# 条件导入Neo4j存储
try:
    from ..storage.neo4j_event_storage import Neo4jEventStorage
except ImportError:
    # 如果neo4j不可用，创建一个占位符类
    class Neo4jEventStorage:
        def __init__(self, *args, **kwargs):
            raise ImportError("Neo4j driver not available. Please install neo4j package.")
        
        def store_event(self, event):
            raise NotImplementedError("Neo4j storage not available")
        
        def get_event(self, event_id):
            raise NotImplementedError("Neo4j storage not available")
        
        def query_events(self, **kwargs):
            raise NotImplementedError("Neo4j storage not available")
        
        def get_event_relations(self, event_id):
            raise NotImplementedError("Neo4j storage not available")
        
        def create_event_relation(self, relation):
            raise NotImplementedError("Neo4j storage not available")
        
        def get_database_statistics(self):
            raise NotImplementedError("Neo4j storage not available")


class EventLayerManager:
    """事件层管理器"""
    
    def __init__(self, storage: Neo4jEventStorage, cache_size: int = 1000, cache_ttl: int = 3600):
        self.storage = storage
        self.logger = logging.getLogger(__name__)
        
        # 缓存机制
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self._event_cache = {}
        self._query_cache = {}
        self._similarity_cache = {}
        self._cache_timestamps = {}
        self._cache_lock = threading.RLock()
        
        # 性能统计
        self.performance_stats = {
            "cache_hits": 0,
            "cache_misses": 0,
            "total_queries": 0,
            "avg_query_time": 0.0,
            "batch_operations": 0
        }
        
        # 事件聚合缓存
        self._aggregation_cache = {}
        self._last_aggregation_update = None
    
    def _get_from_cache(self, cache_type: str, key: str) -> Any:
        """从缓存获取数据"""
        with self._cache_lock:
            cache = getattr(self, f'_{cache_type}_cache', {})
            if key in cache:
                # 检查缓存是否过期
                timestamp = self._cache_timestamps.get(f'{cache_type}_{key}')
                if timestamp and (time.time() - timestamp) < self.cache_ttl:
                    return cache[key]
                else:
                    # 清除过期缓存
                    cache.pop(key, None)
                    self._cache_timestamps.pop(f'{cache_type}_{key}', None)
            return None
    
    def _update_event_cache(self, event_id: str, event: Event):
        """更新事件缓存"""
        with self._cache_lock:
            # 检查缓存大小限制
            if len(self._event_cache) >= self.cache_size:
                # 移除最旧的缓存项
                oldest_key = min(self._cache_timestamps.keys(), 
                               key=lambda k: self._cache_timestamps[k] if k.startswith('event_') else float('inf'))
                if oldest_key.startswith('event_'):
                    cache_key = oldest_key.replace('event_', '')
                    self._event_cache.pop(cache_key, None)
                    self._cache_timestamps.pop(oldest_key, None)
            
            self._event_cache[event_id] = event
            self._cache_timestamps[f'event_{event_id}'] = time.time()
    
    def _invalidate_query_cache(self):
        """清除查询缓存"""
        with self._cache_lock:
            self._query_cache.clear()
            # 清除查询相关的时间戳
            keys_to_remove = [k for k in self._cache_timestamps.keys() if k.startswith('query_')]
            for key in keys_to_remove:
                self._cache_timestamps.pop(key, None)
    
    def _update_performance_stats(self, execution_time: float):
        """更新性能统计"""
        self.performance_stats["total_queries"] += 1
        total_time = self.performance_stats["avg_query_time"] * (self.performance_stats["total_queries"] - 1)
        self.performance_stats["avg_query_time"] = (total_time + execution_time) / self.performance_stats["total_queries"]
        
    def add_event(self, event: Event) -> bool:
        """添加事件到事件层"""
        try:
            # 存储事件
            success = self.storage.store_event(event)
            if success:
                event_id = getattr(event, 'id', getattr(event, 'event_id', 'unknown'))
                self.logger.info(f"事件已添加到事件层: {event_id}")
                
                # 更新缓存
                self._update_event_cache(event_id, event)
                # 清除相关查询缓存
                self._invalidate_query_cache()
                
            return success
        except Exception as e:
            self.logger.error(f"添加事件失败: {str(e)}")
            return False
    
    def batch_add_events(self, events: List[Event]) -> Dict[str, bool]:
        """批量添加事件
        
        Args:
            events: 事件列表
            
        Returns:
            Dict[str, bool]: 事件ID -> 是否成功
        """
        # 调用存储层的batch_store_events方法（如果存在）
        if hasattr(self.storage, 'batch_store_events'):
            return self.storage.batch_store_events(events)
        else:
            # 回退到现有的批量添加方法
            return self.add_events_batch(events)
    
    def add_events_batch(self, events: List[Event]) -> Dict[str, bool]:
        """批量添加事件
        
        Args:
            events: 事件列表
            
        Returns:
            Dict[str, bool]: 事件ID -> 是否成功
        """
        start_time = time.time()
        results = {}
        
        try:
            self.performance_stats["batch_operations"] += 1
            
            # 批量存储到数据库
            if hasattr(self.storage, 'store_events_batch'):
                # 如果存储层支持批量操作
                batch_results = self.storage.store_events_batch(events)
                results.update(batch_results)
            else:
                # 逐个存储
                for event in events:
                    event_id = getattr(event, 'id', getattr(event, 'event_id', f'event_{len(results)}'))
                    success = self.storage.store_event(event)
                    results[event_id] = success
                    
                    if success:
                        # 更新缓存
                        self._update_event_cache(event_id, event)
            
            # 清除查询缓存
            self._invalidate_query_cache()
            
            success_count = sum(1 for success in results.values() if success)
            self.logger.info(f"批量添加事件完成: {success_count}/{len(events)} 成功")
            
            # 更新性能统计
            execution_time = time.time() - start_time
            self._update_performance_stats(execution_time)
            
            return results
            
        except Exception as e:
            self.logger.error(f"批量添加事件失败: {str(e)}")
            return {getattr(event, 'id', f'event_{i}'): False for i, event in enumerate(events)}
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """获取单个事件"""
        start_time = time.time()
        
        try:
            # 检查缓存
            cached_event = self._get_from_cache('event', event_id)
            if cached_event is not None:
                self.performance_stats["cache_hits"] += 1
                return cached_event
            
            self.performance_stats["cache_misses"] += 1
            
            # 从存储层获取
            event = self.storage.get_event(event_id)
            if event:
                self.logger.debug(f"获取事件: {event_id}")
                # 更新缓存
                self._update_event_cache(event_id, event)
            
            # 更新性能统计
            execution_time = time.time() - start_time
            self._update_performance_stats(execution_time)
            
            return event
        except Exception as e:
            self.logger.error(f"获取事件失败 {event_id}: {str(e)}")
            return None
    
    def get_events_batch(self, event_ids: List[str]) -> Dict[str, Optional[Event]]:
        """批量获取事件
        
        Args:
            event_ids: 事件ID列表
            
        Returns:
            Dict[str, Optional[Event]]: 事件ID -> 事件对象
        """
        start_time = time.time()
        results = {}
        cache_misses = []
        
        try:
            self.performance_stats["batch_operations"] += 1
            
            # 首先检查缓存
            for event_id in event_ids:
                cached_event = self._get_from_cache('event', event_id)
                if cached_event is not None:
                    results[event_id] = cached_event
                    self.performance_stats["cache_hits"] += 1
                else:
                    cache_misses.append(event_id)
                    self.performance_stats["cache_misses"] += 1
            
            # 批量获取缓存未命中的事件
            if cache_misses:
                if hasattr(self.storage, 'get_events_batch'):
                    # 如果存储层支持批量操作
                    batch_events = self.storage.get_events_batch(cache_misses)
                    for event_id, event in batch_events.items():
                        results[event_id] = event
                        if event:
                            self._update_event_cache(event_id, event)
                else:
                    # 逐个获取
                    for event_id in cache_misses:
                        event = self.storage.get_event(event_id)
                        results[event_id] = event
                        if event:
                            self._update_event_cache(event_id, event)
            
            # 更新性能统计
            execution_time = time.time() - start_time
            self._update_performance_stats(execution_time)
            
            self.logger.debug(f"批量获取事件完成: {len(results)} 个事件")
            return results
            
        except Exception as e:
            self.logger.error(f"批量获取事件失败: {str(e)}")
            return {event_id: None for event_id in event_ids}
    
    def query_events(self, 
                    event_type: str = None,
                    time_range: Tuple[datetime, datetime] = None,
                    participants: List[str] = None,
                    location: str = None,
                    properties: Dict[str, Any] = None,
                    limit: int = 100,
                    use_cache: bool = True) -> List[Event]:
        """查询事件
        
        Args:
            event_type: 事件类型
            time_range: 时间范围 (start, end)
            participants: 参与者列表
            location: 地点
            properties: 属性过滤
            limit: 结果限制
            use_cache: 是否使用缓存
            
        Returns:
            List[Event]: 匹配的事件列表
        """
        start_query_time = time.time()
        
        try:
            # 生成查询缓存键
            if use_cache:
                cache_key = self._generate_query_cache_key(
                    event_type, time_range, participants, location, properties, limit
                )
                cached_result = self._get_from_cache('query', cache_key)
                if cached_result is not None:
                    self.performance_stats["cache_hits"] += 1
                    return cached_result
                
                self.performance_stats["cache_misses"] += 1
            
            # 构建查询条件
            query_conditions = {}
            
            if event_type:
                query_conditions['event_type'] = event_type
            if location:
                query_conditions['location'] = location
            if properties:
                query_conditions.update(properties)
            
            # 处理event_type参数
            storage_event_type = None
            if event_type:
                if isinstance(event_type, str):
                    # 如果是字符串，尝试转换为EventType枚举
                    try:
                        from ..models.event_data_model import EventType
                        storage_event_type = EventType(event_type)
                    except ValueError:
                        # 如果转换失败，保持为字符串
                        storage_event_type = event_type
                else:
                    storage_event_type = event_type
            
            # 执行查询
            events = self.storage.query_events(
                event_type=storage_event_type,
                entity_name=participants[0] if participants else None,
                properties=properties,
                start_time=time_range[0] if time_range else None,
                end_time=time_range[1] if time_range else None,
                limit=limit
            )
            
            # 确保返回值是列表
            if events is None:
                events = []
            
            # 更新缓存
            if use_cache and events:
                self._update_query_cache(cache_key, events)
            
            # 更新性能统计
            execution_time = time.time() - start_query_time
            self._update_performance_stats(execution_time)
            
            self.logger.info(f"查询到 {len(events)} 个事件")
            return events
            
        except Exception as e:
            self.logger.error(f"查询事件失败: {str(e)}")
            return []
    
    def find_similar_events(self, target_event: Event, 
                           threshold: float = 0.7,
                           limit: int = 10,
                           similarity_threshold: float = None) -> List[Tuple[Event, float]]:
        """查找相似事件
        
        Args:
            target_event: 目标事件
            threshold: 相似度阈值
            limit: 最大结果数
            
        Returns:
            List[Tuple[Event, float]]: (事件, 相似度) 列表
        """
        try:
            # 兼容similarity_threshold参数
            if similarity_threshold is not None:
                threshold = similarity_threshold
                
            # 获取候选事件（同类型或相关类型）
            candidate_events = self._get_candidate_events(target_event)
            
            # 计算相似度
            similar_events = []
            for event in candidate_events:
                # 确保event是Event对象而不是dict
                if isinstance(event, dict):
                    self.logger.warning(f"候选事件是dict格式，跳过相似度计算: {event.get('id', 'unknown')}")
                    continue
                    
                # 获取事件ID，兼容id和event_id字段
                event_id = getattr(event, 'id', getattr(event, 'event_id', None))
                target_id = getattr(target_event, 'id', getattr(target_event, 'event_id', None))
                
                if event_id and target_id and event_id != target_id:
                    similarity = self._calculate_event_similarity(target_event, event)
                    if similarity >= threshold:
                        similar_events.append((event, similarity))
            
            # 按相似度排序
            similar_events.sort(key=lambda x: x[1], reverse=True)
            
            return similar_events[:limit]
            
        except Exception as e:
            self.logger.error(f"查找相似事件失败: {str(e)}")
            return []
    
    def get_event_timeline(self, event_ids: List[str]) -> List[Tuple[Event, datetime]]:
        """获取事件时间线"""
        try:
            events_with_time = []
            
            for event_id in event_ids:
                event = self.get_event(event_id)
                if event and event.timestamp:
                    events_with_time.append((event, event.timestamp))
            
            # 按时间排序
            events_with_time.sort(key=lambda x: x[1])
            
            return events_with_time
            
        except Exception as e:
            self.logger.error(f"获取事件时间线失败: {str(e)}")
            return []
    
    def get_events_in_timerange(self, start_time: str, end_time: str) -> List[Event]:
        """获取时间范围内的事件
        
        Args:
            start_time: 开始时间 (ISO格式字符串)
            end_time: 结束时间 (ISO格式字符串)
            
        Returns:
            List[Event]: 时间范围内的事件列表
        """
        try:
            # 转换时间字符串为datetime对象
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            
            # 查询时间范围内的事件
            events = self.query_events(
                time_range=(start_dt, end_dt),
                limit=10000
            )
            
            return events
            
        except Exception as e:
            self.logger.error(f"获取时间范围事件失败: {str(e)}")
            return []
    
    def get_events_after(self, event_id: str, window_days: int = 7) -> List[Event]:
        """获取指定事件之后的事件
        
        Args:
            event_id: 事件ID
            window_days: 时间窗口（天数）
            
        Returns:
            List[Event]: 后续事件列表
        """
        try:
            # 获取指定事件
            target_event = self.get_event(event_id)
            if not target_event or not target_event.timestamp:
                return []
            
            # 计算时间范围
            if isinstance(target_event.timestamp, str):
                start_dt = datetime.fromisoformat(target_event.timestamp.replace('Z', '+00:00'))
            else:
                start_dt = target_event.timestamp
            
            end_dt = start_dt + timedelta(days=window_days)
            
            # 查询后续事件
            subsequent_events = self.query_events(
                time_range=(start_dt, end_dt),
                limit=1000
            )
            
            # 过滤掉目标事件本身，只返回之后的事件
            filtered_events = []
            for event in subsequent_events:
                if event.id != event_id and event.timestamp:
                    if isinstance(event.timestamp, str):
                        event_dt = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
                    else:
                        event_dt = event.timestamp
                    
                    if event_dt > start_dt:
                        filtered_events.append(event)
            
            # 按时间排序
            filtered_events.sort(key=lambda x: x.timestamp)
            
            return filtered_events
            
        except Exception as e:
            self.logger.error(f"获取后续事件失败: {str(e)}")
            return []
    
    def analyze_event_frequency(self, 
                               event_type: str = None,
                               time_window: str = "month") -> Dict[str, int]:
        """分析事件频率
        
        Args:
            event_type: 事件类型
            time_window: 时间窗口 (day, week, month, year)
            
        Returns:
            Dict[str, int]: 时间段 -> 事件数量
        """
        try:
            events = self.query_events(event_type=event_type, limit=1000)
            frequency = defaultdict(int)
            
            for event in events:
                if event.timestamp:
                    time_key = self._get_time_key(event.timestamp, time_window)
                    frequency[time_key] += 1
            
            return dict(frequency)
            
        except Exception as e:
            self.logger.error(f"分析事件频率失败: {str(e)}")
            return {}
    
    def get_event_relationships(self, event_id: str) -> List[EventRelation]:
        """获取事件关系"""
        try:
            return self.storage.query_event_relations(event_id)
        except Exception as e:
            self.logger.error(f"获取事件关系失败: {str(e)}")
            return []
    
    def create_event_relation(self, relation: EventRelation) -> bool:
        """创建事件关系"""
        try:
            return self.storage.create_event_relation(relation)
        except Exception as e:
            self.logger.error(f"创建事件关系失败: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取事件层统计信息"""
        try:
            stats = self.storage.get_database_statistics()
            
            # 添加事件层特定统计
            event_types = self._get_event_type_distribution()
            temporal_distribution = self._get_temporal_distribution()
            
            return {
                "total_events": stats.get("total_events", 0),
                "total_entities": stats.get("total_entities", 0),
                "total_relations": stats.get("total_relations", 0),
                "event_type_distribution": event_types,
                "temporal_distribution": temporal_distribution,
                "average_participants_per_event": self._calculate_avg_participants()
            }
            
        except Exception as e:
            self.logger.error(f"获取统计信息失败: {str(e)}")
            return {}
    
    def _get_candidate_events(self, target_event: Event) -> List[Event]:
        """获取候选相似事件"""
        # 优先获取同类型事件
        candidates = self.query_events(
            event_type=target_event.event_type.value if hasattr(target_event.event_type, 'value') else str(target_event.event_type),
            limit=200
        )
        
        # 如果同类型事件不足，扩展到相关类型
        if len(candidates) < 50:
            related_types = self._get_related_event_types(target_event.event_type)
            for event_type in related_types:
                additional = self.query_events(event_type=event_type, limit=50)
                candidates.extend(additional)
        
        return candidates
    
    def _calculate_event_similarity(self, event1: Event, event2: Event) -> float:
        """计算事件相似度"""
        similarity_scores = []
        
        # 1. 事件类型相似度
        type_sim = 1.0 if event1.event_type == event2.event_type else 0.3
        similarity_scores.append((type_sim, 0.3))
        
        # 2. 参与者相似度
        participant_sim = self._calculate_participant_similarity(
            event1.participants, event2.participants
        )
        similarity_scores.append((participant_sim, 0.25))
        
        # 3. 描述相似度（简化实现）
        text1 = getattr(event1, 'text', getattr(event1, 'summary', ''))
        text2 = getattr(event2, 'text', getattr(event2, 'summary', ''))
        desc_sim = self._calculate_text_similarity(text1, text2)
        similarity_scores.append((desc_sim, 0.2))
        
        # 4. 时间相似度
        time_sim = self._calculate_time_similarity(
            event1.timestamp, event2.timestamp
        )
        similarity_scores.append((time_sim, 0.1))
        
        # 5. 地点相似度
        location_sim = self._calculate_location_similarity(
            event1.location, event2.location
        )
        similarity_scores.append((location_sim, 0.1))
        
        # 6. 属性相似度
        attr_sim = self._calculate_attribute_similarity(
            event1.properties, event2.properties
        )
        similarity_scores.append((attr_sim, 0.05))
        
        # 加权平均
        total_score = sum(score * weight for score, weight in similarity_scores)
        return min(total_score, 1.0)
    
    def _calculate_participant_similarity(self, participants1: List, participants2: List) -> float:
        """计算参与者相似度"""
        if not participants1 or not participants2:
            return 0.0
        
        # 提取参与者名称
        names1 = []
        for p in participants1:
            if hasattr(p, 'name'):
                names1.append(p.name)
            elif isinstance(p, str):
                names1.append(p)
            elif isinstance(p, dict) and 'name' in p:
                names1.append(p['name'])
        
        names2 = []
        for p in participants2:
            if hasattr(p, 'name'):
                names2.append(p.name)
            elif isinstance(p, str):
                names2.append(p)
            elif isinstance(p, dict) and 'name' in p:
                names2.append(p['name'])
        
        if not names1 or not names2:
            return 0.0
        
        set1 = set(names1)
        set2 = set(names2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度（简化实现）"""
        if not text1 or not text2:
            return 0.0
        
        # 简单的词汇重叠相似度
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_time_similarity(self, time1: Optional[datetime], time2: Optional[datetime]) -> float:
        """计算时间相似度"""
        if not time1 or not time2:
            return 0.5  # 中性分数
        
        try:
            # 确保时间戳是datetime对象
            dt1 = time1 if isinstance(time1, datetime) else datetime.fromisoformat(str(time1).replace('Z', '+00:00'))
            dt2 = time2 if isinstance(time2, datetime) else datetime.fromisoformat(str(time2).replace('Z', '+00:00'))
            
            # 时间差（天）
            time_diff = abs((dt1 - dt2).days)
            
            # 使用指数衰减
            return math.exp(-time_diff / 30)  # 30天半衰期
        except Exception as e:
            # 如果时间转换失败，返回中性分数
            return 0.5
    
    def _calculate_location_similarity(self, loc1: Optional[str], loc2: Optional[str]) -> float:
        """计算地点相似度"""
        if not loc1 or not loc2:
            return 0.5
        
        return 1.0 if loc1.lower() == loc2.lower() else 0.0
    
    def _calculate_attribute_similarity(self, attr1: Dict[str, Any], attr2: Dict[str, Any]) -> float:
        """计算属性相似度"""
        if not attr1 or not attr2:
            return 0.5
        
        common_keys = set(attr1.keys()) & set(attr2.keys())
        if not common_keys:
            return 0.0
        
        matches = sum(1 for key in common_keys if attr1[key] == attr2[key])
        return matches / len(common_keys)
    
    def _get_related_event_types(self, event_type) -> List[str]:
        """获取相关事件类型"""
        # 简化的事件类型关联映射
        type_relations = {
            "business_cooperation": ["business_merger", "partnership", "investment"],
            "business_merger": ["business_cooperation", "investment"],
            "investment": ["business_cooperation", "business_merger", "partnership"],
            "personnel_change": ["organizational_change"],
            "product_launch": ["market_expansion", "technology_breakthrough"]
        }
        
        type_str = event_type.value if hasattr(event_type, 'value') else str(event_type)
        return type_relations.get(type_str, [])
    
    def _get_time_key(self, timestamp: datetime, window: str) -> str:
        """获取时间窗口键"""
        if window == "day":
            return timestamp.strftime("%Y-%m-%d")
        elif window == "week":
            return f"{timestamp.year}-W{timestamp.isocalendar()[1]}"
        elif window == "month":
            return timestamp.strftime("%Y-%m")
        elif window == "year":
            return str(timestamp.year)
        else:
            return timestamp.strftime("%Y-%m")
    
    def _get_event_type_distribution(self) -> Dict[str, int]:
        """获取事件类型分布"""
        try:
            # 这里应该调用存储层的统计方法
            # 简化实现
            return {}
        except Exception:
            return {}
    
    def _get_temporal_distribution(self) -> Dict[str, int]:
        """获取时间分布"""
        try:
            # 这里应该调用存储层的统计方法
            # 简化实现
            return {}
        except Exception:
            return {}
    
    def _calculate_avg_participants(self) -> float:
        """计算平均参与者数量"""
        try:
            # 这里应该调用存储层的统计方法
            # 简化实现
            return 0.0
        except Exception:
            return 0.0
    
    def _generate_query_cache_key(self, event_type: str, time_range: Tuple[datetime, datetime], 
                                 participants: List[str], location: str, 
                                 properties: Dict[str, Any], limit: int) -> str:
        """生成查询缓存键"""
        key_data = {
            'event_type': event_type,
            'time_range': [t.isoformat() if t else None for t in (time_range or [None, None])],
            'participants': participants,
            'location': location,
            'properties': properties,
            'limit': limit
        }
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _update_query_cache(self, cache_key: str, events: List[Event]):
        """更新查询缓存"""
        with self._cache_lock:
            # 检查缓存大小限制
            if len(self._query_cache) >= self.cache_size:
                # 移除最旧的缓存项
                oldest_key = min(self._cache_timestamps.keys(), 
                               key=lambda k: self._cache_timestamps[k] if k.startswith('query_') else float('inf'))
                if oldest_key.startswith('query_'):
                    query_key = oldest_key.replace('query_', '')
                    self._query_cache.pop(query_key, None)
                    self._cache_timestamps.pop(oldest_key, None)
            
            self._query_cache[cache_key] = events
            self._cache_timestamps[f'query_{cache_key}'] = time.time()
    
    def aggregate_events_by_type(self, time_range: Tuple[datetime, datetime] = None) -> Dict[str, Dict[str, Any]]:
        """按事件类型聚合事件
        
        Args:
            time_range: 时间范围 (start, end)
            
        Returns:
            Dict[str, Dict[str, Any]]: 事件类型 -> 聚合统计
        """
        try:
            # 检查聚合缓存
            cache_key = f"type_aggregation_{time_range[0].isoformat() if time_range and time_range[0] else 'all'}_{time_range[1].isoformat() if time_range and time_range[1] else 'all'}"
            
            if (self._last_aggregation_update and 
                time.time() - self._last_aggregation_update < 300):  # 5分钟缓存
                cached_result = self._aggregation_cache.get(cache_key)
                if cached_result:
                    return cached_result
            
            # 查询事件
            events = self.query_events(time_range=time_range, limit=10000, use_cache=False)
            
            # 按类型聚合
            type_aggregation = defaultdict(lambda: {
                'count': 0,
                'participants': set(),
                'locations': set(),
                'time_distribution': defaultdict(int),
                'avg_participants': 0
            })
            
            for event in events:
                event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                agg = type_aggregation[event_type]
                
                agg['count'] += 1
                
                # 参与者统计
                if event.participants:
                    for participant in event.participants:
                        if hasattr(participant, 'name'):
                            agg['participants'].add(participant.name)
                        elif isinstance(participant, str):
                            agg['participants'].add(participant)
                
                # 地点统计
                if event.location:
                    agg['locations'].add(event.location)
                
                # 时间分布
                if event.timestamp:
                    time_key = self._get_time_key(event.timestamp, 'month')
                    agg['time_distribution'][time_key] += 1
            
            # 计算平均参与者数
            result = {}
            for event_type, agg in type_aggregation.items():
                result[event_type] = {
                    'count': agg['count'],
                    'unique_participants': len(agg['participants']),
                    'unique_locations': len(agg['locations']),
                    'time_distribution': dict(agg['time_distribution']),
                    'avg_participants': len(agg['participants']) / agg['count'] if agg['count'] > 0 else 0
                }
            
            # 更新缓存
            self._aggregation_cache[cache_key] = result
            self._last_aggregation_update = time.time()
            
            return result
            
        except Exception as e:
            self.logger.error(f"事件类型聚合失败: {str(e)}")
            return {}
    
    def aggregate_events_by_participant(self, time_range: Tuple[datetime, datetime] = None) -> Dict[str, Dict[str, Any]]:
        """按参与者聚合事件
        
        Args:
            time_range: 时间范围 (start, end)
            
        Returns:
            Dict[str, Dict[str, Any]]: 参与者 -> 聚合统计
        """
        try:
            # 查询事件
            events = self.query_events(time_range=time_range, limit=10000, use_cache=False)
            
            # 按参与者聚合
            participant_aggregation = defaultdict(lambda: {
                'event_count': 0,
                'event_types': set(),
                'locations': set(),
                'time_distribution': defaultdict(int),
                'co_participants': Counter()
            })
            
            for event in events:
                if not event.participants:
                    continue
                
                # 提取参与者名称
                participant_names = []
                for participant in event.participants:
                    if hasattr(participant, 'name'):
                        participant_names.append(participant.name)
                    elif isinstance(participant, str):
                        participant_names.append(participant)
                
                for participant_name in participant_names:
                    agg = participant_aggregation[participant_name]
                    
                    agg['event_count'] += 1
                    
                    # 事件类型统计
                    event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                    agg['event_types'].add(event_type)
                    
                    # 地点统计
                    if event.location:
                        agg['locations'].add(event.location)
                    
                    # 时间分布
                    if event.timestamp:
                        time_key = self._get_time_key(event.timestamp, 'month')
                        agg['time_distribution'][time_key] += 1
                    
                    # 共同参与者统计
                    for other_participant in participant_names:
                        if other_participant != participant_name:
                            agg['co_participants'][other_participant] += 1
            
            # 格式化结果
            result = {}
            for participant, agg in participant_aggregation.items():
                result[participant] = {
                    'event_count': agg['event_count'],
                    'event_types': list(agg['event_types']),
                    'unique_locations': len(agg['locations']),
                    'time_distribution': dict(agg['time_distribution']),
                    'top_co_participants': dict(agg['co_participants'].most_common(5))
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"参与者聚合失败: {str(e)}")
            return {}
    
    def get_event_trends(self, time_window: str = "month", limit_days: int = 365) -> Dict[str, Any]:
        """获取事件趋势分析
        
        Args:
            time_window: 时间窗口 (day, week, month)
            limit_days: 分析的天数限制
            
        Returns:
            Dict[str, Any]: 趋势分析结果
        """
        try:
            # 计算时间范围
            end_time = datetime.now()
            start_time = end_time - timedelta(days=limit_days)
            
            # 查询事件
            events = self.query_events(time_range=(start_time, end_time), limit=10000, use_cache=False)
            
            # 时间序列统计
            time_series = defaultdict(int)
            type_time_series = defaultdict(lambda: defaultdict(int))
            
            for event in events:
                if event.timestamp:
                    time_key = self._get_time_key(event.timestamp, time_window)
                    time_series[time_key] += 1
                    
                    event_type = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                    type_time_series[event_type][time_key] += 1
            
            # 计算趋势
            sorted_times = sorted(time_series.keys())
            if len(sorted_times) >= 2:
                recent_count = sum(time_series[t] for t in sorted_times[-3:])  # 最近3个时间段
                earlier_count = sum(time_series[t] for t in sorted_times[:-3])  # 之前的时间段
                
                if earlier_count > 0:
                    trend_ratio = recent_count / earlier_count
                    trend_direction = "increasing" if trend_ratio > 1.2 else "decreasing" if trend_ratio < 0.8 else "stable"
                else:
                    trend_direction = "new_activity"
                    trend_ratio = float('inf')
            else:
                trend_direction = "insufficient_data"
                trend_ratio = 1.0
            
            return {
                'time_series': dict(time_series),
                'type_time_series': {k: dict(v) for k, v in type_time_series.items()},
                'trend_direction': trend_direction,
                'trend_ratio': trend_ratio,
                'total_events': len(events),
                'time_window': time_window,
                'analysis_period': f"{start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}"
            }
            
        except Exception as e:
             self.logger.error(f"趋势分析失败: {str(e)}")
             return {}
     
    def get_performance_stats(self) -> Dict[str, Any]:
         """获取性能统计信息
         
         Returns:
             Dict[str, Any]: 性能统计数据
         """
         with self._cache_lock:
             cache_hit_rate = (
                 self.performance_stats["cache_hits"] / 
                 (self.performance_stats["cache_hits"] + self.performance_stats["cache_misses"])
                 if (self.performance_stats["cache_hits"] + self.performance_stats["cache_misses"]) > 0 else 0
             )
             
             return {
                 **self.performance_stats,
                 'cache_hit_rate': cache_hit_rate,
                 'cache_sizes': {
                     'event_cache': len(self._event_cache),
                     'query_cache': len(self._query_cache),
                     'similarity_cache': len(self._similarity_cache),
                     'aggregation_cache': len(self._aggregation_cache)
                 },
                 'cache_memory_usage': self._estimate_cache_memory_usage()
             }
     
    def clear_cache(self, cache_type: str = "all"):
         """清除缓存
         
         Args:
             cache_type: 缓存类型 (all, event, query, similarity, aggregation)
         """
         with self._cache_lock:
             if cache_type == "all" or cache_type == "event":
                 self._event_cache.clear()
                 # 清除事件相关的时间戳
                 keys_to_remove = [k for k in self._cache_timestamps.keys() if k.startswith('event_')]
                 for key in keys_to_remove:
                     self._cache_timestamps.pop(key, None)
             
             if cache_type == "all" or cache_type == "query":
                 self._query_cache.clear()
                 # 清除查询相关的时间戳
                 keys_to_remove = [k for k in self._cache_timestamps.keys() if k.startswith('query_')]
                 for key in keys_to_remove:
                     self._cache_timestamps.pop(key, None)
             
             if cache_type == "all" or cache_type == "similarity":
                 self._similarity_cache.clear()
                 # 清除相似性相关的时间戳
                 keys_to_remove = [k for k in self._cache_timestamps.keys() if k.startswith('similarity_')]
                 for key in keys_to_remove:
                     self._cache_timestamps.pop(key, None)
             
             if cache_type == "all" or cache_type == "aggregation":
                 self._aggregation_cache.clear()
                 self._last_aggregation_update = None
         
         self.logger.info(f"已清除 {cache_type} 缓存")
     
    def optimize_cache(self):
         """优化缓存，移除过期项"""
         with self._cache_lock:
             current_time = time.time()
             expired_keys = []
             
             # 检查所有缓存项的过期时间
             for key, timestamp in self._cache_timestamps.items():
                 if (current_time - timestamp) > self.cache_ttl:
                     expired_keys.append(key)
             
             # 移除过期项
             for key in expired_keys:
                 self._cache_timestamps.pop(key, None)
                 
                 if key.startswith('event_'):
                     cache_key = key.replace('event_', '')
                     self._event_cache.pop(cache_key, None)
                 elif key.startswith('query_'):
                     cache_key = key.replace('query_', '')
                     self._query_cache.pop(cache_key, None)
                 elif key.startswith('similarity_'):
                     cache_key = key.replace('similarity_', '')
                     self._similarity_cache.pop(cache_key, None)
             
             # 优化聚合缓存
             if (self._last_aggregation_update and 
                 (current_time - self._last_aggregation_update) > 1800):  # 30分钟
                 self._aggregation_cache.clear()
                 self._last_aggregation_update = None
         
         self.logger.debug(f"缓存优化完成，移除了 {len(expired_keys)} 个过期项")
     
    def _estimate_cache_memory_usage(self) -> Dict[str, str]:
         """估算缓存内存使用量"""
         try:
             import sys
             
             event_cache_size = sum(sys.getsizeof(v) for v in self._event_cache.values())
             query_cache_size = sum(sys.getsizeof(v) for v in self._query_cache.values())
             similarity_cache_size = sum(sys.getsizeof(v) for v in self._similarity_cache.values())
             aggregation_cache_size = sum(sys.getsizeof(v) for v in self._aggregation_cache.values())
             
             def format_bytes(bytes_size):
                 for unit in ['B', 'KB', 'MB', 'GB']:
                     if bytes_size < 1024.0:
                         return f"{bytes_size:.2f} {unit}"
                     bytes_size /= 1024.0
                 return f"{bytes_size:.2f} TB"
             
             return {
                 'event_cache': format_bytes(event_cache_size),
                 'query_cache': format_bytes(query_cache_size),
                 'similarity_cache': format_bytes(similarity_cache_size),
                 'aggregation_cache': format_bytes(aggregation_cache_size),
                 'total': format_bytes(event_cache_size + query_cache_size + similarity_cache_size + aggregation_cache_size)
             }
         except Exception:
             return {'error': 'Unable to estimate memory usage'}
     
    def update_events_batch(self, event_updates: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
         """批量更新事件
         
         Args:
             event_updates: 事件ID -> 更新字段的映射
             
         Returns:
             Dict[str, bool]: 事件ID -> 是否成功
         """
         start_time = time.time()
         results = {}
         
         try:
             self.performance_stats["batch_operations"] += 1
             
             # 批量更新
             if hasattr(self.storage, 'update_events_batch'):
                 # 如果存储层支持批量更新
                 batch_results = self.storage.update_events_batch(event_updates)
                 results.update(batch_results)
             else:
                 # 逐个更新
                 for event_id, updates in event_updates.items():
                     success = self.storage.update_event(event_id, updates)
                     results[event_id] = success
             
             # 清除相关缓存
             for event_id in event_updates.keys():
                 with self._cache_lock:
                     self._event_cache.pop(event_id, None)
                     self._cache_timestamps.pop(f'event_{event_id}', None)
             
             self._invalidate_query_cache()
             
             # 更新性能统计
             execution_time = time.time() - start_time
             self._update_performance_stats(execution_time)
             
             success_count = sum(1 for success in results.values() if success)
             self.logger.info(f"批量更新事件完成: {success_count}/{len(event_updates)} 成功")
             
             return results
             
         except Exception as e:
             self.logger.error(f"批量更新事件失败: {str(e)}")
             return {event_id: False for event_id in event_updates.keys()}
     
    def delete_events_batch(self, event_ids: List[str]) -> Dict[str, bool]:
         """批量删除事件
         
         Args:
             event_ids: 要删除的事件ID列表
             
         Returns:
             Dict[str, bool]: 事件ID -> 是否成功
         """
         start_time = time.time()
         results = {}
         
         try:
             self.performance_stats["batch_operations"] += 1
             
             # 批量删除
             if hasattr(self.storage, 'delete_events_batch'):
                 # 如果存储层支持批量删除
                 batch_results = self.storage.delete_events_batch(event_ids)
                 results.update(batch_results)
             else:
                 # 逐个删除
                 for event_id in event_ids:
                     success = self.storage.delete_event(event_id)
                     results[event_id] = success
             
             # 清除相关缓存
             for event_id in event_ids:
                 with self._cache_lock:
                     self._event_cache.pop(event_id, None)
                     self._cache_timestamps.pop(f'event_{event_id}', None)
             
             self._invalidate_query_cache()
             
             # 更新性能统计
             execution_time = time.time() - start_time
             self._update_performance_stats(execution_time)
             
             success_count = sum(1 for success in results.values() if success)
             self.logger.info(f"批量删除事件完成: {success_count}/{len(event_ids)} 成功")
             
             return results
             
         except Exception as e:
             self.logger.error(f"批量删除事件失败: {str(e)}")
             return {event_id: False for event_id in event_ids}