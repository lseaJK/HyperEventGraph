#!/usr/bin/env python3
"""
Enhanced Cortex Agent - 智能多维度聚类实现
作者: HyperEventGraph 架构师
时间: 2025-08-16

核心改进：
1. 多维度特征提取（时间、实体、语义、类型）
2. 层次化聚类策略
3. 动态参数调整
4. 智能故事生成
"""

import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import re
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import get_config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedCortexAgent:
    """增强版 Cortex 代理 - 智能事件聚类和故事生成"""
    
    def __init__(self, embedding_model=None):
        """初始化增强版 Cortex 代理"""
        self.config = get_config()
        self.cortex_config = self.config.get('cortex', {})
        
        # 聚类参数
        self.time_window_days = self.cortex_config.get('time_window_days', 30)
        self.entity_weight = self.cortex_config.get('entity_weight', 0.3)
        self.semantic_weight = self.cortex_config.get('semantic_weight', 0.4)
        self.time_weight = self.cortex_config.get('time_weight', 0.2)
        self.type_weight = self.cortex_config.get('type_weight', 0.1)
        
        # DBSCAN 参数
        self.dbscan_eps = self.cortex_config.get('dbscan_eps', 0.6)
        self.dbscan_min_samples = self.cortex_config.get('dbscan_min_samples', 2)
        
        # 加载嵌入模型
        if embedding_model:
            self.embedding_model = embedding_model
        else:
            self._load_embedding_model()
    
    def _load_embedding_model(self):
        """加载 BGE 嵌入模型"""
        try:
            from sentence_transformers import SentenceTransformer
            model_name = self.cortex_config.get('vectorizer', {}).get('model_name', 'BAAI/bge-large-zh-v1.5')
            self.embedding_model = SentenceTransformer(model_name)
            logger.info(f"✅ 加载嵌入模型: {model_name}")
        except Exception as e:
            logger.error(f"❌ 嵌入模型加载失败: {e}")
            self.embedding_model = None
    
    def parse_event_date(self, date_str: str) -> datetime:
        """解析多种格式的事件日期"""
        if not date_str:
            return datetime.now()
        
        # 常见日期格式的正则表达式
        patterns = [
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),      # 2023-07-21
            (r'(\d{4})-H(\d)', None),                          # 2023-H1 (上半年)
            (r'(\d{4})-Q(\d)', None),                          # 2023-Q1 (季度)
            (r'(\d{4})', '%Y'),                                # 2023 (年)
        ]
        
        for pattern, fmt in patterns:
            match = re.match(pattern, str(date_str))
            if match:
                if 'H' in date_str:  # 半年
                    year = int(match.group(1))
                    half = int(match.group(2))
                    month = 6 if half == 2 else 1
                    return datetime(year, month, 1)
                elif 'Q' in date_str:  # 季度
                    year = int(match.group(1))
                    quarter = int(match.group(2))
                    month = (quarter - 1) * 3 + 1
                    return datetime(year, month, 1)
                elif fmt:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except:
                        continue
        
        # 默认返回当前时间
        logger.warning(f"⚠️ 无法解析日期格式: {date_str}")
        return datetime.now()
    
    def extract_event_features(self, events: List[Dict]) -> np.ndarray:
        """提取多维度事件特征"""
        logger.info(f"🔍 开始提取 {len(events)} 个事件的特征...")
        
        features = []
        
        for i, event in enumerate(events):
            feature_vector = []
            
            # 1. 时间特征
            event_date = self.parse_event_date(event.get('event_date', ''))
            timestamp = event_date.timestamp()
            feature_vector.append(timestamp)
            
            # 2. 实体特征 - 计算实体数量和重要性
            entities = event.get('involved_entities', [])
            if isinstance(entities, str):
                try:
                    entities = json.loads(entities)
                except:
                    entities = []
            
            entity_count = len(entities) if entities else 0
            entity_types = set()
            entity_roles = set()
            
            for entity in entities:
                if isinstance(entity, dict):
                    entity_types.add(entity.get('entity_type', ''))
                    entity_roles.add(entity.get('role_in_event', ''))
            
            feature_vector.extend([
                entity_count,
                len(entity_types),
                len(entity_roles)
            ])
            
            # 3. 事件类型特征
            event_type = event.get('assigned_event_type', event.get('event_type', ''))
            micro_type = event.get('micro_event_type', '')
            
            # 简单的类型编码（可以用更复杂的嵌入）
            type_hash = hash(event_type) % 100
            micro_hash = hash(micro_type) % 100
            
            feature_vector.extend([type_hash, micro_hash])
            
            # 4. 量化数据特征
            structured_data = event.get('structured_data', {})
            if isinstance(structured_data, str):
                try:
                    structured_data = json.loads(structured_data)
                except:
                    structured_data = {}
            
            quantitative_data = structured_data.get('quantitative_data', {})
            has_quantitative = 1 if quantitative_data else 0
            
            feature_vector.append(has_quantitative)
            
            features.append(feature_vector)
        
        # 标准化特征
        scaler = StandardScaler()
        features_array = np.array(features)
        normalized_features = scaler.fit_transform(features_array)
        
        logger.info(f"✅ 特征提取完成: {normalized_features.shape}")
        return normalized_features
    
    def extract_semantic_features(self, events: List[Dict]) -> np.ndarray:
        """提取语义特征（使用 BGE 模型）"""
        if not self.embedding_model:
            logger.warning("⚠️ 嵌入模型未加载，跳过语义特征")
            return np.zeros((len(events), 1024))  # BGE 模型的维度
        
        logger.info("🔍 提取语义特征...")
        
        texts = []
        for event in events:
            # 组合多个文本字段
            description = ""
            structured_data = event.get('structured_data', {})
            if isinstance(structured_data, str):
                try:
                    structured_data = json.loads(structured_data)
                except:
                    structured_data = {}
            
            if structured_data:
                description = structured_data.get('description', '')
            
            if not description:
                description = event.get('source_text', '')[:200]  # 截取前200字符
            
            texts.append(description or "无描述")
        
        # 批量编码
        try:
            embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
            logger.info(f"✅ 语义特征提取完成: {embeddings.shape}")
            return embeddings
        except Exception as e:
            logger.error(f"❌ 语义特征提取失败: {e}")
            return np.zeros((len(events), 1024))
    
    def calculate_entity_similarity_matrix(self, events: List[Dict]) -> np.ndarray:
        """计算实体相似性矩阵"""
        n_events = len(events)
        similarity_matrix = np.zeros((n_events, n_events))
        
        for i in range(n_events):
            for j in range(i + 1, n_events):
                # 获取两个事件的实体
                entities_i = events[i].get('involved_entities', [])
                entities_j = events[j].get('involved_entities', [])
                
                if isinstance(entities_i, str):
                    try:
                        entities_i = json.loads(entities_i)
                    except:
                        entities_i = []
                
                if isinstance(entities_j, str):
                    try:
                        entities_j = json.loads(entities_j)
                    except:
                        entities_j = []
                
                # 提取实体名称
                names_i = set()
                names_j = set()
                
                for entity in entities_i:
                    if isinstance(entity, dict):
                        names_i.add(entity.get('entity_name', ''))
                
                for entity in entities_j:
                    if isinstance(entity, dict):
                        names_j.add(entity.get('entity_name', ''))
                
                # 计算 Jaccard 相似性
                if names_i or names_j:
                    intersection = len(names_i & names_j)
                    union = len(names_i | names_j)
                    jaccard = intersection / union if union > 0 else 0
                    similarity_matrix[i][j] = jaccard
                    similarity_matrix[j][i] = jaccard
        
        return similarity_matrix
    
    def intelligent_clustering(self, events: List[Dict]) -> List[List[int]]:
        """智能多维度聚类"""
        logger.info(f"🧠 开始智能聚类 {len(events)} 个事件...")
        
        if len(events) < 2:
            return [[0]] if events else []
        
        # 1. 提取多维度特征
        structural_features = self.extract_event_features(events)
        semantic_features = self.extract_semantic_features(events)
        entity_similarity = self.calculate_entity_similarity_matrix(events)
        
        # 2. 组合特征
        # 语义特征降维（PCA 或简单平均）
        semantic_reduced = np.mean(semantic_features.reshape(len(events), -1, 32), axis=2)  # 简单降维
        
        # 组合所有特征
        combined_features = np.hstack([
            structural_features * self.time_weight,
            semantic_reduced * self.semantic_weight,
        ])
        
        # 3. 添加实体相似性到距离计算中
        def custom_distance(X):
            """自定义距离函数，结合欧几里得距离和实体相似性"""
            from sklearn.metrics.pairwise import euclidean_distances
            euclidean_dist = euclidean_distances(X)
            
            # 结合实体相似性（相似性高的事件距离更近）
            entity_dist = 1 - entity_similarity
            
            # 加权组合
            combined_dist = (
                euclidean_dist * (1 - self.entity_weight) +
                entity_dist * self.entity_weight
            )
            
            return combined_dist
        
        # 4. DBSCAN 聚类
        # 由于自定义距离函数的复杂性，先用标准 DBSCAN，然后基于实体相似性进行后处理
        dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples)
        cluster_labels = dbscan.fit_predict(combined_features)
        
        # 5. 后处理：合并高实体相似性的簇
        clusters = self._post_process_clusters(cluster_labels, entity_similarity, events)
        
        logger.info(f"✅ 聚类完成: 发现 {len(clusters)} 个故事簇")
        for i, cluster in enumerate(clusters):
            logger.info(f"   簇 {i}: {len(cluster)} 个事件")
        
        return clusters
    
    def _post_process_clusters(self, cluster_labels: np.ndarray, entity_similarity: np.ndarray, events: List[Dict]) -> List[List[int]]:
        """后处理聚类结果"""
        # 将 DBSCAN 标签转换为簇列表
        clusters = {}
        noise_points = []
        
        for i, label in enumerate(cluster_labels):
            if label == -1:  # 噪声点
                noise_points.append(i)
            else:
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(i)
        
        # 尝试将噪声点分配到相似的簇
        for noise_idx in noise_points:
            best_cluster = None
            best_similarity = 0
            
            for cluster_id, cluster_indices in clusters.items():
                # 计算与簇中所有事件的平均实体相似性
                similarities = [entity_similarity[noise_idx][idx] for idx in cluster_indices]
                avg_similarity = np.mean(similarities)
                
                if avg_similarity > best_similarity and avg_similarity > 0.1:  # 阈值
                    best_similarity = avg_similarity
                    best_cluster = cluster_id
            
            if best_cluster is not None:
                clusters[best_cluster].append(noise_idx)
            else:
                # 创建单独的簇
                new_cluster_id = max(clusters.keys()) + 1 if clusters else 0
                clusters[new_cluster_id] = [noise_idx]
        
        return list(clusters.values())
    
    def generate_enhanced_story_summary(self, event_indices: List[int], events: List[Dict]) -> str:
        """生成增强的故事摘要"""
        cluster_events = [events[i] for i in event_indices]
        
        # 提取关键信息
        entities = set()
        time_range = []
        event_types = set()
        descriptions = []
        
        for event in cluster_events:
            # 实体
            event_entities = event.get('involved_entities', [])
            if isinstance(event_entities, str):
                try:
                    event_entities = json.loads(event_entities)
                except:
                    event_entities = []
            
            for entity in event_entities:
                if isinstance(entity, dict):
                    entities.add(entity.get('entity_name', ''))
            
            # 时间
            event_date = self.parse_event_date(event.get('event_date', ''))
            time_range.append(event_date)
            
            # 类型
            event_types.add(event.get('assigned_event_type', ''))
            
            # 描述
            structured_data = event.get('structured_data', {})
            if isinstance(structured_data, str):
                try:
                    structured_data = json.loads(structured_data)
                except:
                    structured_data = {}
            
            description = structured_data.get('description', '')
            if description:
                descriptions.append(description)
        
        # 构建摘要
        summary_parts = []
        
        # 时间范围
        if time_range:
            time_range.sort()
            start_time = time_range[0]
            end_time = time_range[-1]
            
            if start_time.year == end_time.year:
                if start_time.month == end_time.month:
                    time_str = f"{start_time.year}年{start_time.month}月"
                else:
                    time_str = f"{start_time.year}年{start_time.month}-{end_time.month}月"
            else:
                time_str = f"{start_time.year}-{end_time.year}年"
            
            summary_parts.append(f"时间：{time_str}")
        
        # 主要实体
        if entities:
            entities_list = list(entities)[:5]  # 最多5个实体
            summary_parts.append(f"涉及实体：{', '.join(entities_list)}")
        
        # 事件类型
        if event_types:
            types_list = list(event_types)
            summary_parts.append(f"事件类型：{', '.join(types_list)}")
        
        # 关键描述
        if descriptions:
            key_description = descriptions[0][:100] + "..." if descriptions[0] else ""
            summary_parts.append(f"关键事件：{key_description}")
        
        return " | ".join(summary_parts)

if __name__ == "__main__":
    # 测试代码
    agent = EnhancedCortexAgent()
    print("✅ Enhanced Cortex Agent 初始化完成")
