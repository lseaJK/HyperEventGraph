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

async def run_cortex_workflow():
    """Main function to run the Cortex workflow."""
    print("\n--- Running Cortex Workflow ---")
    
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
    cluster_assignments = orchestrator.cluster_events(events_to_cluster)
    
    # Group events by cluster_id
    clusters = {}
    for event in events_to_cluster:
        cluster_id = cluster_assignments.get(event['id'])
        if cluster_id is not None:
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(event)

    print(f"Grouped events into {len(clusters)} coarse clusters.")

    # 4. Refine each cluster into stories
    all_stories = []
    for cluster_id, events_in_cluster in clusters.items():
        print(f"\nProcessing Cluster #{cluster_id} with {len(events_in_cluster)} events...")
        stories = refiner.refine_cluster(events_in_cluster)
        all_stories.extend(stories)

    # 5. Update database
    # TODO: Implement logic to assign story_ids and update the status
    # of each event in the database to 'pending_relationship_analysis'.
    print(f"\nGenerated a total of {len(all_stories)} stories.")
    print("TODO: Implement database update logic.")

    print("\n--- Cortex Workflow Finished ---")

def main():
    """Entry point of the script."""
    load_config("config.yaml")
    asyncio.run(run_cortex_workflow())

if __name__ == "__main__":
    main()
