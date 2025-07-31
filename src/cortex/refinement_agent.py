# src/cortex/refinement_agent.py

from src.llm.llm_client import LLMClient
import uuid

# A simple, hardcoded prompt template for now.
# TODO: Move this to the PromptManager.
REFINEMENT_PROMPT_TEMPLATE = """
You are a financial news analyst. Below is a list of event descriptions that have been clustered together due to potential similarity. Your task is to synthesize these events into a single, coherent story summary.

Focus on the core narrative. What is the main event or development? Who are the key actors? What are the outcomes? Ignore duplicate information and minor details.

Event Descriptions:
{event_descriptions}

Based on these events, provide a concise, one-paragraph story summary.
"""

class RefinementAgent:
    """
    Uses an LLM to "refine" a coarse cluster of events into one or more
    tightly-related "Story" units.
    """

    def __init__(self, llm_client: LLMClient):
        """
        Initializes the RefinementAgent.
        """
        self.llm_client = llm_client
        print("RefinementAgent initialized.")

    def refine_cluster(self, cluster_events: list[dict]) -> list[dict]:
        """
        Analyzes a cluster of events and synthesizes them into a single story.

        Args:
            cluster_events: A list of event dictionaries from the same cluster.

        Returns:
            A list containing a single story dictionary. The dictionary contains
            the generated story_id, the summary text, and the original event_ids.
            Returns an empty list if no story can be generated.
        """
        if not cluster_events:
            return []

        print(f"Refining a cluster with {len(cluster_events)} events...")

        # TODO: Implement the "summarize-retrieve-expand" strategy for large clusters.
        # For now, we process the whole cluster at once.

        # 1. Format the event descriptions for the prompt
        # We use the 'notes' field which often contains the raw event text or summary.
        # Fallback to source_text if notes is not available.
        descriptions = [f"- {event.get('notes') or event.get('source_text', '')}" for event in cluster_events]
        event_descriptions_str = "\n".join(descriptions)

        # 2. Create the prompt
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(event_descriptions=event_descriptions_str)

        # 3. Call the LLM to get the story summary
        print("Calling LLM to generate story summary...")
        try:
            # Assuming the LLMClient has a generic 'invoke' method
            # and we use the 'triage' model configuration for this task for now.
            summary = self.llm_client.invoke('triage', prompt)
            if not summary:
                print("Warning: LLM returned an empty summary. Skipping story generation for this cluster.")
                return []
            print(f"LLM generated summary: {summary}")
        except Exception as e:
            print(f"Error calling LLM for refinement: {e}")
            return []

        # 4. Create the story object
        story_id = f"story_{uuid.uuid4()}"
        event_ids = [event['id'] for event in cluster_events]
        
        story = {
            "story_id": story_id,
            "summary": summary,
            "event_ids": event_ids
        }

        print(f"Refinement complete. Generated Story ID: {story_id}")
        # The agent now returns a list of story dictionaries
        return [story]