# src/analysis/hybrid_retrieval_prototype.py
"""
This script prototypes a hybrid retrieval system that combines graph-based
exact-match search with vector-based semantic search.
It reuses components from the graph and vector prototypes to demonstrate
the combined power of both approaches.
"""

import sys
from pathlib import Path
import networkx as nx
import chromadb

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

# Reuse logic from our previous prototypes
from src.core.config_loader import load_config
from src.cortex.vectorization_service import VectorizationService
from src.analysis.build_micro_graph import load_data as load_graph_data, build_graph
from src.analysis.vector_search_prototype import prepare_and_embed_data

# --- Configuration ---
INPUT_FILE_PATH = "output/extraction/structured_events.jsonl"
CHROMA_DB_PATH = "chroma_db_prototype" # Use the same DB as the vector prototype
COLLECTION_NAME = "hierarchical_events"
RECORD_LIMIT = 100

class HybridRetriever:
    """A prototype for a hybrid graph and vector retriever."""

    def __init__(self):
        print("Initializing Hybrid Retriever...")
        self.graph = None
        self.vector_collection = None
        self.vectorizer = None
        self._setup()
        print("Hybrid Retriever initialized successfully.")

    def _setup(self):
        """Loads data and builds the necessary graph and vector stores."""
        # Load data
        records = load_graph_data(Path(INPUT_FILE_PATH), RECORD_LIMIT)
        if not records:
            raise ValueError("No data loaded, cannot proceed.")

        # Build graph store
        print("\n--- Building Graph Store (NetworkX) ---")
        self.graph = build_graph(records)

        # Build vector store
        print("\n--- Building Vector Store (ChromaDB) ---")
        self.vectorizer = VectorizationService()
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        # Check if the collection exists and has data
        try:
            self.vector_collection = chroma_client.get_collection(name=COLLECTION_NAME)
            if self.vector_collection.count() > 0:
                print(f"Using existing ChromaDB collection '{COLLECTION_NAME}' with {self.vector_collection.count()} records.")
            else:
                raise ValueError("Collection is empty.")
        except (ValueError, IndexError): # ChromaDB can throw different errors
            print(f"Collection '{COLLECTION_NAME}' not found or empty. Rebuilding...")
            self.vector_collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
            docs, embeds, metas, ids = prepare_and_embed_data(records, self.vectorizer)
            if docs:
                self.vector_collection.add(embeddings=embeds, documents=docs, metadatas=metas, ids=ids)
            print("Vector store rebuilt.")

    def search(self, query_text: str, entity_keyword: str, top_k: int = 3):
        """Performs a hybrid search and prints the results."""
        print("\n" + "="*70)
        print(f"Performing Hybrid Search for Query: '{query_text}'")
        print(f"Graph Keyword (Entity): '{entity_keyword}'")
        print("="*70)

        # 1. Graph-based Search (Exact Match)
        print("\n--- 1. Graph Search Results (Exact & Connected) ---")
        graph_results = []
        if self.graph.has_node(entity_keyword):
            # Find all neighbors of the entity node that are events
            for neighbor in self.graph.neighbors(entity_keyword):
                if self.graph.nodes[neighbor].get('type') == 'event':
                    event_node = self.graph.nodes[neighbor]
                    graph_results.append({
                        "event_id": neighbor,
                        "description": event_node.get('title', 'N/A')
                    })
            if graph_results:
                for i, res in enumerate(graph_results):
                    print(f"  {i+1}. Event ID: {res['event_id']}\n     Description: {res['description'][:150]}...\n")
            else:
                print(f"Found entity '{entity_keyword}', but it's not connected to any events in this data slice.")
        else:
            print(f"Entity '{entity_keyword}' not found in the graph.")

        # 2. Vector-based Search (Semantic Similarity)
        print("\n--- 2. Vector Search Results (Semantically Similar) ---")
        query_embedding = self.vectorizer.get_embedding(query_text)
        vector_results = self.vector_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        for i, (doc, dist, meta) in enumerate(zip(vector_results['documents'][0], vector_results['distances'][0], vector_results['metadatas'][0])):
            print(f"  {i+1}. Distance: {dist:.4f} (Type: {meta.get('type')}, Event ID: {meta.get('event_id')})\n     Text: {doc[:150]}...\n")

def main():
    """Main entry point for the script."""
    load_config("config.yaml")
    try:
        retriever = HybridRetriever()
        # Example Query: Find events related to "华为" (Huawei)
        retriever.search(
            query_text="华为的供应链和合作伙伴",
            entity_keyword="华为"
        )
        # Example Query 2: Find events related to "台积电" (TSMC)
        retriever.search(
            query_text="台积电的产能和技术",
            entity_keyword="台积电"
        )
    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()