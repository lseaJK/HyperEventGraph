# src/llm/llm_client.py
"""
This module provides a unified, configuration-driven client for interacting with 
various Large Language Models (LLMs). It dynamically handles different API providers
and routes requests to the appropriate model based on the task type defined in config.yaml.
"""

import os
import json
import re
import ast # Import the ast module
from openai import AsyncOpenAI, APIError
from typing import Dict, Any, Literal

# Add project root to sys.path
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src.core.config_loader import get_config

# Define valid task types for type hinting and validation
TaskType = Literal["triage", "schema_generation", "extraction", "relationship_analysis"]

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
        
        # Use a more specific key from config if available, e.g., SILICONFLOW_API_KEY
        config_key_name = provider_config.get('api_key_name', 'api_key')

        api_key = os.getenv(api_key_env_var, provider_config.get(config_key_name))
        if not api_key:
            raise ValueError(f"API key for provider '{provider}' not found. "
                             f"Please set the {api_key_env_var} environment variable or add '{config_key_name}' to the provider config.")
        
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=provider_config['base_url']
        )
        self.provider_clients[provider] = client
        return client

    async def get_raw_response(
        self, 
        messages: list[dict],
        task_type: TaskType = None,
        provider: str = None,
        model_name: str = None,
        **kwargs
    ) -> str | None:
        """
        Sends a list of messages and returns the raw string response from the LLM.
        Allows for overriding config-based settings with direct parameters.
        """
        api_params = {}
        
        # Load from config if task_type is provided
        if task_type:
            model_route = self.config.get('models', {}).get(task_type, {})
            api_params.update(model_route)
        
        # Override with direct parameters if provided
        if provider:
            api_params['provider'] = provider
        if model_name:
            api_params['name'] = model_name
        
        # Update with any other keyword arguments
        api_params.update(kwargs)

        final_provider = api_params.get('provider')
        final_model_name = api_params.get('name')

        if not final_provider or not final_model_name:
            raise ValueError("Could not determine provider and model_name. "
                             "Provide a valid task_type or specify provider and model_name directly.")

        print(f"Routing task to provider '{final_provider}' using model '{final_model_name}'...")

        # Prepare the final parameters for the API call
        call_params = {
            "model": final_model_name,
            "messages": messages
        }
        
        # Add optional parameters from the resolved config/kwargs
        optional_params = ["temperature", "top_p", "max_tokens", "frequency_penalty", "presence_penalty"]
        for param in optional_params:
            if param in api_params:
                call_params[param] = api_params[param]

        # --- Smart Parameter Handling for DeepSeek/SiliconFlow ---
        # Models often don't allow both temperature and top_p.
        # This logic prioritizes top_p unless temperature is set very low (for deterministic output).
        if 'temperature' in call_params and 'top_p' in call_params:
            if call_params['temperature'] < 0.1:
                # If temperature is very low, assume user wants deterministic output.
                # Remove top_p and keep temperature.
                del call_params['top_p']
                print("Notice: Low temperature detected. Using temperature sampling and ignoring top_p.")
            else:
                # Otherwise, prioritize top_p as it's generally preferred.
                # Remove temperature and keep top_p.
                del call_params['temperature']
                print("Notice: Both temperature and top_p found. Using top_p sampling and ignoring temperature.")

        try:
            client = self._get_client_for_provider(final_provider)
            response = await client.chat.completions.create(**call_params)
            return response.choices[0].message.content
            
        except APIError as e:
            print(f"An API error occurred with provider '{final_provider}': {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _extract_json_from_response(self, text: str) -> str:
        """
        Extracts a JSON string from a text that might contain markdown code blocks.
        Handles both dicts and lists.
        """
        # Pattern to find JSON object or array within ```json ... ```
        match = re.search(r'```json\s*([\[\{].*?[\]\}])\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        # Fallback for ```{...}``` or ```[...]```
        match = re.search(r'```\s*([\[\{].*?[\]\}])\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        # If no markdown, assume the whole string is JSON
        return text

    async def get_json_response(
        self, 
        messages: list[dict],
        task_type: TaskType = None,
        **kwargs
    ) -> Dict[str, Any] | list | None:
        """
        Sends messages and returns a parsed JSON object (dict or list).
        """
        # Construct default system message if not provided
        has_system_message = any(msg.get("role") == "system" for msg in messages)
        if not has_system_message:
            messages.insert(0, {"role": "system", "content": "You are a helpful assistant designed to output JSON. Please ensure your entire response is a single, valid JSON object or array, without any markdown formatting like ```json."})

        raw_response = await self.get_raw_response(messages=messages, task_type=task_type, **kwargs)
        if not raw_response:
            return None
        
        cleaned_response = self._extract_json_from_response(raw_response)
            
        # Stage 1: Try the standard and strict JSON parser
        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            # Stage 2: If it fails, try the more lenient Python literal evaluator
            try:
                evaluated = ast.literal_eval(cleaned_response)
                if isinstance(evaluated, (dict, list)):
                    return evaluated
            except (ValueError, SyntaxError, MemoryError, TypeError):
                # Stage 3: If both fail, attempt manual regex-based list parsing
                try:
                    # Check if it looks like a list of unquoted strings
                    if cleaned_response.strip().startswith('[') and cleaned_response.strip().endswith(']'):
                        # Extract content within the brackets
                        content = cleaned_response.strip()[1:-1]
                        # Split by comma and clean up each item
                        items = [item.strip().strip("'\"") for item in content.split(',') if item.strip()]
                        return items
                except Exception as e:
                    # If manual parsing also fails, log everything and give up
                    print(f"Manual parsing also failed: {e}")
                    pass # Fall through to the final error logging

        # If all parsing attempts fail, log the error and the problematic response
        print(f"Failed to decode JSON with all methods.")
        print(f"Raw response: \n{raw_response}")
        print(f"Cleaned response attempt: \n{cleaned_response}")
        return None
