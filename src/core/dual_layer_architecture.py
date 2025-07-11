"""事理图谱双层架构核心实现

实现事件层和模式层的双层架构，支持：
- 事件实例的存储和管理
- 事理模式的抽象和存储
- 双层之间的映射关系
- 跨层查询和推理
"""

from typing import Dict, List, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from datetime import datetime

from ..models.event_data_model import Event, EventPattern, Entity, EventRelation
from ..storage.neo4j_event_storage import Neo4jEventStorage
from .event_layer_manager import EventLayerManager
from .pattern_layer_manager import PatternLayerManager
from .layer_mapper import LayerMapper
from .graph_processor import GraphProcessor


@dataclass
class ArchitectureConfig:
    """双层架构配置"""
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    enable_pattern_learning: bool = True
    pattern_similarity_threshold: float = 0.8
    auto_mapping: bool = True
    max_pattern_depth: int = 3
    enable_reasoning: bool = True


class DualLayerArchitecture:
    """事理图谱双层架构"""
    
    def __init__(self, config: ArchitectureConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # 初始化存储
        self.storage = Neo4jEventStorage(
            uri=config.neo4j_uri,
            user=config.neo4j_user,
            password=config.neo4j_password
        )
        
        # 初始化各层管理器
        self.event_layer = EventLayerManager(self.storage)
        self.pattern_layer = PatternLayerManager(self.storage)
        self.layer_mapper = LayerMapper(self.storage)
        self.graph_processor = GraphProcessor(self.storage)
        
        self.logger.info("双层架构初始化完成")
    
    def add_event(self, event: Event, auto_pattern_learning: bool = None) -> bool:
        """添加事件到事件层
        
        Args:
            event: 事件对象
            auto_pattern_learning: 是否自动学习模式
            
        Returns:
            bool: 是否成功添加
        """
        try:
            # 添加到事件层
            success = self.event_layer.add_event(event)
            if not success:
                return False
            
            # 自动模式学习
            if auto_pattern_learning is None:
                auto_pattern_learning = self.config.enable_pattern_learning
                
            if auto_pattern_learning:
                self._learn_patterns_from_event(event)
            
            # 自动映射
            if self.config.auto_mapping:
                self._auto_map_event_to_patterns(event)
            
            self.logger.info(f"成功添加事件: {event.event_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"添加事件失败: {str(e)}")
            return False
    
    def add_pattern(self, pattern: EventPattern) -> bool:
        """添加事理模式到模式层"""
        try:
            success = self.pattern_layer.add_pattern(pattern)
            if success:
                self.logger.info(f"成功添加模式: {pattern.pattern_id}")
            return success
        except Exception as e:
            self.logger.error(f"添加模式失败: {str(e)}")
            return False
    
    def query_events(self, 
                    event_type: str = None,
                    time_range: Tuple[datetime, datetime] = None,
                    participants: List[str] = None,
                    location: str = None,
                    limit: int = 100) -> List[Event]:
        """查询事件层"""
        return self.event_layer.query_events(
            event_type=event_type,
            time_range=time_range,
            participants=participants,
            location=location,
            limit=limit
        )
    
    def query_patterns(self,
                      pattern_type: str = None,
                      complexity_level: int = None,
                      domain: str = None,
                      limit: int = 50) -> List[EventPattern]:
        """查询模式层"""
        return self.pattern_layer.query_patterns(
            pattern_type=pattern_type,
            complexity_level=complexity_level,
            domain=domain,
            limit=limit
        )
    
    def find_similar_events(self, event: Event, similarity_threshold: float = 0.7) -> List[Tuple[Event, float]]:
        """查找相似事件"""
        return self.event_layer.find_similar_events(event, similarity_threshold)
    
    def find_matching_patterns(self, event: Event, threshold: float = None) -> List[Tuple[EventPattern, float]]:
        """查找匹配的事理模式"""
        if threshold is None:
            threshold = self.config.pattern_similarity_threshold
        return self.layer_mapper.find_matching_patterns(event, threshold)
    
    def predict_next_events(self, current_events: List[Event], top_k: int = 5) -> List[Tuple[Event, float]]:
        """基于事理模式预测下一个可能的事件"""
        if not self.config.enable_reasoning:
            return []
        
        return self.graph_processor.predict_next_events(current_events, top_k)
    
    def analyze_event_chain(self, events: List[Event]) -> Dict[str, Any]:
        """分析事件链"""
        return self.graph_processor.analyze_event_chain(events)
    
    def extract_event_patterns(self, events: List[Event], min_support: int = 2) -> List[EventPattern]:
        """从事件中提取事理模式"""
        return self.pattern_layer.extract_patterns_from_events(events, min_support)
    
    def get_architecture_statistics(self) -> Dict[str, Any]:
        """获取架构统计信息"""
        event_stats = self.event_layer.get_statistics()
        pattern_stats = self.pattern_layer.get_statistics()
        mapping_stats = self.layer_mapper.get_statistics()
        
        return {
            "event_layer": event_stats,
            "pattern_layer": pattern_stats,
            "layer_mapping": mapping_stats,
            "total_nodes": event_stats.get("total_events", 0) + pattern_stats.get("total_patterns", 0),
            "architecture_config": {
                "pattern_learning_enabled": self.config.enable_pattern_learning,
                "auto_mapping_enabled": self.config.auto_mapping,
                "reasoning_enabled": self.config.enable_reasoning,
                "pattern_similarity_threshold": self.config.pattern_similarity_threshold
            }
        }
    
    def _learn_patterns_from_event(self, event: Event):
        """从单个事件学习模式"""
        try:
            # 查找相似事件
            similar_events = self.find_similar_events(event, 0.8)
            
            if len(similar_events) >= 2:  # 包括当前事件
                events_for_pattern = [event] + [e[0] for e in similar_events[:4]]
                patterns = self.extract_event_patterns(events_for_pattern, min_support=2)
                
                for pattern in patterns:
                    self.add_pattern(pattern)
                    
        except Exception as e:
            self.logger.warning(f"从事件学习模式失败: {str(e)}")
    
    def _auto_map_event_to_patterns(self, event: Event):
        """自动将事件映射到模式"""
        try:
            matching_patterns = self.find_matching_patterns(event)
            
            for pattern, confidence in matching_patterns:
                self.layer_mapper.create_mapping(
                    event_id=event.event_id,
                    pattern_id=pattern.pattern_id,
                    confidence=confidence,
                    mapping_type="auto"
                )
                
        except Exception as e:
            self.logger.warning(f"自动映射事件到模式失败: {str(e)}")
    
    def close(self):
        """关闭连接"""
        if self.storage:
            self.storage.close()
        self.logger.info("双层架构已关闭")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# 使用示例
if __name__ == "__main__":
    # 配置
    config = ArchitectureConfig(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        enable_pattern_learning=True,
        auto_mapping=True
    )
    
    # 创建架构
    with DualLayerArchitecture(config) as architecture:
        # 示例事件
        event = Event(
            event_id="test_001",
            event_type="business_cooperation",
            description="公司合作事件",
            participants=["company_a", "company_b"],
            attributes={"domain": "technology"}
        )
        
        # 添加事件
        architecture.add_event(event)
        
        # 查询统计
        stats = architecture.get_architecture_statistics()
        print(f"架构统计: {stats}")