# src/analysis/build_micro_graph.py
"""
This script builds a micro knowledge graph from a structured event JSONL file.
It uses networkx for graph representation and pyvis for interactive visualization.
This serves as a prototype for the future GraphStorageAgent.
"""

import json
from pathlib import Path
import networkx as nx
from pyvis.network import Network
from tqdm import tqdm

# --- Configuration ---
INPUT_FILE_PATH = "docs/output/structured_events_0730.jsonl"
OUTPUT_HTML_PATH = "docs/output/micro_knowledge_graph.html"
# To avoid a cluttered graph, we can limit the number of records to process.
# Set to None to process all records.
RECORD_LIMIT = 100 

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
                print(f"Warning: Skipping corrupted line.")
                continue
    print(f"Successfully loaded {len(records)} records.")
    return records

def build_graph(records: list[dict]) -> nx.Graph:
    """Builds a networkx graph from event records."""
    G = nx.Graph()
    print("Building graph from records...")

    for record in tqdm(records, desc="Processing records"):
        event_id = record.get('event_id')
        event_type = record.get('event_type', 'Unknown')
        
        if not event_id:
            continue

        # Add event node
        G.add_node(
            event_id,
            label=f"Event: {event_type}",
            title=record.get('description', ''),
            type='event',
            color='#FFD700' # Gold
        )

        # Add entity nodes and edges
        entities = record.get('involved_entities', [])
        if not isinstance(entities, list):
            continue
            
        for entity in entities:
            entity_name = entity.get('entity_name')
            if not entity_name:
                continue
            
            # Add entity node (if it doesn't exist)
            if not G.has_node(entity_name):
                G.add_node(
                    entity_name,
                    label=entity_name,
                    title=f"Entity: {entity_name}",
                    type='entity',
                    color='#1E90FF' # DodgerBlue
                )
            
            # Add edge from event to entity
            G.add_edge(event_id, entity_name)
            
    print(f"Graph built successfully: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges.")
    return G

def visualize_graph(G: nx.Graph, output_path: Path):
    """Visualizes the graph using pyvis and saves it as an HTML file."""
    if G.number_of_nodes() == 0:
        print("Graph is empty, skipping visualization.")
        return

    print(f"Generating interactive visualization at {output_path}...")
    net = Network(height="800px", width="100%", notebook=False, directed=False)
    net.from_nx(G)
    
    # pyvis options for better layout and interaction
    net.set_options("""
    var options = {
      "nodes": {
        "font": {
          "size": 12
        }
      },
      "edges": {
        "color": {
          "inherit": true
        },
        "smooth": {
          "type": "continuous"
        }
      },
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "tooltipDelay": 200
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000,
          "springConstant": 0.04,
          "springLength": 250
        },
        "minVelocity": 0.75
      }
    }
    """)
    
    output_path.parent.mkdir(exist_ok=True)
    net.save_graph(str(output_path))
    print("Visualization saved successfully.")

def main():
    """Main entry point for the script."""
    try:
        records = load_data(Path(INPUT_FILE_PATH), RECORD_LIMIT)
        if not records:
            return
        graph = build_graph(records)
        visualize_graph(graph, Path(OUTPUT_HTML_PATH))
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()