import json
import sys
import sqlite3
from pathlib import Path
from neo4j import GraphDatabase
from tqdm import tqdm

# --- Configuration ---
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "123654"
NEO4J_DATABASE = "heg"

# Define project root and file paths
project_root = Path(__file__).resolve().parent
SQLITE_DB_PATH = project_root / "data" / "master_state (1).db"
INPUT_FILE_PATH = project_root / "docs" / "output" / "relationships_raw.jsonl"
OUTPUT_FILE_PATH = project_root / "docs" / "output" / "relationships_restored.jsonl"

class Neo4jConnector:
    """A context manager for handling Neo4j connections."""
    def __init__(self, uri, user, password, database):
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = None

    def __enter__(self):
        try:
            self._driver = GraphDatabase.driver(self._uri, auth=(self._user, self._password))
            self._driver.verify_connectivity()
            print("✅ Neo4j connection successful.")
            return self
        except Exception as e:
            print(f"❌ Neo4j connection failed: {e}")
            sys.exit(1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._driver is not None:
            self._driver.close()
            print("🔌 Neo4j connection closed.")

    def get_session(self):
        return self._driver.session(database=self._database)

def fetch_neo4j_mapping(connector: Neo4jConnector) -> dict:
    """Fetches mapping from eventId to _source_id from Neo4j."""
    id_map = {}
    print("📊 Fetching Neo4j Event ID -> Source ID mapping...")
    query = "MATCH (e:Event) WHERE e.eventId IS NOT NULL AND e._source_id IS NOT NULL RETURN e.eventId AS eventId, e._source_id AS sourceId"
    try:
        with connector.get_session() as session:
            results = session.run(query)
            for record in tqdm(results, desc="Processing Neo4j records"):
                id_map[record["eventId"]] = record["sourceId"]
    except Exception as e:
        print(f"❌ Error fetching data from Neo4j: {e}")
        return {}
    print(f"✅ Found {len(id_map):,} mappings in Neo4j.")
    return id_map

def fetch_sqlite_mapping() -> dict:
    """
    Fetches mapping from master_state.id to the eventId found in structured_data.
    """
    if not SQLITE_DB_PATH.exists():
        print(f"❌ Error: SQLite database not found at {SQLITE_DB_PATH}")
        print("Please download 'master_state.db' from your Linux server to your project root.")
        return {}
        
    id_map = {}
    print(f"📖 Reading SQLite DB: {SQLITE_DB_PATH.name}")
    
    try:
        with sqlite3.connect(SQLITE_DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, structured_data FROM master_state WHERE structured_data IS NOT NULL")
            
            for row in tqdm(cursor.fetchall(), desc="Processing SQLite records"):
                master_id, structured_data_json = row
                if structured_data_json:
                    try:
                        structured_data = json.loads(structured_data_json)
                        # Assuming the event_id is at the top level of the JSON
                        event_id = structured_data.get("event_id")
                        if event_id:
                            id_map[master_id] = event_id
                    except (json.JSONDecodeError, TypeError):
                        # Ignore rows with invalid JSON in structured_data
                        continue
    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")
        return {}
        
    print(f"✅ Found {len(id_map):,} mappings in SQLite.")
    return id_map

def restore_ids_to_jsonl(neo4j_map: dict, sqlite_map: dict):
    """
    Reads the raw relationships file, adds the _source_id using the two-step
    mapping, and writes to a new file.
    """
    if not INPUT_FILE_PATH.exists():
        print(f"❌ Error: Input file not found at {INPUT_FILE_PATH}")
        return

    print(f"🔄 Processing file: {INPUT_FILE_PATH.name}")
    
    restored_count = 0
    total_lines = 0
    
    try:
        with open(INPUT_FILE_PATH, 'r', encoding='utf-8') as infile, \
             open(OUTPUT_FILE_PATH, 'w', encoding='utf-8') as outfile:
            
            for line in tqdm(infile, desc="Restoring IDs to records"):
                total_lines += 1
                try:
                    data = json.loads(line)
                    
                    # --- Core Three-Way Restoration Logic ---
                    source_master_id = data.get("source_event_id")
                    
                    # Step 1: Find Neo4j eventId using the master_id from the file
                    neo4j_event_id = sqlite_map.get(source_master_id)
                    
                    # Step 2: Find the final source_id using the Neo4j eventId
                    if neo4j_event_id and neo4j_event_id in neo4j_map:
                        final_source_id = neo4j_map[neo4j_event_id]
                        data["restored_source_id"] = final_source_id
                        restored_count += 1
                    
                    outfile.write(json.dumps(data, ensure_ascii=False) + '\n')
                    
                except json.JSONDecodeError:
                    print(f"⚠️ Warning: Skipping a line that is not valid JSON: {line.strip()}")
                    continue

        print("\n" + "="*20 + " Restoration Complete " + "="*20)
        print(f"📄 Total lines processed: {total_lines:,}")
        print(f"✨ Source IDs restored to {restored_count:,} records.")
        if total_lines > 0 and restored_count == 0:
            print("⚠️ WARNING: No records were restored. This could be due to a mismatch between IDs in the .jsonl file and the SQLite database.")
        print(f"✅ New file created at: {OUTPUT_FILE_PATH}")

    except IOError as e:
        print(f"❌ Error reading or writing file: {e}")

def main():
    """Main function to run the restoration process."""
    sqlite_map = fetch_sqlite_mapping()
    if not sqlite_map:
        print("Aborting due to missing SQLite mapping.")
        return

    with Neo4jConnector(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE) as connector:
        neo4j_map = fetch_neo4j_mapping(connector)
        if not neo4j_map:
            print("Aborting due to missing Neo4j mapping.")
            return
            
        restore_ids_to_jsonl(neo4j_map, sqlite_map)

if __name__ == "__main__":
    main()