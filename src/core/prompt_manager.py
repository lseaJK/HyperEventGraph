# src/core/prompt_manager.py
"""
This module provides a centralized manager for loading and formatting
prompt templates from the external '/prompts' directory.
"""

from pathlib import Path
from typing import Dict, Any

class PromptManager:
    """
    Manages loading and formatting of prompt templates from files.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PromptManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, prompt_dir: str = "prompts"):
        # This check ensures __init__ runs only once for the singleton instance
        if not hasattr(self, 'initialized'):
            self.prompt_dir = Path(__file__).resolve().parents[2] / prompt_dir
            if not self.prompt_dir.exists():
                raise FileNotFoundError(f"Prompt directory not found at: {self.prompt_dir}")
            self.template_cache: Dict[str, str] = {}
            self.initialized = True

    def _load_template(self, template_name: str) -> str:
        """Loads a template from file and caches it."""
        if template_name in self.template_cache:
            return self.template_cache[template_name]

        file_path = self.prompt_dir / f"{template_name}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Prompt template '{template_name}.md' not found in {self.prompt_dir}")

        try:
            template_content = file_path.read_text(encoding='utf-8')
            self.template_cache[template_name] = template_content
            return template_content
        except Exception as e:
            raise IOError(f"Error reading prompt template '{file_path}': {e}")

    def get_prompt(self, template_name: str, **kwargs: Any) -> str:
        """
        Gets a formatted prompt by loading a template and filling placeholders.

        Args:
            template_name: The name of the template file (without .md extension).
            **kwargs: Key-value pairs to fill the placeholders in the template.

        Returns:
            A formatted prompt string.
        """
        template = self._load_template(template_name)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing placeholder in prompt '{template_name}': {e}")

# Singleton instance for easy access across the application
prompt_manager = PromptManager()

if __name__ == '__main__':
    # Example usage:
    try:
        # Triage example
        triage_prompt = prompt_manager.get_prompt(
            "triage",
            domains_str="- financial\n- technology",
            event_types_str="- Company:Acquisition\n- Product:Launch",
            text_sample="Apple announced the new iPhone."
        )
        print("--- Generated Triage Prompt ---")
        print(triage_prompt)

        # Extraction example
        extraction_prompt = prompt_manager.get_prompt(
            "extraction",
            text_sample="Microsoft acquired OpenAI for $10 billion."
        )
        print("\n--- Generated Extraction Prompt ---")
        print(extraction_prompt)

    except (FileNotFoundError, ValueError, IOError) as e:
        print(f"An error occurred: {e}")
