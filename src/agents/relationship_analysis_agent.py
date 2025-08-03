# src/agents/relationship_analysis_agent.py
"""
This agent is responsible for analyzing the relationships between a group of events
that belong to the same story, using an LLM.
"""

import json
from typing import List, Dict, Any, Tuple

# Add project root to sys.path
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.llm.llm_client import LLMClient, TaskType
from src.core.prompt_manager import prompt_manager

class RelationshipAnalysisAgent:
    def __init__(self, llm_client: LLMClient, task_type: TaskType, chunk_size: int = 100):
        self.llm_client = llm_client
        self.task_type = task_type
        self.chunk_size = chunk_size

    async def analyze_relationships(
        self, 
        events_in_story: List[Dict[str, Any]], 
        source_context: str, 
        retrieved_context: str
    ) -> Tuple[str, List[Dict[str, Any]] | None]:
        """
        Analyzes relationships between events in a story, enhanced with retrieved context.

        Args:
            events_in_story: A list of event dictionaries belonging to the same story.
            source_context: The combined source text of the original documents.
            retrieved_context: The context summary retrieved from the knowledge base.

        Returns:
            A tuple containing the raw LLM response and the parsed list of relationship dictionaries.
        """
        if not events_in_story:
            return "", []

        # Prepare the event block for the prompt
        event_block = ""
        for i, event in enumerate(events_in_story):
            # Ensure structured_data is a dict before accessing it
            structured_data = event.get('structured_data')
            if isinstance(structured_data, str):
                try:
                    structured_data = json.loads(structured_data)
                except json.JSONDecodeError:
                    structured_data = {} # Default to empty dict if parsing fails
            elif not isinstance(structured_data, dict):
                structured_data = {}

            event_block += f"Event {i+1} (ID: {event['id']}):\n"
            event_block += json.dumps(structured_data, indent=2, ensure_ascii=False)
            event_block += "\n\n"

        # Get the prompt from the manager
        prompt = prompt_manager.get_prompt(
            self.task_type,
            source_context=source_context,
            retrieved_context=retrieved_context,
            event_block=event_block
        )
        
        messages = [{"role": "user", "content": prompt}]

        print(f"Analyzing relationships for story with {len(events_in_story)} events...")
        
        try:
            # Use get_raw_response to get the full string output
            raw_response = await self.llm_client.get_raw_response(
                messages=messages,
                task_type=self.task_type
            )

            if not raw_response:
                print("Warning: LLM returned an empty response for relationship analysis.")
                return "", None

            # Use the client's robust JSON parsing for the response
            parsed_json = await self.llm_client.get_json_response(
                messages=[{"role": "user", "content": f"Please parse the following text into a valid JSON array. The text is: {raw_response}"}]
            )

            if isinstance(parsed_json, list):
                return raw_response, parsed_json
            else:
                print(f"Warning: Failed to parse relationships into a list. Parsed data: {parsed_json}")
                return raw_response, None

        except Exception as e:
            print(f"An error occurred during relationship analysis: {e}")
            import traceback
            traceback.print_exc()
            return str(e), None