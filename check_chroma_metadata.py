

import yaml
import sys
from pathlib import Path
import chromadb
import json

def check_first_record_metadata():
    """
    Connects to ChromaDB, fetches the first record from a collection,
    and prints its full metadata to check for an original story_id.
    """
    project_root = Path(__file__).resolve().parent
    config_path = project_root / "config.yaml"
    
    if not config_path.exists():
        print(f"❌ Error: config.yaml not found at {config_path}")
        return

    print(f"📖 Loading configuration from {config_path}...")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    storage_config = config.get('storage', {})
    chroma_config_dict = storage_config.get('chroma', {})

    print("\n" + "="*20 + " ChromaDB Metadata Check " + "="*20)
    if not chroma_config_dict or 'path' not in chroma_config_dict:
        print("❓ ChromaDB path configuration not found in config.yaml.")
        return

    chroma_path = project_root / chroma_config_dict['path']
    print(f"🔍 Accessing ChromaDB at: {chroma_path}")
    
    if not chroma_path.exists():
        print(f"❌ Error: ChromaDB path does not exist at '{chroma_path}'.")
        return

    try:
        client = chromadb.PersistentClient(path=str(chroma_path))
        collections = client.list_collections()
        
        if not collections:
            print("ℹ️ No collections found in ChromaDB.")
            return

        # Pick the first available collection for inspection
        collection_to_check = collections[0]
        collection_name = collection_to_check.name
        print(f"🔬 Inspecting the first record of collection: '{collection_name}'...")

        # Fetch one record from the collection
        record = collection_to_check.get(limit=1, include=["metadatas", "documents"])

        if not record or not record['ids']:
            print(f"ℹ️ Collection '{collection_name}' is empty.")
            return

        metadata = record['metadatas'][0]
        document = record['documents'][0]
        record_id = record['ids'][0]

        print("\n" + "--- Record Details ---")
        print(f"🆔 Record ID: {record_id}")
        print(f"📄 Document Text (Preview):")
        print(f"   '{document[:200]}...'")
        print("\n" + "--- Metadata Found ---")
        
        if metadata:
            # Pretty print the metadata dictionary
            print(json.dumps(metadata, indent=4, ensure_ascii=False))
            
            # Explicitly check for the key we need
            if 'story_id' in metadata:
                print("\n" + "✅ SUCCESS: Found 'story_id' in metadata!")
            elif 'source_id' in metadata:
                print("\n" + "✅ SUCCESS: Found 'source_id' in metadata!")
            else:
                print("\n" + "⚠️ WARNING: 'story_id' or 'source_id' not found in the metadata of this record.")
        else:
            print("  (No metadata found for this record)")
        print("------------------------")


    except Exception as e:
        print(f"❌ An error occurred while checking ChromaDB: {e}")

if __name__ == "__main__":
    check_first_record_metadata()

