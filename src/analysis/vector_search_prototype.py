# src/analysis/vector_search_prototype.py
"""
This script prototypes the hierarchical vectorization strategy using ChromaDB.
It loads structured events, generates three different types of text representations
for each event, embeds them, and stores them in a ChromaDB collection.
This serves as a prototype for the future VectorStorageAgent.
"""

import json
import chromadb
import shutil
from pathlib import Path
from tqdm import tqdm
import sys

# Add project root to sys.path to import other modules
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config
from src.cortex.vectorization_service import VectorizationService

# --- Configuration ---
INPUT_FILE_PATH = "output/extraction/structured_events.jsonl"
CHROMA_DB_PATH = "chroma_db_prototype"
COLLECTION_NAME = "hierarchical_events"
RECORD_LIMIT = 100 # Limit records for a quick test

def load_data(file_path: Path, limit: int | None) -> list[dict]:
    """Loads data from the JSONL file."""
    print(f"Loading data from {file_path}...")
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if limit is not None and i >= limit:
                print(f"Record limit of {limit} reached.")
                break
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    print(f"Successfully loaded {len(records)} records.")
    return records

def prepare_and_embed_data(records: list[dict], vectorizer: VectorizationService):
    """
    Prepares documents, metadatas, and ids for ChromaDB batch insertion.
    Implements the hierarchical vectorization strategy.
    """
    documents = []
    metadatas = []
    ids = []
    
    print("Preparing and embedding data with hierarchical strategy...")
    for record in tqdm(records, desc="Processing records"):
        event_id = record.get('event_id')
        if not event_id:
            continue

        # 1. Source Text
        source_text = record.get('text', '')
        if source_text:
            documents.append(source_text)
            metadatas.append({"event_id": event_id, "type": "source_text"})
            ids.append(f"{event_id}_source")

        # 2. Event Description
        description = record.get('description', '')
        if description:
            documents.append(description)
            metadatas.append({"event_id": event_id, "type": "description"})
            ids.append(f"{event_id}_desc")

        # 3. Entity-centric Context
        entities = record.get('involved_entities', [])
        if isinstance(entities, list) and entities:
            entity_names = [e.get('entity_name', '') for e in entities]
            entity_context = "Related Entities: " + ", ".join(filter(None, entity_names))
            documents.append(entity_context)
            metadatas.append({"event_id": event_id, "type": "entity_context"})
            ids.append(f"{event_id}_entities")

    # Batch embed all prepared documents at once for efficiency
    embeddings = vectorizer.get_embeddings(documents)
    
    return documents, embeddings, metadatas, ids

def main():
    """Main entry point for the script."""
    load_config("config.yaml")

    try:
        # Clean up old database directory for a fresh test
        if Path(CHROMA_DB_PATH).exists():
            print(f"Removing old database directory: {CHROMA_DB_PATH}")
            shutil.rmtree(CHROMA_DB_PATH)

        records = load_data(Path(INPUT_FILE_PATH), RECORD_LIMIT)
        if not records:
            return

        vectorizer = VectorizationService()
        chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        
        print(f"Creating new ChromaDB collection: '{COLLECTION_NAME}'")
        collection = chroma_client.create_collection(name=COLLECTION_NAME)

        documents, embeddings, metadatas, ids = prepare_and_embed_data(records, vectorizer)
        
        if not documents:
            print("No valid documents to insert. Exiting.")
            return
            
        print(f"Batch inserting {len(documents)} vectors into ChromaDB...")
        collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print("Insertion complete.")

        print("\n--- Verification Query ---")
        query_text = "华为和苹果的竞争"
        query_embedding = vectorizer.get_embedding(query_text)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5
        )
        
        print(f"Querying for: '{query_text}'")
        print("Top 5 results:")
        for i, (doc, dist, meta) in enumerate(zip(results['documents'][0], results['distances'][0], results['metadatas'][0])):
            print(f"  {i+1}. Distance: {dist:.4f} (Type: {meta.get('type')})\n     Text: {doc[:150]}...\n")

    except Exception as e:
        import traceback
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
