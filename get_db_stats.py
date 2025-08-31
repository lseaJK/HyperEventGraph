import yaml
import sys
from pathlib import Path
import chromadb

# Add project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Now we can import from the src directory
from src.storage.neo4j_event_storage import Neo4jConfig, Neo4jEventStorage

def get_database_stats():
    """
    Connects to Neo4j and ChromaDB based on config.yaml and prints their statistics.
    Includes a diagnostic query for Neo4j node labels.
    """
    config_path = project_root / "config.yaml"
    if not config_path.exists():
        print(f"❌ Error: config.yaml not found at {config_path}")
        return

    print(f"📖 Loading configuration from {config_path}...")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    storage_config = config.get('storage', {})
    neo4j_config_dict = storage_config.get('neo4j', {})
    chroma_config_dict = storage_config.get('chroma', {})

    # --- Neo4j Statistics ---
    neo4j_storage = None
    print("\n" + "="*20 + " Neo4j Status " + "="*20)
    if not neo4j_config_dict:
        print("❓ Neo4j configuration not found in config.yaml.")
    else:
        try:
            print("🔌 Connecting to Neo4j...")
            if 'user' in neo4j_config_dict and 'username' not in neo4j_config_dict:
                neo4j_config_dict['username'] = neo4j_config_dict.pop('user')

            neo4j_config = Neo4jConfig(**neo4j_config_dict)
            neo4j_storage = Neo4jEventStorage(config=neo4j_config)
            
            if neo4j_storage.test_connection():
                print("✅ Neo4j connection successful.")
                print("📊 Fetching graph statistics...")
                stats = neo4j_storage.get_database_statistics()
                
                total_nodes = stats.get('total_events', 0) + stats.get('total_entities', 0)
                total_relations = stats.get('total_relations', 0)
                
                print("\n--- Knowledge Graph Summary ---")
                print(f"  🔹 Total Nodes (Events + Entities): {total_nodes:,}")
                print(f"     - Events:   {stats.get('total_events', 0):,}")
                print(f"     - Entities: {stats.get('total_entities', 0):,}")
                print(f"  🔹 Total Edges (All Relations):     {total_relations:,}")
                print("---------------------------------")

                # --- Diagnostic Query for All Node Labels ---
                print("\n🔬 Running diagnostic query for all node labels...")
                with neo4j_storage.driver.session(database=neo4j_storage.config.database) as session:
                    diagnostic_query = "MATCH (n) RETURN DISTINCT labels(n) AS label, count(n) AS count ORDER BY count DESC"
                    results = session.run(diagnostic_query)
                    
                    print("\n--- Node Label Distribution ---")
                    records_found = False
                    total_nodes_from_diagnostic = 0
                    for record in results:
                        records_found = True
                        label = record["label"]
                        count = record["count"]
                        total_nodes_from_diagnostic += count
                        print(f"  🔹 Label(s): {label}, Count: {count:,}")
                    
                    if not records_found:
                        print("  ℹ️ No nodes found in the database.")
                    else:
                        print(f"  -------------------------------")
                        print(f"  Total nodes found: {total_nodes_from_diagnostic:,}")

                    if total_nodes_from_diagnostic > 0 and total_nodes == 0:
                        print("\n  ⚠️ Anomaly Detected: Nodes exist, but they are not labeled as 'Event' or 'Entity'.")


            else:
                print("❌ Neo4j connection failed. Please check your configuration and ensure the database is running.")

        except Exception as e:
            print(f"❌ An error occurred while connecting to or querying Neo4j: {e}")
        finally:
            if neo4j_storage:
                neo4j_storage.close()
                print("\n🔌 Neo4j connection closed.")

    # --- ChromaDB Statistics ---
    print("\n" + "="*20 + " ChromaDB Status " + "="*20)
    if not chroma_config_dict or 'path' not in chroma_config_dict:
        print("❓ ChromaDB path configuration not found in config.yaml.")
    else:
        chroma_path = project_root / chroma_config_dict['path']
        print(f"🔍 Accessing ChromaDB at: {chroma_path}")
        
        if not chroma_path.exists():
            print(f"❌ Error: ChromaDB path does not exist at '{chroma_path}'.")
        else:
            try:
                client = chromadb.PersistentClient(path=str(chroma_path))
                collections = client.list_collections()
                
                if not collections:
                    print("ℹ️  No collections found in ChromaDB.")
                else:
                    print("\n--- Vector Store Summary ---")
                    print(f"  Found {len(collections)} collection(s):")
                    for collection in collections:
                        count = collection.count()
                        print(f"  🔹 Collection '{collection.name}': {count:,} items")
                    print("----------------------------")

            except Exception as e:
                print(f"❌ An error occurred while connecting to or querying ChromaDB: {e}")


if __name__ == "__main__":
    get_database_stats()