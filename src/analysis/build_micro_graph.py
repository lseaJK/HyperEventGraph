import json
import os
import networkx as nx
import matplotlib.pyplot as plt
import uuid
import random
from matplotlib.font_manager import FontProperties, fontManager
import matplotlib as mpl

# Set the font path explicitly
font_path = '/home/kai/simhei.ttf'

# Add the font to matplotlib's font manager
fontManager.addfont(font_path)
font_prop = FontProperties(fname=font_path)
font_name = font_prop.get_name()

# Set the global font for matplotlib
plt.rcParams['font.family'] = font_name
plt.rcParams['axes.unicode_minus'] = False

def build_knowledge_graph(file_path, sample_size=100):
    """
    Builds a knowledge graph from a sample of structured event data.

    Args:
        file_path (str): Path to the JSONL file.
        sample_size (int): Number of records to sample from the file.

    Returns:
        networkx.DiGraph: The constructed knowledge graph.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Ensure sample_size is not larger than the number of lines
    sample_size = min(sample_size, len(lines))
    sampled_lines = random.sample(lines, sample_size)
    G = nx.DiGraph()

    for line in sampled_lines:
        try:
            event = json.loads(line)

            # Use _source_id from file or generate random UUID
            event_id = event.get('_source_id', str(uuid.uuid4()))
            event_type = event.get('micro_event_type') or event.get('event_type', 'Unknown Event')

            # Add event node with additional metadata
            G.add_node(event_type, 
                       type='event', 
                       label=event_type,
                       event_id=event_id)

            # Process entities
            entities = event.get('involved_entities', [])
            for entity in entities:
                entity_name = entity.get('entity_name')
                entity_type = entity.get('entity_type', 'Unknown')
                role = entity.get('role_in_event', 'involved_in')

                if not entity_name:  # Skip empty entities
                    continue

                # Add entity node if not exists
                if not G.has_node(entity_name):
                    G.add_node(
                        entity_name,
                        type='entity',
                        label=entity_name,
                        entity_type=entity_type
                    )

                # Add edge from entity to event
                G.add_edge(entity_name, event_type, 
                           label=role,
                           event_id=event_id)

        except (json.JSONDecodeError, AttributeError) as e:
            print(f"Error processing line: {e}")
            continue

    return G

def visualize_graph(G, output_path='src/analysis/micro_knowledge_graph.png'):
    plt.figure(figsize=(30, 30))
    
    # Layout and drawing
    pos = nx.spring_layout(G, k=1.5, iterations=50)
    
    node_colors = ['skyblue' if d['type'] == 'event' else 'lightgreen'
                  for _, d in G.nodes(data=True)]
    
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=3000)
    nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=20, 
                         connectionstyle='arc3,rad=0.1', width=1.5)
    
    node_labels = {n: d['label'][:10] + '...' if len(d['label']) > 10 else d['label']
                  for n, d in G.nodes(data=True)}
    
    # Draw labels - font will be handled by global settings
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=12)
    
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10)
    
    plt.title("Micro Knowledge Graph Prototype", fontsize=20)
    plt.axis('off')
    plt.tight_layout()
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, format="PNG", dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Visualization saved to {output_path}")

if __name__ == "__main__":
    data_file = 'output/extraction/structured_events.jsonl'
    
    # Check if data file exists
    if not os.path.exists(data_file):
        print(f"Error: Data file not found at {data_file}")
        exit(1)
        
    # Verify font is properly registered
    available_fonts = [f.name for f in fontManager.ttflist if font_name in f.name]
    print(f"Available fonts containing '{font_name}': {available_fonts}")
    
    # Build and visualize graph
    kg = build_knowledge_graph(data_file, sample_size=50)
    visualize_graph(kg)