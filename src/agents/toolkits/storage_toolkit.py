# src/agents/toolkits/storage_toolkit.py

from typing import List, Dict, Any

# 导入现有的存储模块和数据模型
from src.storage.neo4j_event_storage import Neo4jEventStorage
from src.storage.chroma_event_storage import ChromaEventStorage
from src.models.event_data_model import Event, EventRelation, Entity
from src.event_logic.data_models import RelationType # 用于从字符串转换回枚举

class StorageToolkit:
    """
    封装数据持久化功能的工具包，供StorageAgent使用。
    """
    def __init__(self):
        """
        初始化工具包，建立与数据库的连接。
        """
        try:
            self.neo4j_storage = Neo4jEventStorage()
            self.chroma_storage = ChromaEventStorage()
        except Exception as e:
            print(f"Error initializing storage toolkit: {e}")
            # 可以在这里设置一个失败状态，防止后续方法被调用
            self.neo4j_storage = None
            self.chroma_storage = None

    def _dict_to_event(self, event_dict: Dict[str, Any]) -> Event:
        """辅助函数：将字典转换为Event对象。"""
        # 这个函数需要根据传入字典的实际结构进行健壮的转换
        event_data = event_dict.get("event_data", event_dict)
        
        # 转换参与者
        participants = [
            Entity(name=p.get("name"), entity_type=p.get("type")) 
            for p in event_data.get("participants", []) if isinstance(p, dict)
        ]

        return Event(
            id=event_dict.get("id") or event_data.get("id") or event_data.get("event_id"),
            event_type=event_data.get("event_type", "unknown"),
            text=event_data.get("text", ""),
            summary=event_data.get("summary", ""),
            participants=participants,
            # timestamp, subject, object 等字段也应在此处处理
        )

    def _dict_to_relation(self, rel_dict: Dict[str, Any]) -> EventRelation:
        """辅助函数：将字典转换为EventRelation对象。"""
        return EventRelation(
            id=rel_dict.get("id"),
            source_event_id=rel_dict.get("source_event_id"),
            target_event_id=rel_dict.get("target_event_id"),
            relation_type=RelationType(rel_dict.get("relation_type", "unknown")),
            confidence=rel_dict.get("confidence", 0.0),
            description=rel_dict.get("description", "")
        )

    def save_events_and_relationships(self, events: List[Dict[str, Any]], relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        将事件和关系持久化到数据库。
        这是暴露给 StorageAgent 的核心工具函数。

        Args:
            events: 事件字典列表。
            relationships: 关系字典列表。

        Returns:
            一个包含操作结果摘要的字典。
        """
        if not self.neo4j_storage or not self.chroma_storage:
            return {"status": "failed", "reason": "Storage services not initialized."}

        events_to_store = [self._dict_to_event(e) for e in events]
        relations_to_store = [self._dict_to_relation(r) for r in relationships]

        neo4j_events_saved = 0
        neo4j_relations_saved = 0
        errors = []

        # 1. 存储到 Neo4j
        for event in events_to_store:
            try:
                if self.neo4j_storage.store_event(event):
                    neo4j_events_saved += 1
            except Exception as e:
                errors.append(f"Failed to save event {event.id} to Neo4j: {e}")

        for relation in relations_to_store:
            try:
                if self.neo4j_storage.store_event_relation(relation):
                    neo4j_relations_saved += 1
            except Exception as e:
                errors.append(f"Failed to save relation {relation.id} to Neo4j: {e}")

        # 2. 存储到 ChromaDB
        try:
            chroma_success = self.chroma_storage.add_events(events_to_store)
            chroma_status = "success" if chroma_success else "failed"
        except Exception as e:
            chroma_status = "failed"
            errors.append(f"Failed to save events to ChromaDB: {e}")

        # 3. 构建返回结果
        summary = {
            "status": "success" if not errors else "partial_failure",
            "neo4j_events_processed": len(events_to_store),
            "neo4j_events_saved": neo4j_events_saved,
            "neo4j_relations_processed": len(relations_to_store),
            "neo4j_relations_saved": neo4j_relations_saved,
            "chroma_status": chroma_status,
            "errors": errors
        }
        
        return summary

# 示例用法
if __name__ == '__main__':
    # 这个示例需要Neo4j和ChromaDB/Ollama服务正在运行
    try:
        toolkit = StorageToolkit()
        
        # 模拟事件和关系数据
        sample_events = [
            {"id": "storage_evt_1", "event_type": "test_event", "summary": "第一个测试事件"},
            {"id": "storage_evt_2", "event_type": "test_event", "summary": "第二个测试事件"}
        ]
        sample_relations = [
            {"id": "storage_rel_1", "source_event_id": "storage_evt_1", "target_event_id": "storage_evt_2", "relation_type": "causal"}
        ]

        print("正在存储事件和关系...")
        result = toolkit.save_events_and_relationships(sample_events, sample_relations)

        print("\n存储操作完成。")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"\n运行示例时出错: {e}")
        print("请确保Neo4j, ChromaDB, 和 Ollama 服务正在运行。")
