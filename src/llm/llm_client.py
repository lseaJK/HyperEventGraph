# src/llm/llm_client.py
"""
This module provides a unified, configuration-driven client for interacting with 
various Large Language Models (LLMs). It dynamically handles different API providers
and routes requests to the appropriate model based on the task type defined in config.yaml.
"""

import os
import json
from openai import OpenAI, APIError
from typing import Dict, Any, Literal

# Add project root to sys.path
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.core.config_loader import get_config

# Define valid task types for type hinting and validation
TaskType = Literal["triage", "schema_generation", "extraction"]

class LLMClient:
    """
    A configuration-driven client for handling interactions with multiple LLM providers.
    """

    def __init__(self):
        """Initializes the client by loading the LLM configuration."""
        self.config = get_config().get('llm', {})
        if not self.config or 'providers' not in self.config or 'models' not in self.config:
            raise ValueError("LLM configuration is missing or incomplete in config.yaml.")
        
        self.provider_clients: Dict[str, OpenAI] = {}

    def _get_client_for_provider(self, provider: str) -> OpenAI:
        """
        Lazily initializes and returns an OpenAI-compatible client for a given provider.
        API keys are sourced from environment variables first, then the config file.
        """
        if provider in self.provider_clients:
            return self.provider_clients[provider]

        provider_config = self.config['providers'][provider_name]
        api_key_env_var = f"{provider_name.upper()}_API_KEY"
        
        api_key = os.getenv(api_key_env_var, provider_config.get('api_key'))
        if not api_key:
            raise ValueError(f"API key for provider '{provider_name}' not found. "
                             f"Please set the {api_key_env_var} environment variable.")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=provider_config['base_url']
        )

    def get_json_response(self, prompt: str, task_type: TaskType) -> Dict[str, Any] | None:
        """
        Sends a prompt to the appropriate LLM based on the task type and requests a JSON response.

        Args:
            prompt: The prompt to send to the model.
            task_type: The type of task, which determines which model and provider to use.

        Returns:
            A dictionary parsed from the LLM's JSON response, or None on error.
        """
        model_route = self.config.get('models', {}).get(task_type)
        if not model_route:
            raise ValueError(f"No model route defined for task_type '{task_type}' in config.yaml.")
            
        provider = model_route.get('provider')
        model_name = model_route.get('name')
        
        if not provider or not model_name:
            raise ValueError(f"Incomplete model route for '{task_type}'. 'provider' and 'name' are required.")

        print(f"Routing task '{task_type}' to provider '{provider}' using model '{model_name}'...")

        try:
            client = self._get_client_for_provider(provider)
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            response_content = response.choices[0].message.content
            return json.loads(response_content)
            
        except APIError as e:
            print(f"An API error occurred with provider '{provider}': {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON from LLM response: {e}")
            print(f"Raw response: {response_content}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

if __name__ == '__main__':
    # Example Usage - requires a config file and API keys set as environment variables
    from src.core.config_loader import load_config
    
    # Ensure a valid config.yaml exists for this test to run
    if not Path("config.yaml").exists():
        print("ERROR: config.yaml not found. Please create one based on the new architecture.")
    else:
        try:
            load_config("config.yaml")
            
            # Make sure to set your DEEPSEEK_API_KEY and MOONSHOT_API_KEY env vars
            if not os.environ.get("DEEPSEEK_API_KEY") or not os.environ.get("MOONSHOT_API_KEY"):
                print("\nWARNING: DEEPSEEK_API_KEY or MOONSHOT_API_KEY not set. Skipping live tests.")
            else:
                print("Running live tests with the new LLMClient...")
                client = LLMClient()

                # Test extraction task (routes to DeepSeek)
                print("\n--- Testing Extraction Task ---")
                extraction_prompt = "Extract the company and product from the text: 'Apple announced the new Vision Pro.'"
                extraction_response = client.get_json_response(extraction_prompt, task_type="extraction")
                print("Response:", json.dumps(extraction_response, indent=2))
                assert isinstance(extraction_response, dict)

                # Test schema generation task (routes to Kimi)
                print("\n--- Testing Schema Generation Task ---")
                schema_prompt = "Generate a simple JSON schema for a 'Product Launch' event."
                schema_response = client.get_json_response(schema_prompt, task_type="schema_generation")
                print("Response:", json.dumps(schema_response, indent=2))
                assert isinstance(schema_response, dict)
                
                print("\nLive tests successful!")

        except (ValueError, NotImplementedError) as e:
            print(f"Test setup failed: {e}")