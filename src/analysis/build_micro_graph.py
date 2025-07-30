import json
import os
import networkx as nx
import matplotlib.pyplot as plt
import random

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
    if len(lines) < sample_size:
        sample_size = len(lines)
        
    sampled_lines = random.sample(lines, sample_size)
    
    G = nx.DiGraph()

    for line in sampled_lines:
        try:
            event = json.loads(line)
            
            event_id = event.get('_source_id', str(random.uuid4()))
            event_type = event.get('micro_event_type') or event.get('event_type', 'Unknown Event')
            
            # Add event node
            G.add_node(event_type, type='event', label=event_type)

            entities = event.get('involved_entities', [])
            for entity in entities:
                entity_name = entity.get('entity_name')
                entity_type = entity.get('entity_type', 'Unknown')
                role = entity.get('role_in_event', 'involved_in')

                if not entity_name:
                    continue

                # Add entity node
                if not G.has_node(entity_name):
                    G.add_node(entity_name, type='entity', label=entity_name, entity_type=entity_type)
                
                # Add edge from entity to event
                G.add_edge(entity_name, event_type, label=role)

        except (json.JSONDecodeError, AttributeError):
            continue
            
    return G

def visualize_graph(G, output_path='src/analysis/micro_knowledge_graph.png'):
    """
    Visualizes and saves the knowledge graph.

    Args:
        G (networkx.DiGraph): The graph to visualize.
        output_path (str): The path to save the visualization.
    """
    plt.figure(figsize=(20, 20))
    
    # Use a layout that spreads nodes out
    pos = nx.spring_layout(G, k=0.5, iterations=50)

    # Differentiate node colors by type
    node_colors = []
    for node in G.nodes(data=True):
        if node[1]['type'] == 'event':
            node_colors.append('skyblue')
        else:
            node_colors.append('lightgreen')

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=3000)
    
    # Draw edges and labels
    nx.draw_networkx_edges(G, pos, arrowstyle='->', arrowsize=20, connectionstyle='arc3,rad=0.1')
    
    node_labels = nx.get_node_attributes(G, 'label')
    nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=10)
    
    edge_labels = nx.get_edge_attributes(G, 'label')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

    plt.title("Micro Knowledge Graph Prototype")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, format="PNG")
    print(f"Knowledge graph visualization saved to {output_path}")
    plt.close()


if __name__ == "__main__":
    if not os.path.exists('src/analysis'):
        os.makedirs('src/analysis')
        
    data_file = 'docs/output/structured_events.jsonl'
    kg = build_knowledge_graph(data_file, sample_size=50) # Use a smaller sample for better visualization
    visualize_graph(kg)
