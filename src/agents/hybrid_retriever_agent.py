# src/agents/hybrid_retriever_agent.py
"""
This agent is responsible for retrieving relevant context from both the graph
and vector databases to enrich the input for other agents.
"""

import jieba.analyse
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from unittest.mock import MagicMock

# Add project root to sys.path
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.agents.storage_agent import StorageAgent
from src.core.config_loader import get_config

class HybridRetrieverAgent:
    def __init__(self, storage_agent: StorageAgent):
        """
        Initializes the HybridRetrieverAgent.

        Args:
            storage_agent: An instance of StorageAgent to interact with the databases.
        """
        self.storage_agent = storage_agent
        
        try:
            # Initialize the embedding model, reusing the same config as StorageAgent
            model_config = get_config().get('cortex', {}).get('vectorizer', {})
            model_name = model_config.get('model_name', 'BAAI/bge-large-zh-v1.5')
            cache_dir = get_config().get('model_settings', {}).get('cache_dir')
            self._embedding_model = SentenceTransformer(model_name, cache_folder=cache_dir)
            print(f"Embedding model '{model_name}' loaded for HybridRetrieverAgent.")
        except Exception as e:
            print(f"Error loading embedding model for HybridRetrieverAgent: {e}")
            self._embedding_model = None
            raise
            
        print("HybridRetrieverAgent initialized.")

    def retrieve_context(self, text: str, top_k_entities: int = 5, top_k_similar: int = 3) -> str:
        """
        Retrieves context from both databases and synthesizes a summary.

        Args:
            text: The input text to analyze for context retrieval.
            top_k_entities: The number of top entities to extract from the text.
            top_k_similar: The number of similar documents/events to retrieve.

        Returns:
            A string containing the synthesized context summary.
        """
        print(f"--- Retrieving context for text: '{text[:100]}...' ---")
        
        # 1. Quick Entity Extraction
        entities = self._extract_key_entities(text, top_k=top_k_entities)
        print(f"  Extracted key entities: {entities}")

        # 2. Parallel Queries (simulated with sequential calls for now)
        graph_facts = self._query_graph_database(entities)
        vector_insights = self._query_vector_database(text, top_k=top_k_similar)

        # 3. Synthesize Context Summary
        summary = self._synthesize_summary(graph_facts, vector_insights)
        
        print("--- Context retrieval complete. ---")
        return summary

    def _extract_key_entities(self, text: str, top_k: int) -> List[str]:
        """
        Extracts key entities/keywords from text using jieba, with a stopword filter.
        """
        # A simple, extendable stopword list
        stopwords = {'the', 'a', 'an', 'in', 'on', 'of', 'for', 'with', 'reportedly', 'chinese', 'chipmaker'}
        
        tags = jieba.analyse.extract_tags(text, topK=top_k)
        
        # Filter out stopwords and single-character words
        filtered_tags = [tag for tag in tags if tag.lower() not in stopwords and len(tag) > 1]
        
        return filtered_tags

    def _query_graph_database(self, entities: List[str]) -> List[str]:
        """
        Queries the graph database for facts related to the extracted entities.
        """
        if not entities:
            return []

        print(f"  (GraphDB) Querying for facts related to: {entities}")
        facts = []
        try:
            with self.storage_agent._neo4j_driver.session() as session:
                for entity in entities:
                    # This query finds events the entity is involved in, and any relationships
                    # those events have with other events.
                    query = """
                    MATCH (ent:Entity {name: $entity_name})-[:INVOLVED_IN]->(evt1:Event)
                    OPTIONAL MATCH (evt1)-[r]-(evt2:Event)
                    RETURN ent.name AS entity, type(r) AS relationship, evt2.eventId AS related_event_id, evt1.assigned_event_type as event_type
                    LIMIT 5 // Limit results per entity to avoid overwhelming context
                    """
                    result = session.run(query, entity_name=entity)
                    for record in result:
                        fact = f"实体 '{record['entity']}' 参与了 '{record['event_type']}' 事件"
                        if record['relationship']:
                            fact += f", 该事件与事件 {record['related_event_id']} 存在 '{record['relationship']}' 关系。"
                        else:
                            fact += "。"
                        facts.append(fact)
            
            print(f"  (GraphDB) Found {len(facts)} facts.")
            return list(set(facts)) # Return unique facts
        except Exception as e:
            print(f"  (GraphDB) An error occurred during graph query: {e}")
            return []

    def _query_vector_database(self, text: str, top_k: int) -> List[str]:
        """
        Queries the vector database for semantically similar events or documents.
        """
        if not self._embedding_model:
            print("  (VectorDB) Skipping query: embedding model not available.")
            return []

        print(f"  (VectorDB) Querying for documents similar to: '{text[:50]}...'")
        try:
            query_embedding = self._embedding_model.encode(text, convert_to_tensor=False).tolist()
            
            # Query all three collections
            source_results = self.storage_agent._source_text_collection.query(
                query_embeddings=[query_embedding], n_results=top_k
            )
            event_results = self.storage_agent._event_desc_collection.query(
                query_embeddings=[query_embedding], n_results=top_k
            )
            entity_results = self.storage_agent._entity_context_collection.query(
                query_embeddings=[query_embedding], n_results=top_k
            )

            # Combine and deduplicate results
            all_documents = set()
            if source_results and source_results['documents']:
                all_documents.update(source_results['documents'][0])
            if event_results and event_results['documents']:
                all_documents.update(event_results['documents'][0])
            if entity_results and entity_results['documents']:
                all_documents.update(entity_results['documents'][0])

            print(f"  (VectorDB) Found {len(all_documents)} unique similar documents.")
            return list(all_documents)

        except Exception as e:
            print(f"  (VectorDB) An error occurred during vector query: {e}")
            return []

    def _synthesize_summary(self, graph_facts: List[str], vector_insights: List[str]) -> str:
        """
        Combines the results from both databases into a single context summary.
        """
        if not graph_facts and not vector_insights:
            return "No relevant historical context was found."

        summary = "### Retrieved Context Summary ###\n"
        if graph_facts:
            summary += "Structured Facts from Knowledge Graph:\n"
            for fact in graph_facts:
                summary += f"- {fact}\n"
        
        if vector_insights:
            summary += "\nSemantically Similar Past Events/Documents:\n"
            for insight in vector_insights:
                summary += f"- {insight}\n"
        
        summary += "#################################\n"
        return summary

if __name__ == '__main__':
    # Example Usage (requires a running StorageAgent and populated DBs)
    print("Testing HybridRetrieverAgent...")
    # This is a conceptual test. A real test would need a mocked StorageAgent.
    from src.core.config_loader import load_config
    load_config('config.yaml')
    mock_storage_agent = MagicMock() # Requires unittest.mock
    retriever = HybridRetrieverAgent(storage_agent=mock_storage_agent)
    test_text = "据报道，中国芯片制造商中芯国际（SMIC）已成功量产7纳米芯片，这标志着其在先进半导体制造领域取得了重大突破。"
    context = retriever.retrieve_context(test_text)
    print("\nGenerated Context:\n", context)
