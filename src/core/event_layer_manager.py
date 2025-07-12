"""事件层管理器

负责管理事件层的具体事件实例，包括：
- 事件的存储和检索
- 事件相似性计算
- 事件关系分析
- 时间序列查询
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
from datetime import datetime
import math
from collections import defaultdict

from ..models.event_data_model import Event, EventType, Entity, EventRelation
from ..storage.neo4j_event_storage import Neo4jEventStorage


class EventLayerManager:
    """事件层管理器"""
    
    def __init__(self, storage: Neo4jEventStorage):
        self.storage = storage
        self.logger = logging.getLogger(__name__)
        
    def add_event(self, event: Event) -> bool:
        """添加事件到事件层"""
        try:
            # 存储事件
            success = self.storage.store_event(event)
            if success:
                event_id = getattr(event, 'id', getattr(event, 'event_id', 'unknown'))
                self.logger.info(f"事件已添加到事件层: {event_id}")
            return success
        except Exception as e:
            self.logger.error(f"添加事件失败: {str(e)}")
            return False
    
    def get_event(self, event_id: str) -> Optional[Event]:
        """获取单个事件"""
        try:
            return self.storage.get_event(event_id)
        except Exception as e:
            self.logger.error(f"获取事件失败: {str(e)}")
            return None
    
    def query_events(self, 
                    event_type: str = None,
                    time_range: Tuple[datetime, datetime] = None,
                    participants: List[str] = None,
                    location: str = None,
                    properties: Dict[str, Any] = None,
                    limit: int = 100) -> List[Event]:
        """查询事件
        
        Args:
            event_type: 事件类型
            time_range: 时间范围 (start, end)
            participants: 参与者列表
            location: 地点
            properties: 属性过滤
            limit: 结果限制
            
        Returns:
            List[Event]: 匹配的事件列表
        """
        try:
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
            
            self.logger.info(f"获取到时间范围 {start_time} 到 {end_time} 内的 {len(events)} 个事件")
            return events
            
        except Exception as e:
            self.logger.error(f"获取时间范围内事件失败: {str(e)}")
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
            return self.storage.get_event_relations(event_id)
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