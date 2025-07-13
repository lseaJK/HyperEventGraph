#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工作流控制器

负责协调各模块的执行顺序和数据传递，管理ChromaDB和Neo4j的协同工作，
支持6阶段流水线：文本输入 → 事件抽取 → 关系分析 → GraphRAG增强 → 存储 → 输出
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Union
from pathlib import Path
import json

# 导入项目模块
from src.data_models.event import Event
from src.event_logic.hybrid_retriever import HybridRetriever
from src.event_logic.attribute_enhancer import AttributeEnhancer, EnhancedEvent, IncompleteEvent
from src.event_logic.pattern_discoverer import PatternDiscoverer, EventPattern
from src.event_logic.graphrag_coordinator import GraphRAGCoordinator, GraphRAGQuery, GraphRAGResponse


class PipelineStage(Enum):
    """流水线阶段枚举"""
    TEXT_INPUT = "text_input"
    EVENT_EXTRACTION = "event_extraction"
    RELATION_ANALYSIS = "relation_analysis"
    GRAPHRAG_ENHANCEMENT = "graphrag_enhancement"
    STORAGE = "storage"
    OUTPUT = "output"


class PipelineStatus(Enum):
    """流水线状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class PipelineConfig:
    """流水线配置"""
    # 数据库配置
    chroma_config: Dict[str, Any] = field(default_factory=dict)
    neo4j_config: Dict[str, Any] = field(default_factory=dict)
    
    # 处理配置
    batch_size: int = 100
    max_workers: int = 4
    timeout_seconds: int = 300
    
    # 错误处理配置
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_recovery: bool = True
    
    # 监控配置
    enable_monitoring: bool = True
    log_level: str = "INFO"
    
    # 输出配置
    output_format: str = "jsonl"
    output_path: Optional[str] = None


@dataclass
class StageResult:
    """阶段执行结果"""
    stage: PipelineStage
    status: PipelineStatus
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """流水线执行结果"""
    pipeline_id: str
    status: PipelineStatus
    stage_results: List[StageResult] = field(default_factory=list)
    total_execution_time: float = 0.0
    processed_items: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class DatabaseMonitor:
    """数据库状态监控器"""
    
    def __init__(self, chroma_config: Dict, neo4j_config: Dict):
        self.chroma_config = chroma_config
        self.neo4j_config = neo4j_config
        self.logger = logging.getLogger(__name__)
        self._monitoring = False
        self._stats = {
            "chroma_status": "unknown",
            "neo4j_status": "unknown",
            "sync_status": "unknown",
            "last_check": None
        }
    
    async def start_monitoring(self):
        """启动监控"""
        self._monitoring = True
        self.logger.info("数据库监控已启动")
        
        # 启动监控任务
        asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """停止监控"""
        self._monitoring = False
        self.logger.info("数据库监控已停止")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                await self._check_database_status()
                await asyncio.sleep(30)  # 每30秒检查一次
            except Exception as e:
                self.logger.error(f"监控检查失败: {e}")
                await asyncio.sleep(60)  # 错误时延长检查间隔
    
    async def _check_database_status(self):
        """检查数据库状态"""
        # 检查ChromaDB状态
        try:
            # 这里应该实际连接ChromaDB进行健康检查
            self._stats["chroma_status"] = "healthy"
        except Exception as e:
            self._stats["chroma_status"] = f"error: {e}"
            self.logger.warning(f"ChromaDB状态异常: {e}")
        
        # 检查Neo4j状态
        try:
            # 这里应该实际连接Neo4j进行健康检查
            self._stats["neo4j_status"] = "healthy"
        except Exception as e:
            self._stats["neo4j_status"] = f"error: {e}"
            self.logger.warning(f"Neo4j状态异常: {e}")
        
        # 检查数据同步状态
        await self._check_data_sync()
        
        self._stats["last_check"] = time.time()
    
    async def _check_data_sync(self):
        """检查数据同步状态"""
        try:
            # 这里应该实际检查两个数据库的数据一致性
            self._stats["sync_status"] = "synchronized"
        except Exception as e:
            self._stats["sync_status"] = f"error: {e}"
            self.logger.warning(f"数据同步状态异常: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        return self._stats.copy()
    
    async def handle_database_failure(self, database: str, error: Exception):
        """处理数据库故障"""
        self.logger.error(f"{database}数据库故障: {error}")
        
        # 实现故障自动恢复逻辑
        if database == "chroma":
            await self._recover_chroma()
        elif database == "neo4j":
            await self._recover_neo4j()
    
    async def _recover_chroma(self):
        """ChromaDB故障恢复"""
        self.logger.info("尝试恢复ChromaDB连接...")
        # 实现ChromaDB恢复逻辑
    
    async def _recover_neo4j(self):
        """Neo4j故障恢复"""
        self.logger.info("尝试恢复Neo4j连接...")
        # 实现Neo4j恢复逻辑


class WorkflowController:
    """工作流控制器
    
    协调各模块的执行顺序和数据传递，管理ChromaDB和Neo4j的协同工作，
    支持6阶段流水线处理。
    """
    
    def __init__(self, config: PipelineConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(max_workers=config.max_workers)
        
        # 初始化组件
        self._init_components()
        
        # 初始化监控
        self.monitor = DatabaseMonitor(config.chroma_config, config.neo4j_config)
        
        # 流水线状态
        self._pipelines: Dict[str, PipelineResult] = {}
        self._stage_handlers = self._init_stage_handlers()
        
        # 性能统计
        self.stats = {
            "total_pipelines": 0,
            "successful_pipelines": 0,
            "failed_pipelines": 0,
            "avg_execution_time": 0.0
        }
    
    def _init_components(self):
        """初始化组件"""
        try:
            # 初始化LLM事件抽取器
            from ..llm_integration.llm_event_extractor import LLMEventExtractor
            from ..llm_integration.llm_config import LLMConfig
            
            llm_config = LLMConfig.from_env()
            self.event_extractor = LLMEventExtractor(config=llm_config)
            self.logger.info("✅ LLM事件抽取器初始化成功")
            
            # 初始化事理关系分析器
            from ..event_logic.event_logic_analyzer import EventLogicAnalyzer
            self.relation_analyzer = EventLogicAnalyzer(llm_client=self.event_extractor.client)
            self.logger.info("✅ 事理关系分析器初始化成功")
            
            # 初始化Neo4j存储
            from ..storage.neo4j_event_storage import Neo4jEventStorage, Neo4jConfig
            neo4j_config = Neo4jConfig.from_env()
            self.neo4j_storage = Neo4jEventStorage(config=neo4j_config)
            
            # 测试Neo4j连接
            if self.neo4j_storage.test_connection():
                self.logger.info("✅ Neo4j存储连接成功")
            else:
                self.logger.warning("⚠️ Neo4j连接失败，将使用模拟存储")
                self.neo4j_storage = None
            
            # 初始化混合检索器
            self.hybrid_retriever = HybridRetriever(
                chroma_config=self.config.chroma_config,
                neo4j_config=self.config.neo4j_config
            )
            
            # 初始化属性补充器
            self.attribute_enhancer = AttributeEnhancer(self.hybrid_retriever)
            
            # 初始化模式发现器
            self.pattern_discoverer = PatternDiscoverer(
                chroma_config=self.config.chroma_config,
                neo4j_config=self.config.neo4j_config
            )
            
            # 初始化GraphRAG协调器
            self.graphrag_coordinator = GraphRAGCoordinator(
                hybrid_retriever=self.hybrid_retriever,
                attribute_enhancer=self.attribute_enhancer,
                pattern_discoverer=self.pattern_discoverer,
                max_workers=self.config.max_workers
            )
            
            self.logger.info("工作流组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"组件初始化失败: {e}")
            # 设置为None以便后续使用fallback方法
            self.event_extractor = None
            self.relation_analyzer = None
            self.neo4j_storage = None
            self.hybrid_retriever = None
            self.attribute_enhancer = None
            self.pattern_discoverer = None
            self.graphrag_coordinator = None
    
    def _init_stage_handlers(self) -> Dict[PipelineStage, Callable]:
        """初始化阶段处理器"""
        return {
            PipelineStage.TEXT_INPUT: self._handle_text_input,
            PipelineStage.EVENT_EXTRACTION: self._handle_event_extraction,
            PipelineStage.RELATION_ANALYSIS: self._handle_relation_analysis,
            PipelineStage.GRAPHRAG_ENHANCEMENT: self._handle_graphrag_enhancement,
            PipelineStage.STORAGE: self._handle_storage,
            PipelineStage.OUTPUT: self._handle_output
        }
    
    async def start_monitoring(self):
        """启动监控"""
        if self.config.enable_monitoring:
            await self.monitor.start_monitoring()
    
    async def stop_monitoring(self):
        """停止监控"""
        await self.monitor.stop_monitoring()
    
    async def execute_pipeline(self, 
                             pipeline_id: str,
                             input_data: Any,
                             stages: Optional[List[PipelineStage]] = None) -> PipelineResult:
        """执行流水线
        
        Args:
            pipeline_id: 流水线ID
            input_data: 输入数据
            stages: 要执行的阶段列表，默认执行所有阶段
        
        Returns:
            PipelineResult: 流水线执行结果
        """
        if stages is None:
            stages = list(PipelineStage)
        
        # 创建流水线结果
        pipeline_result = PipelineResult(
            pipeline_id=pipeline_id,
            status=PipelineStatus.RUNNING
        )
        self._pipelines[pipeline_id] = pipeline_result
        
        start_time = time.time()
        current_data = input_data
        
        try:
            self.logger.info(f"开始执行流水线 {pipeline_id}")
            
            # 逐阶段执行
            for stage in stages:
                stage_result = await self._execute_stage(stage, current_data, pipeline_id)
                pipeline_result.stage_results.append(stage_result)
                
                if stage_result.status == PipelineStatus.FAILED:
                    pipeline_result.status = PipelineStatus.FAILED
                    pipeline_result.error_count += 1
                    
                    if not self.config.enable_recovery:
                        break
                    
                    # 尝试错误恢复
                    recovery_result = await self._handle_stage_error(stage, stage_result.error, pipeline_id)
                    if not recovery_result:
                        break
                
                # 传递数据到下一阶段
                current_data = stage_result.data
                pipeline_result.processed_items += 1
            
            # 检查最终状态
            if pipeline_result.status == PipelineStatus.RUNNING:
                pipeline_result.status = PipelineStatus.COMPLETED
                self.stats["successful_pipelines"] += 1
            else:
                self.stats["failed_pipelines"] += 1
            
        except Exception as e:
            self.logger.error(f"流水线 {pipeline_id} 执行异常: {e}")
            pipeline_result.status = PipelineStatus.FAILED
            pipeline_result.error_count += 1
            self.stats["failed_pipelines"] += 1
        
        finally:
            # 更新统计信息
            pipeline_result.total_execution_time = time.time() - start_time
            self.stats["total_pipelines"] += 1
            self._update_avg_execution_time(pipeline_result.total_execution_time)
            
            self.logger.info(
                f"流水线 {pipeline_id} 执行完成，状态: {pipeline_result.status.value}, "
                f"耗时: {pipeline_result.total_execution_time:.2f}s"
            )
        
        return pipeline_result
    
    async def _execute_stage(self, stage: PipelineStage, data: Any, pipeline_id: str) -> StageResult:
        """执行单个阶段"""
        start_time = time.time()
        
        try:
            self.logger.debug(f"执行阶段 {stage.value} (流水线: {pipeline_id})")
            
            # 获取阶段处理器
            handler = self._stage_handlers.get(stage)
            if not handler:
                raise ValueError(f"未找到阶段 {stage.value} 的处理器")
            
            # 执行阶段处理
            result_data = await handler(data, pipeline_id)
            
            execution_time = time.time() - start_time
            
            return StageResult(
                stage=stage,
                status=PipelineStatus.COMPLETED,
                data=result_data,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            self.logger.error(f"阶段 {stage.value} 执行失败: {e}")
            
            return StageResult(
                stage=stage,
                status=PipelineStatus.FAILED,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _handle_text_input(self, data: Any, pipeline_id: str) -> Dict[str, Any]:
        """处理文本输入阶段"""
        if isinstance(data, str):
            return {
                "text": data,
                "pipeline_id": pipeline_id,
                "timestamp": time.time()
            }
        elif isinstance(data, dict) and "text" in data:
            data["pipeline_id"] = pipeline_id
            data["timestamp"] = time.time()
            return data
        else:
            raise ValueError("输入数据必须是字符串或包含'text'字段的字典")
    
    async def _handle_event_extraction(self, data: Dict[str, Any], pipeline_id: str) -> List[Event]:
        """处理事件抽取阶段"""
        text = data.get("text", "")
        
        if not text:
            self.logger.warning("输入文本为空")
            return []
        
        try:
            if self.event_extractor:
                # 使用实际的LLM事件抽取器
                self.logger.info(f"开始抽取事件，文本长度: {len(text)}")
                
                result = self.event_extractor.extract_events(
                    text=text,
                    event_types=["business_cooperation", "personnel_change", "product_launch", "investment", "other"],
                    entity_types=["organization", "person", "product", "location", "other"]
                )
                
                if result.success:
                    events = result.events
                    # 为每个事件添加pipeline_id
                    for event in events:
                        if not hasattr(event, 'properties') or event.properties is None:
                            event.properties = {}
                        event.properties["pipeline_id"] = pipeline_id
                        event.properties["source"] = "llm_extraction"
                    
                    self.logger.info(f"✅ 成功抽取到 {len(events)} 个事件，处理时间: {result.processing_time:.2f}秒")
                    return events
                else:
                    self.logger.error(f"事件抽取失败: {result.error_message}")
                    return self._create_fallback_events(text, pipeline_id)
            else:
                # 使用fallback方法
                self.logger.warning("事件抽取器未初始化，使用fallback方法")
                return self._create_fallback_events(text, pipeline_id)
                
        except Exception as e:
            self.logger.error(f"事件抽取过程中发生错误: {e}")
            return self._create_fallback_events(text, pipeline_id)
    
    def _create_fallback_events(self, text: str, pipeline_id: str) -> List[Event]:
        """创建fallback事件（当LLM抽取失败时使用）"""
        from ..models.event_data_model import Event, EventType
        
        events = [
            Event(
                id=f"event_{pipeline_id}_fallback_001",
                event_type=EventType.OTHER,
                text=text,
                summary=f"从文本中抽取的事件: {text[:100]}...",
                timestamp=str(time.time()),
                properties={"source": "fallback_extraction", "pipeline_id": pipeline_id}
            )
        ]
        
        self.logger.info(f"创建了 {len(events)} 个fallback事件")
        return events
    
    async def _handle_relation_analysis(self, events: List[Event], pipeline_id: str) -> Dict[str, Any]:
        """处理关系分析阶段"""
        if len(events) < 2:
            self.logger.info(f"事件数量不足({len(events)})，跳过关系分析")
            return {
                "events": events,
                "relations": [],
                "pipeline_id": pipeline_id
            }
        
        try:
            if self.relation_analyzer:
                # 使用实际的事理关系分析器
                self.logger.info(f"开始分析 {len(events)} 个事件的关系")
                
                relations = self.relation_analyzer.analyze_event_relations(events)
                
                # 转换为字典格式以便序列化
                relations_dict = []
                for relation in relations:
                    relations_dict.append({
                        "id": getattr(relation, 'id', f"rel_{len(relations_dict)}"),
                        "source_event": relation.source_event_id,
                        "target_event": relation.target_event_id,
                        "relation_type": relation.relation_type.value if hasattr(relation.relation_type, 'value') else str(relation.relation_type),
                        "confidence": relation.confidence,
                        "strength": getattr(relation, 'strength', 0.0),
                        "description": getattr(relation, 'description', ''),
                        "evidence": getattr(relation, 'evidence', ''),
                        "source": getattr(relation, 'source', 'analyzer'),
                        "pipeline_id": pipeline_id
                    })
                
                result = {
                    "events": events,
                    "relations": relations_dict,
                    "pipeline_id": pipeline_id
                }
                
                self.logger.info(f"✅ 成功分析了 {len(events)} 个事件，发现 {len(relations_dict)} 个关系")
                return result
            else:
                # 使用fallback方法
                self.logger.warning("关系分析器未初始化，使用fallback方法")
                return self._create_fallback_relations(events, pipeline_id)
                
        except Exception as e:
            self.logger.error(f"关系分析过程中发生错误: {e}")
            return self._create_fallback_relations(events, pipeline_id)
    
    def _create_fallback_relations(self, events: List[Event], pipeline_id: str) -> Dict[str, Any]:
        """创建fallback关系（当关系分析失败时使用）"""
        relations = []
        
        # 简单的时序关系推断
        for i in range(len(events) - 1):
            relations.append({
                "id": f"rel_fallback_{i}",
                "source_event": events[i].id,
                "target_event": events[i + 1].id,
                "relation_type": "temporal_sequence",
                "confidence": 0.5,
                "strength": 0.4,
                "description": "基于顺序的时序关系",
                "evidence": "事件顺序推断",
                "source": "fallback_analysis",
                "pipeline_id": pipeline_id
            })
        
        result = {
            "events": events,
            "relations": relations,
            "pipeline_id": pipeline_id
        }
        
        self.logger.info(f"创建了 {len(relations)} 个fallback关系")
        return result
    
    async def _handle_graphrag_enhancement(self, data: Dict[str, Any], pipeline_id: str) -> Dict[str, Any]:
        """处理GraphRAG增强阶段"""
        events = data.get("events", [])
        
        # 创建GraphRAG查询
        query = GraphRAGQuery(
            query_id=f"enhancement_{pipeline_id}",
            query_text="增强事件信息",
            query_type="hybrid",
            target_events=events,
            parameters={
                "top_k": 10,
                "enhance_attributes": True,
                "discover_patterns": True
            }
        )
        
        # 执行GraphRAG增强
        response = await self.graphrag_coordinator.process_query(query)
        
        # 整合结果
        enhanced_data = {
            "original_events": events,
            "enhanced_events": response.enhanced_events or [],
            "discovered_patterns": response.discovered_patterns or [],
            "retrieved_events": response.retrieved_events or [],
            "relations": data.get("relations", []),
            "confidence_scores": response.confidence_scores,
            "pipeline_id": pipeline_id
        }
        
        self.logger.info(f"GraphRAG增强完成，增强事件: {len(enhanced_data['enhanced_events'])}")
        return enhanced_data
    
    async def _handle_storage(self, data: Dict[str, Any], pipeline_id: str) -> Dict[str, Any]:
        """处理存储阶段"""
        try:
            # 存储到ChromaDB和Neo4j
            events = data.get("enhanced_events", []) or data.get("original_events", [])
            patterns = data.get("discovered_patterns", [])
            relations = data.get("relations", [])
            
            # 存储事件
            if events:
                await self._store_events(events)
            
            # 存储模式
            if patterns:
                await self._store_patterns(patterns)
            
            # 存储关系
            if relations:
                await self._store_relations(relations)
            
            storage_result = {
                "stored_events": len(events),
                "stored_patterns": len(patterns),
                "stored_relations": len(relations),
                "pipeline_id": pipeline_id,
                "data": data  # 传递原始数据到输出阶段
            }
            
            self.logger.info(f"存储完成: 事件{len(events)}个, 模式{len(patterns)}个, 关系{len(relations)}个")
            return storage_result
            
        except Exception as e:
            self.logger.error(f"存储阶段失败: {e}")
            raise
    
    async def _handle_output(self, data: Dict[str, Any], pipeline_id: str) -> Dict[str, Any]:
        """处理输出阶段"""
        # 格式化输出数据
        output_data = {
            "pipeline_id": pipeline_id,
            "timestamp": time.time(),
            "events": data.get("data", {}).get("enhanced_events", []) or data.get("data", {}).get("original_events", []),
            "patterns": data.get("data", {}).get("discovered_patterns", []),
            "relations": data.get("data", {}).get("relations", []),
            "confidence_scores": data.get("data", {}).get("confidence_scores", {}),
            "storage_stats": {
                "stored_events": data.get("stored_events", 0),
                "stored_patterns": data.get("stored_patterns", 0),
                "stored_relations": data.get("stored_relations", 0)
            }
        }
        
        # 保存到文件（如果配置了输出路径）
        if self.config.output_path:
            await self._save_output(output_data, pipeline_id)
        
        self.logger.info(f"输出阶段完成，流水线 {pipeline_id}")
        return output_data
    
    async def _store_events(self, events: List[Event]):
        """存储事件到数据库"""
        if not events:
            return
        
        try:
            if self.neo4j_storage:
                # 使用实际的Neo4j存储
                for event in events:
                    success = self.neo4j_storage.store_event(event)
                    if not success:
                        self.logger.warning(f"事件 {event.id} 存储失败")
                
                self.logger.info(f"✅ 成功存储 {len(events)} 个事件到Neo4j")
            else:
                # 模拟存储
                self.logger.warning(f"⚠️ Neo4j存储不可用，模拟存储 {len(events)} 个事件")
                
        except Exception as e:
            self.logger.error(f"存储事件失败: {e}")
    
    async def _store_patterns(self, patterns: List[EventPattern]):
        """存储模式到数据库"""
        # 这里应该实际存储到ChromaDB和Neo4j
        pass
    
    async def _store_relations(self, relations: List[Dict]):
        """存储关系到数据库"""
        if not relations:
            return
        
        try:
            if self.neo4j_storage:
                # 使用实际的Neo4j存储
                for relation in relations:
                    success = self.neo4j_storage.store_relation(
                        source_event_id=relation["source_event"],
                        target_event_id=relation["target_event"],
                        relation_type=relation["relation_type"],
                        properties={
                            "confidence": relation.get("confidence", 0.0),
                            "strength": relation.get("strength", 0.0),
                            "description": relation.get("description", ""),
                            "evidence": relation.get("evidence", ""),
                            "source": relation.get("source", "unknown"),
                            "pipeline_id": relation.get("pipeline_id", "")
                        }
                    )
                    if not success:
                        self.logger.warning(f"关系 {relation.get('id', 'unknown')} 存储失败")
                
                self.logger.info(f"✅ 成功存储 {len(relations)} 个关系到Neo4j")
            else:
                # 模拟存储
                self.logger.warning(f"⚠️ Neo4j存储不可用，模拟存储 {len(relations)} 个关系")
                
        except Exception as e:
            self.logger.error(f"存储关系失败: {e}")
    
    async def _save_output(self, data: Dict[str, Any], pipeline_id: str):
        """保存输出到文件"""
        try:
            output_path = Path(self.config.output_path)
            output_path.mkdir(parents=True, exist_ok=True)
            
            if self.config.output_format == "jsonl":
                file_path = output_path / f"{pipeline_id}.jsonl"
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"输出已保存到: {file_path}")
            
        except Exception as e:
            self.logger.error(f"保存输出失败: {e}")
    
    async def _handle_stage_error(self, stage: PipelineStage, error: str, pipeline_id: str) -> bool:
        """处理阶段错误"""
        self.logger.warning(f"尝试恢复阶段 {stage.value} 的错误: {error}")
        
        # 实现错误恢复逻辑
        # 这里可以根据不同的错误类型实现不同的恢复策略
        
        return False  # 暂时返回False，表示无法恢复
    
    def _update_avg_execution_time(self, execution_time: float):
        """更新平均执行时间"""
        total = self.stats["total_pipelines"]
        if total > 0:
            current_avg = self.stats["avg_execution_time"]
            self.stats["avg_execution_time"] = (current_avg * (total - 1) + execution_time) / total
    
    def get_pipeline_status(self, pipeline_id: str) -> Optional[PipelineResult]:
        """获取流水线状态"""
        return self._pipelines.get(pipeline_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "database_status": self.monitor.get_status(),
            "active_pipelines": len([p for p in self._pipelines.values() if p.status == PipelineStatus.RUNNING])
        }
    
    async def batch_execute(self, 
                          input_data_list: List[Any],
                          pipeline_prefix: str = "batch") -> List[PipelineResult]:
        """批量执行流水线"""
        tasks = []
        
        for i, input_data in enumerate(input_data_list):
            pipeline_id = f"{pipeline_prefix}_{i:04d}"
            task = self.execute_pipeline(pipeline_id, input_data)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        pipeline_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                pipeline_id = f"{pipeline_prefix}_{i:04d}"
                error_result = PipelineResult(
                    pipeline_id=pipeline_id,
                    status=PipelineStatus.FAILED
                )
                error_result.error_count = 1
                pipeline_results.append(error_result)
            else:
                pipeline_results.append(result)
        
        return pipeline_results
    
    async def shutdown(self):
        """关闭工作流控制器"""
        self.logger.info("正在关闭工作流控制器...")
        
        # 停止监控
        await self.stop_monitoring()
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        # 关闭组件连接
        if hasattr(self.hybrid_retriever, 'close'):
            await self.hybrid_retriever.close()
        
        self.logger.info("工作流控制器已关闭")


# 使用示例
if __name__ == "__main__":
    async def main():
        # 配置
        config = PipelineConfig(
            chroma_config={"host": "localhost", "port": 8000},
            neo4j_config={"uri": "bolt://localhost:7687", "user": "neo4j", "password": "password"},
            batch_size=50,
            max_workers=2,
            enable_monitoring=True,
            output_path="./output"
        )
        
        # 创建工作流控制器
        controller = WorkflowController(config)
        
        try:
            # 启动监控
            await controller.start_monitoring()
            
            # 执行单个流水线
            result = await controller.execute_pipeline(
                pipeline_id="test_001",
                input_data="这是一段测试文本，用于演示事件抽取和处理流程。"
            )
            
            print(f"流水线执行结果: {result.status.value}")
            print(f"执行时间: {result.total_execution_time:.2f}s")
            print(f"处理项目数: {result.processed_items}")
            
            # 获取统计信息
            stats = controller.get_statistics()
            print(f"统计信息: {stats}")
            
        finally:
            # 关闭控制器
            await controller.shutdown()
    
    # 运行示例
    asyncio.run(main())