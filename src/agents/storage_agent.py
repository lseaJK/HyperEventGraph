# src/agents/storage_agent.py
"""
This agent is responsible for all storage operations, interacting with both the
Neo4j graph database for structured knowledge and the ChromaDB vector store
for semantic search capabilities.
"""

import chromadb
import json
from neo4j import GraphDatabase, basic_auth
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

# Add project root to sys.path
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.core.config_loader import get_config

class StorageAgent:
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, chroma_db_path):
        """
        Initializes the StorageAgent and connects to the databases.
        """
        print("Initializing StorageAgent...")
        try:
            self._neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=basic_auth(neo4j_user, neo4j_password))
            self._neo4j_driver.verify_connectivity()
            print("Neo4j connection successful.")
        except Exception as e:
            print(f"Error connecting to Neo4j: {e}")
            raise

        try:
            self._chroma_client = chromadb.PersistentClient(path=str(chroma_db_path))
            # Initialize collections for different types of text data with correct embedding dimension
            # BGE-large-zh-v1.5 outputs 1024-dimensional embeddings
            metadata = {"hnsw:space": "cosine"}
            self._source_text_collection = self._chroma_client.get_or_create_collection(
                "source_texts", 
                embedding_function=None,  # We'll provide embeddings manually
                metadata=metadata
            )
            self._event_desc_collection = self._chroma_client.get_or_create_collection(
                "event_descriptions",
                embedding_function=None,
                metadata=metadata
            )
            self._entity_context_collection = self._chroma_client.get_or_create_collection(
                "entity_centric_contexts",
                embedding_function=None,
                metadata=metadata
            )
            print(f"ChromaDB client connected at '{chroma_db_path}'.")
        except Exception as e:
            print(f"Error connecting to ChromaDB: {e}")
            raise
            
        try:
            # Initialize the embedding model
            model_config = get_config().get('cortex', {}).get('vectorizer', {})
            model_name = model_config.get('model_name', 'BAAI/bge-large-zh-v1.5')
            cache_dir = get_config().get('model_settings', {}).get('cache_dir')
            self._embedding_model = SentenceTransformer(model_name, cache_folder=cache_dir)
            print(f"Embedding model '{model_name}' loaded for StorageAgent.")
        except Exception as e:
            print(f"Error loading embedding model for StorageAgent: {e}")
            self._embedding_model = None
            raise

    def close(self):
        """Closes the database connections."""
        if self._neo4j_driver:
            self._neo4j_driver.close()
            print("Neo4j connection closed.")

    def store_event(self, event_id: str, event_data: Dict[str, Any]):
        """
        Stores a single event and its entities in Neo4j and ChromaDB.
        """
        print(f"--- Storing event {event_id} ---")
        
        # 1. Store in Neo4j
        self._store_event_node_in_neo4j(event_id, event_data)

        # 2. Store in ChromaDB
        self._store_in_chromadb(event_id, event_data)

        print(f"--- Successfully stored event {event_id} ---")

    def store_relationships(self, relationships: List[Dict[str, Any]]):
        """
        Stores a list of relationships in Neo4j.
        """
        if not relationships:
            return
            
        print(f"--- Storing {len(relationships)} relationships in Neo4j ---")
        try:
            with self._neo4j_driver.session() as session:
                session.execute_write(self._create_event_relationships_tx, relationships)
            print("  (Neo4j) Successfully stored relationships.")
        except Exception as e:
            print(f"  (Neo4j) Error storing relationships: {e}")

    def _store_event_node_in_neo4j(self, event_id: str, event_data: Dict[str, Any]):
        """
        Helper to store just the event and entity nodes in Neo4j.
        """
        try:
            with self._neo4j_driver.session() as session:
                session.execute_write(self._create_event_and_entities_tx, event_id, event_data)
            print(f"  (Neo4j) Successfully stored event node {event_id} and its entity links.")
        except Exception as e:
            print(f"  (Neo4j) Error storing event {event_id}: {e}")

    @staticmethod
    def _create_event_and_entities_tx(tx, event_id: str, event_data: Dict[str, Any]):
        """
        A single transaction to create an event node, find/create entity nodes,
        and link them together. This ensures atomicity.
        """
        # 1. Create the main Event node
        # We store the full event data as properties for rich context.
        event_properties = {k: v if not isinstance(v, (dict, list)) else json.dumps(v) for k, v in event_data.items()}
        event_properties['eventId'] = event_id # Ensure the primary ID is a property
        
        query = """
        MERGE (e:Event {eventId: $event_id})
        SET e += $props
        """
        tx.run(query, event_id=event_id, props=event_properties)

        # 2. Create Entity nodes and link them to the Event
        # Assumes 'involved_entities' is a list of dicts with 'entity_name' and 'entity_type'
        entities = []
        involved_entities_str = event_data.get('involved_entities')
        if isinstance(involved_entities_str, str):
            try:
                entities = json.loads(involved_entities_str)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode 'involved_entities' JSON for event {event_id}")
                entities = []
        
        if not isinstance(entities, list):
            entities = []

        for entity in entities:
            entity_name = entity.get('entity_name')
            entity_type = entity.get('entity_type', 'Unknown') # Default type if not provided
            if not entity_name:
                continue

            query = """
            MERGE (ent:Entity {name: $entity_name})
            ON CREATE SET ent.type = $entity_type
            WITH ent
            MATCH (evt:Event {eventId: $event_id})
            MERGE (ent)-[:INVOLVED_IN]->(evt)
            """
            tx.run(query, entity_name=entity_name, entity_type=entity_type, event_id=event_id)

    @staticmethod
    def _create_event_relationships_tx(tx, relationships: List[Dict[str, Any]]):
        """
        A single transaction to create all relationships between events.
        """
        # Use native Cypher CREATE statement since APOC is not available
        query = """
        MATCH (source:Event {eventId: $source_id})
        MATCH (target:Event {eventId: $target_id})
        CREATE (source)-[r:RELATES_TO {type: $rel_type, reason: $reason}]->(target)
        RETURN r
        """
        for rel in relationships:
            # Basic validation
            if not all(k in rel for k in ['source_event_id', 'target_event_id', 'relationship_type']):
                print(f"Skipping invalid relationship object: {rel}")
                continue
            
            tx.run(query, 
                   source_id=rel['source_event_id'], 
                   target_id=rel['target_event_id'],
                   rel_type=rel['relationship_type'].upper(), # Ensure rel type is uppercase
                   reason=rel.get('analysis_reason', ''))

    def _store_in_chromadb(self, event_id: str, event_data: Dict[str, Any]):
        """
        Generates and stores embeddings for the event in ChromaDB.
        """
        if not self._embedding_model:
            print("  (ChromaDB) Skipping storage: embedding model not available.")
            return

        # 添加空值检查
        if not event_data:
            print(f"  (ChromaDB) Error: event_data is None for event {event_id}")
            return

        try:
            # 1. Store original source text
            source_text = event_data.get('source_text', '') or event_data.get('text', '') if event_data else ''
            if source_text:
                source_embedding = self._embedding_model.encode([source_text])[0].tolist()
                self._source_text_collection.add(
                    documents=[source_text],
                    embeddings=[source_embedding],
                    metadatas=[{"event_id": event_id, "type": "source_text"}],
                    ids=[f"{event_id}_source"]
                )

            # 2. Store event description - 安全处理None值
            structured_data = event_data.get('structured_data') if event_data else None
            
            # 如果structured_data是None，跳过处理
            if structured_data is None:
                print(f"  (ChromaDB) Skipping event description: structured_data is None for {event_id}")
            else:
                if isinstance(structured_data, str):
                    try:
                        structured_data = json.loads(structured_data)
                    except json.JSONDecodeError:
                        structured_data = {}
                
                if isinstance(structured_data, dict):
                    event_description = structured_data.get('description', '')
                    if event_description:
                        desc_embedding = self._embedding_model.encode([event_description])[0].tolist()
                        self._event_desc_collection.add(
                            documents=[event_description],
                            embeddings=[desc_embedding],
                            metadatas=[{"event_id": event_id, "type": "event_description"}],
                            ids=[f"{event_id}_desc"]
                        )

            # 3. Store entity-centric context - 安全处理None值
            entities = event_data.get('involved_entities') if event_data else None
            
            # 如果involved_entities是None，跳过处理
            if entities is None:
                print(f"  (ChromaDB) Skipping entities: involved_entities is None for {event_id}")
            else:
                if isinstance(entities, str):
                    try:
                        entities = json.loads(entities)
                    except json.JSONDecodeError:
                        entities = []
                
                if not isinstance(entities, list):
                    entities = []

                entity_contexts = []
                entity_ids = []
                event_description = ""
                
                # 获取事件描述用于实体上下文
                if structured_data and isinstance(structured_data, dict):
                    event_description = structured_data.get('description', '')
                
                for i, entity in enumerate(entities):
                    # 安全检查entity不为None且为字典
                    if entity is not None and isinstance(entity, dict):
                        entity_name = entity.get('entity_name')
                        if entity_name and event_description:
                            context = f"实体: {entity_name}; 事件: {event_description}"
                            entity_contexts.append(context)
                            entity_ids.append(f"{event_id}_entity_{i}")
            
                if entity_contexts:
                    entity_embeddings = self._embedding_model.encode(entity_contexts).tolist()
                    self._entity_context_collection.add(
                        documents=entity_contexts,
                        embeddings=entity_embeddings,
                        metadatas=[{"event_id": event_id, "type": "entity_context"}] * len(entity_contexts),
                        ids=entity_ids
                    )
            
            print(f"  (ChromaDB) Successfully stored vectors for event {event_id}.")

        except Exception as e:
            print(f"  (ChromaDB) Error storing vectors for event {event_id}: {e}")

if __name__ == '__main__':
    # Example usage for testing
    print("Testing StorageAgent initialization...")
    # This requires a running Neo4j instance and a valid config.yaml
    # For now, this just demonstrates the structure.
    from src.core.config_loader import load_config, get_config
    load_config("config.yaml")
    config = get_config().get('storage', {})
    neo4j_config = config.get('neo4j', {})
    chroma_config = config.get('chroma', {})
    
    try:
        agent = StorageAgent(
            neo4j_uri=neo4j_config.get('uri'),
            neo4j_user=neo4j_config.get('user'),
            neo4j_password=neo4j_config.get('password'),
            chroma_db_path=chroma_config.get('path')
        )
        agent.close()
    except Exception as e:
        print(f"Test failed: {e}")
