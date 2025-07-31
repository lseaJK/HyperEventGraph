# src/cortex/refinement_agent.py

from src.llm.llm_client import LLMClient
from src.core.config_loader import get_config
import uuid
import asyncio
import math

# TODO: Move this to the PromptManager.
REFINEMENT_PROMPT_TEMPLATE = """
You are a financial news analyst. Below is a list of event descriptions that have been clustered together due to potential similarity. Your task is to synthesize these events into a single, coherent story summary.

Focus on the core narrative. What is the main event or development? Who are the key actors? What are the outcomes? Ignore duplicate information and minor details.

Event Descriptions:
{event_descriptions}

Based on these events, provide a concise, one-paragraph story summary.
"""

MERGE_SUMMARIES_PROMPT_TEMPLATE = """
You are a master news editor. You have been given several story summaries that were generated from different subsets of a large, related group of events. Your task is to synthesize these summaries into one final, overarching story.

Identify the core narrative, eliminate redundancy, and create a single, coherent, and comprehensive summary that captures the essence of all the provided points.

Summaries to merge:
{summaries}

Provide the final, merged story summary.
"""

class RefinementAgent:
    """
    Uses an LLM to "refine" a coarse cluster of events into one or more
    tightly-related "Story" units. It uses a special strategy for large clusters.
    """

    def __init__(self, llm_client: LLMClient):
        """
        Initializes the RefinementAgent.
        """
        self.llm_client = llm_client
        config = get_config()
        refinement_config = config.get('cortex', {}).get('refinement', {})
        self.large_cluster_threshold = refinement_config.get('large_cluster_threshold', 20)
        self.chunk_size = refinement_config.get('chunk_size', 15) # How many events per chunk
        print(f"RefinementAgent initialized. Large cluster threshold: {self.large_cluster_threshold}, Chunk size: {self.chunk_size}.")

    def refine_cluster(self, cluster_events: list[dict]) -> list[dict]:
        """
        Analyzes a cluster of events and synthesizes them into stories.
        This is a synchronous wrapper around the async implementation.
        """
        return asyncio.run(self._refine_cluster_async(cluster_events))

    async def _refine_cluster_async(self, cluster_events: list[dict]) -> list[dict]:
        """
        Asynchronously directs cluster processing based on size.
        """
        if not cluster_events:
            return []

        num_events = len(cluster_events)
        print(f"Refining a cluster with {num_events} events...")

        if num_events > self.large_cluster_threshold:
            return await self._handle_large_cluster(cluster_events)
        else:
            return await self._handle_small_cluster(cluster_events)

    async def _summarize_chunk(self, chunk: list[dict]) -> str | None:
        """Helper to summarize a single chunk of events."""
        descriptions = [f"- {event.get('notes') or event.get('source_text', '')}" for event in chunk]
        event_descriptions_str = "\n".join(descriptions)
        prompt = REFINEMENT_PROMPT_TEMPLATE.format(event_descriptions=event_descriptions_str)
        
        try:
            summary = await self.llm_client.get_raw_response(prompt, task_type='triage')
            return summary
        except Exception as e:
            print(f"Error summarizing chunk: {e}")
            return None

    async def _handle_small_cluster(self, cluster_events: list[dict]) -> list[dict]:
        """
        Handles a small cluster by summarizing all events at once.
        """
        print("Processing as a small cluster...")
        summary = await self._summarize_chunk(cluster_events)
        if not summary:
            print("Warning: Failed to generate summary for the cluster.")
            return []
        
        print(f"LLM generated summary: {summary}")
        story_id = f"story_{uuid.uuid4()}"
        event_ids = [event['id'] for event in cluster_events]
        
        story = {"story_id": story_id, "summary": summary, "event_ids": event_ids}
        print(f"Refinement complete. Generated Story ID: {story_id}")
        return [story]

    async def _handle_large_cluster(self, cluster_events: list[dict]) -> list[dict]:
        """
        Handles a large cluster using a 'summarize-and-merge' strategy.
        """
        print(f"Processing as a large cluster using 'summarize-and-merge' strategy with chunk size {self.chunk_size}...")
        
        # 1. Chunk events
        num_events = len(cluster_events)
        chunks = [cluster_events[i:i + self.chunk_size] for i in range(0, num_events, self.chunk_size)]
        print(f"Split into {len(chunks)} chunks.")

        # 2. Summarize each chunk concurrently
        print("Summarizing all chunks...")
        summarization_tasks = [self._summarize_chunk(chunk) for chunk in chunks]
        chunk_summaries = await asyncio.gather(*summarization_tasks)
        
        # Filter out any failed summaries
        valid_summaries = [s for s in chunk_summaries if s]
        if not valid_summaries:
            print("Error: Failed to generate any valid summaries from chunks.")
            return []
        
        print(f"Successfully generated {len(valid_summaries)} chunk summaries.")

        # 3. Merge the summaries
        print("Merging chunk summaries into a final story...")
        summaries_str = "\n\n---\n\n".join(valid_summaries)
        merge_prompt = MERGE_SUMMARIES_PROMPT_TEMPLATE.format(summaries=summaries_str)
        
        try:
            final_summary = await self.llm_client.get_raw_response(merge_prompt, task_type='triage')
            if not final_summary:
                print("Warning: LLM failed to merge summaries.")
                return []
        except Exception as e:
            print(f"Error merging summaries: {e}")
            return []

        print(f"Final merged summary: {final_summary}")
        
        # 4. Create the final story object
        story_id = f"story_{uuid.uuid4()}"
        event_ids = [event['id'] for event in cluster_events] # The story covers all events
        
        story = {"story_id": story_id, "summary": final_summary, "event_ids": event_ids}
        print(f"Large cluster refinement complete. Generated Story ID: {story_id}")
        return [story]
