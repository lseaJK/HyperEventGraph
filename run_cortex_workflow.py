# run_cortex_workflow.py
"""
This script drives the Cortex workflow.
It reads pending events from the database, uses the ClusteringOrchestrator
to create coarse clusters, and then uses the RefinementAgent to produce
fine-grained "Story" units, updating the database accordingly.
"""

import asyncio
from pathlib import Path
import sys

# Add project root to sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.core.config_loader import load_config, get_config
from src.core.database_manager import DatabaseManager
from src.llm.llm_client import LLMClient
from src.cortex.vectorization_service import VectorizationService
from src.cortex.clustering_orchestrator import ClusteringOrchestrator
from src.cortex.refinement_agent import RefinementAgent

def run_cortex_workflow():
    """Main function to run the Cortex workflow."""
    print("\n--- Running Cortex Workflow ---")
    
    # 0. Load configuration first
    config_path = project_root / "config.yaml"
    load_config(config_path)
    print("✅ Configuration loaded successfully")
    
    # 1. Initialization
    config = get_config()
    db_path = config.get('database', {}).get('path')
    db_manager = DatabaseManager(db_path)
    llm_client = LLMClient()
    vectorizer = VectorizationService()
    orchestrator = ClusteringOrchestrator(vectorizer)
    refiner = RefinementAgent(llm_client)

    # 2. Fetch pending events
    print("Fetching events pending clustering from the database...")
    events_to_cluster = db_manager.get_records_by_status_as_df('pending_clustering').to_dict('records')
    
    if not events_to_cluster:
        print("No events found pending clustering. Workflow complete.")
        return

    print(f"Found {len(events_to_cluster)} events to process.")

    # 3. Perform coarse clustering
    cluster_assignments, stats = orchestrator.cluster_events(events_to_cluster)
    
    # Update database with cluster results
    print("Updating database with cluster assignments...")
    clustered_events = []
    for event_id, cluster_id in cluster_assignments.items():
        if cluster_id != -1:
            # This event belongs to a valid cluster
            db_manager.update_cluster_info(event_id, cluster_id, 'pending_refinement')
            # Find the original event dict to pass to the next stage
            event_data = next((event for event in events_to_cluster if event['id'] == event_id), None)
            if event_data:
                event_data['cluster_id'] = cluster_id
                clustered_events.append(event_data)
        else:
            # This event is considered noise
            db_manager.update_cluster_info(event_id, cluster_id, 'clustered_as_noise')
    
    print(f"{len(clustered_events)} events assigned to clusters. {len(events_to_cluster) - len(clustered_events)} events marked as noise.")

    # Group events by cluster_id for the refinement stage
    clusters = {}
    for event in clustered_events:
        cluster_id = event['cluster_id']
        if cluster_id not in clusters:
            clusters[cluster_id] = []
        clusters[cluster_id].append(event)

    print(f"Grouped events into {len(clusters)} coarse clusters for refinement.")

    # 4. Refine each cluster into stories
    all_stories = []
    if not clusters:
        print("No clusters to refine. Skipping refinement stage.")
    else:
        for cluster_id, events_in_cluster in clusters.items():
            print(f"\nProcessing Cluster #{cluster_id} with {len(events_in_cluster)} events...")
            # The agent now returns a list of story dictionaries
            stories = refiner.refine_cluster(events_in_cluster)
            all_stories.extend(stories)

    # 5. Update database with story information
    if not all_stories:
        print("\nNo stories were generated. No database updates to perform.")
    else:
        print(f"\nGenerated a total of {len(all_stories)} stories. Updating database...")
        for story in all_stories:
            story_id = story['story_id']
            event_ids_in_story = story['event_ids']
            # Update all events in the story with the new story_id and set status
            # for the next stage in the pipeline.
            db_manager.update_story_info(event_ids_in_story, story_id, 'pending_relationship_analysis')
        print("Database updated with story information.")

    print("\n--- Cortex Workflow Finished ---")
    print("\n--- Clustering Summary ---")
    print(f"Total Events Processed: {stats['total_events_processed']}")
    print(f"  - Entity Parsing Success: {stats['entity_parsing_success']}")
    print(f"  - Entity Parsing Warnings: {stats['entity_parsing_warnings']}")
    print(f"Clusters Found: {stats['clusters_found']}")
    print(f"Noise Points (unclustered): {stats['noise_points']}")
    print("--------------------------\n")

def main_standalone():
    """Entry point for standalone execution."""
    print("Initializing configuration for standalone Cortex run...")
    load_config("config.yaml")
    run_cortex_workflow()

if __name__ == "__main__":
    main_standalone()
