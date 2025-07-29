# src/llm/llm_client.py
"""
This module provides a unified, configuration-driven client for interacting with 
various Large Language Models (LLMs). It dynamically handles different API providers
and routes requests to the appropriate model based on the task type defined in config.yaml.
"""

import os
import json
from openai import AsyncOpenAI, APIError
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
        
        self.provider_clients: Dict[str, AsyncOpenAI] = {}

    def _get_client_for_provider(self, provider: str) -> AsyncOpenAI:
        """
        Lazily initializes and returns an AsyncOpenAI client for a given provider.
        API keys are sourced from environment variables first, then the config file.
        """
        if provider in self.provider_clients:
            return self.provider_clients[provider]

        provider_config = self.config['providers'][provider]
        api_key_env_var = f"{provider.upper()}_API_KEY"
        
        api_key = os.getenv(api_key_env_var, provider_config.get('api_key'))
        if not api_key:
            raise ValueError(f"API key for provider '{provider}' not found. "
                             f"Please set the {api_key_env_var} environment variable.")
        
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=provider_config['base_url']
        )
        self.provider_clients[provider] = client
        return client

    async def get_raw_response(self, prompt: str, task_type: TaskType) -> str | None:
        """
        Sends a prompt and returns the raw string response from the LLM.
        This is useful for debugging and prompt tuning.
        """
        model_route = self.config.get('models', {}).get(task_type)
        if not model_route:
            raise ValueError(f"No model route defined for task_type '{task_type}' in config.yaml.")
            
        provider = model_route.get('provider')
        model_name = model_route.get('name')
        
        if not provider or not model_name:
            raise ValueError(f"Incomplete model route for '{task_type}'. 'provider' and 'name' are required.")

        print(f"Routing task '{task_type}' to provider '{provider}' using model '{model_name}'...")

        # Prepare the parameters for the API call
        api_params = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant designed to output JSON."},
                {"role": "user", "content": prompt}
            ]
        }

        # Add optional parameters from config if they exist
        optional_params = ["temperature", "top_p", "max_tokens", "frequency_penalty", "presence_penalty"]
        for param in optional_params:
            if param in model_route:
                api_params[param] = model_route[param]

        try:
            client = self._get_client_for_provider(provider)
            
            response = await client.chat.completions.create(**api_params)
            return response.choices[0].message.content
            
        except APIError as e:
            print(f"An API error occurred with provider '{provider}': {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def get_json_response(self, prompt: str, task_type: TaskType) -> Dict[str, Any] | None:
        """
        Sends a prompt and returns a parsed JSON dictionary.
        """
        raw_response = await self.get_raw_response(prompt, task_type)
        if not raw_response:
            return None
            
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON from LLM response: {e}")
            print(f"Raw response: {raw_response}")
            return None
